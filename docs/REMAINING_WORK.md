# Remaining Work — Audit and Pending Sub-phases

This document is the authoritative checklist of what remains to close the
Phase 4 plan completely. It exists because over many sub-phases the
backlog has been spread across multiple plans and reports, and items
risk being forgotten.

Last updated: post-Phase 4d-4 (audit and overdue decisions).

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

Validators currently green across all 5 versions:
`openapi-spec-validator`, `openapi-generator-cli` Python smoke,
`spectral lint` (0 errors, 256–286 unused-component warnings only).

## What remains pending

### Sub-phase 4d-6 — Description merge policy

Define `overlays/descriptions/<schema>.yaml` format. When present,
appends operational notes as `**Operational note:** {text}` after
harvested description. Migrate notes from manual `specs/` for the
22 curated schemas only.

### Sub-phase 4d-7 — Live samples linking

Format decision: native OpenAPI `examples` blocks vs
`x-weblogic-sample-paths` extension. Recommendation: hybrid (native
for canonical, extension for the rest). Acotar: 22 originally
curated MBeans only.

### Sub-phase 4d-8 — Server / Cluster surface curation

Server has 165 props vs 27 in manual. Cluster 77 vs 11. Decide:
keep full / two-variant (Server + ServerCommon) / tag-and-filter.
**Alfredo decision required.**

### Sub-phase 4d-9 — Path expansion to resolve unused components

256–286 unused-component warnings. Investigate: which schemas are
unused and why. Two categories expected: missing traversal rules
(extend path-builder) vs genuinely unreachable (exclude from
emission).

### Sub-phase 4e-2 — Editorial curation per subsystem

Pick **at most 3** subsystems for curation. Candidates: JTA, WLDF,
work managers, JMS detail, security, deployments. **Alfredo decision
required.** Recommendation given background: JTA, WLDF, plus one of
work managers or deployments.

### Sub-phase 4e-3 — Body fidelity for 12 polymorphic stubs

OAMAuthenticator, JMSQueueRuntime, JDBCProxyDataSourceRuntime, etc.
Options: accept stubs / selective manual (JMS first) / full manual.
**Alfredo decision required.** Bonus work, core spec functions
correctly with stubs.

### Sub-phase 4f — Manual specs/ replacement and merge to main

Strategic. Decide: replace specs/ or coexist. Tag v0.4.0. PR + merge.
Bridge to second LinkedIn post.

## Items removed from scope

- Java scraping beyond startIn*: structurally limited.
- Discriminator nesting for JDBCSystemResource: OAS 3.0 forbids.
- Cross-hierarchy nested polymorphism: OAS 3.0 limitation.

## Decisions Alfredo needs to make before some sub-phases start

| Sub-phase | Decision |
|---|---|
| 4d-8 | Surface curation: full / two-variant / tag-and-filter |
| 4e-2 | Which ≤3 subsystems to curate |
| 4e-3 | 12 stubs: accept / selective / full |
| 4f | Replace specs/ or coexist |

## Notes on context preservation

This document is the authoritative checklist. **Start every new
sub-phase by re-reading this document** to re-anchor on what is
closed and what remains. Each completed sub-phase updates the
"What is closed" section.
