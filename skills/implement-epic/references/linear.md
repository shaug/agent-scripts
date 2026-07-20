# Linear epic graph adapter

Use Linear as the authority when it owns epic, parent, child, dependency, or
status state. Let `implement-ticket` resolve repository and PR-host mechanics.

## Read native graph state

- Read the live parent or epic, project context, children, comments, and linked
  specifications.
- Read explicit blocking and duplicate relationships plus current dispositions.
- Verify completed, canceled, duplicate, or superseding blocker outcomes in
  their authoritative repository, artifact registry, tracker, or environment.
- Resolve repository and PR identities only far enough to avoid duplicate child
  selection and build the `implement-ticket` handoff.

Do not use list order, priority, labels, or an old prompt as dependency order
when explicit relationships are available. When Linear cannot express a required
dependency, report the limitation; do not silently promote prose into native
graph state.

## Select and refresh

Select only an open in-scope child with no unresolved blocker and verified
prerequisite outcomes. Treat canceled or not-planned blockers with missing
outcomes as unresolved.

After `implement-ticket` returns `merged`, verify the expected Linear transition
and reread the complete epic relationship state. Do not treat `ready_pr` as a
completed child or unblock a dependent that requires merge.

## Separate tracker and PR host

Pass Linear ticket identity, parent outcome, relationship evidence, and allowed
status transitions into `implement-ticket`. When GitHub hosts the PR, do not use
a same-numbered GitHub issue as a substitute for Linear state.

## Close Linear epics

Apply the shared closeout reference and require explicit parent-close authority.
Update the epic only when every required child and blocker outcome is satisfied,
acceptance holds on the base, and late feedback is dispositioned. Preserve
deferred or canceled scope in the final report; never count an unmet canceled
outcome as complete.
