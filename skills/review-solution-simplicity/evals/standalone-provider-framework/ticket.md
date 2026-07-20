# Export a report to a local file

Add an `export(path, value)` operation that writes a generated report to the
caller-provided local path. Report generation must remain unchanged.

Remote storage providers and a public provider-extension API are outside this
ticket. The existing filesystem exception behavior is sufficient.
