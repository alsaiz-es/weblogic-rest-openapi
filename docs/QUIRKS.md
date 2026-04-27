# WebLogic REST Management API — Consolidated Quirks

This document collects every behaviour we observed during v0.1.x →
v0.3.0 verification that is either undocumented in Oracle's REST
reference, contradicts what the official documentation says, or is
counter-intuitive given how the rest of the API is named. Each entry
records the version where the behaviour was observed, what one would
expect from docs or naming, what actually happens, the operational
implication for clients, and a link to the spec that models it.

The verification rig was a pair of lab VMs running WebLogic 14.1.2
(vanilla `base_domain`) and 12.2.1.4 (FMW/OSB `dev` domain), driven
by curl with full request/response capture. Sample artefacts live
under `samples/{version}/...`.

---

## 1. Casing inconsistencies across runtimes

Same conceptual values use **different cases** in different parts of
the API.

- **Observed on:** 12.2.1.4 and 14.1.2 (identical behaviour).
- **Expected (per Oracle naming convention):** consistent casing for
  the same enum across runtimes.
- **Actual:**
  - `ServerRuntime.state` → UPPERCASE (`RUNNING`, `ADMIN`,
    `SHUTDOWN`, `FORCE_SUSPENDING`, …).
  - `JDBCDataSourceRuntime.state` → Title Case (`Running`,
    `Suspended`).
  - `healthState.state` → lowercase tokens (`ok`, `warning`,
    `critical`, `failed`, `overloaded`). Note: Oracle's
    `weblogic.health.HealthState` Java API documents the
    UPPERCASE constants `HEALTH_OK`, `HEALTH_WARN`, …; the JSON
    serialisation downcases them.
  - `JVMRuntime.OSName` and `JVMRuntime.OSVersion` use an
    **uppercase `OS` prefix**; everywhere else in the API the
    convention would be `osName` / `osVersion`.
  - `JMSServerRuntime.insertionPausedState` returns hyphenated
    descriptive strings (`Insertion-Enabled`, `Insertion-Paused`)
    — neither all-caps nor lowercase.
- **Implication:** clients **must** model these as separate enums
  per resource. Generating a single `ServerState` enum and reusing
  it on JDBC runtimes will deserialise wrong.
- **Modelled in:** `specs/domain-runtime/servers.yaml` (UPPERCASE
  enum), `specs/domain-runtime/jdbc.yaml` (Title Case enum),
  `specs/common/schemas.yaml#HealthState` (lowercase enum),
  `specs/domain-runtime/jvm.yaml` (uppercase-prefixed `OSName`,
  `OSVersion`), `specs/domain-runtime/jms.yaml#JMSPausedState`.

---

## 2. Selective `X-Requested-By` enforcement on `GET /domainRuntime/serverRuntimes`

A single `GET` endpoint refuses to serve unless an `X-Requested-By`
header is present, and only when the domain has at least one managed
server in `RUNNING` state.

- **Observed on:** 12.2.1.4 and 14.1.2 (identical).
- **Expected (per Oracle docs):** `X-Requested-By` is documented as
  required only on mutating methods (POST/PUT/DELETE). GETs should
  be unaffected.
- **Actual:** `GET /domainRuntime/serverRuntimes` (the collection,
  not individual servers) returns `HTTP 400 Bad Request` (JSON
  envelope, no useful detail) without `X-Requested-By`. Adding any
  non-empty value (`X-Requested-By: probe`, `X-Requested-By: 1`,
  …) returns 200 with the full collection. The header name is
  case-insensitive (HTTP standard) but other headers
  (`Requested-By`, `X-CSRF-Token`, `X-XSRF-TOKEN`, etc.) do not
  satisfy the gate.

  The check is **conditional on domain state**: with only the
  AdminServer running and no managed servers up, the same
  anonymous GET succeeds. The 400 only manifests once a managed
  server reaches `RUNNING`.

  The check is **selective**: of the eight `/domainRuntime/*`
  endpoints we probed (`serverRuntimes`, `migrationDataRuntimes`,
  `nodeManagerRuntimes`, `serviceMigrationDataRuntimes`,
  `serverLifeCycleRuntimes`,
  `systemComponentLifeCycleRuntimes`, plus the `/domainRuntime`
  root and the `JNDI` singleton), **only** `serverRuntimes`
  enforces the header.

  **Note on history:** v0.1.1 of this repo originally documented
  this 400 as an "OSB-specific 12.2.1.4 serialization bug". v0.2.0
  retracted that diagnosis after the matrix in
  `samples/{version}/csrf-test/` showed the symptom on a vanilla
  14.1.2 domain too and pinpointed the header as the gate. Full
  retraction text is in `CHANGELOG.md` v0.2.0 "Corrections from
  v0.1.x".
