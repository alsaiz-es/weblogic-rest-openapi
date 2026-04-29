# Changelog

## 0.4.1 — 2026-04-29

Bug-fix release. Discovered empirically while integrating v0.4.0 into
a deployment-lifecycle consumer.

### Fixed

- **`array: true` on action parameters was being dropped.** The
  generator's `operations.py:_action_op` was building the request
  body schema from `_java_to_oas(p["type"])` only, ignoring the
  `array: true` flag declared in `extension.yaml`. Result: action
  parameters like `AppDeploymentRuntime.start.targets` (and the
  matching `stop`, `redeploy`, `update` shapes) emitted as
  `targets: type: string` instead of `targets: type: array, items:
  type: string`. WebLogic 14.1.2 returns HTTP 400 (`valid signatures
  are: stop(targets: [string], deploymentOptions: {key: string})`)
  when sent a scalar — the spec contradicted the live runtime.
- **Affected MBeans (6):** `AppDeploymentRuntime`,
  `LibDeploymentRuntime`, `DeploymentManager`,
  `DeploymentProgressObject`, `DomainMBean`, `DomainRuntimeMBean`.
  Affected actions cover deployment lifecycle (`start`, `stop`,
  `redeploy`, `update`) and a handful of multi-target operations.
  All 5 generated specs regenerated.

### Added

- **Phase 4g level-1 regression suite.** Every action parameter
  declared in `<wrc>/resources/.../extension.yaml` is cross-checked
  against the generated spec's request body schema. The new test
  `tools/openapi-generator/tests/test_action_param_shapes.py` runs
  parametrised across all 5 generated specs (245 cases pass on this
  release; the rest skip because the action's parent MBean isn't
  reachable on every version). Catches `array`-flag drift, the class
  of bug that motivated this release.

  Run with: `cd tools/openapi-generator && uv run pytest tests/`.

### Notes for consumers

- If your client carries a workaround that wraps `targets` in an
  array on the consumer side (e.g. a TypeScript cast like
  `targets: targetList as unknown as string`), it can be removed
  once the v0.4.1 spec is consumed.

## 0.4.0 — 2026-04-29

**The spec is now generated.** This release replaces the v0.3.x
hand-written specs with output from a mechanical pipeline that
consumes Oracle's open-source [`weblogic-remote-console`](https://github.com/oracle/weblogic-remote-console)
harvested MBean YAMLs and refines them with a small set of editorial
overlays that capture knowledge no harvested catalog can produce on
its own.

### Headline numbers

- **5 WebLogic versions covered** (12.2.1.3, 12.2.1.4, 14.1.1, 14.1.2, 15.1.1) — up from 2 in v0.3.x.
- **~600–660 schemas per version**, up from ~25 in v0.3.x. The harvested
  catalog declares ~830 MBeans per version; the generator emits the
  reachable subset and a transitive-closure prune drops what nothing
  references.
- **~1 100–2 400 paths per version**, up from ~50 in v0.3.x. The
  12.2.1.x ↔ 14.1.x path-count delta reflects Multi-Tenant deprecation
  in 14.1.x — real WebLogic behaviour, not a generator artifact.
- **Validators green on every version**: `openapi-spec-validator`
  strict PASS, `@stoplight/spectral-cli` 0 errors / 0 warnings,
  `openapi-generator-cli` Python smoke PASS (~850 generated model
  classes consumable end-to-end).

### Pipeline shape

The generator (`tools/openapi-generator/`) is data-driven:

1. **Harvested loader** parses the Remote Console YAMLs and walks
   `baseTypes` chains to merge inherited properties.
2. **Schema builder** maps each MBean to an OpenAPI 3.0 component
   schema, lifts UI-overlay enums (`legalValues`), normalises names,
   and wraps in `allOf [EnvelopeBase]`.
3. **Path builder** recursively walks the containment graph rooted at
   `DomainRuntimeMBean` / `DomainMBean`, emitting collection + item
   paths with cycle detection.
