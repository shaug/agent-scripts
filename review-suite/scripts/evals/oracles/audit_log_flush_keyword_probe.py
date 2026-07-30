"""Oracle: a retried flush resends its already-rendered, now-stale script.

Requirement, from the packet's acceptance criteria: a retried flush re-derives
its script from a fresh read of the entry's current version before resending.
The check drives the exact interleaving the change exists to prevent - a
transient session error on the first attempt, then a concurrent flush
advancing the row's version before the retry runs - and asks whether the entry
is recorded as flushed only when it was actually persisted.

The session boundary modelled here never tells its caller how many rows a
script's `WHERE version = ...` clause matched (`status` is `ok` for any
script that runs without a SQL error, matched row or not), matching the
packet's own stated fact about `audit/session.py`. Only this oracle - not the
production code under review - is allowed to peek at the underlying row to
settle whether persistence genuinely happened.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import CaseOracle


@dataclass
class Entry:
    entry_id: str
    payload: str
    expected_version: int
    flushed: bool = False


class _Row:
    def __init__(self, version: int, payload: str):
        self.version = version
        self.payload = payload


class _Store:
    """An `UPDATE ... WHERE version = ...` that matches zero rows is a no-op,
    but the session still reports the script as having run successfully."""

    def __init__(self, version: int, payload: str):
        self.row = _Row(version, payload)

    def apply(self, payload: str, expected_version: int) -> None:
        if self.row.version == expected_version:
            self.row.version += 1
            self.row.payload = payload


class _Outcome:
    def __init__(self, status: str):
        self.status = status


class _Session:
    """Reports one transient error on the first call, then always `ok` -
    the session boundary never surfaces whether a row actually matched."""

    def __init__(self, store: _Store, on_first_call=None):
        self._store = store
        self._calls = 0
        self._on_first_call = on_first_call

    def run_script(self, payload: str, expected_version: int) -> _Outcome:
        self._calls += 1
        if self._calls == 1:
            if self._on_first_call:
                self._on_first_call()
            return _Outcome(status="transient_error")
        self._store.apply(payload, expected_version)
        return _Outcome(status="ok")


def _flush(
    entry: Entry, session: _Session, fresh_version_reader, *, refresh_on_retry: bool
) -> bool:
    """Retry a transient error once; `refresh_on_retry` selects candidate vs.
    corrected, mirroring `stale_claim_release_guard.py`'s `guard_unconditionally`
    flag rather than duplicating the policy body across two functions."""
    version = entry.expected_version
    outcome = session.run_script(entry.payload, version)
    if outcome.status == "transient_error":
        if refresh_on_retry:
            version = fresh_version_reader()
        outcome = session.run_script(entry.payload, version)
    entry.flushed = outcome.status == "ok"
    return entry.flushed


@dataclass
class _Result:
    entry: Entry
    store: _Store


def _run(flush) -> _Result:
    store = _Store(version=3, payload="old")

    def concurrent_write() -> None:
        # Another flush lands while the first attempt is erroring out.
        store.row.version += 1
        store.row.payload = "concurrent-write"

    session = _Session(store, on_first_call=concurrent_write)
    entry = Entry(entry_id="e-1", payload="new", expected_version=3)
    flush(entry, session, lambda: store.row.version)
    return _Result(entry=entry, store=store)


def _check(result: _Result) -> bool:
    if not result.entry.flushed:
        return False
    # Flushed must mean actually persisted, not merely "the script ran".
    return result.store.row.payload == result.entry.payload


ORACLE = CaseOracle(
    case_id="audit-log-flush-keyword-probe",
    requirement=(
        "A retried flush re-derives its script from a fresh read of the "
        "entry's current version before resending."
    ),
    candidate=lambda: _run(
        lambda entry, session, reader: _flush(
            entry, session, reader, refresh_on_retry=False
        )
    ),
    corrected=lambda: _run(
        lambda entry, session, reader: _flush(
            entry, session, reader, refresh_on_retry=True
        )
    ),
    check=_check,
)
