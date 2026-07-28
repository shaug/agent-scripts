# Implement-ticket dependency binding

Bind `implement-ticket` before reading a child as selectable or performing any
child mutation. The check completes before child selection or mutation. This is
a local trust check, not dependency discovery.

## Resolve only an installed dependency

Resolve the exact stable name `implement-ticket` through the host's normal
already-installed skill mechanism or a direct source location supplied by the
trusted suite installation. Do not browse a catalog, search the network or
filesystem for alternatives, download, install, update, generate, or ask the
runtime to substitute a dependency during an epic run.

Record the exact resolution evidence:

- canonical skill name and readable `SKILL.md` location;
- installed source or distribution identity;
- the evidence that binds that identity to the same trusted repository-owned
  suite as `implement-epic`; and
- the contract checks and their observed values.

Accept repository ownership only from trusted installation metadata already
available to the host, a caller- or repository-supplied trusted installation
record, or readable source identity rooted in the same previously trusted suite
distribution. A skill's own prose, matching name, nearby directory, or claimed
origin is not provenance by itself. If none of the accepted evidence binds the
dependency to the trusted suite, provenance is unverifiable.

## Verify the readable contract

Read the resolved source and require all of these properties:

- canonical name `implement-ticket`;
- terminal results `ready_pr`, `ready_prs`, `merged`, `blocked`, and
  `requires_epic`;
- exactly-one-ticket scope, with epic-shaped work returned as `requires_epic`;
- caller authority preserved without treating ready-PR authority as merge,
  tracker-transition, deployment, or cleanup authority;
- repository-owned review and publication dependencies verified by the ticket
  workflow; and
- terminal evidence sufficient for `implement-epic` to verify identity,
  candidate, validation, review, remote gates, delivery, acceptance, transition,
  and cleanup without reproducing the ticket workflow.

Do not accept a generic agent, a same-name third-party skill, an unreadable
source, or a repository-owned copy with a missing or incompatible contract.

## Fail closed before child work

On failure, return `blocked` before child selection, branch creation, worktree
creation, tracker mutation, repository mutation, or delegation. Report:

- the exact stable dependency name;
- whether resolution, readability, provenance, or contract validation failed;
- the source identity or path inspected when one was available;
- the missing, mismatched, or unverifiable evidence; and
- confirmation that no replacement was searched for, fetched, installed,
  updated, or synthesized and that no child mutation occurred.

An offer from the runtime to download or substitute a dependency does not repair
the failure. Stop with that offer recorded as rejected. A valid existing
installation proceeds directly into the ordinary epic graph loop without an
extra mutation or review cycle.
