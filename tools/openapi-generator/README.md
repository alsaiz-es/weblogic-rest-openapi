# OpenAPI generator

Transforms WebLogic Remote Console harvested MBean YAMLs (plus a small set of
manual overlays) into a complete OpenAPI 3.0 specification.

Source data: clone <https://github.com/oracle/weblogic-remote-console> to
`/tmp/wrc` (shallow clone is enough). The relevant trees are:

- `weblogic-bean-types/src/main/resources/harvestedWeblogicBeanTypes/<wls-version>/`
  — one YAML per MBean with introspected properties, types, descriptions,
  defaults, deprecation flags, containment relationships, RBAC roles.
- `resources/src/main/resources/<MBeanName>/type.yaml` — UI overlays that
  add `legalValues` (enums) and a few presentation hints.
- `resources/src/main/resources/<MBeanName>/extension.yaml` — declarative
  MBean operations (start, shutdown, suspend, restartSSLChannels, etc.).

## Quick start

```bash
cd tools/openapi-generator
uv sync
uv run python src/main.py            # writes out/spec-14.1.2.0.0.yaml
uv run python src/phase4c_report.py  # writes out/PHASE4C_REPORT.md
```

To run only the schema comparison from earlier phases:

```bash
uv run python src/compare.py          # ServerRuntime schema vs manual
uv run python src/phase4b_runner.py   # all 22 schemas vs manual
```

## Pipeline

```
harvested-yaml (per MBean, per WLS version)
  └─► HarvestedLoader.load_with_inheritance()  ── walks `baseTypes` chain, merges properties
      └─► schema_builder.build_component_schema()  ── applies UI overlays for enums, normalizes names
          └─► component schema  (one per Phase 4b target MBean)

DomainRuntimeMBean / DomainMBean
  └─► path_builder.PathBuilder.build_all()  ── recursive containment walk with cycle detection
      └─► OpenAPI paths  (collection + item URLs, GET-read-trees, GET/POST/DELETE-edit)

extension.yaml per MBean
  └─► operations.collect_actions_for()  ── POST endpoints with request body / response schema

overlays/envelopes.yaml          (Identity, Link, ErrorResponse, X-Requested-By, common params)
overlays/operations-virtual.yaml (change-manager surface — no MBean exists)

  └─► main.build_spec() merges everything, validates against openapi-spec-validator
      └─► out/spec-<wls-version>.yaml
```

## Layout

```
src/
  harvested_loader.py    # parse harvested YAML + baseType inheritance
  overlays.py            # UI overlay loader (legalValues, writable: never)
  schema_builder.py      # MBean → OpenAPI schema fragment
  path_builder.py        # containment graph → paths
  operations.py          # extension.yaml → POST endpoints
  manual_loader.py       # parse manual specs (for diffing)
  main.py                # orchestrator
  phase4b_runner.py      # batch schema comparison
  phase4c_report.py      # final consolidated report
out/
  spec-14.1.2.0.0.yaml   # generated spec
  schemas/               # one YAML per generated MBean schema
  PHASE4B_REPORT.md      # per-MBean schema diff vs manual
  PHASE4C_REPORT.md      # paths + operations + validation summary
```

## Validation

The generated spec is validated against:

- [`openapi-spec-validator`](https://pypi.org/project/openapi-spec-validator/)
  in OAS 3.0 strict mode (run automatically by `main.py`).
- [`@stoplight/spectral-cli`](https://github.com/stoplightio/spectral) with
  the `spectral:oas` ruleset (errors must be 0; warnings are tracked).
- Smoke test of [`openapi-generator-cli`](https://github.com/OpenAPITools/openapi-generator-cli)
  — generates a Python client to verify the spec is consumable end-to-end.

Swagger UI render via Docker is documented but skipped automatically when
Docker is not available.

```bash
# Spectral
npx --yes @stoplight/spectral-cli@latest lint out/spec-14.1.2.0.0.yaml \
  --ruleset /tmp/spectral.yaml --format=text

# Python client (smoke test)
npx --yes @openapitools/openapi-generator-cli@latest generate \
  -i out/spec-14.1.2.0.0.yaml -g python -o /tmp/python-client \
  --skip-validate-spec
```

## License attribution

Schemas in the generated specifications are derived from
[Oracle WebLogic Remote Console](https://github.com/oracle/weblogic-remote-console)'s
harvested MBean YAMLs, licensed under the Universal Permissive License (UPL) 1.0.
The generator code, manual overlays, validation tooling, and reports are
copyright the contributors of this project, licensed under Apache License 2.0.
