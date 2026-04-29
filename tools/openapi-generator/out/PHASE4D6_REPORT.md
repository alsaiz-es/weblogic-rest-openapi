# Phase 4d-6 — Description merge policy

## Goal

Migrate operational notes from the manual `specs/` directory into structured `overlays/descriptions/<schema>.yaml` files so that the generator preserves the editorial value of the manual layer when the spec source-of-truth shifts to harvested generation.

After 4d-6, every schema where the manual layer added operational guidance beyond Oracle's harvested description carries that guidance in the generated spec, appended after harvested text (and after any quirk overlay) as `**Operational note:** {text}`.

## Scope

The 22 originally curated schemas only. Subsystems newly covered by 4e bulk (deployments, JMS detail, work managers, JTA, WLDF) are deferred to 4e-2 per the plan.

## Format

`overlays/descriptions/<SchemaName>.yaml`:

```yaml
schema: <SchemaName>
schema_level:
  operational_note: |
    markdown text
properties:
  <propertyName>:
    operational_note: |
      markdown text
```

Merge order in the pipeline: harvested description (base) → quirks overlay descriptions (4d-2) → description overlay operational notes (4d-6). Each layer appends with a blank-line separator. The new layer stamps `x-weblogic-description-overlay: true` on the affected node so consumers can audit which descriptions carry post-harvested guidance.

## Overlays created (21)

Located at `overlays/descriptions/`:

| Schema | schema_level | property notes |
|---|---|---|
| `ServerRuntime` | yes | `serverClasspath`, `currentMachine`, `adminServerListenPort`, `administrationURL`, `inSitConfigState` |
| `ThreadPoolRuntime` | yes | `stuckThreadCount`, `hoggingThreadCount`, `pendingUserRequestCount`, `throughput`, `sharedCapacityForWorkManagers` |
| `JVMRuntime` | yes | `heapFreePercent`, `javaVMVendor` |
| `JDBCDataSourceRuntimeBase` | yes | `waitingForConnectionFailureTotal`, `leakedConnectionCount`, `failuresToReconnectCount`, `unresolvedTotalCount`, `databaseProductVersion`, `deploymentState` |
| `ApplicationRuntime` | — | `internal`, `partitionName` |
| `WebAppComponentRuntime` | — | `sessionMonitoringEnabled`, `sessionCookieMaxAgeSecs`, `servletReloadCheckSecs`, `JSPPageCheckSecs` |
| `EJBComponentRuntime` | yes | — |
| `AppClientComponentRuntime` | yes | — |
| `ConnectorComponentRuntime` | — | `schema`, `configuration` |
| `DeploymentState` | yes | — |
| `ServerChannelRuntime` | — | `channelName` |
| `JMSRuntime` | yes | `name` |
| `JMSPausedState` | yes | — |
| `JMSServerRuntime` | yes | `pendingTransactions`, `transactions` |
| `Server` | — | `name` |
| `Cluster` | yes | — |
| `JDBCSystemResource` | — | `targets` |
| `JDBCDriverParamsBean` | — | `url`, `password` |
| `JDBCConnectionPoolParamsBean` | — | `testTableName`, `invokeBeginEndRequest` |
| `JDBCDataSourceParamsBean` | — | `globalTransactionsProtocol` |
| `ChangeManagerState` | — | `editSession` |

Total per version: **21 schemas attached, with schema-level notes on 12 and property-level notes on 17** (cumulative across schemas — most schemas have either or both).

## Notes intentionally skipped

The plan asks to skip aggressively. Categories deliberately not migrated:

- **Notes that paraphrase the harvested description.** Most `name`, `type`, `identity` field descriptions in `specs/` simply reword the harvested text; no operational signal is added by re-stating them.
- **Notes already covered by 4d-2 quirks.** All 14 migrated quirks (`overlays/quirks/`) cover state casing, `X-Requested-By` semantics, JVM `OS` prefix, JDBC `properties.user`, JDBC `JDBCSystemResources` partial-create, lifecycle async-task envelope, etc. No description overlay duplicates a quirk.
- **`processCpuLoad` (JVMRuntime), `intervalToPoll` (ServerLifeCycleTaskRuntime).** Both are documented in the manual `specs/jvm.yaml` and `specs/lifecycle/lifecycle.yaml` based on live observation, but Oracle's harvested YAMLs do not declare them as properties of those MBeans. The generator therefore cannot emit them — overlays for these properties were drafted, run, and then dropped because they had no attachment target.
- **Manual examples and per-path documentation.** The `examples` blocks and `description` text on individual operations in `specs/` are out of scope for description overlays — they belong with samples (4d-7) and operation-level metadata (already in 4d-1).

## Generator pipeline change

New module `tools/openapi-generator/src/descriptions.py`:

- `load_overlays()` reads every `overlays/descriptions/*.yaml` (sorted, name-keyed by stem).
- `apply_descriptions(doc)` walks `components.schemas`, locates each overlay's target schema (and optional property via the same `_props_of` walker pattern as `quirks.py`), and appends the operational note as `**Operational note:** {text}` separated from the existing description by a blank line.
- Stamps `x-weblogic-description-overlay: true` on every affected node.
- Returns a `{ applied, skipped_schema_not_found, skipped_property_not_found }` stats dict.

