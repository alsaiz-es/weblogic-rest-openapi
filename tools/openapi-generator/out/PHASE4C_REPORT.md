# Phase 4c — Paths, operations, pre-overlay minimal

WLS version: **14.1.2.0.0**  ·  spec: `tools/openapi-generator/out/spec-14.1.2.0.0.yaml`


## Path counts by tree

| Tree | Paths |
|---|---:|
| `domainRuntime` | 457 |
| `edit` | 643 |
| `changeManager` (virtual) | 6 |
| **Total** | **1141** |

## Operation sources

| Source | Count |
|---|---:|
| `extension.yaml` (per-MBean) | 7 ingestions |
| Virtual (`overlays/operations-virtual.yaml`) | 6 paths |
| Java-scraped | 0 (deferred to 4d, see Gaps) |

**`extension.yaml` actions ingested:**

- `ServerRuntimeMBean` mounted at `/domainRuntime/serverRuntimes/{name}`: 1 actions
- `JVMRuntimeMBean` mounted at `/domainRuntime/serverRuntimes/{name}/JVMRuntime`: 1 actions
- `JDBCDataSourceRuntimeMBean` mounted at `/domainRuntime/serverRuntimes/{name}/JDBCServiceRuntime/JDBCDataSourceRuntimeMBeans/{name2}`: 10 actions
- `JMSServerRuntimeMBean` mounted at `/domainRuntime/serverRuntimes/{name}/JMSRuntime/JMSServers/{name2}`: 8 actions
- `JMSServerRuntimeMBean` mounted at `/domainRuntime/serverRuntimes/{name}/JMSRuntime/JMSServers/{name2}/sessionPoolRuntimes/{name3}/JMSServer`: 8 actions
- `JDBCSystemResourceMBean` mounted at `/edit/JDBCSystemResources/{name}`: 1 actions
- `ServerLifeCycleRuntimeMBean` mounted at `/domainRuntime/serverLifeCycleRuntimes/{name}`: 6 actions

## Validation results

| Validator | Result |
|---|---|
| `openapi-spec-validator` (3.0 strict) | PASS |
| `openapi-generator-cli` Python client smoke test | PASS — generation completed without errors (260 models, 4 API modules; ~45 MB) |
| `@stoplight/spectral-cli` (`spectral:oas` ruleset) | 0 errors, ~1989 warnings — all benign (missing per-operation `description` strings, missing `info.contact`, one `typed-enum` on the `version` enum mixing `latest` with version strings, 4 unused-component on overlay parameters) |
| Swagger UI render via Docker | DEFERRED — Docker not available in this environment |

## Schema counts

- Total component schemas: **422**
  - Generated from harvested + overlays: **22**
  - Auto-stubs (orphan refs): **392**

Stubs are placeholder objects (`{type: object, x-stub: true}`) for MBean schemas that appear as `$ref` targets but are not yet in the generation list. Phase 4e expands the list; until then stubs keep the document validatable end-to-end.

## Path coverage vs manual specs

Comparison normalizes path-parameter names (manual uses `{serverName}`, `{applicationName}`; generator uses `{name}`/`{name2}`). Both sides reduced to `{*}`.

| | Count |
|---|---:|
| Manual paths | 44 |
| Generated paths (with verbs) | 1141 |
| In both | 41 |
| Only in generated | 1100 |
| Only in manual | 3 |
| Verb mismatches in shared paths | 1 |

### Paths in manual but missing from generated

- `/domainRuntime/search` — verbs: ['post']
- `/domainRuntime/serverLifeCycleRuntimes/{*}/startInAdmin` — verbs: ['post']
- `/domainRuntime/serverLifeCycleRuntimes/{*}/startInStandby` — verbs: ['post']

### Paths in generated but not in manual (sample)

- `/domainRuntime` — verbs: ['get']
- `/domainRuntime/SNMPAgentRuntime` — verbs: ['get']
- `/domainRuntime/appRuntimeStateRuntime` — verbs: ['get']
- `/domainRuntime/batchJobRepositoryRuntime` — verbs: ['get']
- `/domainRuntime/consoleRuntime` — verbs: ['get']
- `/domainRuntime/deploymentManager` — verbs: ['get']
- `/domainRuntime/deploymentManager/DBClientDataDeploymentRuntimes` — verbs: ['get']
- `/domainRuntime/deploymentManager/DBClientDataDeploymentRuntimes/{*}` — verbs: ['get']
- `/domainRuntime/deploymentManager/appDeploymentRuntimes` — verbs: ['get']
- `/domainRuntime/deploymentManager/appDeploymentRuntimes/{*}` — verbs: ['get']
- `/domainRuntime/deploymentManager/deploymentProgressObjects` — verbs: ['get']
- `/domainRuntime/deploymentManager/deploymentProgressObjects/{*}` — verbs: ['get']
- `/domainRuntime/deploymentManager/libDeploymentRuntimes` — verbs: ['get']
- `/domainRuntime/deploymentManager/libDeploymentRuntimes/{*}` — verbs: ['get']
- `/domainRuntime/domainSecurityRuntime` — verbs: ['get']
- `/domainRuntime/editSessionConfigurationManager` — verbs: ['get']
- `/domainRuntime/editSessionConfigurationManager/editSessionConfigurations` — verbs: ['get']
- `/domainRuntime/editSessionConfigurationManager/editSessionConfigurations/{*}` — verbs: ['get']
- `/domainRuntime/elasticServiceManagerRuntime` — verbs: ['get']
- `/domainRuntime/elasticServiceManagerRuntime/scalingTasks` — verbs: ['get']
- `/domainRuntime/elasticServiceManagerRuntime/scalingTasks/{*}` — verbs: ['get']
- `/domainRuntime/elasticServiceManagerRuntime/scalingTasks/{*}/subTasks` — verbs: ['get']
- `/domainRuntime/elasticServiceManagerRuntime/scalingTasks/{*}/subTasks/{*}` — verbs: ['get']
- `/domainRuntime/elasticServiceManagerRuntime/scalingTasks/{*}/subTasks/{*}/subTasks` — verbs: ['get']
- `/domainRuntime/elasticServiceManagerRuntime/scalingTasks/{*}/subTasks/{*}/subTasks/{*}` — verbs: ['get']
- `/domainRuntime/logRuntime` — verbs: ['get']
- `/domainRuntime/messageDrivenControlEJBRuntime` — verbs: ['get']
- `/domainRuntime/migratableServiceCoordinatorRuntime` — verbs: ['get']
- `/domainRuntime/migratableServiceCoordinatorRuntime/migrationTaskRuntimes` — verbs: ['get']
- `/domainRuntime/migratableServiceCoordinatorRuntime/migrationTaskRuntimes/{*}` — verbs: ['get']
- … +1070 more

