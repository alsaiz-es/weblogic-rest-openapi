# WLS 12.2.1.4 Baseline Captures

Real JSON responses captured on 2026-04-15 from a live WebLogic Server
12.2.1.4 OSB domain (Stack Patch Bundle 12.2.1.4.240111, WLS PSU
12.2.1.4.240104). One AdminServer + one managed server `osb_server1`
joined to cluster `cluster1`. Host/IP sanitized to
`wls-admin.example.com` and `wls-host`; DB schema names (`DEV_SOAINFRA`,
etc.) left as-is (public FMW convention).

These files are the authoritative reference for what v0.1.0 specs
model — if the spec disagrees with the JSON here, the spec is wrong.

**v0.2.0 update (2026-04-27).** Additional captures added for the
endpoints introduced in v0.2.0 (`serverChannelRuntimes`,
`applicationRuntimes` detail, `JMSRuntime` + `JMSServer` detail,
bulk `POST /search`). The OSB-deployed JMS servers
(`wlsbJMSServer_auto_2`, `UMSJMSServer_auto_2`,
`AgentTestJMSServer`) provided the populated counter samples; an
additional empty `myJMSServer` was created via WLST next to them
(named to match the spec's generic example) to confirm the field
set holds for non-OSB JMS servers, then destroyed.

## Files

| File | Endpoint | Notes |
|---|---|---|
| `serverRuntime_AdminServer.json` | `/domainRuntime/serverRuntimes/AdminServer` | 28 top-level keys, all links |
| `serverRuntime_osb_server1.json` | `/domainRuntime/serverRuntimes/osb_server1` | 28 top-level keys, clustered member |
| `serverRuntime_direct_osb_server1.json` | `/serverRuntime` (port 7003, direct) | Same shape as above — differs only in transient counters |
| `serverRuntime_direct_keys.txt` | — | Sorted top-level keys from the direct-access response |
| `serverRuntimes_collection.json` | `/domainRuntime/serverRuntimes` | **400** — see quirk below |
| `domainRuntime_root.json` | `/domainRuntime` | Root bean — 22 child runtime rels, only 4 covered in v0.1.0 |
| `jdbcServiceRuntime_osb_server1.json` | `.../JDBCServiceRuntime` | Parent bean (4 fields) |
| `jdbc_datasources_collection.json` | `.../JDBCDataSourceRuntimeMBeans` | 8 datasources, full fields |
| `jdbc_datasource_wlsbjmsrpDataSource.json` | `.../wlsbjmsrpDataSource` | XA DS, currCapacity=5 |
| `threadPoolRuntime_osb_server1.json` | `.../threadPoolRuntime` | 18 fields |
| `jvmRuntime_osb_server1.json` | `.../JVMRuntime?excludeFields=threadStackDump` | HotSpot 1.8.0_401, heap ~3.5 GB |
| `applicationRuntimes_summary.json` | `.../applicationRuntimes` | 76 apps, 6-field summary (for v0.2.0) |
| `error_400_sample.json` | bogus query string | JSON envelope: status/type/title/detail |
| `error_404_sample.json` | non-existent server name | JSON envelope, detail carries the bad name |
| `error_401_sample.html` | wrong password | **HTML**, not JSON — ErrorResponse schema doesn't apply |

## 12.2.1.4-specific quirks observed

> **Note (v0.2.0 update).** Items 1 and 2 below are the **original
> v0.1.0 observations**, both of which were retracted in v0.2.0 after
> additional verification. Item 1 was misdiagnosed as a serialization
> bug; the actual cause is a request-side `X-Requested-By` gate that
> reproduces identically on 14.1.2 (so it is neither 12.2.1.4-specific
> nor OSB-specific). Item 2 was misdiagnosed as a broken DSL; the
> actual cause was the same missing `X-Requested-By` header. Both
> retractions are documented in `CHANGELOG.md` under v0.2.0
> "Corrections from v0.1.x", and the controlled probe matrix is
> preserved verbatim under `samples/{version}/csrf-test/`. The
> historical text is kept here for traceability, not as current
> guidance.

1. `/serverRuntimes` collection endpoint returns **HTTP 400** when
   `osb_server1` is running. Individual `/serverRuntimes/{name}` works
   fine. Suspect WLS serialization bug triggered by OSB-specific
   bean state — needs re-test against 14.1.2.
2. `/domainRuntime/search` POST returns 400 on every query shape
   attempted (empty body, top-level fields, nested children query).
   Oracle docs describe a JSON query DSL but don't publish a schema;
   search endpoint effectively undocumented for 12.2.1.4.
3. 401 responses are **text/html**, not the JSON error envelope used
   by 400/404/500. Clients must branch on `Content-Type`.

## Uncovered runtimes under `/domainRuntime` (for future phases)

From `domainRuntime_root.json` links, v0.1.0 covers only `serverRuntimes`.
Remaining child rels in 12.2.1.4:

- `serverLifeCycleRuntimes` — start/stop (Phase 3, `lifecycle/`)
- `nodeManagerRuntimes` — NM state per machine
- `logRuntime` — server log access
- `deploymentManager` — deploy/undeploy operations
- `rolloutService` — rolling updates
- `search` — bulk query (broken in 12.2.1.4, see above)
- `domainPartitionRuntimes`, `currentDomainPartitionRuntime` — multi-tenant
- `migratableServiceCoordinatorRuntime`, `migrationDataRuntimes`, `serviceMigrationDataRuntimes` — WLS migration
- `SNMPAgentRuntime`, `batchJobRepositoryRuntime`, `consoleRuntime`,
  `appRuntimeStateRuntime`, `domainSecurityRuntime`,
  `editSessionConfigurationManager`, `elasticServiceManagerRuntime`,
  `messageDrivenControlEJBRuntime`, `policySubjectManagerRuntime`,
  `resourceGroupLifeCycleRuntimes`, `systemComponentLifeCycleRuntimes`

## How to re-capture

```bash
BASE=http://<admin>:7001/management/weblogic/latest
AUTH="-u weblogic:<password>"
# Example: individual server runtime
curl -sS $AUTH "$BASE/domainRuntime/serverRuntimes/AdminServer" | jq . > serverRuntime_AdminServer.json
```