- **Implication:** any monitoring or LLM-tool client polling the
  domain inventory must add `X-Requested-By` defensively.
  Workarounds when the header cannot be set: fetch each server by
  name, or use `POST /domainRuntime/search` with a `serverRuntimes`
  child.
- **Modelled in:** `specs/domain-runtime/servers.yaml` (description
  of the collection endpoint plus `Server` schema description).
  Verbatim probe matrix in `samples/{version}/csrf-test/`.

---

## 3. `POST /domainRuntime/search` requires `X-Requested-By` (and that single fact made v0.1.1 misdiagnose the endpoint as broken)

Search is a *read* operation in semantic terms — it does not mutate
state, and Oracle's docs treat the search endpoints as queries.
However, because it is delivered over HTTP `POST`, it inherits the
generic CSRF guard.

- **Observed on:** 12.2.1.4 and 14.1.2 (identical).
- **Expected (per Oracle docs):** `X-Requested-By` is required for
  state-changing requests (POST/PUT/DELETE per RFC 9110 sense).
  The bulk-search DSL is documented as the way to harvest many
  runtime values in one call — i.e. logically a read. Many client
  libraries reasonably skip CSRF headers for read operations.
- **Actual:** without `X-Requested-By`, the endpoint returns
  `HTTP 400 Bad Request` with a `text/html` body literally reading
  `Bad Request` (no JSON, no diagnostic). With any non-empty
  `X-Requested-By` value the documented DSL works as Oracle
  describes: `fields` filters properties (unknown names silently
  ignored), `links` controls HATEOAS (`[]` to suppress; **must be
  an array** — string `"none"` is rejected with proper JSON
  error), `children` is recursive to arbitrary depth, `name`
  filters collection members.
- **Implication:** v0.1.1 captured every body shape against both
  versions and concluded the endpoint was unusable. That was wrong
  — the missing header was the issue, not the DSL. The endpoint is
  fully functional when called correctly. Any client wrapping a
  lightweight "read-only" REST client around WebLogic should still
  send the header on POST search calls.
- **Modelled in:** `specs/domain-runtime/search.yaml` (treats the
  header as a first-class required parameter; documents the
  text/html-vs-JSON 400 bodies as separate diagnostic states).

---

## 4. Edit-tree validation errors use a different envelope

Errors thrown by edit-session validation use a richer JSON shape
than the standard `ErrorResponse` documented in
`common/schemas.yaml`.

- **Observed on:** 12.2.1.4 and 14.1.2.
- **Expected (per Oracle docs and the rest of the API):** the
  `ErrorResponse` envelope (`status`, `type`, `title`, `detail`)
  used by 401/404/500 across the read-side trees.
- **Actual:** edit-side validation returns:
  ```json
  {
    "status": 400,
    "type": "...",
    "title": "ERRORS",
    "wls:errorsDetails": [
      { "type": "...", "title": "FAILURE", "detail": "..." },
      { "type": "...", "title": "FAILURE", "detail": "..." }
    ]
  }
  ```
  The colon in the property name is real — it is a namespaced
  field, valid JSON but unfortunate for clients that auto-generate
  Java/TypeScript/Go types (most generators replace `:` with `_`
  silently).

  Cross-version difference: 12.2.1.4 keeps the fully-qualified Java
  exception class name in each `detail` (e.g.
  `weblogic.management.provider.EditNotEditorException: Not edit
  lock owner`). 14.1.2 strips the FQCN and keeps only the
  message. Same pattern visible in JDBC validation errors.
- **Implication:** clients consuming `/edit/` errors must branch
  on the presence of `wls:errorsDetails`. String comparison on
  `detail` text breaks across versions; either match the trailing
  fragment or normalise.
- **Modelled in:** `specs/edit/change-manager.yaml#EditErrorResponse`,
  referenced from `specs/edit/servers.yaml`,
  `specs/edit/clusters.yaml`, `specs/edit/datasources.yaml`.

---

## 5. `startEdit` is idempotent

