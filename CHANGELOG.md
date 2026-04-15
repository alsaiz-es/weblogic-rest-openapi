# Changelog

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
