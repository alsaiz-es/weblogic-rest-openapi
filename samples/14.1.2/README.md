# WLS 14.1.2 Baseline Captures

Real JSON responses captured on 2026-04-15 from a live WebLogic Server
14.1.2.0.0 install (banner: `Thu Sep 11 09:33:31 GMT 2025 local`).
Plain `base_domain` — AdminServer only, no managed servers, no OSB/SOA
applications. JVM: **HotSpot 21.0.9** (notable jump from 1.8.0_401 in
the 12.2.1.4 baseline).

Host/IP sanitized to `wls-admin.example.com` / `wls-host`.

## Files

Same layout as `samples/12.2.1.4/`. The stock `base_domain` ships with
no datasources configured; `jdbc_datasource_TestDS.json` was captured
against a temporary Derby datasource created via WLST for the sole
purpose of verifying the `JDBCDataSourceRuntimeMBean` shape. The DS was
destroyed immediately after capture.

## Diff vs. 12.2.1.4 (the valuable part)

### Property-set compatibility (identical in both versions)

- **ServerRuntime** — 28 fields, zero diff.
- **JDBCServiceRuntime** — 5 fields, zero diff.
- **JDBCDataSourceRuntime** — 47 fields, zero diff.
  `state` serializes as `"Running"` (Title Case) in both versions —
  the casing quirk survives. Verified with a Derby `TestDS` on 14.1.2
  and `wlsbjmsrpDataSource` on 12.2.1.4.
- **ThreadPoolRuntime** — 19 fields, zero diff.

### JVMRuntime — one new field in 14.1.2

```
+ javaVendorVersion   (string, nullable — observed null on the HotSpot 21.0.9 build)
```

Everything else carries over. `threadStackDump` is still present
(~53 KB on this idle AdminServer vs ~108 KB on a busy OSB managed
server). The `OSName`/`OSVersion` uppercase-prefix quirk survives.

### New HATEOAS links in 14.1.2

Under `/domainRuntime`:
```
+ JNDI               — JNDI tree browser resource
+ consoleBackend     — replaces the 12.2.1.4 `consoleRuntime` rel
+ getServerHttpURL   — action helper
```

Under `/domainRuntime/serverRuntimes/{name}` (ServerRuntime):
```
+ consoleBackend
```

Under `/domainRuntime/serverRuntimes/{name}/JVMRuntime`:
```
+ action: runGC     — new administrative hook for explicit System.gc()
```

### Rels *removed* in 14.1.2 (Multi-Tenant deprecation)

```
- domainPartitionRuntimes           (from /domainRuntime root)
- resourceGroupLifeCycleRuntimes    (from /domainRuntime root)
- partitionRuntimes                 (from ServerRuntime)
- consoleRuntime                    (renamed → consoleBackend)
```

The WebLogic Multi-Tenant partitioning feature (`DomainPartitionMBean`
and friends), which was deprecated in 14.1.1, is fully removed from
the 14.1.2 REST surface. Any client that touches the `partitionRuntimes`
rel must detect the WLS version and degrade gracefully.

### Behavioral diffs on edge cases

| Case | 12.2.1.4 | 14.1.2 | Notes |
|---|---|---|---|
| `GET /serverRuntimes` collection | **HTTP 400** with osb_server1 up | **HTTP 200** | Was OSB-specific serialization bug, gone here |
| `POST /domainRuntime/search` | 400 on every body shape tried | 400 on every body shape tried | Undocumented in both — requires further reverse-engineering |
| 401 response body | HTML | HTML | `ErrorResponse` JSON schema does not apply to 401 |
| 404 response body | JSON envelope | JSON envelope | Identical shape and `detail` format |

### Casing quirks (all 5 survive unchanged)

Confirmed in 14.1.2:
- `ServerRuntime.state` = `"RUNNING"` (uppercase)
- `healthState.state` = `"ok"` (lowercase)
- `JVMRuntime.OSName` / `OSVersion` (uppercase `OS` prefix)
- `name` field semantics still vary per bean

The `state` Title-Case quirk for `JDBCDataSourceRuntime` was verified
directly on 14.1.2 by creating a temporary Derby `TestDS` via WLST:
the response carries `"state": "Running"` with the same Title Case used
in 12.2.1.4.

## Actionable spec changes for v0.1.1

1. `specs/domain-runtime/jvm.yaml`: add `javaVendorVersion` (nullable string).
2. Documentation: note Multi-Tenant rel removal and the `consoleRuntime` →
   `consoleBackend` rename as 14.1.2-specific.
3. `README.md`: mark specs as verified on both 12.2.1.4 and 14.1.2.
