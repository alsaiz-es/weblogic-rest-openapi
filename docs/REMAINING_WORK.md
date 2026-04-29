# Remaining Work — Audit and Pending Sub-phases

This document is the authoritative checklist of what remains to close the
Phase 4 plan completely. It exists because over many sub-phases the
backlog has been spread across multiple plans and reports, and items
risk being forgotten.

Last updated: post-Phase 4d-4 + Alfredo's decisions on pending
sub-phases.

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

Validators currently green across all 5 versions:
`openapi-spec-validator`, `openapi-generator-cli` Python smoke,
`spectral lint` (0 errors, 256–286 unused-component warnings only).

## What remains pending

Decisions resolved by Alfredo on 2026-04-28 are noted inline. Each
pending sub-phase has a detailed execution plan in its own document
under `docs/`; this section is a high-level index.

### Sub-phase 4d-9 — Path expansion to resolve unused components

Detailed plan: `docs/PHASE4D9_PATH_EXPANSION.md`.

256–286 unused-component warnings. Investigate which schemas are
unreachable from tree roots and why. Two categories: missing
traversal rules (extend path-builder) vs genuinely unreachable
(exclude from emission). Investigative first, action second.

### Sub-phase 4e-2 — Editorial curation per subsystem

Detailed plan: `docs/PHASE4E2_CURATION.md`.

**Alfredo's decision (2026-04-28):** four subsystems —
**Deployments, JMS detail, Work Managers, plus JTA and WLDF
optionally**. Plan acotar pragmatically: deployments and JMS as
priority, work managers second, JTA and WLDF as opportunistic
extensions. Per subsystem, description overlays for user-facing
properties only; internal-only properties stay harvested.

### Sub-phase 4e-3 — Body fidelity for 12 polymorphic stubs

Detailed plan: `docs/PHASE4E3_STUBS.md`.

**Alfredo's decision (2026-04-28):** option C — full manual authoring
of all 12 subtypes (OAMAuthenticator, JMSQueueRuntime,
JDBCProxyDataSourceRuntime, etc.). Sources: Oracle MBean Reference
Javadoc, public docs, empirical observation where available. Quality
will be inferior to harvested but bodies become non-empty for
deserialization.

### Sub-phase 4f — Manual specs/ replacement and merge to main

Detailed plan: `docs/PHASE4F_MERGE.md`.

**Alfredo's decision (2026-04-28):** option C — replace `specs/`
in main with the generated equivalent. v0.3.1 remains accessible
via git tag. README explains the transition. Tag v0.4.0 on the
branch, open PR, merge.

This sub-phase is the bridge to the second LinkedIn post.

## Items removed from scope

- Java scraping beyond startIn*: structurally limited.
- Discriminator nesting for JDBCSystemResource: OAS 3.0 forbids.
- Cross-hierarchy nested polymorphism: OAS 3.0 limitation.
- Surface curation (4d-8): Alfredo decided to keep full surface;
  no overlay layer for "common" subset. Consumers use `fields=...`
  query parameter for filtering.
- SettableBean partial inheritance: dissolved by audit in 4d-4
  (premise was incorrect; chain walks correctly).

## Recommended execution order

The pending sub-phases can be executed independently, but the
recommended order is:

1. 4d-9 (path expansion) — eliminates the only remaining warnings.
2. 4e-2 (subsystem curation) — biggest scope, can be split if needed.
3. 4e-3 (12 stubs) — bonus polish, can ship before or after 4e-2.
4. 4f (merge) — bridge to main and second LinkedIn post.

If energy/context runs short, item 1 alone produces a defensibly
complete branch. Items 2-3 are quality multipliers but not blocking.
Item 4 is the strategic bridge regardless of how much of 2-3 lands.

## Notes on context preservation

This document is the authoritative checklist. **Start every new
sub-phase by re-reading this document and the corresponding
`docs/PHASE<id>_*.md` plan** to re-anchor on what is closed and what
remains. Each completed sub-phase updates the "What is closed"
section above and removes its line from "What remains pending".
