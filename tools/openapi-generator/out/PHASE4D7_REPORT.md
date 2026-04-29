# Phase 4d-7 — Live samples linking

## Goal

Reference the verbatim JSON samples under `samples/{12.2.1.4,14.1.2}/`
from the generated spec. Hybrid format per the plan: native OpenAPI
`examples` for the canonical sample per operation, `x-weblogic-sample-paths`
extension for overflow / unmappable status / large-payload cases.

After 4d-7, generated specs for 12.2.1.4 and 14.1.2 carry inline live
responses on the most useful operations and link to the broader sample
corpus for everything else. The other three versions (12.2.1.3,
14.1.1, 15.1.1) have no live captures and remain unchanged.

## Sample inventory

| Source dir | JSON files | Mapped (canonical+overflow+error) | Mapped (canonical only) | Unmapped (skipped) |
|---|---:|---:|---:|---:|
| `samples/12.2.1.4/` | 51 | 47 | 27 canonical + 18 overflow + 2 error | 4 (generic 4xx + 401 HTML + 1 12.2.1.4-only artefact `error_400_sample.json`) |
| `samples/14.1.2/` | 64 | 62 | 28 canonical + 28 overflow + 6 error | 2 (`error_404_sample.json`, `error_401_sample.html`) |

Plus 30 `csrf-test/*.txt` raw HTTP captures across both versions, intentionally not mapped (text artefacts illustrating CSRF behavior; their content is captured by quirk 06 / quirk 08).

## Per-version application

| Version | ops with samples | native canonical | extension-only canonical | overflow paths | error native | error paths | unmatched |
|---|---:|---:|---:|---:|---:|---:|---:|
| `12.2.1.3.0` | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `12.2.1.4.0` | 33 | 27 | 3 | 18 | 0 | 4 | 0 |
| `14.1.1.0.0` | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `14.1.2.0.0` | 35 | 28 | 4 | 28 | 0 | 4 | 0 |
| `15.1.1.0.0` | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

The three versions without samples are correct: there are no live captures for them, and per the plan we do not synthesise new samples or cross-version-port existing ones.

## Mapping policy

Implemented in `tools/openapi-generator/src/sample_loader.py` as an explicit
per-file table (one entry per known sample). With ~60 files per version
the hand-curated map is more reliable than a heuristic regex-based mapper
and the report can document each decision.

Each table row carries:

- Relative path under `samples/<version>/`.
- Operation key `(path_template, method)` — using the exact placeholders
  the path-builder emits (`{serverName}`, `{channelName}`,
  `{applicationName}`, `{componentName}`, `{dataSourceName}`,
  `{JMSServerName}`, `{clusterName}`, `{systemResourceName}`).
- Role: `canonical` (single most representative — emitted as native
  `examples`), `overflow` (additional — emitted as
  `x-weblogic-sample-paths`), or `error` (4xx — emitted natively if
  the operation has the response defined as a non-`$ref`, otherwise as
  extension).
- Response status (`200` for reads, `400` for partial-create / wrong-state
  errors, etc.).
- One-line summary used as the OpenAPI `examples.<key>.summary`.

## Canonical selection rules (used for operations with multiple candidates)

Per the plan, canonical preference goes to:

1. **AdminServer over managed servers** when both samples cover the
   same operation (more universal): `serverRuntime_AdminServer.json`,
   `jmsRuntime_AdminServer.json`, etc.
2. **Healthy / steady-state samples over edge cases**: `_full.json`
   over `_default.json` and over `_after_update.json` for edit-tree
   endpoints.
3. **Richest content over minimal**: `applicationRuntimes_collection_AdminServer.json`
   wins over `applicationRuntimes_summary.json` (the latter is included
   as overflow).
4. **Empty-state included**: where the empty-collection / no-resource
   case is meaningful (`jmsServers_collection_AdminServer.json`),
   it remains canonical because it is the *typical* state for stock
   domains.

## Generator emission

New module `tools/openapi-generator/src/sample_loader.py`:

