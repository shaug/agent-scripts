# Repository evidence

Repository: `example/admin` Base branch: `main` Candidate head:
`8d8d8d8d8d8d8d8d8d8d8d8d8d8d8d8d8d8d8d8d` Comparison base:
`9d9d9d9d9d9d9d9d9d9d9d9d9d9d9d9d9d9d9d9d`

`auth.py:require_active_admin(actor)` is the repository-owned authorization
boundary. It raises `Forbidden` unless the actor has the admin role and is not
suspended. Existing administrator actions call this helper directly, and the
repository instructs contributors not to duplicate authorization policy.
