# Repository evidence

Repository: `example/coordinator` Base branch: `main` Candidate head:
`5959595959595959595959595959595959595959` Comparison base:
`9595959595959595959595959595959595959595`

`docs/CLAIMS.md` states that a stale claim may only be released once its
snapshot ownership is confirmed absent or the claim itself has expired.
`lib/claims.py` is the only place `release_if_stale` is defined or called.
`tests/test_claims.py` previously contained one test,
`test_release_denied_for_mismatched_owner`, which constructs a snapshot with a
present owner that does not match the claim's holder. This candidate adds the
new guard clause but does not add or change any other test in
`tests/test_claims.py`.
