# Phase 4d-2 — Quirks migration and operations gap closure

WLS version: **14.1.2.0.0**  ·  spec: `tools/openapi-generator/out/spec-14.1.2.0.0.yaml`


## Quirks migrated

**14 of 14 applied** (skipped: 0 target-not-found, 0 out-of-version).

Attachment kinds applied: `global: 2, path: 3, property: 8, schema: 5`.

| # | Quirk id | Attachments | Status | Source |
|---|---|---:|---|---|
| 1 | `state-casing-inconsistencies` | 3 | ok | docs/QUIRKS.md#1-casing-inconsistencies-across-runtimes |
| 2 | `healthstate-lowercase` | 1 | ok | docs/QUIRKS.md#1-casing-inconsistencies-across-runtimes |
| 3 | `jvm-os-prefix-uppercase` | 2 | ok | docs/QUIRKS.md#1-casing-inconsistencies-across-runtimes |
| 4 | `name-semantics-vary` | 1 | ok | docs/QUIRKS.md |
| 5 | `healthstate-subsystemname-null` | 1 | ok | docs/QUIRKS.md |
| 6 | `csrf-on-mutations` | 1 | ok | docs/QUIRKS.md |
| 7 | `channel-missing-listenAddress-listenPort` | 1 | ok | docs/QUIRKS.md#10-serverchannelruntime-does-not-expose-listenaddress-listenport-or-protocol |
| 8 | `csrf-serverRuntimes` | 1 | ok | docs/QUIRKS.md#2-selective-x-requested-by-enforcement-on-get-domainruntimeserverruntimes |
| 9 | `jdbc-systemresources-400-staged-create` | 1 | ok | docs/QUIRKS.md#6-post-editjdbcsystemresources-always-returns-http-400 |
| 10 | `lifecycle-async-task-shape` | 1 | ok | docs/QUIRKS.md#7-lifecycle-operations-return-an-async-task-descriptor |
| 11 | `edit-error-envelope-fqcn` | 2 | ok | docs/QUIRKS.md#4-edit-tree-validation-errors-use-a-different-envelope |
| 12 | `startedit-idempotent` | 1 | ok | docs/QUIRKS.md#5-startedit-is-idempotent |
| 13 | `jvm-threadstackdump-size` | 1 | ok | docs/QUIRKS.md#9-jvmruntimethreadstackdump-payload-size |
| 14 | `jdbc-properties-user-exposure` | 1 | ok | docs/QUIRKS.md |

Each applied quirk also stamps an `x-weblogic-quirks: [{id, doc}]` marker on its target node so consumers can audit provenance and follow the canonical write-up in `docs/QUIRKS.md`. Some quirks add additional `x-weblogic-*` extensions (`x-weblogic-conditional-csrf`, `x-weblogic-staged-create`, `x-weblogic-non-fatal-status`, `x-weblogic-csrf-header`, `x-weblogic-large-payload`, `x-weblogic-recommended-exclude`, `x-weblogic-idempotent-for-owner`, `x-weblogic-readable-credential-fragment`).

## Operations gap closure

| Path | Source | Decision rationale |
|---|---|---|
| `POST /domainRuntime/search` | manual overlay (`overlays/operations-virtual.yaml`) | No MBean. Ported verbatim from `specs/domain-runtime/search.yaml`; the DSL (`fields`, `links`, `children`, `name`) is non-trivial and the manual spec already had it precise. Re-deriving would re-introduce the v0.1.x mistake of treating the endpoint as broken instead of as CSRF-gated. |
| `POST .../serverLifeCycleRuntimes/{serverName}/startInAdmin` | manual overlay | Java scraping attempted. Result: the only `startInAdmin*` symbol in the Remote Console source is `AppDeploymentRuntimeMBeanCustomizer.startInAdminMode` — an *application deployment* startup option, not the *server lifecycle* action. The server-side `startInAdmin` MBean method does not appear in any `extension.yaml` overlay nor in any `WebLogicRest*PageRepo.java` we inspected; it is invoked by the WLS REST framework itself, outside the Remote Console source. Manual overlay is the correct fallback per the plan. |
| `POST .../serverLifeCycleRuntimes/{serverName}/startInStandby` | manual overlay | Same situation as `startInAdmin`. Both endpoints share the request body shape (optional `properties` array of NodeManager start properties) and return the standard `ServerLifeCycleTaskRuntime` async-task envelope. |

## Validation results

