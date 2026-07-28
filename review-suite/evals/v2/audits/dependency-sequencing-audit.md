# Dependency/sequencing audit

Run against the live `#51`–`#57` graph, read directly through GraphQL on
2026-07-28 (queries and raw results below). Requirement (#59's own text): native
edges match artifact prerequisites; only genuine leaves are actionable; no child
can implement an unapproved mechanism or integrate a contract that does not
exist. Independent of `scope-completeness-audit.md` and
`shovel-readiness-audit.md`.

## Live graph read-back

`gh api graphql` query per issue, `blockedBy`/`blocking`/`parent`/`state`/
`updatedAt`, 2026-07-28:

| issue | state | parent | blockedBy (state)      | blocking (state)       |
| ----- | ----- | ------ | ---------------------- | ---------------------- |
| #51   | OPEN  | #49    | #59 (OPEN)             | #52 (OPEN)             |
| #52   | OPEN  | #49    | #51 (OPEN)             | #56 (OPEN), #53 (OPEN) |
| #53   | OPEN  | #49    | #52 (OPEN)             | #54 (OPEN)             |
| #54   | OPEN  | #49    | #53 (OPEN)             | #55 (OPEN)             |
| #55   | OPEN  | #49    | #54 (OPEN)             | #57 (OPEN)             |
| #56   | OPEN  | #49    | #52 (OPEN)             | #57 (OPEN)             |
| #57   | OPEN  | #49    | #56 (OPEN), #55 (OPEN) | (none)                 |
| #59   | OPEN  | #49    | #58 (CLOSED)           | #51 (OPEN)             |

No native edge was added or removed by this ticket. #51's `blockedBy #59` edge
is deliberately left in place rather than deleted once #59 closes, matching this
repository's own established convention: #58's `blockedBy #50` edge is still
present today even though #50 has been closed since before #58 started (verified
in the same query above, and independently re-confirmed via a direct `#58` query
returning `blockedBy: [{number: 50, state: CLOSED}]`). `implement-epic`'s own
readiness rule (`skills/implement-epic/references/github.md`: "Choose an
in-scope child whose native `blockedBy` set has no open issue") keys off open
blockers, not edge presence, so this is consistent with how the epic
orchestrator actually selects work.

## Predicted vs. actual net effect once #59 closes

`DECISION-RECORD.md`'s "Net effect on the dependency graph" section predicts:
once #59 closes, #51 has zero *open* blockers (its only blocker, #59, is closed)
and is the only issue in the epic with that property. Checking every other
child's `blockedBy` set above against the current *open* graph: #52 (#51, open),
#53 (#52, open), #54 (#53, open), #55 (#54, open), #56 (#52, open), #57 (#56,
#55, both open). Every one of #52–#57 has at least one open blocker regardless
of #59's state. **Confirmed: #51 is the only genuine leaf once #59 closes; the
predicted net effect matches what the live graph actually produces.** #59
remains open as of this audit (it is being closed only after this audit and the
shovel-readiness audit both pass, per this ticket's own required sequencing), so
this is a verified prediction about the graph's structure, not yet an
observation of #51 sitting unblocked in production — the structural fact (every
other child's *independent* open blocker) does not depend on #59's own state to
hold.

## Artifact-prerequisite check

Confirmed each edge corresponds to a real, stated artifact dependency, not
merely a sequencing convention:

- **#52 → #51**: #52's body states its `consumer_impact_evidence` addition bumps
  `review-result.schema.json` `"1.1 → 1.2"`, explicitly "delivered by #51." Real
  prerequisite: #52 cannot define a delta from a schema version #51 hasn't
  shipped yet.
- **#53 → #52**: #53's body bumps `"1.2 → 1.3"`, and its traversal pass
  populates `consumer_impact_evidence`, a field #52 defines. Real prerequisite.
- **#54 → #53**: #54's own gate text requires "the measured single-pass
  improvements from #53" — a result that can only exist after #53 ships and is
  scored. Real prerequisite, and correctly *not* pointed at #59 (per
  `DECISION-RECORD.md`'s explicit instruction: "Keep it blocked on #53's
  eventual evidence, not #59 itself" — confirmed: #54's `blockedBy` is `#53`
  only).
- **#55 → #54**: #55's gate depends on "#54 (or its evidence-backed
  replacement)" establishing final orchestrator behavior. Real prerequisite.
- **#57 → #55, #56**: #57 requires "migrated caller integration from #55" and
  "operational feedback/corpus workflow from #56" as named required inputs. Real
  prerequisite for both edges.
- **#56 → #52**: weaker than the others after #52's narrowing. #56's body,
  post-fix, no longer claims any technical dependency on #52's
  `consumer_impact_evidence` schema — its intake/curation record is explicitly
  "compatible with the corpus contract from #50/#58," a different,
  already-existing contract family. **This is a genuine open question, not a
  clear defect**: no evidence found that #56 *cannot* be implemented before #52
  ships, but no evidence was found that it structurally *must* wait either. Per
  this ticket's own instruction to report a discrepancy rather than quietly
  reconcile it, this edge is left unchanged (removing it was not part of the
  owner's settled disposition for #56, which addressed evidence-backing and
  sourcing only, not sequencing), and is flagged here for the owner to confirm
  or sever. It does not change the actionable-leaf outcome above either way,
  since #52 is itself gated on #51 regardless of whether #56 also waits on it.

## Unapproved-mechanism check

Confirmed no child's current body describes implementing a mechanism this
ticket's decision record did not approve, and no child integrates a contract
version that does not yet exist in the sequence above:

- #51 implements only its own schema `1.0 → 1.1` delta — no forward reference to
  a version another ticket owns.
- #52 implements only `1.1 → 1.2`, explicitly built on #51's delivered version,
  and explicitly does not add the changed-surface ledger, acceptance trace, or
  risk profile the decision record dropped.
- #53 implements only `1.2 → 1.3`, explicitly built on #52's delivered version,
  and explicitly does not add any specialist module.
- #54, #55, #57 each state their own gate is not yet satisfied and commit to no
  premature implementation; #54's remaining "conditional specialist explorer"
  bullet was corrected during the scope/completeness pass to no longer imply a
  #52 risk profile that does not exist, and is now explicitly marked
  hypothetical.
- #56 integrates only the existing `#50`/`#58` corpus/expectation/provenance
  contracts, not any not-yet-shipped review-result schema version.

No finding here.

## Result

**Clean pass, one flagged-but-unresolved open question** (the #56→#52 edge's
weakened-but-not-contradicted justification, reported above for the owner to
confirm or sever) **that does not change the audited outcome**: every native
edge matches a real artifact prerequisite except that one weaker case, only
genuine leaves are actionable, #51 is confirmed as the sole next actionable leaf
once #59 closes, and no child implements an unapproved mechanism or integrates a
contract that does not yet exist in the sequence.
