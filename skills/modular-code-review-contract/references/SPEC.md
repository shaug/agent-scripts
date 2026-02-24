# Canonical Specification: Modular Atelier-Agnostic Code Review Contract (v1)

## 1. Purpose

This contract standardizes principal-level code review behavior so the same
review logic can be used across multiple runtimes without prompt drift.

Outcomes:

- Predictable, high-signal review outputs.
- Clear scope boundaries and review intent.
- Deterministic, machine-consumable findings.
- Explicit separation between evaluation logic and delivery shape.

Design principle: philosophy is stable, delivery is pluggable.

## 2. Portability constraints

The contract must remain:

- Atelier-agnostic (no Beads, hooks, or Atelier runtime assumptions).
- Runtime-agnostic (usable in CLI, hosted agents, GitHub bots, Slack bots, or
  custom services).
- Schema-stable with deterministic ordering rules.
- Explicit about ambiguity handling (missing/unclear `review_type` requires
  clarification response before review proceeds).

## 3. Input contract (`ReviewRequest`)

```yaml
schema_version: "1.0.0"  # required
review_type: "pr_review | architecture_review | targeted_review"  # required
philosophy_profile: "scott-principal-v1"  # optional, default scott-principal-v1
scope:
  mode: "branch | project | targeted"  # required
  base_ref: "string"  # optional, used by branch mode
  target_ref: "string"  # optional, used by branch mode
  targets: ["path/or/module", "..."]  # required for targeted mode
delivery:
  mode: "inline | summary | executive"  # required
  include_severity_labels: true  # optional, default true
  include_code_quotes: true  # optional, default true for inline mode
  max_findings: 50  # optional safety cap
strictness:
  level: "relaxed | standard | strict"  # optional, default standard
depth:
  level: "surface | standard | deep"  # optional, default standard
modifiers:
  functional_bias: false  # optional
  architecture_discipline: true  # optional
  domain_specific:
    enabled: false  # optional
    lens_name: "string"  # required when enabled=true
    lens_context: "string"  # required when enabled=true
output:
  format: "structured-v1"  # required
  include_empty_sections: true  # optional, default true
metadata:
  invocation_id: "string"  # optional trace id
  repository: "owner/name"  # optional
  commit_or_pr: "string"  # optional
```

Validation rules:

- `review_type` is mandatory.
- For `scope.mode=targeted`, `scope.targets` is mandatory.
- For `modifiers.domain_specific.enabled=true`, both `lens_name` and
  `lens_context` are mandatory.
- Unknown modifiers are ignored and emitted as metadata warnings.
- Missing or ambiguous `review_type` returns `status: needs_clarification`
  (instead of defaulting silently).

## 4. Output contract (`ReviewResult`)

```yaml
schema_version: "1.0.0"
status: "completed | needs_clarification | failed_validation"
review_type: "..."
philosophy_profile: "scott-principal-v1"
metadata:
  invocation_id: "..."
  generated_at: "RFC3339"
  scope_mode: "branch | project | targeted"
  delivery_mode: "inline | summary | executive"
  strictness: "relaxed | standard | strict"
  depth: "surface | standard | deep"
  warnings: ["..."]
summary:
  overall_assessment: "string"
  risk_level: "low | medium | high"
  blocker_count: 0
  recommendation_count: 0
  optional_count: 0
findings:
  - id: "F-001"
    severity: "blocking | strong_recommendation | optional_improvement"
    confidence: "high | medium | low"
    dimension: "correctness | intent_alignment | clarity | consistency | simplicity | dry | abstraction_boundaries | public_surface_area | test_coverage"
    scope_ref: "branch | project | targeted"
    location:
      file: "path/to/file"
      start_line: 10
      end_line: 14
      symbol: "optionalSymbol"
    title: "short finding title"
    concern: "what is wrong"
    impact: "why it matters"
    recommendation: "specific action"
    evidence: ["short excerpt or references"]
architectural_observations:
  - "system-level note"
quality_improvements:
  - "non-blocking quality improvement"
test_and_docs_gaps:
  - "missing tests/docs"
next_steps:
  - "ordered actionable step"
clarification_prompt:
  question: "..."
  choices: ["pr_review", "architecture_review", "targeted_review"]
```

Determinism requirements:

- Findings are sorted by severity, then stable location ordering.
- IDs are generated sequentially in output order (`F-001`, `F-002`, ...).
- When `include_empty_sections=true`, all top-level sections are present even if
  empty.

## 5. Core modular review criteria

The following dimensions are mandatory and cannot be removed by modifiers:

1. Correctness: logical validity, edge cases, regressions, side effects.
2. Intent alignment: implementation matches intended scope and goal.
3. Clarity: readability, maintainability, explicit intent.
4. Consistency: adherence to codebase conventions and patterns.
5. Simplicity: smallest sufficient design; avoid unjustified abstraction.
6. DRY and duplication: repeated logic and consolidation opportunities.
7. Abstraction boundaries: layering and ownership boundaries remain intact.
8. Public surface area: API/export changes, compatibility, and docs impact.
9. Test coverage: behavioral confidence, regression protection, granularity.

## 6. Scope controls

- `branch`: evaluate introduced deltas against a base reference.
- `project`: evaluate holistic architecture and systemic quality.
- `targeted`: evaluate only caller-selected files/modules plus integration
  notes.

Scope mode constrains the review window and prevents implicit scope expansion.

## 7. Delivery modes

