# Consumption disciplines

How a skill metabolizes a review finding or a piece of pull-request feedback,
before it changes a line. These four disciplines govern the fix loop in
`implement-ticket`, the feedback and CI loops in `babysit-pr`, and review
communication in `carve-changesets`.

They are house-owned, ported with attribution from superpowers'
`receiving-code-review`. The port is deliberate rather than a delegation: that
peer adjudicates between a human author and a human reviewer, and its protocol
turns on a partner who can be asked. The consumers here are autonomous loops
metabolizing findings from this repository's own review suite and from live PR
feedback, where no such partner is in the loop and an ask-a-human step maps to a
typed terminal result instead. The stance survives that translation; the
protocol does not.

Each discipline states the failure it prevents. A discipline whose failure no
longer occurs is a candidate for deletion.

## Verify each finding against the codebase before implementing

Read the code the finding names and confirm the described condition actually
holds at the current candidate. A finding that does not reproduce is answered
with that evidence, not implemented.

*Prevents:* a confident, well-argued finding about code that does not exist.
Reviewers reason from a diff and can misread scope, miss a guard three lines up,
or describe a prior revision. Implementing it produces a change that fixes
nothing, and because the change is real and the reasoning was plausible, nothing
downstream distinguishes it from a fix that mattered. Automated reviewers fail
this way at scale: they are fluent enough that an unverified finding reads
exactly like a verified one.

## Clarify every unclear finding before implementing any

Resolve ambiguity across the whole set first, then implement. Do not start on
the clear findings while an unclear one is still open.

*Prevents:* a guessed reading of one finding that the next finding contradicts.
Findings from a single review are frequently connected — two comments on the
same function often describe one underlying disagreement — so a guess made early
gets built on, and the contradiction surfaces only after the dependent work
exists. Batching the clarification also keeps the reviewer's context intact:
asking four questions across four separate fix rounds costs more of everyone's
attention than asking them once.

## Never perform agreement

Reply with what was verified, what changed, and what did not. Do not open with
thanks, praise the catch, or affirm a finding before checking it. Do not soften
a rejection into partial agreement.

*Prevents:* two distinct losses. Performed agreement records a verdict that was
never reached — "good catch" before verification is a claim about the finding's
correctness, and it becomes the thread's stated position. And in an autonomous
loop the courtesy is pure noise: it consumes the reply that should carry
evidence, and a later reader scanning the thread for what was actually
established finds sentiment instead. Rejecting a finding with evidence is a
service to the reviewer; agreeing without it is not.

## Implement blocking, then simple, then complex

Order the accepted findings by severity first and cost second, and validate each
one on its own before starting the next.

*Prevents:* a batch of fixes landing together, one of which breaks something,
with no way to tell which. Individual validation is what makes a regression
attributable. Taking the blocking findings first also means the candidate is
never left in a state where a cheap cosmetic fix landed and a correctness fix
did not — the ordering that a bounded cycle budget can strand.

## What these do not govern

They govern consumption, not production: reviewer-side contracts, lens rubrics,
severity vocabulary, and the shared result shape belong to the review-suite
contract, `review-suite/CONTRACT.md` in this repository. That is named rather
than linked, because this file is bundled into skills that do not all ship a
copy of it beside them, and a relative link would resolve to nothing there. The
disciplines do not set a cycle budget, a re-review trigger, or an escalation
rule; each consuming skill keeps its own.
