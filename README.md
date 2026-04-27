# WebLogic REST Management API — Unofficial OpenAPI Specification

Oracle WebLogic Server exposes a comprehensive RESTful management interface for administration, monitoring, deployment, and configuration. Despite being a full CRUD REST API, **Oracle does not publish an OpenAPI (Swagger) specification** for it.

This project provides an **unofficial, community-driven OpenAPI 3.0 specification** for the WebLogic REST Management API, enabling:

- **API client generation** (Python, Java, Go, TypeScript, etc.) via OpenAPI tooling
- **Interactive documentation** via Swagger UI or Redoc
- **Request validation** in Postman, Insomnia, Bruno, and similar tools
- **LLM tool integration** — use this spec to generate [ToolSpec](https://github.com/alsaiz-es/llm-toolspec) descriptors and let AI agents manage WebLogic domains via REST
- **Automated testing** of WebLogic management endpoints

## Important Caveats

The WebLogic REST Management API is **dynamically generated at runtime** from the server's MBean trees. This means:

1. **Available resources depend on domain configuration.** A domain with 3 data sources exposes 3 JDBC runtime resources; a domain with none exposes zero. This spec documents the _structure_ and _operations_, not the specific instances.
2. **The API is HATEOAS-driven.** Responses include `links` arrays for navigation between related resources. This spec documents the known link patterns but cannot capture the full dynamic graph.
3. **Version-specific differences exist.** This spec targets **WebLogic Server 14.1.1.0 (14c)** and **14.1.2.0**. Earlier versions (12.2.1.x) share most of the structure but may differ in details.

## Spec Structure

The specification is organized by bean tree, mirroring Oracle's own reference structure:

```
specs/
├── domain-runtime/     # /management/weblogic/{version}/domainRuntime/...
│   ├── servers.yaml    # serverRuntimes (state, health, activation time)
│   ├── jdbc.yaml       # JDBCServiceRuntime, datasource metrics
│   ├── threading.yaml  # threadPoolRuntime
│   ├── jvm.yaml        # JVMRuntime (heap, GC)
│   └── deployments.yaml # appRuntimes
├── edit/               # /management/weblogic/{version}/edit/...
│   ├── servers.yaml    # server CRUD
│   ├── clusters.yaml   # cluster CRUD
│   ├── datasources.yaml # JDBC system resource CRUD
│   └── deployments.yaml # application deployment
├── server-runtime/     # /management/weblogic/{version}/serverRuntime/...
├── lifecycle/          # /management/weblogic/{version}/domainRuntime/...
│   └── lifecycle.yaml  # start, shutdown, suspend, resume
└── common/
    └── schemas.yaml    # shared component schemas
```

## Coverage Status

| Bean Tree | Area | Status |
|-----------|------|--------|
| domainRuntime | Server state & health | ✅ Verified (12.2.1.4, 14.1.2) |
| domainRuntime | JDBC runtime metrics | ✅ Verified (12.2.1.4, 14.1.2) |
| domainRuntime | Thread pool runtime | ✅ Verified (12.2.1.4, 14.1.2) |
| domainRuntime | JVM runtime | ✅ Verified (12.2.1.4, 14.1.2) |
| domainRuntime | Application runtime | ✅ Verified (12.2.1.4, 14.1.2) — 12.2.1.4 has extra `partitionName` |
| domainRuntime | Component runtime (web/EJB/appclient/connector) | ✅ Verified (12.2.1.4, 14.1.2) — 4 subtypes via `type` discriminator |
| domainRuntime | Server channel runtime | ✅ Verified (12.2.1.4, 14.1.2) — identical 12-field set |
| domainRuntime | Bulk search (`POST /search`) | ✅ Verified (12.2.1.4, 14.1.2) — DSL identical, CSRF header required on both |
| domainRuntime | JMS runtime (container + per-`JMSServer`) | ✅ Container verified both versions; `JMSServer` detail (37 fields) verified on 12.2.1.4 OSB; per-destination drill-down deferred to v0.3.0 |
| edit | Change session model | ✅ Verified (12.2.1.4, 14.1.2) — `wls:errorsDetails` envelope, FQCN-strip cross-version |
| edit | Server CRUD | ✅ Verified (12.2.1.4, 14.1.2) — 136 fields, 5+5 cross-version delta |
| edit | Cluster CRUD | ✅ Verified (12.2.1.4, 14.1.2) — 73/69 fields, 4 14.1.2-only |
| edit | JDBC resource CRUD | ✅ Verified (12.2.1.4, 14.1.2) — staged-create workflow, partial-create quirk |
| lifecycle | Server lifecycle ops | ✅ Verified (12.2.1.4, 14.1.2) — 8 actions, async-task response shape |

"Verified" means the property set, field names, data types, and enum
casings in the spec were cross-checked against the JSON emitted by a
running WebLogic Server — not just inferred from the MBean reference.

## Known API Quirks

The WebLogic REST API has several inconsistencies that are not documented
in the Oracle reference and regularly surprise implementers. These were
uncovered while verifying v0.1.0 against a live WLS 12.2.1.4 server and
are modelled explicitly in the specs.

1. **`state` casing varies by subsystem.** `ServerRuntime.state` is
   **UPPERCASE** (`RUNNING`, `SHUTDOWN`, ...), while
   `JDBCDataSourceRuntime.state` is **Title Case** (`Running`,
   `Suspended`, ...). Use separate enum types — do not assume a single
   lifecycle enum across runtimes.

2. **`healthState.state` uses lowercase tokens.** The REST serialization
   returns `ok`, `warning`, `critical`, `failed`, `overloaded` — **not**
   the `HEALTH_OK`/`HEALTH_WARN` Java constants that most blog examples
   show. Oracle's own `weblogic.health.HealthState` API documents the
   uppercase names; the JSON output downcases them.

3. **JVMRuntime uses `OSName`/`OSVersion` with uppercase `OS` prefix.**
   Every other place in the API that exposes operating-system information
   would use `osName`/`osVersion`. JVMRuntime is the exception — these
   two fields start with an uppercase `OS`.

4. **`name` has different semantics depending on the bean.**
   - `ServerRuntime.name` → the configured server name (e.g. `AdminServer`).
   - `ThreadPoolRuntime.name` → literally the string `ThreadPoolRuntime`.
   - `JDBCServiceRuntime.name` / `JVMRuntime.name` → the hosting server
     name (same as `ServerRuntime.name`, not a bean-specific identifier).

   Do not assume `name` uniquely identifies a bean across runtimes; use
   `identity` or the `self` link for a stable identifier.

5. **`healthState.subsystemName` is often `null`.** Only certain beans
   populate it (e.g. `ThreadPoolRuntime` sets it to `"threadpool"`,
   lowercase). Most server-level `healthState` responses leave it
   `null` even when the server is healthy. Do not rely on it being
   present.

6. **`POST` requires `X-Requested-By` (CSRF guard).** Every state-changing
   request — including `POST /domainRuntime/search` — is rejected with a
   plain-text `HTTP 400 Bad Request` (no JSON body) when the
   `X-Requested-By` header is missing. Any non-empty value is accepted.
   The Oracle REST docs do not call this out, and the symptom is
   indistinguishable from a malformed body. Verified on WLS 14.1.2;
   `v0.1.1` of this repo originally documented `POST /search` as
   universally broken — it wasn't, the CSRF header was missing.

7. **`ServerChannelRuntime` does not expose `listenAddress`/`listenPort`.**
   Oracle's `ServerChannelRuntimeMBean` reference lists `listenAddress`,
   `listenPort`, `protocol`, `publicAddress`, `publicPort` as readable
   properties. The REST serialization returns none of them — even when
   asked explicitly via `?fields=listenAddress,...`. The only network
   address surfaced is the concatenated `publicURL`
   (`<protocol>://<host>:<port>`). Parse it client-side if you need the
   components separately.

8. **`GET /domainRuntime/serverRuntimes` requires `X-Requested-By`
   when managed servers are RUNNING.** This is the second endpoint
   (alongside the POST /search of quirk 6) where Oracle's CSRF guard
   shows up — but on a plain `GET`, contradicting Oracle's
   documentation that limits the header to mutating methods. Without
   the header the collection returns `HTTP 400 Bad Request` (JSON
   envelope, no detail). With any non-empty value (`-H 'X-Requested-By:
   anything'`) it returns 200. **The check is conditional on domain
   state**: with only the AdminServer up and no managed servers
   RUNNING, the same anonymous GET succeeds. **The check is also
   selective**: of the eight `/domainRuntime/*` endpoints we probed,
   only `serverRuntimes` enforces it; the seven siblings
   (`migrationDataRuntimes`, `nodeManagerRuntimes`,
   `serviceMigrationDataRuntimes`, `serverLifeCycleRuntimes`,
   `systemComponentLifeCycleRuntimes`, plus the `/domainRuntime` root
   and `JNDI` singleton) all accept anonymous GETs. Reproduced
   identically on WLS 12.2.1.4 and 14.1.2. Earlier `v0.1.1` notes
   attributed the symptom to an OSB-specific 12.2.1.4 serialization
   bug; that attribution was wrong on all three counts (not OSB-
   specific, not 12.2.1.4-specific, not silently fixed in 14.1.2). See
   `CHANGELOG.md` v0.2.0 "Corrections from v0.1.x" for the full
   retraction. Workarounds: send the header, fetch each server by
   name, or use `POST /domainRuntime/search` with a `serverRuntimes`
   child.

## Version-specific differences: 12.2.1.4 vs 14.1.2

Verified by capturing the same bean set from both versions and diffing.
The bean property sets are otherwise identical across versions — these
are the only observed differences.

**JVMRuntime — new field in 14.1.2**
- `javaVendorVersion` (string, nullable). Observed `null` on Oracle JDK 21
  builds; field is absent entirely from 12.2.1.4 responses.

**Multi-Tenant removed in 14.1.2**

WebLogic Multi-Tenant partitioning was deprecated in 14.1.1 and the
REST surface was fully removed in 14.1.2. These HATEOAS rels disappear:

- `/domainRuntime` → `domainPartitionRuntimes`, `resourceGroupLifeCycleRuntimes`
- `/domainRuntime/serverRuntimes/{name}` → `partitionRuntimes`

Clients that followed these rels must detect version and degrade.

**Renamed in 14.1.2**
- `/domainRuntime` → `consoleRuntime` is now `consoleBackend`.
  The underlying resource is similar; the rel name changed.

**New in 14.1.2**
- `/domainRuntime` → `JNDI` (tree-browser resource),
  `consoleBackend`, `getServerHttpURL` (action).
- `/domainRuntime/serverRuntimes/{name}` → `consoleBackend`.
- `/domainRuntime/serverRuntimes/{name}/JVMRuntime` → `action: runGC`
  (triggers an explicit `System.gc()` via REST).

**Selective `X-Requested-By` enforcement on `GET /serverRuntimes`**
(reclassified in v0.2.0; previously misattributed to an OSB-specific
12.2.1.4 serialization bug — see Known API Quirk #8 above and the
CHANGELOG retraction). Reproduces identically on both 12.2.1.4 and
14.1.2 once at least one managed server is RUNNING; disappears on
admin-only domains.

**`POST /domainRuntime/search` works in both versions** (reclassified
in v0.2.0)
- v0.1.1 reported the search endpoint as broken on every body shape.
  Re-verification on 14.1.2 traced this to a missing `X-Requested-By`
  header: WebLogic's CSRF guard rejects POSTs without it and answers
  with a plain `Bad Request` page. Once the header is supplied, the
  documented DSL (`fields`, `links`, `children`, `name`) works as
  Oracle describes. See `specs/domain-runtime/search.yaml`.

**Platform note.** 14.1.2 requires JDK 17+ and commonly runs on JDK 21
(the stock Oracle install we tested is on HotSpot 21.0.9). 12.2.1.4 is
still on JDK 8. This does not affect the REST schema but matters for
anyone re-verifying captures — the `javaVersion` field will look very
different.

## serverRuntime vs domainRuntime

WebLogic exposes the same runtime beans under two different URL prefixes:

- **`/management/weblogic/{version}/domainRuntime/serverRuntimes/{serverName}/...`**
  — served by the Administration Server, reachable for any managed
  server in the domain.
- **`/management/weblogic/{version}/serverRuntime/...`**
  — served by each managed server directly, scoped to that server only.

Verified on WLS 12.2.1.4 by diffing the same bean fetched both ways:
the two responses contain **identical property sets and types**. The
only drift observed is in transient counters that change between
requests (for example `openSocketsCurrentCount` differed by 1 because
the two curls were sampled moments apart).

The specs under `specs/domain-runtime/` therefore also describe the
`serverRuntime` tree — just change the path prefix when generating a
client that talks directly to a managed server. A dedicated
`specs/server-runtime/` folder will be added in a future release only
if subsystem-specific differences surface; none have so far.

## Compatibility

- **WebLogic Server**: 14.1.1.0 (14c), 14.1.2.0
- **OpenAPI Specification**: 3.0.3
- **Validated with**: Swagger Editor, Spectral, swagger-cli

## Usage

### Swagger UI (local)

```bash
docker run -p 8080:8080 \
  -e SWAGGER_JSON=/specs/domain-runtime/servers.yaml \
  -v $(pwd)/specs:/specs \
  swaggerapi/swagger-ui
```

### Generate a Python client

```bash
openapi-generator-cli generate \
  -i specs/domain-runtime/servers.yaml \
  -g python \
  -o clients/python
```

### Generate a ToolSpec for LLM agents

```bash
# Using llm-toolspec (https://github.com/alsaiz-es/llm-toolspec)
toolspec-generator --input specs/domain-runtime/servers.yaml --output toolspec.json
```

## Oracle Documentation References

- [Administering WebLogic Server with RESTful Management Services (14.1.1.0)](https://docs.oracle.com/en/middleware/standalone/weblogic-server/14.1.1.0/wlrur/index.html)
- [RESTful Edit Reference](https://docs.oracle.com/en/middleware/standalone/weblogic-server/14.1.1.0/wlrer/)
- [RESTful Domain Runtime Reference](https://docs.oracle.com/en/middleware/standalone/weblogic-server/14.1.1.0/wlrdr/)
- [RESTful Server Runtime Reference](https://docs.oracle.com/en/middleware/standalone/weblogic-server/14.1.1.0/wlrsr/)
- [RESTful Lifecycle Reference](https://docs.oracle.com/en/middleware/standalone/weblogic-server/14.1.1.0/wlrml/)
- [MBean Reference](https://docs.oracle.com/en/middleware/standalone/weblogic-server/14.1.1.0/wlmbr/)

## Contributing

This is an unofficial, community-maintained specification. Contributions, corrections, and extensions are welcome. If you have access to a running WebLogic domain and can validate endpoints, your input is especially valuable.

## Disclaimer

This project is not affiliated with, endorsed by, or supported by Oracle Corporation. "WebLogic" and "Oracle" are trademarks of Oracle Corporation. This specification is derived from publicly available Oracle documentation and empirical API testing.

## License

Apache License 2.0