Calling `POST /edit/changeManager/startEdit` while you already hold
the lock is **not** an error — it returns `200 {}` and leaves the
session in the same state.

- **Observed on:** 12.2.1.4 and 14.1.2.
- **Expected (per intuitive REST semantics for a "lock acquire"):**
  a 409 Conflict or 423 Locked, or at least a 400 with a
  "session already active" message.
- **Actual:** repeated `startEdit` calls are no-ops if you are the
  current lock owner. A different user attempting `startEdit`
  while someone else holds the lock would presumably collide
  (not verified — the lab uses a single admin account).
- **Implication:** clients that crash mid-session can re-acquire
  with `startEdit` instead of having to call `cancelEdit` first.
  This makes finally-clause cleanup safe (`startEdit` →
  `cancelEdit` → done, regardless of prior state). The
  documented `safeResolve` / `forceResolve` operations are still
  needed when **another** user has activated changes underneath
  you — that scenario manifests as `mergeNeeded: true` on the
  state object.
- **Modelled in:** `specs/edit/change-manager.yaml` (description of
  the `startEdit` operation).

---

## 6. `POST /edit/JDBCSystemResources` always returns HTTP 400 — but the parent shell is registered anyway

The minimal create call for a JDBC system resource fails server-side
validation, yet leaves a partial bean in place that subsequent calls
can complete.

- **Observed on:** 12.2.1.4 and 14.1.2.
- **Expected:** `POST /edit/JDBCSystemResources` with body
  `{"name": "<unique>"}` (or the full nested tree) should return
  201 with an empty body, mirroring how
  `POST /edit/servers` and `POST /edit/clusters` behave.
- **Actual:**
  - Body `{"name": "myDS"}` returns `HTTP 400` with
    `detail: "JDBCDataSource: Name cannot be null"`. The reason
    is that WLS auto-creates a child `JDBCResource` MBean during
    the parent shell creation, that child is created with
    `name=null`, and **its** validation fails. The error refers
    to the child, not the parent.
  - Despite the 400, the parent shell `JDBCSystemResource` **is
    registered** in the edit session. A `GET` on
    `/edit/JDBCSystemResources/myDS` returns 200 with the
    15-field shell.
  - Posting the full nested tree
    (`{"name": "myDS", "JDBCResource": {"name": ..., "JDBCDataSourceParams": ..., "JDBCDriverParams": ..., "JDBCConnectionPoolParams": ...}}`)
    returns the same 400 with the same partial-create. The
    nested fields are silently ignored at the parent POST.
  - The reliable workflow is staged: `POST` shell (accept the
    400), then `POST .../JDBCResource {"name": ...}`, then
    `POST` each of `JDBCDataSourceParams`, `JDBCDriverParams`,
    `JDBCConnectionPoolParams` separately. Each sub-resource
    POST returns `HTTP 200 {}` cleanly.
  - 12.2.1.4 includes the FQCN of the validation exception in the
    `detail`; 14.1.2 strips it.
- **Implication:** treating the 400 as fatal causes clients to
  delete the partial parent and retry, producing the exact same
  400 in a loop. Treat the 400 as a non-fatal status and
  continue with the staged workflow. The same applies to the
  full-tree POST attempted by clients that map a one-shot DTO to
  the resource hierarchy.
- **Modelled in:** `specs/edit/datasources.yaml` — file-level
  description and per-operation notes describe both the failure
  mode and the staged workflow.

---

## 7. Lifecycle operations return an async-task descriptor — even when they finish synchronously

`POST /domainRuntime/serverLifeCycleRuntimes/{name}/<action>` returns
a structured `ServerLifeCycleTaskRuntime` JSON object describing the
job, **not** an empty void.

- **Observed on:** 12.2.1.4 and 14.1.2 (identical shape, identical
  18-field set).
- **Expected (per Oracle's REST docs and intuitive REST semantics
  for "actions"):** an empty 200 response on success, similar to
  many other action endpoints. Async-style responses are typical
  for long-running jobs; lifecycle ops like `suspend` complete in
  ~35 ms in our captures.