| Validator | Phase 4d-3 end | Phase 4d-2 end |
|---|---|---|
| `openapi-spec-validator` 3.0 strict | PASS | **PASS** |
| `openapi-generator-cli` Python smoke test | PASS (5 APIs, 276 models) | **PASS** (5 APIs, 280 models — adds `BulkSearchRequest`, `HealthState`, `HealthSymptom`) |
| `@stoplight/spectral-cli` (`spectral:oas`) | 0 / 0 | **0 / 0** |

### Spot-check: 3 quirks at distinct attachment kinds

**Path attachment** — `csrf-serverRuntimes` on `GET /domainRuntime/serverRuntimes`:

```
List all `ServerRuntimes` resources in this collection.

**Quirk — selective CSRF gate on this read endpoint.** Oracle's
docs state that `X-Requested-By` is required only on mutating
methods. On this collection it is also required for GET — but
x-weblogic-conditional-csrf: {'header': 'X-Requested-By', 'condition': 'at-least-one-managed-server-in-RUNNING-state'}
```

**Schema attachment** — `channel-missing-listenAddress-listenPort` on `ServerChannelRuntime`:

```
Runtime information for NetworkAccessPoints or "Channels".

**Quirk — REST projection does not expose channel network triplet.**
The underlying `ServerChannelRuntimeMBean` declares
`listenAddress`, `listenPort`, `protocol`, `publicAddress`, and
```

**Property attachment** — `jvm-threadstackdump-size` on `JVMRuntime.threadStackDump`:

```
JVM thread dump. Thread dump is available only on 1.5 VM

**Quirk — payload size.** Despite the field name, this is a complete
`Thread.dumpAllStacks()`-style multi-line text dump of every JVM
thread. We measured ~108 KB on a busy 12.2.1.4 OSB server and
x-weblogic-large-payload: True
x-weblogic-recommended-exclude: True
```

## Coverage vs manual spec

Manual paths: 44  ·  Generated paths with verbs: 1144  ·  Manual paths still missing from generated: **0**.

Every path the manual spec documented now appears in the generated spec (the three operations gap from 4c is closed).

## Edge cases discovered

- **`HealthState` was an auto-stub before this phase.** The schema is referenced from many places (every `*Runtime.healthState` property) but wasn't generated from a harvested MBean — it lived in `specs/common/schemas.yaml` as a curated type. The first attempts to attach quirks 2 and 5 (`healthState.state` and `healthState.subsystemName`) hit the stub and failed with `target not found`. Fix: promoted `HealthState` and `HealthSymptom` into `overlays/envelopes.yaml` so they exist with real properties; quirks now attach cleanly.
- **Java scraping for `startInAdmin` / `startInStandby` produced no matches.** The only `startInAdmin*` symbol in the Remote Console source tree is for *application deployment* (`startInAdminMode`), not *server lifecycle*. The server-side methods are invoked by the WLS REST framework itself, which is not part of `oracle/weblogic-remote-console`. Manual overlay is the correct path; documented as such.
- **Quirk `x_extensions` work at any attachment kind.** Verified that the same overlay format (description + x-extensions) injects consistently into path operations, schemas, and properties. The `x-weblogic-quirks` audit marker is appended at every target so downstream consumers can trace which editorial quirks affected a given node.
- **`description_replace` not used.** Per the plan's editorial preference, every quirk uses `description_append`. The harvested descriptions (when they exist) are preserved verbatim and the quirk text follows after a blank line. None of the 14 quirks needed to discard harvested text.
- **Cross-version applicability.** Every quirk declares `applies_to_versions` covering all five harvested versions; we have not observed version-conditional quirks in this batch. Phase 4d-5 (multi-version generation) will exercise this filter for real.

## Deferred to later sub-phases

- Server / Cluster surface curation → 4d-4.
- Multi-version specs (12.2.1.3, 12.2.1.4, 14.1.1, 15.1.1) → 4d-5.
- Description merge policy (harvested + curated operational notes beyond the quirk layer) → 4d-5.
- Live samples linking from `samples/` → 4d-5.
- Coverage expansion to JTA / WLDF / work managers / additional security beans → 4e.

## Verdict

All 14 quirks migrated to structured overlay files and injected at the right attachment points; the editorial layer that distinguished the manual spec is now part of the generator pipeline. Three operation gaps closed (`/domainRuntime/search` + `startInAdmin` + `startInStandby`); the manual spec's path coverage is now fully represented in the generated output. Validators all green; Python client smoke test grew from 276 → 280 models, picking up the new schemas without breakage.