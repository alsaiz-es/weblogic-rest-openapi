# Phase 1 — Domain Runtime Monitoring Endpoints

## Goal
Document the most-used WebLogic REST monitoring endpoints as OpenAPI 3.0.3 YAML.
This is the "80% use case" — what administrators and monitoring tools need.

## Target Version
- WebLogic Server 14.1.1.0 (14c) — primary
- WebLogic Server 14.1.2.0 — note differences where known

## Base URL Pattern
```
http://{host}:{port}/management/weblogic/{version}/domainRuntime
```
Where `{version}` is either a specific version like `14.1.1.0` or `latest`.

## Authentication
- HTTP Basic Auth (username/password)
- HTTPS requires domain-wide administration port enabled
- Roles: Admin, Deployer, Operator, Monitor (GET requires Monitor+)

## Common Response Patterns

All responses follow a consistent structure:
- Single bean: `{ identity: [...], name: "...", <properties>, links: [...] }`
- Collection: `{ items: [ <beans> ], links: [...] }`
- Links always include `self`, `canonical`, `parent`
- Query params: `?fields=name,state&links=none&excludeFields=...`

## Endpoints to Document (Phase 1)

### 1. Server Runtimes (HIGH PRIORITY)
**Path**: `/domainRuntime/serverRuntimes`
**Path**: `/domainRuntime/serverRuntimes/{serverName}`

Key properties:
- `state` (RUNNING, SHUTDOWN, STANDBY, ADMIN, etc.)
- `healthState` (object with state, subsystemName, symptoms)
- `activationTime` (long — epoch millis)
- `openSocketsCurrentCount`
- `weblogicVersion`
- `javaVersion`
- `osName`, `osVersion`
- `currentMachine`
- `clusterRuntime` (reference)

Children to include:
- `threadPoolRuntime` (see below)
- `JVMRuntime` (see below)
- `JDBCServiceRuntime` (see below)

### 2. Thread Pool Runtime (HIGH PRIORITY)
**Path**: `/domainRuntime/serverRuntimes/{serverName}/threadPoolRuntime`

Key properties:
- `executeThreadTotalCount`
- `executeThreadIdleCount`
- `hoggingThreadCount`
- `pendingUserRequestCount`
- `completedRequestCount`
- `throughput` (double)
- `healthState`
- `stuckThreadCount`
- `queueLength`

### 3. JVM Runtime (HIGH PRIORITY)
**Path**: `/domainRuntime/serverRuntimes/{serverName}/JVMRuntime`

Key properties:
- `heapSizeCurrent` (long, bytes)
- `heapSizeMax` (long, bytes)
- `heapFreeCurrent` (long, bytes)
- `heapFreePercent` (double)
- `javVMVendor`, `javaVersion`
- `uptime` (long, millis)

### 4. JDBC Service Runtime (HIGH PRIORITY)
**Path**: `/domainRuntime/serverRuntimes/{serverName}/JDBCServiceRuntime`
**Path**: `/domainRuntime/serverRuntimes/{serverName}/JDBCServiceRuntime/JDBCDataSourceRuntimeMBeans`
**Path**: `/domainRuntime/serverRuntimes/{serverName}/JDBCServiceRuntime/JDBCDataSourceRuntimeMBeans/{dsName}`

Key properties per datasource:
- `name`
- `state` (Running, Suspended, Shutdown, etc.)
- `activeConnectionsCurrentCount`
- `activeConnectionsHighCount`
- `waitingForConnectionCurrentCount`
- `waitingForConnectionHighCount`
- `waitingForConnectionFailureTotal`
- `waitSecondsHighCount`
- `connectionDelayTime`
- `currCapacity`
- `numAvailable`
- `leakedConnectionCount`
- `connectionsTotalCount`

### 5. Application Runtime (MEDIUM PRIORITY)
**Path**: `/domainRuntime/serverRuntimes/{serverName}/applicationRuntimes`
**Path**: `/domainRuntime/serverRuntimes/{serverName}/applicationRuntimes/{appName}`

Key properties:
- `name`
- `healthState`
- `overallHealthState`
- `activeVersionState`

### 6. Bulk Query / Search (MEDIUM PRIORITY)
**Path**: `/domainRuntime/search` (POST)

This is WebLogic's "GraphQL-like" feature — you POST a JSON query describing
which beans and properties you want, and get a tree slice back.
Documenting this is valuable but the request schema is complex.

## Shared Schemas to Define

- `HealthState` — { state: "HEALTH_OK"|"HEALTH_WARN"|"HEALTH_CRITICAL"|"HEALTH_FAILED", subsystemName: string, symptoms: [...] }
- `Identity` — array of strings representing bean path
- `Link` — { rel: string, href: string, title?: string }
- `LinksArray` — array of Link
- `ErrorResponse` — { status: int, detail: string, type: string }
- `BulkQuery` — the POST body for search endpoints
- `FilterParams` — query parameters (fields, excludeFields, links)

## Open Questions

1. **Single file vs. multi-file?** Each bean tree as a separate YAML with `$ref` to common schemas, or one monolithic file? Multi-file is cleaner but some tools handle `$ref` across files poorly.
   → **Decision**: Multi-file with common schemas. Use `$ref` relative paths. Provide a bundled single-file version via a build script for tools that need it.

2. **How to handle `{version}` in the path?** Use a path parameter or hardcode `latest`?
   → **Decision**: Use `{version}` as a path parameter with enum of known values + `latest`.

3. **Property completeness** — Oracle's MBean reference documents hundreds of properties per MBean. Do we document all or just the commonly useful ones?
   → **Decision**: Phase 1 documents the "monitoring essentials" — properties people actually query. Full MBean property coverage is Phase 3 (crawler-generated).

## Validation Strategy

1. `spectral lint` on every YAML file
2. Load in Swagger Editor (editor.swagger.io) — visual check
3. Generate a Python client and verify it compiles
4. If possible, validate against a real WebLogic 14c instance

## Sources

- Oracle REST reference docs (links in README.md)
- Oracle MBean reference: https://docs.oracle.com/en/middleware/standalone/weblogic-server/14.1.1.0/wlmbr/
- Real WebLogic responses from Alfie's support experience
- dbi-services blog examples: https://www.dbi-services.com/blog/using-weblogic-12c-restful-management-for-monitoring-weblogic-domains/