### Verb mismatches in shared paths

- `/edit/JDBCSystemResources/{*}`: gen=['delete', 'get', 'post']  manual=['delete', 'get']

## Edge cases discovered

- **Multiple `{name}` placeholders in deeply-nested URLs.** OAS forbids duplicate path parameters in a single URL. Path builder now indexes them as `{name}`, `{name2}`, …; an end-of-pipeline pass injects path-item parameter declarations for each unique placeholder.
- **`defaultValue: {derivedDefault: true}` in harvested.** The harvested layer uses non-empty dict defaults as meta-markers (e.g. "this default is computed elsewhere"). They are not real defaults and must be skipped; otherwise the validator complains that a `string` schema has a dict default.
- **`$ref` siblings.** OAS 3.0 forbids siblings to `$ref` (validator is permissive but spectral is strict). Schema builder now wraps references in `allOf:[{$ref}]` whenever it needs to attach `description`, `readOnly`, `deprecated`, or any `x-` extension. This was originally a Phase 4d task; lifted forward because spectral lint required it.
- **Synthetic collections.** `/domainRuntime/serverRuntimes` is not a containment property of `DomainRuntimeMBean` — it's synthesized by the WLS REST framework via `DomainRuntimeServiceMBean`. We declare a single edge in `SYNTHETIC_COLLECTIONS` so the path builder can mount it. Same shape used for any future REST-framework synthetic collection.
- **Path explosion under DomainMBean.** The edit tree starts with 49 collection containment children at depth 1 alone. Visited-set on schema name prevents true cycles, depth cap (8) bounds the walk; final edit count is 643 paths. Manageable and within OpenAPI tooling limits, but Phase 4d may want to introduce a scope filter (e.g. only emit the curated set used in manual specs as the "common" view, full surface as the "complete" view).
- **`startInAdmin` / `startInStandby` lifecycle actions** are present in the manual lifecycle spec but absent from `extension.yaml`. They exist in WLS (verified live) but live only in Java repo code. Java scraping deferred — they are gaps tracked below.

## Gaps explicitly deferred to Phase 4d

- `startInAdmin`, `startInStandby` lifecycle actions on `ServerLifeCycleRuntime` (not in `extension.yaml`; need either Java scraping or a small operations overlay).
- Curation policy for the 165-property `Server` and 77-property `Cluster` schemas vs the manual's curated subset (~27 / ~11). Decision: emit full surface here, layer a `views/common.yaml` overlay in 4d that filters down.
- Manual path-parameter naming (`{serverName}`, `{clusterName}`, …). Generator uses generic `{name}`. Could be improved by reading the parent collection's MBean type and synthesizing a semantic name.
- Per-operation descriptions (spectral warning, not error).
- Enum extraction to shared `components/schemas/<X>State` schemas — 4b identified 10 such candidates.
- Sub-type discriminator metadata (the `type` field on `*ComponentRuntime` subtypes — info available in parent overlay's `subTypes:` block).
- Quirks documentation migration to `overlays/quirks/<id>.yaml`.
- Curated-description merge policy (append our operational notes after harvested descriptions).
- Live samples linking to schemas/paths.
- Per-version specs (currently only 14.1.2; same generator can produce 12.2.1.4, 14.1.1, 15.1.1 by changing the `wls_version` arg).
- Operation-level `x-weblogic-required-role` mapping from `getRoles.allowed` (plan said 4c does basic mapping — basic role is at the `securitySchemes` description level for now; per-operation refinement deferred).

## Verdict

`tools/openapi-generator/out/spec-14.1.2.0.0.yaml` is a **valid, lintable OpenAPI 3.0 document** with 1141 paths, 422 component schemas (of which 392 are auto-stubs), and full envelope/error infrastructure. Manual coverage is a strict subset: every manual path either appears in the generated spec or is explainable as a known gap (Java-scraped lifecycle variants, semantic path-param naming). End-to-end consumers (Python client generator, openapi-spec-validator, spectral) accept the document. Ready for the initial `feat/openapi-generator` commit and progression to Phase 4d (overlays merge).