# review-correctness evaluations

Each `standalone-*/` directory holds raw forward-evaluation inputs. Every
expected outcome lives outside its input directory, under
`expected/<name>.result.json`, so a forward-testing reviewer pointed at an input
directory cannot read the answer key.

- `standalone-ticket-regression/`: a preserved-behavior regression (duplicate
  webhook delivery reapplying an event).
- `standalone-sibling-call-site-traversal/`: #53's consumer/impact-traversal
  pass, modeled on a changed shared helper whose default tightens while an
  existing sibling call site keeps an explicit permissive override that the diff
  never touches.
- `standalone-verification-sufficiency-gap/`: ordinary correctness review's
  test-sufficiency judgment (the mandated verification-sufficiency pass this
  case originally modeled was removed by #93 for lack of demonstrated value; the
  underlying defect pattern -- a release guard whose only claimed test exercises
  an already-safe branch instead of the actual owner-absent triggering condition
  the change addresses -- remains a genuine correctness catch expected from the
  ordinary review dimensions in `references/correctness-rubric.md`, without a
  separate mandated pass or required evidence field).
