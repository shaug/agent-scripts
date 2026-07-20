# Repository evidence

Repository: `example/exporter` Base branch: `main` Candidate head:
`8787878787878787878787878787878787878787` Comparison base:
`9797979797979797979797979797979797979797`

`AGENTS.md` says to add extension surfaces only for current consumers. The
repository has no provider registry or remote-storage dependency. Nearby local
output code calls `Path(path).write_text(value)` directly and lets filesystem
errors propagate to the caller.
