---
name: modular-code-review-contract
description: >-
  Portable, atelier-agnostic contract for principal-level code review behavior
  with deterministic, machine-consumable output. Use when implementing or
  invoking code review across CLI tools, hosted agents, bots, and chat
  surfaces.
license: MIT
metadata:
  contract_version: 1.0.0
  output_format: structured-v1
  runtime_dependency: none
---

# Modular Code Review Contract

Use this skill as the canonical behavior contract for generalized code review.

Always load:

- `references/SPEC.md`

## Operating rules

1. Validate the request against the `ReviewRequest` contract before analysis.
2. If `review_type` is missing or ambiguous, return
   `status: needs_clarification` and prompt with valid choices.
3. Keep philosophy and evaluation logic independent from delivery format.
4. Enforce deterministic output ordering and stable section presence.
5. Treat this contract as runtime-agnostic: no Atelier-only assumptions.

## Intended use

- Define shared review semantics across multiple interfaces.
- Keep adapter implementations aligned with one stable core contract.
- Extend review behavior through explicit modifiers and profile versioning.