- **Actual:** every call returns:
  ```json
  {
    "links": [{"rel": "job", "href": ".../tasks/_<n>_<operation>"}],
    "identity": ["serverLifeCycleRuntimes", "<server>", "tasks", "<name>"],
    "type": "ServerLifeCycleTaskRuntime",
    "name": "_<n>_<operation>",
    "operation": "<operation>",
    "progress": "success",
    "taskStatus": "TASK COMPLETED",
    "running": false,
    "completed": true,
    "taskError": null,
    "startTime": "...", "endTime": "...",
    "intervalToPoll": 1000,
    "...": "..."
  }
  ```
  Even synchronous operations follow the async-job protocol. The
  `tasks` collection child of each lifecycle runtime accumulates
  history of all past invocations. `suspend` requests are
  internally recorded as `suspendWithTimeout` regardless of
  whether the body included a timeout.
- **Implication:** clients can write a uniform polling loop that
  reads `taskStatus` / `completed` instead of branching on action
  type. Failures are reported via `taskError` (non-null), not
  via HTTP status — a misbehaving NodeManager returns a 200
  task whose `taskError` carries the wrapped exception.
- **Modelled in:** `specs/lifecycle/lifecycle.yaml#LifecycleTaskResponse`
  used as the response body of every action.

---

## 8. Cross-version field-set deltas

The bean shapes are **mostly** identical between WLS 12.2.1.4 and
14.1.2, but each release carries a small set of additions and
removals. The list below is exhaustive per-bean for the resources
modelled in this spec.

| Resource | 14.1.2 | 12.2.1.4 | Notes |
|---|---|---|---|
| `ServerRuntime` (read) | 28 | 28 | Identical. |
| `JDBCDataSourceRuntime` (read) | 47 | 47 | Identical. |
| `ThreadPoolRuntime` (read) | 19 | 19 | Identical. |
| `JVMRuntime` (read) | 16 | 15 | 14.1.2 adds `javaVendorVersion`. |
| `applicationRuntime` (read) | 9 | 10 | 12.2.1.4 has `partitionName` (Multi-Tenant artifact removed in 14.1.2). |
| `ServerChannelRuntime` (read) | 12 | 12 | Identical. |
| `JMSRuntime` (container, read) | 9 | 9 | Identical. |
| `JMSServerRuntime` (read) | 37 | 37 | Identical (verified across three independent captures). |
| `ComponentRuntime` types (read) | identical | identical | 4 subtypes; field counts identical cross-version on every observed type. |
| `Server` (edit) | 136 | 136 | 5/5 different fields each side; details below. |
| `Cluster` (edit) | 73 | 69 | 14.1.2 strict superset (4 added). |
| `JDBCSystemResource` shell (edit) | 15 | 15 | Identical. |
| `JDBCResource` (edit) | 5 | 5 | Identical. |
| `JDBCDataSourceParams` (edit) | 11 | 11 | Identical. |
| `JDBCDriverParams` (edit) | 6 | 6 | Identical. |
| `JDBCConnectionPoolParams` (edit) | 37 | 36 | 14.1.2 adds `invokeBeginEndRequest`. |
| `ServerLifeCycleRuntime` | 6 | 6 | Identical. |
| `LifecycleTaskResponse` | 18 | 18 | Identical. |

**`Server` (edit) detail.**

Fields added in 14.1.2:
- `virtualThreadEnableOption` — JDK 21 virtual-thread dispatch
  toggle.
- `selfTuningThreadPoolSizeMin`, `selfTuningThreadPoolSizeMax` —
  bounds on the self-tuning pool.
- `synchronizedSessionTimeoutEnabled` — coordinated session-timeout
  flag.
- `logCriticalRemoteExceptionsEnabled` — log severity tweak for
  cross-server exceptions.

Fields removed in 14.1.2 (still present on 12.2.1.4):
- `buzzAddress`, `buzzPort`, `buzzEnabled` — "Buzz" cluster
  transport, removed from the 14.1.x cluster stack.
- `administrationProtocol` — replaced by the broader
  `administrationPort` + listen-channel model in 14.1.x.
- `isolatePartitionThreadLocals` — Multi-Tenant artifact, consistent
  with the rest of the partition removal.

**`Cluster` (edit) detail.** The four 14.1.2-additive fields:
`replicationTimeoutMillis`, `rebalanceDelayPeriods`,
`autoMigrationTableCreationDDLFile`,
`autoMigrationTableCreationPolicy`.

**HATEOAS rels removed in 14.1.2** (Multi-Tenant deprecation):
- `/domainRuntime` no longer exposes `domainPartitionRuntimes`,
  `resourceGroupLifeCycleRuntimes`.
- `/domainRuntime/serverRuntimes/{name}` no longer exposes
  `partitionRuntimes`.
