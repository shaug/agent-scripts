"""Oracle: the parser reads the canonical field and ignores retired aliases.

Requirements, from the packet's acceptance criteria: the canonical link field is
read, a retired alias is not, and a bare string entry keeps working. All three
hold against the candidate, which is why the request to add coverage pinning a
retired alias was declined on the merits: it would pin behaviour the change
exists to remove.

Clean-expected, so there is no `corrected` leg.
"""

from __future__ import annotations

from . import CaseOracle

CANONICAL_LINK = "link_type"


class _Candidate:
    @staticmethod
    def parent_links(entry):
        links = []
        for item in entry.get("dependencies") or []:
            if isinstance(item, str):
                links.append(item)
                continue
            if item.get(CANONICAL_LINK) == "parent_child":
                links.append(item["issue"]["id"])
        return links


def _check(subject) -> bool:
    canonical = {
        "dependencies": [{"link_type": "parent_child", "issue": {"id": "p-2"}}]
    }
    retired = {"dependencies": [{"type": "parent_child", "issue": {"id": "p-3"}}]}
    also_retired = {
        "dependencies": [{"relation": "parent_child", "issue": {"id": "p-4"}}]
    }
    return (
        subject.parent_links(canonical) == ["p-2"]
        and subject.parent_links(retired) == []
        and subject.parent_links(also_retired) == []
        and subject.parent_links({"dependencies": ["p-1"]}) == ["p-1"]
    )


ORACLE = CaseOracle(
    case_id="dependency-hint-parser-coverage",
    requirement=(
        "The canonical link field is read, a retired alias is not, and a bare "
        "string entry keeps working."
    ),
    candidate=_Candidate,
    check=_check,
)
