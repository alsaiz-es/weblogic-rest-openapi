# Phase 4d-5 — Multi-version generation

Generated specifications for the five WLS versions present in the Remote Console harvested YAMLs. Each spec passes the same three validators independently; cross-version diffs are documented in `tools/openapi-generator/out/VERSION_DELTAS.md`.

## Per-version generation results

| Version | Schemas | Paths | Operations | spec-validator | Spectral | Python smoke |
|---|---:|---:|---:|---|---|---|
| `12.2.1.3.0` | 479 | 2341 | 4366 | PASS | 0 / 0 | PASS via JSON input (300 models, 5 APIs) |
| `12.2.1.4.0` | 482 | 2353 | 4394 | PASS | 0 / 0 | PASS via JSON input (301 models, 5 APIs) |
| `14.1.1.0.0` | 433 | 1110 | 1968 | PASS | 0 / 0 | PASS (275 models, 5 APIs) |
| `14.1.2.0.0` | 439 | 1144 | 2021 | PASS | 0 / 0 | PASS (280 models, 5 APIs) |
| `15.1.1.0.0` | 451 | 1178 | 2094 | PASS | 0 / 0 | PASS (287 models, 5 APIs) |

### YAML codepoint limit note (12.2.1.x)

The 12.2.1.3 and 12.2.1.4 specs each weigh ~5 MB JSON (~6.5 MB YAML), past Swagger Parser's default SnakeYAML codepoint limit of 3 145 728. Setting `JAVA_OPTS="-Dmaxyaml=..."` did not propagate through `openapi-generator-cli`'s Node wrapper in our environment. Workaround used for the smoke test: convert the generated YAML to JSON and feed JSON to the generator. JSON parsing has no equivalent codepoint limit. The generated spec itself is unaffected — the constraint is purely in the consumer toolchain. We document this in `VERSION_DELTAS.md` and the README so downstream users hit it once and not twice.

- `12.2.1.3.0` — YAML input fails: spec exceeds SnakeYAML's default 3 145 728 codepoint limit; JSON input works.
- `12.2.1.4.0` — YAML input fails: spec exceeds SnakeYAML's default 3 145 728 codepoint limit; JSON input works.

## Cross-version diff summary

| From | To | Schemas Δ (real) | Properties +/− | Type changes | Paths +/− |
|---|---|---|---|---:|---|
| `12.2.1.3.0` | `12.2.1.4.0` | +0 / -0 | +8 / -0 | 0 | +12 / -0 |
| `12.2.1.4.0` | `14.1.1` | +0 / -0 | +3 / -2 | 0 | +5 / -1248 |
| `14.1.1` | `14.1.2` | +0 / -0 | +9 / -5 | 0 | +34 / -0 |
| `14.1.2` | `15.1.1` | +0 / -0 | +12 / -1 | 0 | +36 / -2 |

Details per pair are in `tools/openapi-generator/out/VERSION_DELTAS.md`.

The 12.2.1.4 → 14.1.1 transition removes 1248 paths, dominated by the Multi-Tenant deprecation (`domainPartitionRuntimes` and `resourceGroupLifeCycleRuntimes` and their subtrees). All other transitions are smaller — single-digit schema property additions and dozens of path additions, consistent with Oracle's release-to-release MBean evolution.

## Quirks × version

All 14 quirks declare `applies_to_versions` covering every supported version, so all 14 inject into every per-version spec. This was intentional — the quirks we collected are surface behaviors that have not changed across the harvested versions, even when the underlying mechanism differs (e.g. `edit-error-envelope-fqcn` describes the FQCN-stripping behavior *difference* between 12.2.1.4 and 14.x within a single quirk text, rather than splitting into two version-conditional quirks). If a future quirk applies to fewer versions, the `applies_to_versions` list in its overlay file is the only thing that needs to change.

