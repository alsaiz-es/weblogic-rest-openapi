# WebLogic REST Management API — Unofficial OpenAPI Specification

Oracle WebLogic Server exposes a comprehensive RESTful management interface for administration, monitoring, deployment, and configuration. **Oracle does not publish an OpenAPI (Swagger) specification** for it.

This project provides an **unofficial, community-driven OpenAPI 3.0 specification** for the WebLogic REST Management API across **five WebLogic versions** (12.2.1.3, 12.2.1.4, 14.1.1, 14.1.2, 15.1.1), enabling:

- **API client generation** (Python, Java, Go, TypeScript, …) via OpenAPI tooling.
- **Interactive documentation** via Swagger UI or Redoc.
- **Request validation** in Postman, Insomnia, Bruno, and similar tools.
- **LLM tool integration** — drive [ToolSpec](https://github.com/alsaiz-es/llm-toolspec) descriptors so AI agents can manage WebLogic domains via REST.
- **Automated testing** of WebLogic management endpoints.

## How the spec is built (v0.4.0)

Starting in v0.4.0 the specification is **generated mechanically** from Oracle's open-source [`weblogic-remote-console`](https://github.com/oracle/weblogic-remote-console) harvested MBean YAMLs (the same source of truth Oracle uses internally to drive the Remote Console UI), and refined with a small set of editorial overlays that capture knowledge no harvested catalog can produce on its own.

```
Oracle weblogic-remote-console (UPL 1.0)        This project (Apache 2.0)
─────────────────────────────────────────       ───────────────────────────
harvested-yaml (~830 MBeans / version)  ──┐
UI overlays (legalValues, read-only hints)  ├─►  generator pipeline
extension.yaml (POST operations)          ──┘    └─► OpenAPI 3.0 spec / version
                                                     + manual overlays
                                                     + transitive prune
                                                     ────────────────────────
                                                     specs/generated/<v>.yaml
```

### What is generated mechanically

- **Schemas.** ~600–660 schemas per version, derived from the harvested MBean YAMLs with `baseTypes` chain merging, name normalization, enum lifting via UI overlays, and `allOf`+EnvelopeBase wrapping. Polymorphic hierarchies are emitted with OAS 3.0 discriminators.
- **Paths.** ~1100–2400 paths per version, computed from the harvested containment graph rooted at `DomainRuntimeMBean` / `DomainMBean`. The path-count delta between 12.2.1.x (~2400) and 14.1.x+ (~1150) reflects Multi-Tenant deprecation in 14.1.x — real WebLogic behaviour, not a generator artifact.
- **Operations.** Declarative MBean actions (`start`, `shutdown`, `suspend`, `restartSSLChannels`, …) injected from `extension.yaml` per MBean.
- **Cross-version diffs.** [`tools/openapi-generator/out/VERSION_DELTAS.md`](tools/openapi-generator/out/VERSION_DELTAS.md) lists per-pair deltas so a consumer can spot what differs between 12.2.1.4 and 14.1.2 (or any adjacent pair).

### The manual overlay layer

Five thin layers add knowledge no harvested catalog can produce:

| Layer | Count (14.1.2) | Lives at | Purpose |
|---|---:|---|---|
| **Quirks** | 14 | `overlays/quirks/*.yaml` | Documented anomalies (CSRF gates, casing inconsistencies, JDBC partial-create, `OS` prefix on `JVMRuntime`, …). Each has a stable id + external doc reference. |
| **Description overlays** | 50 | `overlays/descriptions/*.yaml` | Operational notes appended to harvested descriptions. 21 from the original curated set + 29 from per-subsystem editorial pass (Deployments, JMS detail, Work Managers, JTA, WLDF). |
| **Live samples** | 33 ops linked | `samples/<version>/` ↔ `overlays/sample-loader` | Real JSON responses from running WebLogic captures. Canonical sample → native OpenAPI `examples`; overflow → `x-weblogic-sample-paths` extension. Two versions covered with samples (12.2.1.4, 14.1.2). |
| **Empirical nullability** | 20 | `overlays/nullability.yaml` | Property-level `nullable: true` corrections discovered while validating samples — fields the harvested set declares as non-null but the live REST projection returns as `null`. |
| **Manual subtype bodies** | 12 | `overlays/manual-schemas/*.yaml` | Polymorphic subtype bodies the Remote Console UI overlay declares but Oracle has no harvested YAML for (`OAMAuthenticator`, `JMSQueueRuntime`, `JMSTopicRuntime`, `JDBCProxyDataSourceRuntime`, …). Authored from Oracle Javadoc + public docs + samples; flagged with `x-weblogic-manual-schema: true` and `x-weblogic-source` for provenance. |

The generator runs a final **transitive-closure prune** that drops any schema unreferenced from the path tree or other components — Oracle's catalog includes legacy / internal MBeans that the REST projection does not expose, and the prune keeps `components.schemas` honest.

### Validation

Every generated spec passes three independent toolchains across all five versions:

- `openapi-spec-validator` strict (OAS 3.0).
- `openapi-generator-cli generate -g python` (consumable end-to-end — produces ~850 model classes).
- `@stoplight/spectral-cli lint` with `spectral:oas` ruleset — **0 errors, 0 warnings** on every version.

## Important caveats

The WebLogic REST Management API is **dynamically generated at runtime** from the server's MBean trees:

1. **Available resources depend on domain configuration.** A domain with 3 datasources exposes 3 JDBC runtime resources. This spec documents the *structure* and *operations*, not the specific instances.
2. **The API is HATEOAS-driven.** Responses include `links` arrays for navigation. The spec documents the known link patterns; the dynamic graph is captured at runtime.
3. **Quality is honest, not absolute.** Manually-authored polymorphic subtypes are flagged via `x-weblogic-manual-schema: true` so consumers can filter them out if they only want harvested-derived data.

## Generated specifications

| File | WLS version | Schemas | Paths |
|---|---|---:|---:|
| [`specs/generated/12.2.1.3.0.yaml`](specs/generated/12.2.1.3.0.yaml) | 12.2.1.3.0 | 656 | 2 403 |
| [`specs/generated/12.2.1.4.0.yaml`](specs/generated/12.2.1.4.0.yaml) | 12.2.1.4.0 | 661 | 2 415 |
| [`specs/generated/14.1.1.0.0.yaml`](specs/generated/14.1.1.0.0.yaml) | 14.1.1.0.0 | 611 | 1 144 |
| [`specs/generated/14.1.2.0.0.yaml`](specs/generated/14.1.2.0.0.yaml) | 14.1.2.0.0 | 608 | 1 180 |
| [`specs/generated/15.1.1.0.0.yaml`](specs/generated/15.1.1.0.0.yaml) | 15.1.1.0.0 | 620 | 1 227 |

### Consuming the spec

```bash
# Render the 14.1.2 spec in Swagger UI via Docker
docker run -p 8080:8080 -e SWAGGER_JSON=/spec.yaml \
  -v "$(pwd)/specs/generated/14.1.2.0.0.yaml:/spec.yaml" \
  swaggerapi/swagger-ui

# Generate a Python client for 14.1.2
npx @openapitools/openapi-generator-cli generate \
  -i specs/generated/14.1.2.0.0.yaml \
  -g python -o ./client

# Generate against 12.2.1.x specs (~9 MB YAML)
# Swagger Parser's default SnakeYAML codepoint limit is exceeded by
# the 12.2.1.x specs (Multi-Tenant subtree doubles the path count);
# convert to JSON first:
python -c "import yaml, json; \
  json.dump(yaml.safe_load(open('specs/generated/12.2.1.4.0.yaml')), \
  open('/tmp/spec.json','w'))"
npx @openapitools/openapi-generator-cli generate \
  -i /tmp/spec.json -g python -o ./client
```

### Regenerating the spec

```bash
git clone https://github.com/oracle/weblogic-remote-console /tmp/wrc  # source data
cd tools/openapi-generator
uv sync
uv run python -c "import sys; sys.path.insert(0,'src'); \
  from multiversion import build_all_versions; build_all_versions(bulk=True)"
# Outputs to tools/openapi-generator/out/spec-<version>.yaml
```

See [`tools/openapi-generator/README.md`](tools/openapi-generator/README.md) for the pipeline detail and validation commands.

## Known API quirks

The WebLogic REST API has several inconsistencies that are not documented in the Oracle reference and regularly surprise implementers. Each is modelled as a quirk overlay in [`overlays/quirks/`](overlays/quirks/) with a stable id, attaches automatically to the affected schema / path / property at generation time, and is marked in the generated spec with `x-weblogic-quirks: [{id, doc}]`.

> **Consolidated reference.** Every quirk discovered across v0.1.x through v0.4.0 — with version-of-observation, expected vs actual behaviour, operational implication, and the spec target — is collected in [`docs/QUIRKS.md`](docs/QUIRKS.md).

Highlights (full list in `docs/QUIRKS.md`):

1. **`state` casing varies by subsystem.** `ServerRuntime.state` is **UPPERCASE** (`RUNNING`, `SHUTDOWN`, …); `JDBCDataSourceRuntime.state` is **Title Case** (`Running`, `Suspended`, …). Use separate enums.
2. **`healthState.state` uses lowercase tokens** (`ok`, `warning`, `critical`, …) — *not* the `HEALTH_OK`/`HEALTH_WARN` Java constants Oracle's API documents.
3. **`JVMRuntime.OSName`/`OSVersion` keep an uppercase `OS` prefix.** Every other place in the API would use camelCase `osName`/`osVersion`.
4. **`name` semantics differ across beans.** `ServerRuntime.name` is the server name; `ThreadPoolRuntime.name` is literally `"ThreadPoolRuntime"`; `JDBCServiceRuntime.name`/`JVMRuntime.name` mirror the hosting server name. Don't assume `name` is a stable identifier.
5. **`POST` requires `X-Requested-By` (CSRF guard)** — including `POST /domainRuntime/search`. The plain-text 400 returned without the header is indistinguishable from a malformed body.
6. **`GET /domainRuntime/serverRuntimes` requires `X-Requested-By` when at least one managed server is RUNNING** — selective CSRF on a read endpoint, contradicting Oracle's docs. Workarounds: send the header, fetch each server by name, or use `POST /search`.
7. **`ServerChannelRuntime` does not expose `listenAddress`/`listenPort`/`protocol`** — only the concatenated `publicURL`. Parse client-side for components.
8. **`POST /edit/JDBCSystemResources` returns 400 but registers the parent shell anyway** — the documented full-tree create does not propagate nested fields. Use the staged-create workflow (one POST per sub-resource).
9. **Edit-tree errors use `wls:errorsDetails` envelope** — different from the standard `ErrorResponse`. 12.2.1.4 keeps the FQCN in `detail`; 14.1.2 strips it.
10. **Lifecycle actions return a `ServerLifeCycleTaskRuntime` envelope, even synchronously** — same shape whether the operation completed in milliseconds or is still running.

The remaining four are documented in `docs/QUIRKS.md`.

## Cross-version differences

Five WebLogic versions are covered (12.2.1.3, 12.2.1.4, 14.1.1, 14.1.2, 15.1.1). Per-pair diffs (path additions/removals, schema-property deltas, Multi-Tenant deprecation in 14.1.x, JDK-21 / virtual-thread additions in 14.1.2 and 15.1.1) live in [`tools/openapi-generator/out/VERSION_DELTAS.md`](tools/openapi-generator/out/VERSION_DELTAS.md).

The path-count delta (~2 400 on 12.2.1.x vs ~1 150 on 14.1.x+) is dominated by Multi-Tenant feature removal — partition / resource-group lifecycle endpoints disappear in 14.1.x. JDK-21 fields (`virtualThreadEnableOption`, `selfTuningThreadPoolSize{Min,Max}`) appear from 14.1.2. The harvested set itself is Oracle's source of truth for what each version exposes; the generator does not synthesise paths.

## Compatibility

- **WebLogic Server**: 12.2.1.3, 12.2.1.4, 14.1.1, 14.1.2, 15.1.1.
- **OpenAPI Specification**: 3.0.3.
- **Validated with**: `openapi-spec-validator`, `@stoplight/spectral-cli`, `@openapitools/openapi-generator-cli`.

## Compatibility note for v0.3.x consumers

v0.4.0 **replaces** the hand-written `specs/{common,domain-runtime,edit,lifecycle}/` directories with `specs/generated/<version>.yaml`. The old directory layout is gone from `main`. If you depend on the v0.3.1 layout:

```bash
git checkout v0.3.1     # historical snapshot stays accessible via tag
```

Migration: the generated specs cover everything the v0.3.x manual specs did and substantially more. Most consumers will just point at `specs/generated/14.1.2.0.0.yaml` (or whichever version they target). The endpoint paths are identical — only the spec file layout changed.

## Oracle documentation references

- [Administering WebLogic Server with RESTful Management Services (14.1.1.0)](https://docs.oracle.com/en/middleware/standalone/weblogic-server/14.1.1.0/wlrur/index.html)
- [RESTful Edit Reference](https://docs.oracle.com/en/middleware/standalone/weblogic-server/14.1.1.0/wlrer/)
- [RESTful Domain Runtime Reference](https://docs.oracle.com/en/middleware/standalone/weblogic-server/14.1.1.0/wlrdr/)
- [RESTful Server Runtime Reference](https://docs.oracle.com/en/middleware/standalone/weblogic-server/14.1.1.0/wlrsr/)
- [RESTful Lifecycle Reference](https://docs.oracle.com/en/middleware/standalone/weblogic-server/14.1.1.0/wlrml/)
- [MBean Reference](https://docs.oracle.com/en/middleware/standalone/weblogic-server/14.1.1.0/wlmbr/)

## Contributing

Contributions, corrections, and extensions are welcome. The most valuable contributions are:

- **New live samples.** Run a real WebLogic instance, capture a response that disagrees with the spec, open an issue with the diff. The empirical layer (samples → nullability fixes) was built that way.
- **Quirk reports.** A behaviour that contradicts harvested or Oracle docs is candidate for a new quirk overlay.
- **Subsystem curation.** Description overlays in `overlays/descriptions/` add operational guidance beyond harvested. The pattern is documented in `docs/PHASE4D6_DESCRIPTIONS.md`.

## License

This project's source code, manual overlays, generator, and reports are licensed under **Apache License 2.0**.

The generated specifications include schemas derived from Oracle's [`weblogic-remote-console`](https://github.com/oracle/weblogic-remote-console) harvested MBean YAMLs, which are licensed under the **Universal Permissive License (UPL) 1.0**. Both licenses are permissive and compatible; the redistribution of the generated specs is governed by UPL 1.0 for the harvested-derived parts and Apache 2.0 for the manual-overlay parts.

## Disclaimer

This project is not affiliated with, endorsed by, or supported by Oracle Corporation. "WebLogic" and "Oracle" are trademarks of Oracle Corporation. The unofficial OpenAPI specifications in this repository are produced by mechanically transforming Oracle's publicly-available open-source catalog and refining the result with empirically-discovered overlays.
