# Phase 4c — Paths, Operations, and Pre-overlay Minimal

## Goal

Produce a complete generated OpenAPI specification for one WLS version
(14.1.2) by extending the schema-only output from Phase 4b with:

1. A **pre-overlay minimal** — the smallest set of envelope/error schemas
   needed for paths to reference. Anything beyond that stays for Phase 4d.
2. **Path generation** from the containment graph in harvested YAMLs.
3. **Operations** ingest from `extension.yaml` and Java repos.
4. **End-to-end validation** of the generated spec.

After 4c, the generator produces specs that an OpenAPI client (Swagger UI,
Redocly, openapi-generator-cli) can render and use, even though many
quirks/operations/sample overlays are still pending.

## Pre-overlay minimal

Create `overlays/envelopes.yaml` with only what 4c paths require:

- `Identity` — array of strings (already documented in
  `specs/common/schemas.yaml`; mirror it).
- `Link` — `{ rel, href, title? }` (already documented; mirror it).
- `EnvelopeBase` — mixin schema with `identity` and `links` properties.
  Every generated bean schema gets composed with this via `allOf` at
  emission time.
- `CollectionEnvelope` — `{ items: [...], links: [...] }` for collection
  responses. Generic on item schema.
- `ErrorResponse` — the standard `{ status, type, title, detail, messages? }`
  envelope from existing manual specs.
- `EditErrorResponse` — the `wls:errorsDetails` envelope discovered in
  Phase 2 of the manual work. Required for any path under `/edit/`.
- Common query parameters: `fields`, `excludeFields`, `links`,
  `excludeLinks`. Defined once, referenced from every read path.
- Common header: `X-Requested-By` — required for POST/PUT/DELETE per
  Oracle docs, plus the conditional case on `GET /serverRuntimes`
  (the latter goes into a quirks overlay in 4d, not here).

Anything else (per-quirk overlays, description merge policy, sample
linking, sub-type discriminators, enum extraction) is **out of scope
for 4c** and stays for 4d.

## Path generation

### Algorithm

For each generated schema:

1. Walk the harvested MBean's `properties[]` looking for entries with
   `relationship: containment`.
2. For each containment property:
   - **Singleton (no `array: true`):** emit a path
     `<parent-path>/<propName>` with method `GET` returning the contained
     bean schema.
   - **Collection (`array: true`):** emit two paths:
     - `<parent-path>/<propName>` — `GET` returning
       `CollectionEnvelope<refSchema>`.
     - `<parent-path>/<propName>/{name}` — `GET` returning the bean
       schema.
3. Recurse into the contained bean to derive its sub-paths. Cycle
   detection via visited-set on schema names.
4. Apply per-tree root prefix:
   - `domainRuntime` tree → `/management/weblogic/{version}/domainRuntime/...`
   - `serverRuntime` tree → `/management/weblogic/{version}/serverRuntime/...`
   - `edit` tree → `/management/weblogic/{version}/edit/...`
   - `serverConfig` tree → `/management/weblogic/{version}/serverConfig/...`
   - `domainConfig` tree → `/management/weblogic/{version}/domainConfig/...`
5. The `{version}` path parameter is enum-bound to the supported WLS
   versions (`12.2.1.3.0`, `12.2.1.4.0`, `14.1.1.0.0`, `14.1.2.0.0`,
   `15.1.1.0.0`, `latest`).

### HTTP verbs per tree

- **domainRuntime / serverRuntime / serverConfig / domainConfig:**
  GET only on read paths.
- **edit:**
  - GET on read paths.
  - POST on collection paths to create new resources.
  - POST on item paths to update.
  - DELETE on item paths.
  - All POST/PUT/DELETE require `X-Requested-By` header (referenced from
    `overlays/envelopes.yaml`).
- **Operations (any tree):** POST.

### Authorization metadata

Map `getRoles.allowed` from harvested to `x-weblogic-required-role`
extension on each path operation. Multiple roles join with OR semantics.
Not used by OpenAPI tooling natively, but documents the role boundary
explicitly. Real authorization stays at WebLogic itself.

## Operations ingest

Operations are MBean methods that aren't getters/setters
(`start`, `shutdown`, `suspend`, `resume`, `restartSSLChannels`, etc.).
They are NOT in harvested YAMLs.

### Source 1: `extension.yaml` overlays

For each MBean we generate, look up
`/tmp/wrc/resources/src/main/resources/<MBeanName>/extension.yaml`.
If `actions:` is present, ingest each action:

```yaml
actions:
- name: "restartSSLChannels"
  type: "void"
- name: "suspend"
  type: "ServerLifeCycleTaskRuntimeMBean"
  parameters:
  - name: "timeout"
    type: "int"
  - name: "ignoreSessions"
    type: "boolean"
```

Map to OpenAPI:
- Path: `<parent-path>/<actionName>`.
- Method: POST.
- Request body: object with the parameters as properties (or empty
  object if no parameters).
- Response: `void` → 204 No Content; otherwise a 200 with the return
  type as schema (resolved via the same name normalization as schemas).

### Source 2: Java repos for non-declarative operations

Some operations exist only in the Java code of the Remote Console
(`server/src/main/java/.../WebLogicRest*PageRepo.java`). Scrape these
files looking for hardcoded action invocations.

