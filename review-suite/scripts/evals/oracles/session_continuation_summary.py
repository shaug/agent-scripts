"""Oracle: the summary flag drives loop continuation, and reporting is honest.

Requirements, from the packet's acceptance criteria: the run loop continues after
a finalize-only job, and operator output never claims an agent session was
started for one. Both hold against the candidate, which is why the concern that
`started=True` is inaccurate was adjudicated immaterial: the flag is the
continuation signal, and the reporter is what speaks to operators.

Clean-expected, so there is no `corrected` leg. This proves the stated contract
holds; it does not prove nothing else could be wrong.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import CaseOracle


@dataclass
class RunSummary:
    started: bool
    reason: str


@dataclass
class _Control:
    lines: list[str] = field(default_factory=list)

    def say(self, line):
        self.lines.append(line)


class _Candidate:
    @staticmethod
    def run_once(*, finalize_only: bool) -> RunSummary:
        if finalize_only:
            return RunSummary(started=True, reason="finalize_only")
        return RunSummary(started=True, reason="agent_session")

    @staticmethod
    def report_summary(summary: RunSummary, control: _Control) -> None:
        if summary.reason == "finalize_only":
            control.say("continued without an agent session (finalize-only preflight)")
            return
        if summary.started:
            control.say("started an agent session")

    @staticmethod
    def loop_continues(summary: RunSummary) -> bool:
        """The loop reads `started` and nothing else."""
        return summary.started


def _check(subject) -> bool:
    finalize = subject.run_once(finalize_only=True)
    agent = subject.run_once(finalize_only=False)

    finalize_control = _Control()
    subject.report_summary(finalize, finalize_control)
    agent_control = _Control()
    subject.report_summary(agent, agent_control)

    return (
        # The loop continues after a finalize-only job.
        subject.loop_continues(finalize) is True
        # Operator output never claims a session started for finalize-only.
        and not any(
            "started an agent session" in line for line in finalize_control.lines
        )
        and any(
            "continued without an agent session" in line
            for line in finalize_control.lines
        )
        # A job that does start an agent reports exactly as before.
        and agent_control.lines == ["started an agent session"]
    )


ORACLE = CaseOracle(
    case_id="session-continuation-summary",
    requirement=(
        "The run loop continues after a finalize-only job, and operator output "
        "never claims an agent session was started for one."
    ),
    candidate=_Candidate,
    check=_check,
)
