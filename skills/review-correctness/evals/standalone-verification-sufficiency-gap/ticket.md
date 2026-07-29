# Stop releasing a claim while its snapshot owner is transiently absent

`release_if_stale` currently skips its holder-mismatch guard whenever the
snapshot has no recorded owner for a resource, treating an absent owner as proof
the claim is safe to release. That is wrong when the snapshot is simply
incomplete: the claim may still be legitimately held.

Add a guard clause so that, when the snapshot owner is absent, the claim is
released only if it has actually expired.
