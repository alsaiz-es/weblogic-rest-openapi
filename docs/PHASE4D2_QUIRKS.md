# Phase 4d-2 — Quirks migration and operations gap closure

## Goal

Close two related gaps that keep the generated spec from matching the
manual spec's editorial value:

1. **Quirks migration.** Migrate every quirk documented in
   `docs/QUIRKS.md` into structured overlay files under
   `overlays/quirks/<id>.yaml`, and have the generator inject each
   quirk into the right schema/path/property of the generated spec.
2. **Operations gap closure.** The generated spec is missing
   operations that the manual spec covered: `startInAdmin`,
   `startInStandby` (only in Java code, not in `extension.yaml`), and
   `POST /domainRuntime/search` (a virtual endpoint with no MBean).

After 4d-2, the generated spec carries the same operational knowledge
that the manual spec did, plus the schema breadth that the harvested
YAMLs added.

## Out of scope for 4d-2

- Server / Cluster surface curation → 4d-4
- Multi-version specs → 4d-5
- Description merge policy → 4d-5
- Live samples linking → 4d-5
- Coverage expansion to JTA/WLDF/work managers → 4e

## Quirks overlay format

Each quirk lives in `overlays/quirks/<id>.yaml`:

```yaml
id: csrf-serverRuntimes
title: "GET /domainRuntime/serverRuntimes requires X-Requested-By when managed servers are running"
applies_to_versions:
  - "12.2.1.3.0"
  - "12.2.1.4.0"
  - "14.1.1.0.0"
  - "14.1.2.0.0"
  - "15.1.1.0.0"
attachment:
  type: path
  path: "/management/weblogic/{version}/domainRuntime/serverRuntimes"
  method: get
inject:
  description_append: |
    **Quirk:** This endpoint requires the `X-Requested-By` header when
    the domain has any managed server in RUNNING state...
  x_extensions:
    x-weblogic-conditional-csrf:
      header: X-Requested-By
      condition: "managed servers in RUNNING state"
external_doc: docs/QUIRKS.md#1
```

`attachment.type` admite: `path`, `schema`, `property`, `global`.
`inject` admite: `description_append`, `description_replace` (evitar),
`x_extensions`, `parameters_add`, `responses_add`.

El generador lee todo `overlays/quirks/*.yaml` después de schemas + paths,
aplica las injections, emite el spec mergeado.

## Quirks a migrar (los 14 de QUIRKS.md)

| # | Quirk | Attachment |
|---|---|---|
| 1 | State casing inconsistencies | property — multiple |
| 2 | healthState lowercase tokens | property — `healthState.state` |
| 3 | JVMRuntime OSName/OSVersion uppercase prefix | property — JVMRuntime |
| 4 | `name` semantics differing across beans | global + per-schema |
| 5 | healthState.subsystemName often null | property — HealthState |
| 6 | POST requires X-Requested-By | global + edit paths |
| 7 | ServerChannelRuntime missing listenAddress/listenPort | schema |
| 8 | GET serverRuntimes selective CSRF | path |
| 9 | JDBCSystemResources POST 400 staged-create | path |
| 10 | Lifecycle ops async-task | schema |
| 11 | Edit tree error envelope FQCN | global + 4xx under /edit/ |
| 12 | startEdit idempotency | path |
| 13 | JVMRuntime threadStackDump payload | property |
| 14 | properties.user JDBC exposure | property |

Cada uno: archivo overlay con la estructura. El texto debe preservar
el insight operacional sin duplicar Oracle docs.

## Operations gap closure

### `/domainRuntime/search` (virtual)
Sin MBean. Portar desde `specs/domain-runtime/search.yaml` a
`overlays/operations-virtual.yaml`. El query DSL es no-trivial — usar
verbatim del manual, no re-derivar.

### `startInAdmin` y `startInStandby`
No están en `ServerLifeCycleRuntimeMBean/extension.yaml`. Existen en
código Java. Intentar Java scraping primero. Si es brittle (regex hell,
false positives), fallback a manual overlay en
`overlays/operations-virtual.yaml`. Criterio: si scraping encuentra
fiablemente las acciones con parámetros, shippearlo. Si necesita
hand-tuning per call site, hand-write directamente.

Ambas toman opcional `properties` parameter. Match shape del manual.

## Validación

- `openapi-spec-validator` strict PASS.
- Smoke test cliente Python PASS — debe tener los 14 quirks visibles,
  /search, startInAdmin/startInStandby.
- `spectral lint` 0/0.
- Spot-check 3 quirks en attachment points distintos.

## Coverage check vs manual

Paths: missing 3 → 0. Quirks: 14 surfaced.

## Report

`tools/openapi-generator/out/PHASE4D2_REPORT.md`:
- One-line por quirk (id, attachment, ok/warning/skipped).
- Operations added con source (overlay vs Java-scraped).
- Validation results.
- Coverage vs manual.
- Edge cases.
- Diferidos a 4d-4 / 4d-5 / 4e.

## Commit

Mensaje:
```
feat(generator): Phase 4d-2 — quirks migration and operations gap closure

Adds the editorial layer that distinguishes this spec from a mechanical
harvested-to-OpenAPI conversion:

- Migrates the 14 quirks from docs/QUIRKS.md into structured
  overlays/quirks/<id>.yaml files. The generator injects each quirk at
  its attachment point during emission.

- Closes the three operation gaps:
  - POST /domainRuntime/search as virtual endpoint with query DSL.
  - startInAdmin / startInStandby via Java scraping or manual overlay
    (see report).

Generated spec now carries the same operational knowledge as the manual
v0.3.1 spec, plus the schema breadth from harvested YAMLs.
```

Sin push.

## Stop conditions

- Overlay format insuficiente para algún quirk → parar, refinar formato.
- Java scraping de startIn* peor que overlay manual → escribir manual,
  documentar decisión.
- Spec falla validador tras injection → parar, lógica de injection
  viola regla estructural.
- Smoke test cliente Python falla → parar, x-* extensions o estructura
  problemáticos.

## Editorial notes

- Los quirks son el valor real de la capa manual. Su wording es lo que
  un admin verá en Swagger UI.
- `description_append` es la injection más segura. `description_replace`
  reservar para casos donde harvested está genuinamente mal (raro).
- Java scraping es best-effort. Overlay manual es fallback legítimo,
  no derrota.
