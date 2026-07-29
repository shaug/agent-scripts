# Tighten the dependency-check default to strict

Our shared dependency-check helper defaults to permissive verification, which
lets a caller silently skip readiness checks. Change the shared default to
strict so every caller is checked. A caller may keep permissive verification
only if that exception is explicitly recorded in `AGENTS.md`; do not leave an
unrecorded permissive caller in place.

Update the orchestrator's call site to pass `mode` explicitly now that the
default is changing, matching the repository's existing convention of naming the
mode at every call site.