4. **Operations injector** reads `extension.yaml` per MBean and adds
   declarative actions (`start`, `shutdown`, `suspend`, …) as POST
   endpoints with correct request/response schemas.
5. **Polymorphism module** detects discriminator hierarchies from UI
   overlays and emits OAS 3.0 `oneOf + discriminator + mapping`.
6. **Enum extractor** lifts inline enums that recur in ≥2 places to
   shared schemas.
7. **Editorial overlay layer** (5 modules: quirks, descriptions,
   manual-schemas, nullability, samples).
8. **Transitive-closure prune** drops any schema unreferenced from
   the path tree or other components.

### Five overlay layers (the manual edge)

| Layer | Count (14.1.2) | Lives at | Purpose |
|---|---:|---|---|
| Quirks | 14 | `overlays/quirks/` | Documented anomalies (CSRF gates, casing inconsistencies, JDBC partial-create, `OS` prefix, …). Stable id + external doc reference. |
| Description overlays | 50 | `overlays/descriptions/` | Operational notes appended to harvested descriptions: 21 from the original curated set + 29 from a per-subsystem editorial pass (Deployments, JMS detail, Work Managers, JTA, WLDF). |
| Live samples | 33 ops linked | `samples/<version>/` ↔ `sample_loader.py` | Real JSON responses from running WebLogic captures. Canonical sample → native `examples`; overflow → `x-weblogic-sample-paths` extension. |
| Empirical nullability | 20 | `overlays/nullability.yaml` | `nullable: true` corrections discovered while validating samples — fields the harvested set declared as non-null but the live REST projection returns as `null`. |
| Manual subtype bodies | 12 | `overlays/manual-schemas/` | Polymorphic subtype bodies the Remote Console UI overlay declares but Oracle has no harvested YAML for (`OAMAuthenticator`, `JMSQueueRuntime`, `JMSTopicRuntime`, `JDBCProxyDataSourceRuntime`, …). Authored from Oracle Javadoc + public docs + samples; flagged with `x-weblogic-manual-schema: true` and `x-weblogic-source` for provenance. |

### Repository changes

- **Removed**: `specs/{common,domain-runtime,edit,lifecycle,server-runtime}/`
  — the v0.3.x hand-written tree. v0.3.1 stays accessible via the
  `v0.3.1` git tag for anyone needing the historical layout.
- **Added**: `specs/generated/<version>.yaml` — one OpenAPI 3.0 spec per
  WLS version.
- **Added**: `tools/openapi-generator/` — the Python+uv generator with
  its own README and pipeline documentation.
- **Added**: `overlays/{quirks,descriptions,manual-schemas,nullability.yaml}`
  + `samples/{12.2.1.4,14.1.2}/` — the editorial layer.
- **Added**: `tools/openapi-generator/out/VERSION_DELTAS.md` — adjacent-pair
  cross-version diffs.
- **Added**: per-phase reports under `tools/openapi-generator/out/`
  (PHASE4B through PHASE4E3) — auditable record of the transformation.

### What this means for v0.3.x consumers

The endpoint paths are unchanged — they're WebLogic's, not ours. Only
the *spec file layout* changed. Most consumers replace one path:

```diff
- specs/domain-runtime/servers.yaml
+ specs/generated/14.1.2.0.0.yaml      # contains every endpoint
```

The generated spec is much larger (~1 180 paths vs ~50 in v0.3.x) but
covers the same endpoints v0.3.x did, plus the ~95% of the WebLogic
REST surface v0.3.x didn't.

If you specifically need the v0.3.x layout (typed subdirectory by bean
tree), `git checkout v0.3.1` is the right answer.

### Honesty notes

- **Manual subtype bodies are below harvested quality by design.** The
  12 manually-authored polymorphic subtypes carry
  `x-weblogic-manual-schema: true` and `x-weblogic-source: [...]` so
  consumers can filter them out if they only want harvested-derived
  data.
