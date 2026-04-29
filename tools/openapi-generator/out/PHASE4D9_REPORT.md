# Phase 4d-9 — Path expansion / unused-component resolution

## Goal

Resolve the 256–286 `oas3-unused-component` warnings appearing across the 5 versions. Per the plan, investigate before acting: classify each unused schema and apply either a reachability fix (extend path-builder) or a filter fix (drop from emission).

## Investigation findings

### Per-version warning counts (baseline — entering this sub-phase)

| Version | `oas3-unused-component` warnings |
|---|---:|
| `12.2.1.3.0` | 257 |
| `12.2.1.4.0` | 256 |
| `14.1.1.0.0` | 286 |
| `14.1.2.0.0` | 263 |
| `15.1.1.0.0` | 265 |

### Cross-version intersection

235 of the unused schema names appear on **all five** versions. The set is stable; the version-specific delta is small (per-release additions/removals on the harvested set).

### Reference graph analysis (14.1.2)

For each of the 263 unused schemas in 14.1.2 I counted `$ref` occurrences across the entire spec text (paths + components + extensions).

| Group | Count | Interpretation |
|---|---:|---|
| Schemas with **0** `$ref` from anywhere | 263 | Truly disconnected — not referenced by any path, by any other schema's `allOf`/`oneOf`/`properties`, or by any non-schema component. |
| Schemas with ≥1 `$ref` | 0 | None — every flagged schema is genuinely orphan. |

### Polymorphism check (14.1.2)

| Sub-category | Count |
|---|---:|
| Polymorphic parents (have `oneOf`) | 3 |
| Polymorphic subtypes whose parent is reachable | 0 |
| Polymorphic subtypes whose parent is also unused | 0 |
| Plain unused (no `oneOf`, no `allOf` parent) | 260 |

The 3 polymorphic parents are also unused: their subtypes are emitted with `allOf` to them, but nothing in the path tree returns the parent, so the entire hierarchy is stranded.

### What the unused schemas actually represent

Spot-check across the 263 names confirms they fall into the categories the plan anticipated:

- **Internal / legacy MBeans.** `AdminMBean` ("tagging interface to support interop with pre-WLS 8.1 clients" — straight from the harvested description), `AdminServerMBean`, `AccessRuntimeMBean` (`weblogic.diagnostics.accessor.runtime.AccessRuntimeMBean` — internal diagnostics access).
- **Reference-only target types.** Beans only referenced via `relationship: reference` from somewhere else. The harvested catalog declares them so the type graph is closed, but the REST projection returns these as `Identity` arrays instead of expanding the target. They never appear on any path.
- **Sub-resources of sub-resources of sub-resources.** Beans deep enough in containment that no traversal currently reaches them. Adding traversal would invent paths Oracle doesn't actually serve, which the plan calls out as out-of-scope.
- **Polymorphic-only subtypes whose parent is also dead.** Cascade orphan.

**No schema in the unused set has a documented REST endpoint that the path-builder is missing.** Investigation shows the path-builder coverage matches what the harvested containment graph supports. Extending path-builder traversal would amount to inventing endpoints rather than discovering them.

## Resolution applied

**Transitive-closure prune.** A new module `tools/openapi-generator/src/prune_unused.py` runs at the end of the pipeline (after paths, polymorphism, quirks, descriptions, nullability, samples). It computes the reachable set of schemas by walking `$ref` references — seeded from `paths`, `info`, and non-schema components, transitively expanded through schema bodies (`allOf`, `oneOf`, `properties`, …). Any schema not in the reachable set is dropped from `components.schemas`.

The walker also picks up `discriminator.mapping` values explicitly, so polymorphic subtypes whose parent is reachable are kept even when they're only referenced through the mapping table.

Wired into `main.py` after `apply_samples` so every other layer's contributions to the reference graph are accounted for.

## Per-version application

| Version | Schemas before | Dropped | Schemas after |
|---|---:|---:|---:|
| `12.2.1.3.0` | 974 | 318 | 656 |
| `12.2.1.4.0` | 978 | 317 | 661 |
| `14.1.1.0.0` | 974 | 363 | 611 |
| `14.1.2.0.0` | 946 | 338 | 608 |
| `15.1.1.0.0` | 960 | 340 | 620 |

The dropped count is higher than the spectral warning count because cascading orphans (subtypes whose parent was dropped) are pruned in the same pass, even though spectral only flagged the top of each chain.

## Validation

| Check | Baseline (4d-7) | 4d-9 |
|---|---|---|
| `openapi-spec-validator` strict (5 versions) | PASS | **PASS** all 5 |
| `spectral lint` errors | 0 | **0** all 5 |
| `spectral lint` warnings | 256–286 | **0 all 5** |
| `openapi-generator-cli generate -g python` smoke (14.1.2 JSON) | PASS, 1190 models | **PASS, 852 models** |
| Spec size (14.1.2) | 5.9 MB | 5.1 MB (-13%) |

Spectral is now silent on the bulk specs. The python model count drop is proportional to the schema drop (946 → 608 ≈ 35%). Operations and paths are unchanged: the prune only removes orphan components, not anything reachable from a path.

## Polymorphic-only "false positive" residual

The plan anticipated a residual class — schemas that exist purely because a discriminator parent's `oneOf` lists them. After this pass that class is **empty** in practice: when a polymorphic subtype is reachable through its parent's `oneOf` `$ref` array, the prune pass picks it up via the standard `$ref` walk. Subtypes orphaned only because their parent is itself unreachable are correctly dropped along with the parent. No residual false-positive warnings remain.

## Edge cases

- **Discriminator `mapping` values.** OpenAPI 3.0 lets discriminators carry a `mapping: {<value>: '#/components/schemas/X'}` table whose values are JSON-Reference strings without the `$ref` keyword. The prune walker recognises these explicitly so subtypes referenced only through mapping are preserved.
- **EnvelopeBase and shared envelopes.** `EnvelopeBase`, `ErrorResponse`, and the shared `*Identity` schemas are referenced from many composed schemas; they are reachable transitively and stay.
- **Manual overlay schemas.** `ChangeManagerState` (virtual), `EnvelopeBase`, and other overlay-introduced schemas are reached through paths or other components and stay.
- **Non-schema components.** Parameters (`VersionPathParam`, `FieldsParam`, …) and responses (`Unauthorized`, `EditError`, …) are seed sources, not prune targets. The prune touches `components.schemas` only.
- **Quirks attachment integrity.** All 14 quirks attach to schemas that are reachable from a path (verified: `applied: 14, skipped_attachment_not_found: 0` in the prune-applied run for every version). No quirk targets a schema we drop.

## Stop conditions revisited

None hit. Categorization was clean — all unused schemas fell into "drop or keep, no ambiguity". Path-builder was not extended, so existing path counts are unchanged. Reference resolution still works (validators green). Warnings went down monotonically.

## Verdict

Sub-phase complete. The bulk specs are now warning-free across all 5 versions. The branch's only Spectral output is "PASS, 0 problems" everywhere. Schema count dropped ~35% in line with the cleanup; path counts unchanged. The pipeline gained a reusable prune step that runs cheaply at the end and will keep specs clean as future overlays add or remove references.