The scraper's job is **best-effort**, not exhaustive. For 4c, target
the operations we know exist from manual coverage:

- `serverLifeCycleRuntime`: `start`, `shutdown`, `forceShutdown`,
  `suspend`, `resume`, etc.
- `changeManager`: `startEdit`, `cancelEdit`, `activate`, `safeResolve`,
  `forceResolve`. These are virtual endpoints (no MBean) and require
  manual definitions; they live in a small overlay file
  `overlays/operations-virtual.yaml` rather than being scraped.
- Any operation found in `extension.yaml` of monitoring/edit MBeans
  takes precedence over Java-scraped versions.

If 4c can't reasonably scrape something, log it as a gap and document
it as a Phase 4d task to handle via a manual operations overlay.

## End-to-end validation

The generated spec for 14.1.2 must:

1. Pass `openapi-spec-validator` strict mode.
2. Render in Swagger UI without errors (run a local container as in
   the README).
3. Generate a Python client successfully via `openapi-generator-cli`
   (smoke test: just verify the generation doesn't fail; don't validate
   functional correctness).
4. Spectral lint clean (or only warnings explicable by the
   shared-components pattern, like in earlier phases).

Compare the path count against the manual spec to confirm coverage at
the path level, not just the schema level.

## Deliverables

- `overlays/envelopes.yaml` — the pre-overlay minimal.
- `overlays/operations-virtual.yaml` — operations not derivable from
  any source (change manager only, for now).
- `tools/openapi-generator/src/path_builder.py`
- `tools/openapi-generator/src/operations.py`
- Updated `main.py` orchestrator that emits a complete OpenAPI document
  per WLS version under `tools/openapi-generator/out/spec-{version}.yaml`.
- A `tools/openapi-generator/out/PHASE4C_REPORT.md` with:
  - Path count per tree (domainRuntime, edit, lifecycle).
  - Operation count per source (extension.yaml, virtual, Java-scraped).
  - Validation results (spec-validator, Swagger UI render, client generation).
  - Mismatches against manual paths (paths in manual spec missing from
    generated, or vice versa).
  - Edge cases discovered.
  - Known gaps deferred to 4d.

## Stop conditions

- If the generated spec fails `openapi-spec-validator` and the cause is
  structural (not just a schema issue), stop and reassess before
  continuing.
- If path generation produces wildly different paths than the manual
  specs (e.g. wrong base prefix, missing `{version}` parameter,
  containment graph cycles), stop and report.
- If operation scraping from Java is too brittle (regex hell, false
  positives), stop and defer the Java-scraping operations to a manual
  overlay file in 4d.
- Session over ~75 minutes → report partial progress.

## Editorial decisions confirmed before 4c

1. **Generated schemas include the full MBean surface** (e.g. all 165
   `Server` properties, not the curated 27 from the manual spec).
   Filtering or curation happens via overlays in Phase 4d, not in the
   generator.

2. **Initial commit after 4c**, on a feature branch
   (`feat/openapi-generator` or similar). The generator with schemas +
   paths + envelope minimal is a defensible milestone. Phase 4d work
   can land on the same branch incrementally.

3. **Virtual endpoints stay manual.** `ChangeManagerMBean` does not
   exist in harvested. The change-manager schemas and operations stay
   hand-written in `overlays/operations-virtual.yaml`. This is by design,
   not a workaround.

## What stays for Phase 4d

Carried over from PHASE4_GENERATOR.md plus newly identified:

### From earlier phases
- `allOf:[{$ref}]` wrapper for sibling description on `$ref`.
- `getRoles` RBAC mapping refinement (4c does the basic mapping; 4d
  refines).
- `relationship: reference` validation on a config-tree MBean
  (e.g. `ServerMBean.Cluster`).
- Enum extraction to shared schemas (10 inline-vs-$ref mismatches from 4b).
- `x-weblogic-restart-needed` semantic on runtime beans (filter or keep?).
- Overlay vocabulary not honored (`dateAsLong`, `multiLineString`,
  `presentation`, `customizers`).
- `baseTypes` chains breaking outside harvested (descriptor beans).
- Sub-type discriminator extraction (the 4 `type` mismatches in
  `*ComponentRuntime`).

### Quirks documentation migration
Move every quirk from `docs/QUIRKS.md` into `overlays/quirks/<id>.yaml`
files with a defined schema (which schema/path/property it affects,
description/example/extension to inject, applicable versions).

### Curated description merge policy
Default = harvested description. If an overlay file in
`overlays/descriptions/<schema>.yaml` provides operational notes, append
them as `**Operational note:** ...` after the harvested text.
Both Oracle's text and our notes preserved.

### Live samples linking
Decide format: OpenAPI `examples` blocks (verbose, standard) vs
`x-weblogic-sample-paths` extension pointing to `samples/` files.

### Server/Cluster surface curation
Decide whether to filter the 165-prop `Server` and 77-prop `Cluster`
schemas via overlays for "common operations" views, or leave the full
surface and add operational notes pointing readers to use `fields=...`
query parameters in practice.

### Coverage expansion
Phase 4e starts when 4d is complete. With the pipeline in place,
expanding to JTA, WLDF, work managers, JMS per-destination, deployments,
security, etc. is "run the generator on more MBean YAMLs".