- **Some MBeans are still stubs on some versions.** When a subtype is
  harvested on 12.2.1.x but stubbed on 14.1.2 (`IPlanetAuthenticator`,
  `NovellAuthenticator`, `OracleVirtualDirectoryAuthenticator`,
  `JDBCProxyDataSourceRuntime`), the manual overlay fills the stub
  while never overwriting harvested. The stat is reported per version
  in the PHASE4E3 report.
- **The empirical layer is built from samples, not speculation.** The
  20 nullability fixes are real schema corrections — every one was
  discovered because a captured sample failed `oas3-valid-media-example`
  against the harvested type.

### Acknowledgements

The harvested MBean YAMLs that drive the generator are produced by
Oracle's open-source [`weblogic-remote-console`](https://github.com/oracle/weblogic-remote-console)
project under the Universal Permissive License (UPL) 1.0. Without
that catalog this transformation would not have been possible. The
generator code, manual overlays, and reports are Apache 2.0 licensed.

## 0.3.0 — 2026-04-27

Phase 2 — domain administration. Adds the entire edit-tree CRUD
surface (change manager, server, cluster, JDBC system resource) plus
server-lifecycle actions, verified end-to-end against both lab
versions on real WebLogic instances. Both lab domains were returned
to their pre-test state; cleanup verification confirms zero
`OpenAPISpec*` resources remain.

### New specs

- `specs/edit/change-manager.yaml` — six change-session endpoints
  (`GET`, `startEdit`, `activate`, `cancelEdit`, `safeResolve`,
  `forceResolve`). Documents the
  `EditErrorResponse` shape (the `wls:errorsDetails` array) used
  by edit-tree validation failures.
- `specs/edit/servers.yaml` — server CRUD. 136-field
  `Server` schema with `additionalProperties: true`; documents the
  5+5 cross-version delta (14.1.2-only:
  `virtualThreadEnableOption`, `selfTuningThreadPoolSizeMax/Min`,
  `synchronizedSessionTimeoutEnabled`,
  `logCriticalRemoteExceptionsEnabled`; 12.2.1.4-only:
  `buzz{Address,Port,Enabled}`, `administrationProtocol`,
  `isolatePartitionThreadLocals`).
- `specs/edit/clusters.yaml` — cluster CRUD. 73/69 field counts
  with 4 14.1.2-additive fields documented
  (`replicationTimeoutMillis`, `rebalanceDelayPeriods`,
  `autoMigrationTableCreationDDLFile`,
  `autoMigrationTableCreationPolicy`).
- `specs/edit/datasources.yaml` — JDBC system resource CRUD.
  Documents the **staged creation workflow** required because the
  single-shot full-tree POST does not propagate nested fields and
  always returns 400 with a partial parent shell registered.
  Sub-resource schemas: `JDBCSystemResource` (15 fields),
  `JDBCResource` (5), `JDBCDataSourceParams` (11),
  `JDBCDriverParams` (6), `JDBCConnectionPoolParams` (37 on
  14.1.2; 36 on 12.2.1.4 — `invokeBeginEndRequest` is
  14.1.2-only).
- `specs/lifecycle/lifecycle.yaml` — eight lifecycle actions
  (`suspend`, `forceSuspend`, `resume`, `shutdown`,
  `forceShutdown`, `start`, `startInAdmin`, `startInStandby`)
  plus the `tasks` collection. Models the `LifecycleTaskResponse`
  shape returned by every action.

### New documentation

- `docs/EDIT_TREE_WORKFLOW.md` — sequence diagram (mermaid) of
  the change-session lifecycle, header requirements, error
  envelope shape, recovery hints.

### Discoveries

- **Edit-side errors use a different envelope.** The
  `wls:errorsDetails` array is the new shape; standard
  `ErrorResponse` does not apply. Cross-version: 12.2.1.4 keeps
  the fully-qualified Java exception class name in each `detail`
  (e.g. `weblogic.management.provider.EditNotEditorException: ...`),
  14.1.2 strips the FQCN and keeps the message only. Same
  pattern applies to JDBC validation errors.
