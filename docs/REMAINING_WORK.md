# Remaining Work — Audit and Pending Sub-phases

This document is the authoritative checklist of what remains to close the
Phase 4 plan completely. It exists because over many sub-phases the
backlog has been spread across multiple plans and reports, and items
risk being forgotten.

Last updated: 2026-04-29, after closing 4f. The Phase 4 plan is
fully closed; this document is preserved as a historical record.

## What is closed (do not re-open)

| Sub-phase | Item | Closed in |
|---|---|---|
| 4a-1 | Initial prototype (single MBean) | 4a iteration 1 |
| 4a-2 | Inheritance via baseTypes | 4a iteration 2 |
| 4a-2 | UI overlays for enums | 4a iteration 2 |
| 4a-2 | Schema name normalization | 4a iteration 2 |
| 4b | Schema generation at scale (22 curated) | 4b |
| 4c | Path generation from containment | 4c |
| 4c | Operations from extension.yaml | 4c |
| 4c | Pre-overlay minimal (envelopes, errors, common params) | 4c |
| 4c | allOf wrapper for `$ref` siblings | 4c |
| 4c | getRoles RBAC mapping (basic) | 4c (refinement deferred) |
| 4d-1 | Operation descriptions, summaries, tags | 4d-1 |
| 4d-1 | Semantic path parameters | 4d-1 |
| 4d-1 | Document-level metadata (info block) | 4d-1 |
| 4d-1 | Spectral warnings reduction (1989 → 0) | 4d-1 |
| 4d-3 | Enum extraction to shared schemas | 4d-3 |
| 4d-3 | Sub-type discriminator with mapping | 4d-3 |
| 4d-2 | 14 quirks migration to overlays/quirks/ | 4d-2 |
| 4d-2 | `/domainRuntime/search` virtual endpoint | 4d-2 |
| 4d-2 | `startInAdmin` / `startInStandby` operations | 4d-2 |
| 4d-2 | HealthState/HealthSymptom promotion to envelopes | 4d-2 (incidental fix) |
| 4d-5 | Multi-version generation (5 versions) | 4d-5 |
| 4d-5 | Cross-version diffs (VERSION_DELTAS.md) | 4d-5 |
| 4e | Bulk coverage (22 curated → ~950 schemas) | 4e |
| 4e | Re-application of enum/discriminator at scale | 4e |
| 4e | Quirks re-injection at scale | 4e |
| 4e | VERSION_DELTAS regeneration | 4e |
| 4d-4 | getRoles RBAC mapping refinement (per-property `x-weblogic-required-role`) | 4d-4 |
| 4d-4 | `relationship: reference` validation on config-tree (`ServerMBean.cluster` confirmed Identity) | 4d-4 |
| 4d-4 | `x-weblogic-restart-needed` filter on read-only properties | 4d-4 |
| 4d-4 | Overlay vocabulary triage (`required`, `dateAsLong`, `multiLineString` honored; rest ignored with rationale) | 4d-4 |
| 4d-4 | SettableBean inheritance audit (premise disproved — SettableBean is a marker interface, chain walks correctly) | 4d-4 |
| 4d-8 | Surface curation decision (Alfredo: keep full surface, no variants) | decided 2026-04-28 — no implementation needed |
| 4d-6 | Description merge policy — 21 overlays for the 22 curated schemas | 4d-6 |
| 4d-7 | Live samples linking (hybrid `examples` + `x-weblogic-sample-paths`) | 4d-7 |
| 4d-7 | Empirical nullability overlay (20 fields) — discovered by sample injection | 4d-7 |
| 4d-9 | Path expansion / unused-component resolution — transitive-closure prune | 4d-9 |
| 4e-2 | Editorial curation per subsystem (Deployments + JMS detail + Work Managers + JTA + WLDF) — 29 new overlays | 4e-2 |
| 4e-3 | Manual bodies for the 12 polymorphic stubs (option C, hybrid harvested+manual) | 4e-3 |
| 4f | `specs/` replacement (`specs/generated/<v>.yaml`) + README/CHANGELOG rewrite + tag v0.4.0 + merge to main | 4f |

Validators currently green across all 5 versions:
`openapi-spec-validator`, `openapi-generator-cli` Python smoke,
`spectral lint` (0 errors, 0 warnings).

## What remains pending

Nothing. The Phase 4 plan is closed.

Post-merge follow-ups (out of scope for Phase 4, tracked separately):

- Second LinkedIn post anchored on v0.4.0 — material is in `CHANGELOG.md`.
- Phase 5 — ToolSpec / MCP integration (separate plan when ready).
- Coverage expansion when Oracle ships harvested data for new WLS versions.

## Items removed from scope

- Java scraping beyond startIn*: structurally limited.
- Discriminator nesting for JDBCSystemResource: OAS 3.0 forbids.
- Cross-hierarchy nested polymorphism: OAS 3.0 limitation.
- Surface curation (4d-8): Alfredo decided to keep full surface;
  no overlay layer for "common" subset. Consumers use `fields=...`
  query parameter for filtering.
- SettableBean partial inheritance: dissolved by audit in 4d-4
  (premise was incorrect; chain walks correctly).

## Notes on context preservation

This document is the authoritative checklist. It served as the
re-anchor point at the start of every sub-phase. Every line item in
"What is closed" links back to the corresponding `docs/PHASE<id>_*.md`
plan and the per-phase report under `tools/openapi-generator/out/`.

Phase 4 is closed; v0.4.0 was merged to `main` and tagged.
