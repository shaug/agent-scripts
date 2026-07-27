# Executable oracles

An oracle is a **second independent adjudication by machine**. For a correctness
case whose minimized reproduction can be made to run, materiality stops being an
opinion: the requirement the change contract states either holds against the
candidate code or it does not.

This matters because of what the alternatives are. The first adjudication is the
recorded source disposition — strong for a root cause, thin for severity, and
unavailable for formulations. The obvious second adjudicator, a fresh agent
context, is **not** independent of a reviewer it shares a model family with: the
errors correlate, so recall would rise without the reviewer improving. A machine
that runs the code has no such correlation. Where an oracle exists, use it.

## What an oracle asserts

Each module exposes exactly one `ORACLE`, a `CaseOracle`:

- `candidate()` — the reproduction in the state the candidate leaves it.
- `corrected()` — the same reproduction with the root cause fixed. `None` for a
  clean-expected case, where there is nothing to correct.
- `check(subject)` — the requirement from the packet's change contract,
  expressed as code. Returns `True` when the requirement holds.

`review-suite/scripts/tests/test_eval_oracles.py` then asserts, per case:

| expected verdict   | on `candidate()`          | on `corrected()`          |
| ------------------ | ------------------------- | ------------------------- |
| `changes_required` | the requirement **fails** | the requirement **holds** |
| `clean`            | the requirement **holds** | not applicable            |

The `corrected()` leg is what makes the oracle an adjudication of the *root
cause* rather than of the symptom: the stated cause, corrected, is what makes
the requirement hold. A case whose requirement fails for some other reason fails
this test.

## What an oracle does not prove

It covers the requirements the change contract states, and nothing else. An
oracle passing on a clean-expected case does **not** prove the diff is free of
every possible defect — only that the requirements it claims to satisfy are
satisfied. Read a clean control as "the stated contract holds and the raised
concern was adjudicated immaterial", never as "nothing is wrong here".

An oracle is also not the reviewer's task. The reviewer sees a packet and must
reason from it; the oracle runs code the reviewer never receives. Oracles are
private curation evidence and live outside every corpus's `reviewer/` tree.

## Where no oracle exists

The simplicity strata have none: "this is over-engineered" and "this complexity
is requirement-justified" have no executable form. Those cases need the owner.
See [the adjudication plan](../../../evals/baseline/v1/ADJUDICATION-PLAN.md).