- `/domainRuntime` → `consoleRuntime` was renamed to
  `consoleBackend`.

**HATEOAS rels added in 14.1.2:**
- `/domainRuntime` → `JNDI` (tree-browser resource),
  `consoleBackend`, `getServerHttpURL` (action).
- `/domainRuntime/serverRuntimes/{name}` → `consoleBackend`.
- `/domainRuntime/serverRuntimes/{name}/JVMRuntime` → `action: runGC`
  (triggers an explicit `System.gc()` via REST).

- **Implication:** clients that target both versions must check for
  field presence rather than rely on schema; treating an absent
  field as `null` is the safe default for the additive direction.
  Tools generating Java/TypeScript types should use nullable
  fields throughout the cross-version surface, or generate two
  models keyed off `info.servers[].variables.version`.
- **Modelled in:** every per-resource spec carries a description
  of its own delta. The list above is the authoritative summary.

---

## 9. `JVMRuntime.threadStackDump` payload size

`JVMRuntime` includes a `threadStackDump` field returning a textual
dump of every JVM thread's stack at the moment of the GET.

- **Observed on:** 12.2.1.4 (~108 KB on a busy OSB server) and
  14.1.2 (~53 KB on an idle AdminServer).
- **Expected (per the field name):** a small string identifying the
  current thread, or maybe a 1–2 KB summary.
- **Actual:** complete `Thread.dumpAllStacks()`-style multi-line
  text. On busy servers it can exceed 100 KB and produces
  noticeable HTTP latency. On AdminServers monitoring a domain
  with many managed servers, polling `JVMRuntime` without
  excluding this field can produce >MB monitoring traffic per
  cycle.
- **Implication:** **always exclude this field** from monitoring
  polls. The recommended idiom is
  `?excludeFields=threadStackDump&links=none`. Or use
  `?fields=heapFreeCurrent,heapSizeCurrent,uptime,javaVersion,...`
  to allow-list only what you need.
- **Modelled in:** `specs/domain-runtime/jvm.yaml` (the field is
  documented with a size warning and the recommended
  `?excludeFields=` idiom).

---

## 10. `ServerChannelRuntime` does not expose `listenAddress`, `listenPort`, or `protocol`

Despite the bean name suggesting that channel-level network
information is available there, the REST projection does not
serialise it.

- **Observed on:** 12.2.1.4 and 14.1.2.
- **Expected (per the underlying `ServerChannelRuntimeMBean` in
  Oracle's MBean reference):** `listenAddress`, `listenPort`,
  `protocol`, `publicAddress`, `publicPort` are all readable
  properties. `servers.yaml` originally hinted that these "live in
  `serverChannelRuntimes`".
- **Actual:** the REST projection returns 12 fields:
  `identity`, `name`, `channelName`, `type`, `publicURL`,
  `associatedVirtualTargetName`, `acceptCount`, `connectionsCount`,
  `bytesReceivedCount`, `bytesSentCount`, `messagesReceivedCount`,
  `messagesSentCount`. None of `listenAddress`, `listenPort`,
  `protocol`, `publicAddress`, `publicPort` are returned, even
  when explicitly requested via
  `?fields=listenAddress,listenPort,protocol,publicAddress,publicPort,channelName`
  — that returns only `channelName`.

  The only network-endpoint information surfaced is the
  concatenated `publicURL` string
  (`<protocol>://<host>:<port>`).
- **Implication:** clients needing the components separately must
  parse `publicURL` themselves. There is no path to obtain them via
  REST that we found. The `servers.yaml` description was updated
  in v0.2.0 to reflect this and cross-link to `channels.yaml`.
- **Modelled in:** `specs/domain-runtime/channels.yaml`
  (`ServerChannelRuntime` schema), `specs/domain-runtime/servers.yaml`
  (cross-reference plus warning).

---

## A note on retraction history

Two of the items above (sections 2 and 3) overturn earlier
recorded findings. The repo keeps the original v0.1.x text in
`samples/12.2.1.4/README.md` for traceability and points to the
v0.2.0 retraction in `CHANGELOG.md` "Corrections from v0.1.x". If
this document drifts from the CHANGELOG, the CHANGELOG is the
authoritative timestamped record; this file is the
search-friendly index.

If you find an Oracle source that documents any of the behaviours
above — particularly section 2's selective GET-time
`X-Requested-By` enforcement, which we have not been able to find
in any official reference — please open an issue or PR with the
link.