`main.py` invokes `apply_descriptions` immediately after `apply_quirks` so the chain is harvested → quirk append → description overlay append.

## Validation

| Check | Baseline (4e) | 4d-6 |
|---|---|---|
| `openapi-spec-validator` strict (5 versions) | PASS | **PASS** all 5 |
| `spectral lint` errors | 0 | **0** all 5 |
| `spectral lint` warnings (unused-component) | 256–286 | 256–286 (12.2.1.3.0: 257; 12.2.1.4.0: 256; 14.1.1.0.0: 286; 14.1.2.0.0: 263; 15.1.1.0.0: 265) |
| `openapi-generator-cli generate -g python` smoke (14.1.2 JSON) | PASS, ~1180 models | **PASS** (1190 models, 5 APIs) |

The python smoke test continues to require the JSON workaround (Swagger Parser's SnakeYAML codepoint limit) documented in 4d-5 — purely a consumer-side concern.

## Per-version application

| Version | Overlays applied | Skipped properties (intentional version-skewed) |
|---|---|---|
| `12.2.1.3.0` | 21 / 21 | `JDBCConnectionPoolParamsBean.invokeBeginEndRequest` (14.1.2-only field) |
| `12.2.1.4.0` | 21 / 21 | `JDBCConnectionPoolParamsBean.invokeBeginEndRequest` (14.1.2-only field) |
| `14.1.1.0.0` | 21 / 21 | — |
| `14.1.2.0.0` | 21 / 21 | `ApplicationRuntime.partitionName` (Multi-Tenant, removed in 14.1.2) |
| `15.1.1.0.0` | 21 / 21 | `ApplicationRuntime.partitionName` (Multi-Tenant, removed in 14.1.2+) |

The skips are correct: when a property does not exist in the harvested set for a given version, there is no node to attach to. The notes themselves document those absences (e.g. *"disappears entirely from 14.1.2"*) and only attach where the property exists.

## Spot-check (5 schemas, 14.1.2)

Verified directly in `out/spec-14.1.2.0.0.yaml`:

1. **`JDBCDataSourceRuntimeBase.leakedConnectionCount`** — harvested text *"The number of leaked connections..."* preserved verbatim, `**Operational note:** Cumulative connections reclaimed because the application never returned them..."* appended after blank line.
2. **`ServerRuntime.serverClasspath`** — harvested *"Get the classpath for this server..."* preserved, exclude-fields recommendation appended.
3. **`DeploymentState` (schema-level)** — base *"Shared enum extracted by Phase 4d-3 from 16 occurrences"* preserved, numeric mapping note appended.
4. **`JMSPausedState` (schema-level)** — base extraction note preserved, tri-state semantic appended.
5. **`Cluster` (schema-level)** — harvested *"This bean represents a cluster in the domain..."* preserved on the outer wrapper schema (the one consumers see); 73-vs-69 cross-version field-set note appended. The inner `allOf` branch retains its harvested-only copy unchanged.

All five checks confirm: harvested text is **preserved verbatim**, the `**Operational note:**` prefix appears with the correct blank-line separation, and no harvested text is overwritten.

## Edge cases

- **Cluster (allOf wrapper).** When a schema is `allOf`-wrapped (every Phase 4b-generated schema is, since `main.py` composes `{ allOf: [EnvelopeBase, harvested], description: harvested }`), the outer wrapper carries a copy of the harvested description. The overlay attaches to the outer wrapper. Net effect: the outer description is harvested + overlay (what consumers see), the inner branch retains harvested only. Validator and spectral are silent on this; tools rendering the schema use the outer description.
- **`JDBCDataSourceRuntimeBase` vs `JDBCDataSourceRuntime`.** Pool counters (leak, fail, etc.) live on the polymorphic *Base* schema and are inherited by 3 subtypes via `allOf` ($ref to Base). Overlays target the Base; subtypes inherit naturally with no further wiring. Verified in spectral output: no duplicate-component warning is generated by adding descriptions on Base.
- **Version-skewed property absence.** As documented above, two properties (`invokeBeginEndRequest`, `partitionName`) are intentionally version-specific. The generator emits them on the versions where harvested declares them; the overlay attaches there and silently skips elsewhere. Stats track the skips so the report can distinguish "intentional skip" from "overlay typo".

## Verdict

Sub-phase complete. The 22-curated description-overlay layer preserves the operational guidance that lived in the manual `specs/`, applies cleanly across all 5 supported WLS versions, validates green on all checks, and adds 21 overlay files (one per curated schema with non-trivial editorial content; the 22nd, `JDBCServiceRuntime`, had no operational guidance beyond what harvested already says).

Subsystem-level curation for newly-bulk-covered MBeans (deployments, JMS detail, work managers, JTA, WLDF) follows in 4e-2 per Alfredo's 2026-04-28 decision.