- `inline`: file/line-aware findings for comment-level review workflows.
- `summary`: structured engineering report with full sections.
- `executive`: high-level risk and direction for decision-makers.

Delivery mode changes presentation only, never evaluation criteria.

## 8. Optional modifiers

Modifiers add emphasis but cannot remove required dimensions.

- `functional_bias`: prefer declarative patterns and minimized mutation.
- `architecture_discipline`: increase focus on coupling and layering integrity.
- `domain_specific`: apply caller-provided domain lens context.

Modifier behavior rules:

- Additive only: modifiers can add checks or weighting.
- Non-destructive: modifiers cannot suppress mandatory dimensions.
- Unknown modifiers produce warnings, not hard failure.

## 9. Strictness and depth

Strictness sets finding threshold:

- `relaxed`: high-confidence, high-impact findings only.
- `standard`: balanced default threshold.
- `strict`: lower tolerance for ambiguity and inconsistency.

Depth sets analysis breadth:

- `surface`: major risk scan.
- `standard`: normal engineering review depth.
- `deep`: exhaustive path and edge-case scrutiny.

Interplay:

- Strictness affects issue-raising threshold.
- Depth affects coverage and analysis effort.

## 10. Example configurations

### Example A: branch summary, standard

```yaml
schema_version: "1.0.0"
review_type: "pr_review"
scope:
  mode: "branch"
  base_ref: "main"
  target_ref: "feature/x"
delivery:
  mode: "summary"
  include_severity_labels: true
strictness:
  level: "standard"
depth:
  level: "standard"
modifiers:
  functional_bias: false
  architecture_discipline: true
  domain_specific:
    enabled: false
output:
  format: "structured-v1"
  include_empty_sections: true
```

### Example B: targeted inline with domain lens

```yaml
schema_version: "1.0.0"
review_type: "targeted_review"
scope:
  mode: "targeted"
  targets:
    - "app/utilities/emailDomainClassificationLogic.ts"
delivery:
  mode: "inline"
  include_severity_labels: true
  include_code_quotes: true
strictness:
  level: "strict"
depth:
  level: "deep"
modifiers:
  functional_bias: true
  architecture_discipline: true
  domain_specific:
    enabled: true
    lens_name: "email-risk-modeling"
    lens_context: "Prioritize false-positive risk, explainability, and policy evolvability."
output:
  format: "structured-v1"
  include_empty_sections: true
```

### Example C: missing review type

```yaml
schema_version: "1.0.0"
scope:
  mode: "project"
delivery:
  mode: "executive"
```

Expected behavior:

- Return `status: needs_clarification`.
- Include `clarification_prompt.choices`: `pr_review`, `architecture_review`,
  `targeted_review`.

## 11. Example output (abbreviated)

```yaml
schema_version: "1.0.0"
status: "completed"
review_type: "pr_review"
philosophy_profile: "scott-principal-v1"
summary:
  overall_assessment: "Change is directionally sound but introduces boundary leakage in classification logic."
  risk_level: "medium"
  blocker_count: 1
  recommendation_count: 2
  optional_count: 1
findings:
  - id: "F-001"
    severity: "blocking"
    confidence: "high"
    dimension: "abstraction_boundaries"
    location:
      file: "app/services/classifier.ts"
      start_line: 82
      end_line: 108
    title: "Policy logic bypasses domain service boundary"
    concern: "Route-level handler embeds policy branching that belongs in domain service."
    impact: "Increases coupling and raises policy-change risk across handlers."
    recommendation: "Move policy branching into the domain service behind a narrow orchestration method."
    evidence:
      - "classifier.ts:82-108"
      - "service contract lacks policy method"
next_steps:
  - "Refactor policy branch into domain service."
  - "Add regression test validating policy behavior at the service boundary."
```

## 12. Extensibility strategy

Supported extension points:

- `modifiers` registry for additive lenses.
- `philosophy_profile` variants (for example, security-first, performance-first)
  that inherit mandatory criteria.
- Named domain lens overlays with documented semantics.

Compatibility rules:

- New fields must be optional by default.
- Existing required fields and enum meanings cannot change in minor versions.
- Unknown extensions must generate warnings unless caller requests strict
  validation failure.

## 13. Versioning strategy

Use semantic versioning for both schema and philosophy profile:

- `schema_version`: contract structure and field behavior.
- `philosophy_profile`: rubric philosophy and weighting profile.

Version semantics:

- Major: breaking shape or behavioral semantics.
- Minor: backward-compatible additions.
- Patch: clarifications, deterministic behavior fixes, non-breaking corrections.

Every result must emit exact `schema_version` and `philosophy_profile` values.

## 14. Risks and trade-offs

- Risk: too many options reduce usability.
  - Mitigation: minimal required fields, safe defaults.
- Risk: determinism can flatten nuanced narrative.
  - Mitigation: preserve free-text sections inside a fixed envelope.
- Risk: modifier sprawl fragments review behavior.
  - Mitigation: governed extension registry, compatibility policy, deprecation
    discipline.
- Trade-off: deep review raises cost and latency.
  - Mitigation: explicit depth controls and configurable finding cap.

## 15. Implementation guidance (non-runtime)

When implementing adapters for this contract:

- Keep philosophy/rubric definition separate from parsing and rendering.
- Keep parsing/validation separate from transport interfaces.
- Preserve deterministic ordering and output shape invariants.
- Do not couple contract semantics to any single orchestration framework.