| Quirk | 12.2.1.3.0 | 12.2.1.4.0 | 14.1.1 | 14.1.2 | 15.1.1 |
|---|---|---|---|---|---|
| `channel-missing-listenAddress-listenPort` | OK | OK | OK | OK | OK |
| `csrf-on-mutations` | OK | OK | OK | OK | OK |
| `csrf-serverRuntimes` | OK | OK | OK | OK | OK |
| `edit-error-envelope-fqcn` | OK | OK | OK | OK | OK |
| `healthstate-lowercase` | OK | OK | OK | OK | OK |
| `healthstate-subsystemname-null` | OK | OK | OK | OK | OK |
| `jdbc-properties-user-exposure` | OK | OK | OK | OK | OK |
| `jdbc-systemresources-400-staged-create` | OK | OK | OK | OK | OK |
| `jvm-os-prefix-uppercase` | OK | OK | OK | OK | OK |
| `jvm-threadstackdump-size` | OK | OK | OK | OK | OK |
| `lifecycle-async-task-shape` | OK | OK | OK | OK | OK |
| `name-semantics-vary` | OK | OK | OK | OK | OK |
| `startedit-idempotent` | OK | OK | OK | OK | OK |
| `state-casing-inconsistencies` | OK | OK | OK | OK | OK |

## Edge cases discovered

- **YAML codepoint limit on 12.2.1.x specs.** The 12.2.1.x specs generate ~2350 paths each due to the Multi-Tenant subtree (~2× the 14.1.x+ counts). The resulting YAML exceeds Swagger Parser's default 3 145 728 codepoint limit. `openapi-spec-validator` (Python) handles them fine; only the Java-based `openapi-generator-cli` trips. Workaround: feed the equivalent JSON instead. The generator does not need to worry about this — it is purely a consumer-side concern.
- **Generator state across versions.** Schema-name normalization uses a module-level cache. We verified by running 14.1.2 alone, then again after generating 12.2.1.4 first, and observed identical totals — no leakage. The cache is deterministic per Java FQN, so any leak across versions would manifest as inflated schema counts; none observed.
- **Quirks `applies_to_versions` filter is exercised but inert.** Every overlay lists all five versions, so the filter never skips a quirk in this pass. This validates that the loader *reads* the field correctly (we re-parse the overlays per version build), but the actual filtering behavior — quirks appearing only on a subset — remains untested with real-world data. A version-conditional quirk is the natural way to test the filter; we did not invent one for this sub-phase.
- **`build_spec` is reasonably fast.** Each per-version build completes in ≤2 s on the lab machine (excluding validators); the five-version run plus three validators completes in roughly a minute. No need for caching or parallelization yet.
- **Curated schemas drift gracefully across versions.** The 22 MBeans we curate are present in all five harvested directories. `ServerRuntime`, `Server`, `Cluster`, etc. all have stable schema names and progressively-extended property sets across versions. No schema disappears or is renamed across the supported window.

## Deferred to follow-up sub-phases

- Server / Cluster surface curation → 4d-4.
- Description merge policy (harvested base + curated operational notes appended beyond the quirk layer) → follow-up.
- Live samples linking from `samples/` into the generated specs → follow-up.
- Coverage expansion to JTA / WLDF / work managers / additional security beans → 4e.
- Decision on the manual `specs/` directory's fate (keep as historical, redirect to generated, or delete) — explicitly out of scope per the plan; belongs to the merge-to-main conversation.

## Verdict

The branch's promise of multi-version coverage is now real. Five specifications, one per supported WLS release, all passing the same three validators independently. The cross-version deltas are documented in `VERSION_DELTAS.md` and consistent with what Oracle's release notes describe (Multi-Tenant deprecation in 14.1.x, JDK-21 / virtual-thread additions in 14.1.2 and 15.1.1).

Next decision points (per the plan): 4d-4 (editorial Server/Cluster curation), merge to main (strategic), or 4e (coverage expansion). Any is defensible; none is forced by 4d-5's outcome.