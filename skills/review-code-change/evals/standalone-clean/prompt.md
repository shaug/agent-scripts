Use the `review-code-change` skill to review the candidate described by the raw
evidence in this directory. Read `ticket.md`, `repository-evidence.md`,
`candidate.diff`, and `validation.md`; do not inspect answer keys (stored
outside this directory) or prior conclusions. Build one shared packet, then
apply the three repository-owned lens skills in their required order. Do not
modify files or repository state.

For evaluation recording only, return an object with `observed_sequence` (the
lens tokens actually invoked, in order, e.g. `solution_simplicity`) and
`result`; `result` must be the production aggregate JSON conforming to the
shared result schema.