- `load_inventory(version)` walks the explicit map for the version,
  reads each file, and groups by operation.
- `apply_samples(doc, version)` walks `paths` and injects:
  - **Canonical** sample → `examples.canonical` on the response keyed
    by status. Adds `x-weblogic-sample-source: <repo-relative path>`
    on every example for provenance.
  - **Overflow** + **status with no defined response** + **explicit
    extension-only operations** → `x-weblogic-sample-paths` on the
    operation as `[{path, summary}, ...]`.
  - **Error** sample with a defined non-`$ref` response → native
    `examples.canonical` on that status.

Wired into `main.py` after `apply_descriptions` (4d-6) and after
`apply_nullability` (introduced this phase, see below).

## Empirical nullability fixes (`overlays/nullability.yaml`)

Native sample injection produced `oas3-valid-media-example` errors
because the harvested MBean YAMLs declare several fields as
non-nullable (`type: string` or `type: array`) while the live REST
projection returns `null`. These are real schema/sample mismatches —
the harvested set is too strict. Fixed by adding `nullable: true` to
the affected properties via a new overlay layer.

20 entries added, applied by `tools/openapi-generator/src/nullability.py`
after the schemas are assembled and before sample injection:

| Schema | Properties marked nullable |
|---|---|
| `JVMRuntime` | `javaVendorVersion` |
| `ServerChannelRuntime` | `associatedVirtualTargetName` |
| `JDBCDataSourceBean` | `datasourceType` |
| `JDBCConnectionPoolParamsBean` | `connectionLabelingCallback`, `driverInterceptor`, `fatalErrorCodes`, `initSql` |
| `JDBCDataSourceParamsBean` | `connectionPoolFailoverCallbackHandler`, `dataSourceList`, `proxySwitchingCallback`, `proxySwitchingProperties` |
| `JDBCDriverParamsBean` | `password`, `url` |
| `Cluster` | `notes`, `autoMigrationTableCreationDDLFile`, `clusterAddress`, `clusterBroadcastChannel`, `coherenceClusterSystemResource`, `dataSourceForAutomaticMigration`, `dataSourceForJobScheduler`, `dataSourceForSessionPersistence`, `siteName`, `frontendHost`, `remoteClusterAddress` |

## Extension-only operations (canonical bypassed)

Three classes route the canonical sample to `x-weblogic-sample-paths`
instead of the native `examples` block:

1. **`/edit/servers` and `/edit/servers/{serverName}` (GET).** The
   136-property edit-tree `Server` schema trips spectral's
   `Maximum call stack size exceeded` when validating an example
   against it. The samples are large but otherwise valid; pushing
   them to the extension keeps spectral green.
2. **`/edit/JDBCSystemResources/{systemResourceName}/JDBCResource`
   (GET).** `datasourceType` is a non-nullable enum (`GENERIC`, `MDS`,
   `AGL`, `UCP`, `PROXY`); the live default sample returns `null`.
   OAS 3.0 evaluates `enum` independently of `nullable`, so a
   nullable+enum schema still rejects null. Extension only.
3. **`/edit/clusters/{clusterName}` (GET).** `migratableTargets` has a
   structural shape mismatch — harvested types it as
   `array<array<string>>` (bean-reference tuples), the live REST
   projection returns `array<{identity: array<string>}>`. Fixing this
   would require a deeper schema correction beyond per-property
   nullability; extension routing is the pragmatic minimum.

## $ref-only response handling

A second class of would-be-injection issue: 4xx responses on edit-tree
operations resolve to `$ref: '#/components/responses/...'`. Adding
`content` / `description` siblings to a `$ref` is forbidden in OAS 3.0
(`no-$ref-siblings`). The sample loader detects this case
(`_response_is_ref`) and routes the error sample to
`x-weblogic-sample-paths` instead.

Affected: 4 error samples per version (the change-manager
`safeResolve_idle_400` / `forceResolve_idle_400` plus the JDBC
partial-create 400 plus the cluster/manager equivalents).

## Validation

