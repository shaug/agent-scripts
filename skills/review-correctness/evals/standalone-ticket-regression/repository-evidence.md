# Repository evidence

Repository: `example/webhooks` Base branch: `main` Candidate head:
`8484848484848484848484848484848484848484` Comparison base:
`9494949494949494949494949494949494949494`

`AGENTS.md` requires webhook handlers to remain idempotent by provider event ID.
`webhooks.py` is the only handler for these events. Before this candidate it
looked up an existing delivery before applying the event. Nearby handler tests
assert that a duplicate event returns the stored result and does not call the
mailer a second time.
