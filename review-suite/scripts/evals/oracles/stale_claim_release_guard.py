"""Oracle: the ownership guard is skipped when the captured owner was absent.

Requirement, from the packet's acceptance criteria: a claim taken by another
worker between scan and apply is never released. The check drives the exact
interleaving - unowned at scan, owned at apply - and requires the claim to
survive.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import CaseOracle

TTL = 60


@dataclass
class Entry:
    entry_id: str
    owner: str | None
    claimed_at: int


class _Store:
    def __init__(self, entries):
        self._entries = {entry.entry_id: entry for entry in entries}

    def scan(self):
        return list(self._entries.values())

    def load(self, entry_id):
        return self._entries.get(entry_id)

    def set_owner(self, entry_id, owner):
        self._entries[entry_id].owner = owner

    def release(self, entry_id):
        self._entries[entry_id].owner = None
        self._entries[entry_id].claimed_at = 0


def _collect(now, store, *, guard_unconditionally: bool):
    actions = []
    for entry in store.scan():
        if entry.claimed_at is None or now - entry.claimed_at <= TTL:
            continue
        snapshot_owner = entry.owner

        def _release(entry_id=entry.entry_id, snapshot_owner=snapshot_owner):
            current = store.load(entry_id)
            if current is None:
                return
            if guard_unconditionally:
                if current.owner != snapshot_owner:
                    return
            elif snapshot_owner is not None and current.owner != snapshot_owner:
                return
            store.release(entry_id)

        actions.append(_release)
    return actions


def _run(*, guard_unconditionally: bool):
    """Scan an expired unowned entry, let a worker claim it, then apply."""
    store = _Store([Entry(entry_id="e-1", owner=None, claimed_at=0)])
    actions = _collect(
        now=TTL * 10, store=store, guard_unconditionally=guard_unconditionally
    )
    store.set_owner("e-1", "worker-b")  # another worker claims it after the scan
    for action in actions:
        action()
    return store


def _check(store) -> bool:
    # The live claim taken after the scan must still be held.
    return store.load("e-1").owner == "worker-b"


ORACLE = CaseOracle(
    case_id="stale-claim-release-guard",
    requirement=(
        "A claim taken by another worker between scan and apply is never released."
    ),
    candidate=lambda: _run(guard_unconditionally=False),
    corrected=lambda: _run(guard_unconditionally=True),
    check=_check,
)
