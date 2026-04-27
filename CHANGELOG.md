# Changelog

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