- **`startEdit` is idempotent** when called by the same user who
  already holds the lock. Useful for clients that recover from
  intermittent failures by re-acquiring rather than tracking
  state externally.
- **`POST /edit/JDBCSystemResources {"name": "..."}` always
  returns 400** on both versions ("JDBCDataSource: Name cannot be
  null") because WLS auto-creates an empty `JDBCResource` child
  with `name=null` whose own validation fails. **The parent shell
  is registered anyway**; the staged workflow continues from
  there. This is documented as a partial-create quirk in
  `datasources.yaml`.
- **Lifecycle ops are async-task-shaped, not void.** Every action
  returns a `ServerLifeCycleTaskRuntime` with `taskStatus`,
  `progress`, `taskError`, and a `links.rel=job` URL even when
  the operation finished synchronously in milliseconds. Suspend
  internally maps to `suspendWithTimeout` regardless of whether
  a timeout was supplied.
- **NodeManager dependency made explicit.** `start*` actions and
  graceful `shutdown` go through NodeManager; `suspend`/`resume`
  do not. Lab observation: NodeManager unreachable returns a
  task whose `taskError` carries the wrapped exception, not an
  HTTP error.

### Cross-version field-set deltas summary

| Resource | 14.1.2 | 12.2.1.4 | Notes |
|---|---|---|---|
| `Server` | 136 | 136 | 5/5 different fields each side; full list in spec |
| `Cluster` | 73 | 69 | 14.1.2 strict superset (4 added) |
| `JDBCSystemResource` shell | 15 | 15 | identical |
| `JDBCResource` | 5 | 5 | identical |
| `JDBCDataSourceParams` | 11 | 11 | identical |
| `JDBCDriverParams` | 6 | 6 | identical |
| `JDBCConnectionPoolParams` | 37 | 36 | 14.1.2 adds `invokeBeginEndRequest` |
| `ServerLifeCycleRuntime` | 6 | 6 | identical |
| `LifecycleTaskResponse` | 18 | 18 | identical |

### Samples added

`samples/12.2.1.4/edit-tree/` and `samples/14.1.2/edit-tree/` —
change manager idle/active/cancel/safe+forceResolve-error,
server bean (full + minimal), cluster bean, JDBC sub-resource
defaults, JDBC populated tree, JDBC create errors verbatim
(both shell-only and full-tree variants).

`samples/12.2.1.4/lifecycle/` and `samples/14.1.2/lifecycle/` —
serverLifeCycleRuntime bean (with and without HATEOAS links),
suspend/resume/suspend-with-args responses, tasks collection.

### Cleanup verification

After the full test suite, both VMs were verified to contain:
- No edit session held (`locked: false`).
- No server, cluster, or JDBC resource named `OpenAPISpec*` or
  `Test*`.
- All managed servers back in `RUNNING` state.

The probes at `samples/{version}/edit-tree/changeManager_*` and
the cleanup confirmation at `serverRuntimes` collection all show
the pre-v0.3.0 state.

## 0.2.1 — 2026-04-27

Closes the `componentRuntimes` child of `applicationRuntimes` —
per-application module drill-down for web, EJB, application client,
and JCA connector modules. New endpoints:

- `GET /domainRuntime/serverRuntimes/{serverName}/applicationRuntimes/{applicationName}/componentRuntimes`
- `GET /domainRuntime/serverRuntimes/{serverName}/applicationRuntimes/{applicationName}/componentRuntimes/{componentName}`

### New spec

- `specs/domain-runtime/components.yaml` — polymorphic
  `ComponentRuntime` schema with a `type` discriminator and four
  concrete subtypes built from real captures:

  | `type` | Fields | Verified |
  |---|---|---|
  | `WebAppComponentRuntime` | 35 | 12.2.1.4 + 14.1.2, identical |
  | `EJBComponentRuntime` | 5 (collection-default; rich data via `EJBRuntimes` child rel) | 12.2.1.4 |
  | `AppClientComponentRuntime` | 5 (same shape as EJB) | 12.2.1.4 |
  | `ConnectorComponentRuntime` | 28 | 12.2.1.4 + 14.1.2, identical |

  `JDBCDataSourceRuntime` instances also surface in this collection
  on EAR-bundled datasources (FMW domain quirk); the spec does not
  redefine that schema and points to `jdbc.yaml`. Per-EJB and
  per-destination drill-down (children of EJB and Connector
  components) are deferred to v0.3.x.

### Cross-version notes

- `WebAppComponentRuntime` 35-field set: identical between
  12.2.1.4 (`wsm-pm` web modules on the FMW domain) and 14.1.2
  (`wls-management-services` web module on the vanilla domain).
- `ConnectorComponentRuntime` 28-field set: identical between both
  versions, captured on the same shipped adapter
  (`jms-internal-xa-adp`).
- EJB and AppClient component types only observed on 12.2.1.4
  (no EJB or app-client deployments in the 14.1.2 lab domain). The
  5-field shape is too minimal to vary cross-version; the
  detail-bearing subtree (`EJBRuntimes`) is what would actually
  matter for cross-version verification, and it is roadmap.

### Samples added

`samples/12.2.1.4/`:
`componentRuntimes_collection_wsm-pm.json` (mixed EJB + 5 web
modules),
`componentRuntimes_collection_service-bus-routing.json` (AppClient
+ web),
`componentRuntime_individual_wsm-pm_webapp.json` (full WebApp
field set),
`componentRuntime_individual_wsm-pm_ejb.json`,
`componentRuntime_individual_service-bus-routing_appclient.json`,
`componentRuntime_individual_jmsadp_connector.json` (full
Connector field set on the shipped JMS XA adapter).

`samples/14.1.2/`:
`componentRuntimes_collection_wls-management-services.json`,
`componentRuntime_individual_wls-management-services_webapp.json`
(cross-version baseline for WebApp),
`componentRuntimes_collection_jms-internal-xa-adp.json`,
`componentRuntime_individual_jmsadp_connector.json`
(cross-version baseline for Connector).

### Documentation

- `README.md` Coverage Status — `componentRuntimes` row added,
  marked verified on both versions.

## 0.2.0 — 2026-04-27

Domain-runtime monitoring coverage extended. Four new spec files and a
substantial set of cross-checked discoveries that overturn two findings
recorded in v0.1.1.

### New specs

- `specs/domain-runtime/applications.yaml` —
  `applicationRuntimes` collection and per-application detail. 9
  verified properties; `internal` boolean is the practical filter for
  user-deployed applications since the framework ships ~5 internal
  apps that always appear in the collection.
- `specs/domain-runtime/channels.yaml` —
  `serverChannelRuntimes` collection and per-channel detail. 12
  verified properties; documents the hidden truth that the REST view
  exposes only `publicURL` (parsed `<protocol>://<host>:<port>`) and
  none of the `listenAddress`/`listenPort`/`protocol` properties from
  the underlying MBean.
- `specs/domain-runtime/search.yaml` —
  `POST /domainRuntime/search` with the recursive `BulkSearchRequest`
  schema. The CSRF gotcha and the failure-mode table are first-class
  parts of the spec.
- `specs/domain-runtime/jms.yaml` —
  `JMSRuntime` container (9 verified properties) and `JMSServers`
  collection envelope. Per-`JMSServer` detail schema is intentionally
  deferred to v0.3.0 because no domain in this verification cycle had
  any JMS resources targeted at a server.

### Corrections from v0.1.x

The HTTP 400 documented in v0.1.x as "an OSB-specific serialization bug
on 12.2.1.4, silently fixed in 14.1.2" is incorrect on all three counts:

- It is NOT OSB-specific (reproducible in OSB-free 14.1.2 domains).
- It is NOT 12.2.1.4-specific (reproducible identically in 14.1.2).
- It was NOT silently fixed in 14.1.2 (still present).

The actual cause is a request-side gate: the endpoint
`GET /domainRuntime/serverRuntimes` returns HTTP 400 unless the request
includes the `X-Requested-By` header. The same header value normally
reserved for CSRF protection on mutating requests.

This is unusual for two reasons:

1. Oracle's own documentation states that `X-Requested-By` is only
   required for POST/PUT/DELETE operations, not GETs.
2. The check is selective: of the eight collections directly under
   `/domainRuntime` that we tested (serverRuntimes, migrationDataRuntimes,
   nodeManagerRuntimes, serviceMigrationDataRuntimes, serverLifeCycleRuntimes,
   systemComponentLifeCycleRuntimes, plus the root and JNDI singleton),
   only `serverRuntimes` enforces the header. The rest accept anonymous
   GETs.

The check is also conditional on domain state: with **only** the
AdminServer running and no managed servers, all six request shapes —
including the no-header case — return 200. The 400 only manifests once
at least one managed server reaches RUNNING. Captured admin-only and
managed-up matrices on both versions are saved verbatim in
`samples/{version}/csrf-test/`.

Behavior verified identically in WLS 12.2.1.4 (FMW/OSB domain) and
14.1.2 (vanilla domain). The matrix of test variations is preserved
in `samples/{version}/csrf-test/`.

We have not found this documented anywhere in Oracle's official
references. If a reader knows of an Oracle source documenting this
selective enforcement, an issue or PR pointing to it is welcome.

A second v0.1.x claim is also retracted: `ServerChannelRuntime` was
implied to expose `listenAddress` and `listenPort`, but the REST
projection of the underlying MBean omits them. Asking explicitly via
`?fields=listenAddress,listenPort,protocol,publicAddress,publicPort,channelName`
returns only `channelName`. The only network endpoint information
exposed over REST is `publicURL` (concatenated
`<protocol>://<host>:<port>`); clients must parse it themselves if
the components are needed. Verified on both 12.2.1.4 and 14.1.2.

### Discoveries (the real value of v0.2.0)

- **`POST /domainRuntime/search` works after all.** v0.1.1 declared
  the search endpoint broken across every body shape on both
  versions. Re-verification on 14.1.2 found the cause: the
  `X-Requested-By` header is **mandatory**. Without it, WebLogic's
  CSRF guard returns a plain-text `400 Bad Request` (no JSON, no
  diagnostic) before the body parser ever runs. With any non-empty
  value supplied, the DSL behaves exactly as Oracle's docs describe:
  `fields` filters properties (unknown names silently ignored),
  `links` controls HATEOAS expansion (`[]` to suppress, must be an
  array — string `"none"` returns 400 with proper JSON error),
  `children` is recursive to arbitrary depth, and `name` filters
  collection members.
- **`GET /domainRuntime/serverRuntimes` 400 is request-side and
  conditional.** Adding any non-empty `X-Requested-By` header turns
  the 400 into 200 — but only when at least one managed server is
  RUNNING. With only the AdminServer up, the collection returns 200
  even without any header. See the formal retraction above for the
  full probe matrix and operational implications.
- **`ServerChannelRuntime` REST serialization is much narrower than
  the MBean reference.** Oracle's `ServerChannelRuntimeMBean` exposes
  `listenAddress`, `listenPort`, `protocol`, `publicAddress`,
  `publicPort`. The REST projection returns **none** of those, even
  when explicitly requested via `?fields=`. Only `publicURL` carries
  the network endpoint information, concatenated as
  `<protocol>://<host>:<port>`.
- **`applicationRuntimes` mixes user and framework apps.** A plain
  `base_domain` returns 6 internal applications on `AdminServer`
  (`bea_wls_internal`, `wls-management-services`, `mejb`,
  `jms-internal-xa-adp`, `jms-internal-notran-adp`) plus `jamagent`
  on the AdminServer specifically. The `internal: true|false` field
  is the only practical way to separate user deployments
  client-side; there is no server-side filter.

### Documentation

- `README.md` Coverage Status — applicationRuntimes,
  serverChannelRuntimes, and bulk search marked verified on 14.1.2;
  JMSRuntime marked container-only.
- `README.md` "Known API Quirks" — quirks 6/7/8 added (CSRF on POST
  and on the `serverRuntimes` collection GET; channel-runtime
  hidden properties).
- `README.md` "Version-specific differences" — corrected the
  OSB-only and search-broken claims from v0.1.1; both reduce to the
  same CSRF root cause.

### Cross-version validation status

- 14.1.2: full set captured against `base_domain` with `AdminServer`
  and `server1` (cluster1) RUNNING.
- 12.2.1.4: full set captured against the `dev` OSB domain
  (`AdminServer` + `osb_server1` RUNNING). 76 deployed applications,
  3 JMS servers (`AgentTestJMSServer`, `wlsbJMSServer_auto_2`,
  `UMSJMSServer_auto_2`) — exactly the kind of OSB-rich state the
  v0.1.x captures lacked.

### Cross-version field-set deltas

- `ApplicationRuntime` — 12.2.1.4 includes a `partitionName: null`
  property; 14.1.2 omits it (Multi-Tenant artifact removed in
  14.1.2). All other fields identical.
- `serverChannelRuntimes` — 12-field set identical between versions.
- `JMSRuntime` container — 9-field set identical between versions.
- `JMSServerRuntime` per-server detail — 37-field set **identical**
  across three independent captures: an OSB-deployed populated JMS
  server on 12.2.1.4 (`wlsbJMSServer_auto_2`, 9 destinations,
  402 messages received), a freshly-created `myJMSServer` on the
  14.1.2 lab domain, and the same `myJMSServer` re-created on
  12.2.1.4 next to the OSB servers. All resources created for
  schema verification were destroyed after capture; both lab
  domains are returned to their pre-v0.2.0 state.
- Search DSL behavior — identical CSRF requirement and identical
  acceptance/rejection of body shapes on both versions.
- `GET /serverRuntimes` collection 400 — reproduced on both 12.2.1.4
  (`osb_server1` RUNNING) and 14.1.2 (vanilla `server1` in
  `cluster1` RUNNING). The bug is not OSB-specific and not 12.2.1.4-
  specific, contrary to v0.1.1's note.

### Samples added under `samples/12.2.1.4/`

`serverChannelRuntimes_collection_osb_server1.json`,
`serverChannelRuntime_individual_osb_server1_t3.json`,
`applicationRuntimes_collection_osb_server1.json`,
`applicationRuntime_individual_osb_server1_DbAdapter.json`,
`jmsRuntime_osb_server1.json`,
`jmsServers_collection_osb_server1.json`,
`jmsServer_individual_osb_server1_wlsbJMSServer_auto_2.json`,
`jmsServer_individual_osb_server1_myJMSServer.json`,
`jmsRuntime_osb_server1_after_myJMSServer.json` (the last two
captured by creating `myFileStore` + `myJMSServer` next to the
existing OSB JMS servers via WLST, and destroyed after capture),
`search_servers_basic.json`, `search_servers_threadpool.json`,
`serverRuntimes_collection_with_managed_400.json`,
`serverRuntimes_collection_with_csrf_header.json` (workaround
proving the same request returns 200 once the header is set),
`search_post_tests_v0.2.0.log`,
`csrf-test/` (controlled probe matrix per
"Corrections from v0.1.x" — six numbered tests in admin+managed
state, six numbered tests in admin-only state, and three
`managed-direct/` probes confirming `/domainRuntime` is not served
from managed-server ports at all).

### Samples added under `samples/14.1.2/`

`serverChannelRuntimes_collection_AdminServer.json`,
`serverChannelRuntime_individual_AdminServer_t3.json`,
`serverChannelRuntimes_collection_server1.json`,
`applicationRuntimes_collection_AdminServer.json`,
`applicationRuntime_individual_AdminServer_jamagent.json`,
`applicationRuntime_individual_AdminServer_bea_wls_internal.json`,
`applicationRuntimes_collection_server1.json`,
`jmsRuntime_AdminServer.json`,
`jmsServers_collection_AdminServer.json`,
`jmsRuntime_server1.json`,
`jmsServers_collection_server1.json`,
`search_empty.json`, `search_servers_basic.json`,
`search_servers_threadpool.json`, `search_servers_filtered.json`,
`search_workaround_for_400_collection.json`,
`serverRuntimes_collection_with_server1_400.json`,
`search_post_tests_v0.2.0.log` (full progressive probe transcript),
`csrf-test/` (controlled probe matrix mirroring the 12.2.1.4 set:
admin+managed, admin-only, managed-direct, plus
`additional_axes.txt` documenting which sibling collections enforce
the header and which do not),
`jmsRuntime_server1_with_jmsserver.json`,
`jmsServers_collection_server1_with_jmsserver.json`,
`jmsServer_individual_server1_myJMSServer.json` (the last three
captured by creating `myFileStore` + `myJMSServer` via WLST,
recording the per-server detail, then destroying both — the domain
is left in its original state).

## 0.1.1 — 2026-04-15

Cross-verified the v0.1.0 specs against WebLogic Server 14.1.2.0.0
(AdminServer on Oracle JDK 21.0.9, plain `base_domain`). Property sets
for `ServerRuntime`, `JDBCServiceRuntime`, and `ThreadPoolRuntime` match
12.2.1.4 exactly; `JVMRuntime` gains one new field.

### Spec changes
- `jvm.yaml`: add `javaVendorVersion` (string, nullable; present only in 14.1.2+).
- `jvm.yaml`: description updated to reflect verification on both versions.

### Documentation
- `README.md` Coverage Status — domainRuntime monitoring marked verified on both versions.
- `README.md` new section "Version-specific differences: 12.2.1.4 vs 14.1.2".
- `samples/14.1.2/` — full baseline capture + README with bean diff.

### Discoveries
- JDBC datasource bean shape (47 fields) is byte-for-byte compatible
  between 12.2.1.4 and 14.1.2; verified by creating a temporary Derby
  `TestDS` on the 14.1.2 install via WLST and diffing against the
  `wlsbjmsrpDataSource` capture from 12.2.1.4. The `state` Title-Case
  casing quirk (`Running` vs `RUNNING`) survives unchanged.
- Multi-Tenant (`domainPartitionRuntimes`, `resourceGroupLifeCycleRuntimes`,
  `partitionRuntimes`) fully removed from the REST surface in 14.1.2.
- `consoleRuntime` rel renamed to `consoleBackend`; new rels `JNDI`,
  `getServerHttpURL`, and `action: runGC` on JVMRuntime.
- `GET /serverRuntimes` 400 observed on 12.2.1.4 with an OSB-heavy managed
  server is not reproducible on 14.1.2 — OSB-specific serialization bug.
- `POST /domainRuntime/search` returns 400 on every body shape attempted
  against both versions; query DSL effectively undocumented.

## 0.1.0 — 2026-04-15

Initial release. Domain runtime monitoring endpoints verified against
WebLogic Server 12.2.1.4 (OSB domain).

### Specs
- `common/schemas.yaml` — shared schemas (HealthState, Identity, Link, ErrorResponse)
- `domain-runtime/servers.yaml` — ServerRuntimeMBean (server state, health, activation)
- `domain-runtime/jdbc.yaml` — JDBCServiceRuntime + JDBCDataSourceRuntimeMBeans (46 fields)
- `domain-runtime/threading.yaml` — ThreadPoolRuntime (18 fields)
- `domain-runtime/jvm.yaml` — JVMRuntime (15 fields)

### Discoveries
- `state` uses UPPERCASE for servers, Title Case for JDBC datasources
- `healthState.state` uses lowercase (`ok`, `warning`, not `HEALTH_OK`)
- JVMRuntime uses `OSName`/`OSVersion` (uppercase prefix)
- `threadStackDump` in JVMRuntime can be ~100 KB — must be excluded in monitoring polls
- `serverRuntime` (direct) and `domainRuntime/serverRuntimes/{name}` (via AdminServer) return identical property sets
