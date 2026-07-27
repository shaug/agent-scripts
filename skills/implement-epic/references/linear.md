# Linear epic graph adapter

Use Linear as the authority when it owns epic, parent, child, dependency, or
status state. Let `implement-ticket` resolve repository and PR-host mechanics.

## Read native graph state

- Read the live parent or epic, project context, children, comments, linked
  specifications, acceptance criteria, and required verification items.
- Read explicit blocking and duplicate relationships plus current dispositions.
- Verify completed, canceled, duplicate, or superseding blocker outcomes in
  their authoritative repository, artifact registry, tracker, or environment.
- Read criterion-specific acceptance ledgers for every required child regardless
  of Linear state.
- Resolve repository and PR identities only far enough to avoid duplicate child
  selection and build the `implement-ticket` handoff.

Do not use list order, priority, labels, or an old prompt as dependency order
when explicit relationships are available. When Linear cannot express a required
dependency, report the limitation; do not silently promote prose into native
graph state.

## Select and refresh

Select an in-scope child with no unresolved blocker and verified prerequisite
outcomes when it is either open or auto-closed with required acceptance still
missing. Route the latter through `implement-ticket` with its closeout
observation and granted or withheld reopen authority. Do not select an accepted,
superseded, or otherwise terminal closed child. Treat canceled or not-planned
blockers with missing outcomes as unresolved.

After every caller-verified merge, delivery, or Linear transition, reread the
complete graph regardless of the returned terminal state. Verify the live
transition first, then separately decide which edges require delivery and which
require the child's complete current acceptance ledger. For a stacked delivery,
also verify every completed PR transition and full-chain representation on the
base. A `ready_pr`, `ready_prs`, or merged delivery with acceptance pending
remains incomplete but must still inform the refreshed ready set.

## Separate tracker and PR host

Pass Linear ticket identity, parent outcome, relationship evidence, and allowed
status transitions into `implement-ticket`. When GitHub hosts the PR, do not use
a same-numbered GitHub issue as a substitute for Linear state.

## Close Linear epics

Apply the shared closeout reference and require explicit parent-close authority.
Update the epic only when every required child ledger and blocker outcome is
satisfied, the parent's own acceptance ledger holds on the current base and
required deployment, and late feedback is dispositioned. Preserve deferred or
canceled scope in the final report; never count an unmet outcome or completed
Linear state as acceptance.
