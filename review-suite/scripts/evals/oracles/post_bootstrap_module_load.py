"""Oracle: the module is bound after the runtime selection reorders the path.

Requirement, from the packet's acceptance criteria: the store module is loaded
after the runtime selection has run, so the entry path binds the selected runtime
rather than whichever copy was importable first. That is exactly what a
module-level import cannot do, which is why the deferred load was adjudicated
intentional and only a comment was added.

Clean-expected, so there is no `corrected` leg. The check models the ordering
directly: a resolver whose answer depends on selection having run first.
"""

from __future__ import annotations

from . import CaseOracle


class _Runtime:
    """Stands in for `sys.path`: the answer depends on selection order."""

    def __init__(self):
        self.selected = False
        self.load_order = []

    def select_runtime(self):
        self.selected = True
        self.load_order.append("select_runtime")

    def import_module(self, name):
        self.load_order.append(name)
        return "selected" if self.selected else "stale-installed-copy"


def _candidate():
    """Deferred load: selection runs, then the module is resolved."""
    runtime = _Runtime()
    runtime.select_runtime()
    store = runtime.import_module("toolkit.store")
    return runtime, store


def _check(result) -> bool:
    runtime, store = result
    return store == "selected" and runtime.load_order.index(
        "select_runtime"
    ) < runtime.load_order.index("toolkit.store")


ORACLE = CaseOracle(
    case_id="post-bootstrap-module-load",
    requirement=(
        "The store module is loaded after the runtime selection has run, so the "
        "entry path binds the selected runtime."
    ),
    candidate=_candidate,
    check=_check,
)