| Check | Baseline (4d-6) | 4d-7 |
|---|---|---|
| `openapi-spec-validator` strict (5 versions) | PASS | **PASS** all 5 |
| `spectral lint` errors | 0 | **0** all 5 |
| `spectral lint` warnings | 256–286 | 256–286 unchanged (12.2.1.3: 257; 12.2.1.4: 256; 14.1.1: 286; 14.1.2: 263; 15.1.1: 265) |
| `openapi-generator-cli generate -g python` smoke (14.1.2 JSON) | 1190 models | **1190 models, 5 APIs — PASS** |
| Spec size (14.1.2) | 5.6 MB | 5.9 MB (+5%) |
| Spec size (12.2.1.4) | 9.4 MB | 9.3 MB (within noise — text overhead offsets harvested-only content shifts) |

Spec size growth stays well within the 50% stop-condition. The increase
on 14.1.2 is the embedded JSON of ~28 native examples; bigger
operations route to the extension instead.

## Spot-check (3 operations, 14.1.2)

Verified directly in `out/spec-14.1.2.0.0.yaml`:

1. **Single-sample read — `GET /domainRuntime/serverRuntimes/{serverName}/JVMRuntime`.**
   200 response carries one canonical example
   (`samples/14.1.2/jvmRuntime_AdminServer.json`); no overflow.
   `javaVendorVersion: null` validates because the property is now
   nullable.
2. **Multi-sample read — `GET /edit/JDBCSystemResources/{name}/JDBCResource/JDBCDataSourceParams`.**
   Canonical = `_full.json`; two overflow paths
   (`_after_update.json`, `JDBCResource_JDBCDataSourceParams_default.json`)
   on `x-weblogic-sample-paths`. All three target paths exist on disk.
3. **Lifecycle read — `GET /domainRuntime/serverLifeCycleRuntimes/{serverName}`.**
   Canonical = `lifecycle/serverLifeCycleRuntime_server1.json`;
   overflow = `_with_links.json`. Lifecycle action POSTs (`/suspend`,
   `/shutdown`, …) have no live samples in the corpus and remain
   sample-less, which is honest.

All `x-weblogic-sample-source` values resolve to existing files under
`samples/`.

## Edge cases

- **Cross-version sample lineage.** Many operations have samples on
  both 12.2.1.4 and 14.1.2 captured from different live domains (OSB
  on 12.2.1.4, vanilla `base_domain` on 14.1.2). They are not the
  *same* values; the spec for each version carries its own set, per
  the plan ("treat each version's samples as belonging only to that
  version's spec").
- **Versions without samples.** 12.2.1.3, 14.1.1, 15.1.1 emit specs
  with zero `examples` blocks and zero `x-weblogic-sample-paths`
  arrays. This is correct: claiming empirical validation we do not
  have would be wrong.
- **Sample-side schema drift.** The 20 nullability overrides are real
  schema corrections discovered by sample injection. They apply to
  every version (the harvested-vs-live mismatch is structural, not
  per-capture). Their stats track schema-not-found / property-not-found
  cases (e.g. `JVMRuntime.javaVendorVersion` only exists from 14.1.2;
  on 12.2.1.x its overlay correctly skips).
- **Generic 4xx samples (`error_404_sample.json`, etc.).** Not mapped
  per the plan ("don't cleanly map"). They illustrate envelope shape
  without binding to any specific operation; consumers get the same
  shape via the global `ErrorResponse` schema.
- **csrf-test text artefacts.** 30 `.txt` raw HTTP captures across
  both versions deliberately not mapped — they are not JSON, and
  their semantic ("X-Requested-By behavior on this endpoint") is
  already covered by quirks 06 (mutations) and 08 (selective on
  `serverRuntimes`).

## Verdict

Sub-phase complete. 33–35 operations on the two versions with live
captures now carry inline canonical examples and/or sample-path
extensions. The 20-entry `overlays/nullability.yaml` is a side-benefit:
real schema corrections discovered by example validation, not a sample
workaround. Validators stay green; the spec size growth is bounded.
