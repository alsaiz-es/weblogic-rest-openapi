# Phase 4 Plan — OpenAPI Generator from Remote Console Harvested YAMLs

## Background

The Oracle WebLogic Remote Console (https://github.com/oracle/weblogic-remote-console)
ships a directory `weblogic-bean-types/src/main/resources/harvestedWeblogicBeanTypes/`
containing ~850 YAML files per WLS version (12.2.1.3, 12.2.1.4, 14.1.1, 14.1.2, 15.1.1).
Each file describes one MBean, harvested by introspection: properties, types,
descriptions, defaults, enums, deprecation flags, containment relationships,
RBAC roles.

This is the source of truth Oracle uses internally. We can transform it into
an OpenAPI 3.0 specification and stop hand-writing schemas.

## Why this is a strategic shift, not just an optimization

Up to v0.3.1 the project was "OpenAPI spec written manually from Oracle docs
+ live curls". This works but caps coverage at ~25% of the API surface. Going
to 70-80%+ manually is months of repetitive work.

The harvested YAMLs change the economics: schemas, types, enums, descriptions,
deprecation, version differences — all of it can be generated. What stays
manual:

1. URL paths and HTTP verbs (derivable from containment relationships).
2. MBean operations (start, shutdown, suspend, etc. — these are NOT in
   harvested YAMLs, only in UI overlays and Java code).
3. Response envelopes ({identity, links, items}, error formats).
4. Quirks documentation (the CSRF gate, the JDBC POST 400, etc.).
5. Live samples and cross-version validation.

The new project shape: harvested YAMLs → transformer → generated OpenAPI base
+ manual overlay (operations, envelopes, quirks, samples) = final spec.

## Project structure (in same repo)

```
weblogic-rest-openapi/
├── tools/
│   └── openapi-generator/        # NEW
│       ├── README.md
│       ├── pyproject.toml
│       ├── src/
│       │   ├── harvested_loader.py    # parse harvested YAMLs (with inheritance)
│       │   ├── overlays.py            # parse UI overlays (legalValues, writable: never, ...)
│       │   ├── path_builder.py        # derive paths from containment
│       │   ├── schema_builder.py      # MBean → JSON schema
│       │   ├── operations.py          # parse extension.yaml + Java repos
│       │   ├── manual_overlays.py     # merge manual overlays
│       │   ├── compare.py             # diff against hand-written specs
│       │   └── main.py                # orchestrator
│       └── tests/
├── overlays/                     # NEW
│   ├── envelopes.yaml            # error envelope, paginated collections, etc.
│   ├── operations.yaml           # MBean operations (start, shutdown, ...)
│   ├── quirks/                   # one file per documented quirk
│   │   ├── csrf-serverRuntimes.yaml
│   │   ├── jdbc-systemresources-400.yaml
│   │   └── ...
│   └── examples/                 # real samples linked to schemas
├── specs/                        # OUTPUT (generated + overlays merged)
│   └── (existing structure, but now generated, not hand-written)
└── samples/                      # untouched
```

## Language choice

Python. Reasons:
- YAML libraries are mature (ruamel.yaml preserves comments/order).
- Schema manipulation is more readable than in JS.
- Integration with `openapi-spec-validator` and `prance` for validation.
- One-time tool; no end-user packaging concerns.

## Data flow

```
harvested-yaml (per version)
  + UI overlays (resources/.../<MBean>/type.yaml — for legalValues, writable: never)
  + extension.yaml overlays (for actions)
  + Java repos scraping (for operations Oracle hasn't exposed declaratively)
  + manual overlays (envelopes, quirks, examples)
       │
       ▼
   transformer
       │
       ▼
  specs/{tree}/{group}.yaml  (OpenAPI 3.0)
```

## Mapping rules

### Type mapping
- `int`, `long`, `short`, `byte` → `integer` (with format)
- `float`, `double` → `number`
- `boolean` → `boolean`
- `String` → `string`
- `weblogic.management.runtime.X` → `$ref` to that MBean schema (normalized)
- `array: true` → `array` of element type
- `legalValues` → enum
- `defaultValue` → default
- `descriptionHTML` → description (HTML stripped to plain text)

### Containment mapping
- A property with `relationship: containment` and `array: true` →
  collection endpoint at `/parent/<propName>` plus item endpoint at
  `/parent/<propName>/{name}`.
- A property with `relationship: containment` and singleton →
  endpoint at `/parent/<propName>`.
- A property with `relationship: reference` → field of type
  `Identity` (array of strings), not a sub-resource.

### Read-only / writable mapping
- `writable: false` (harvested) or `writable: never` (overlay) → readOnly: true
- `restartNeeded: true` → x-weblogic-restart-needed: true (custom extension)
- `redeployNeeded: true` → x-weblogic-redeploy-needed: true
- `deprecated: <version>` → deprecated: true + description note

### Filtering
- `supported: false` → exclude from output
- `excluded: true` → exclude from output
- `restInternal: true` → exclude from output
- `excludeFromRest: true` → exclude from output

### Schema name normalization (Phase 4a iteration 2)
- Strip `MBean` suffix from schema names: `ServerRuntimeMBean` → `ServerRuntime`
- Apply normalization both to the schema's own name and to all `$ref` targets
- Bidirectional mapping (`_JAVA_TO_SCHEMA` / `_SCHEMA_TO_JAVA`) preserved for traceability
- Beans without `MBean` suffix (e.g. `JDBCDataSourceBean`, `CompositeData`) left untouched

### Inheritance via baseTypes (Phase 4a iteration 2)
- Walk the `baseTypes` chain recursively to the root
- Child properties override parent properties on name collision
- Cache loaded MBeans to avoid re-reads
- Chains breaking outside the harvested set (e.g. `JDBCDataSourceBean → SettableBean`)
  truncate cleanly; report partial inheritance in the comparison output

### Per-version handling

Each WLS version produces its own output spec (or a unified spec with
version-conditional notes). Decision deferred to session 2 — first see how
big the cross-version diffs are when generated mechanically vs how we
documented them manually.

Likely approach: one OpenAPI spec per version, plus a meta-document
`docs/VERSION_DELTAS.md` highlighting the differences.

## Phased execution

### Phase 4a — Prototype (session 1, completed)

**Goal:** transform a single MBean (`ServerRuntimeMBean`, one version,
14.1.2.0.0) into OpenAPI and compare against `specs/domain-runtime/servers.yaml`
(hand-written).

**Status:** ✅ COMPLETE (two iterations).

**Iteration 1 result:** 69 properties generated, 24/28 of manual covered (86%),
1 type mismatch (state enum), 4 properties only in manual (identity, links, name, type).

**Iteration 2 result:** added inheritance + UI overlay enums + name normalization.
71 properties generated, 26/28 of manual covered (93%), state enum resolved
correctly (20 values vs 14 manual, strict superset). Only `identity` and `links`
remain as manual-only — both belong to the REST envelope, not the MBean.

**Decision:** direction validated, scale to 4b.

### Phase 4b — Schemas at scale (next session)

Generate schemas for all MBeans we currently document manually (servers,
threading, jvm, jdbc, applications, components, channels, jms, edit
servers/clusters/datasources, lifecycle, change manager). Compare each against
the hand-written equivalent. Produce a consolidated report.

**Decisions already taken for 4b:**
- Enums stay inline (extraction to shared schemas deferred to 4d).
- Orphan `$ref`s to MBeans not in the target list are reported but not failed.

**Stop conditions:**
- Coverage below 50% on any MBean → stop and report (structural issue).
- Edge case breaking a whole group of MBeans → stop and report.
- Session over ~60 minutes → report partial progress.

### Phase 4c — Paths and operations (session 3)

Derive paths mechanically from containment relationships. Add operations
from extension.yaml overlays. For operations that aren't in extension.yaml
(start, shutdown, etc.), scrape from `WebLogicRest*PageRepo.java` files.

**Specific tasks for 4c:**
- Path generation from containment graph (collection vs singleton).
- HTTP verb assignment (GET for read, POST for create/operations, DELETE for
  delete in edit tree).
- Operations parsing from `resources/.../<MBean>/extension.yaml` `actions:` list.
- Operations not in extension.yaml: scrape from
  `server/src/main/java/.../WebLogicRest*PageRepo.java`.
- Authorization: map `getRoles.allowed` to `x-weblogic-required-role` extension.

### Phase 4d — Manual overlays merged (session 4)

This is where everything we've been deferring lands. The exhaustive list of
items to handle in 4d, accumulated across all prior sessions:

#### From Phase 4a iteration 1
- **Sibling description on $ref:** OpenAPI 3.0 ignores `description` and
  `readOnly` next to `$ref`. Wrap with `allOf: [{$ref: ...}]` + `description`
  for strict OAS 3.0 clients (the pattern we already use in `overallHealthState`).
- **getRoles RBAC mapping:** map `getRoles.allowed` to a custom
  `x-weblogic-required-role` extension. Useful for documenting auth requirements
  on paths (4c) but the metadata lives at property level.
- **`relationship: reference` validation:** verify mapping to
  `Identity` (array of strings) on a config-tree MBean that exercises it
  (`ServerMBean.Cluster` is the canonical case). 4a only saw runtime MBeans.

#### From Phase 4a iteration 2
- **Enum extraction to shared schemas:** when the same `legalValues` set
  appears in multiple schemas (e.g. `state` reused across runtime beans),
  extract to `components/schemas/<Bean><Property>` and replace inline enums
  with `$ref`. Post-processing pass after 4b.
- **`x-weblogic-restart-needed` semantic on runtime beans:** the flag is
  metadata inherited from the config layer. On runtime beans (e.g.
  `currentMachine` on `ServerRuntime`) the flag is technically present but
  semantically irrelevant — properties are not modifiable. Decide whether to
  filter the flag on runtime schemas or leave it as harmless noise.
- **Overlay vocabulary not yet honored:** `dateAsLong`, `multiLineString`,
  `presentation`, `customizers` (Java callbacks). All ignored silently in 4a.
  Decide for each whether it produces an OpenAPI hint
  (`x-weblogic-presentation: ...`) or stays ignored.
- **`baseTypes` chains breaking outside harvested:** descriptor beans
  (e.g. `JDBCDataSourceBean → SettableBean`) lose part of their inheritance.
  Decide: scrape the missing parents from elsewhere, or document the partial
  coverage explicitly.
- **`weblogic.descriptor.SettableBean` and friends:** if descriptor beans
  matter for edit-tree coverage, harvest the missing ancestors from
  Oracle's MBean Reference Javadoc HTML or from the Java source in the
  Remote Console.

#### Envelope and REST-level concerns (always planned for 4d)
- **`identity` and `links` properties:** REST envelope, not MBean. Add
  globally to every schema (or as a base schema all generated schemas extend).
- **Error envelopes:** the standard `ErrorResponse` we documented + the
  `wls:errorsDetails` envelope used by the edit tree. Both as
  reusable schemas in `overlays/envelopes.yaml`.
- **Collection envelopes:** `{ items: [...], links: [...] }` shape applied
  to every collection endpoint.
- **Common query parameters:** `fields`, `excludeFields`, `links`, `excludeLinks`,
  documented once and referenced from every read endpoint.

#### Quirks documentation (migrate from existing manual docs)
The existing `docs/QUIRKS.md` and per-spec descriptions document quirks that
must be preserved in the generated output. List of quirks to migrate to
`overlays/quirks/`:

1. State casing inconsistencies (UPPERCASE servers vs Title Case JDBC)
2. healthState lowercase tokens
3. JVMRuntime OSName/OSVersion uppercase prefix
4. `name` semantics differing across beans
5. healthState.subsystemName often null
6. POST requires X-Requested-By (CSRF guard)
7. ServerChannelRuntime missing listenAddress/listenPort
8. GET /domainRuntime/serverRuntimes selective CSRF gate
9. JDBCSystemResources POST always returns 400 (staged-create workflow)
10. Lifecycle ops always return async-task
11. Edit tree error envelope (FQCN strip cross-version)
12. `startEdit` idempotency
13. JVMRuntime threadStackDump payload size
14. `properties.user` exposure on JDBC datasources

Each quirk becomes a small YAML file under `overlays/quirks/` describing:
- which schema/path/property it affects
- what description, example, or x-extension to inject
- which version(s) it applies to

#### Curated operational descriptions (the manual layer's real value)
The harvested descriptions are accurate but Oracle-flavored ("returns the
list of currently running Applications"). The manually written ones add
operational guidance ("include `excludeFields=serverClasspath` when listing
collections to avoid 100KB payloads"). For 4d, define a merge policy:

- Default: harvested description.
- If an overlay file in `overlays/descriptions/<schema>.yaml` provides an
  override for a property, append the overlay note after the harvested text
  rather than replacing it. Format:
  > "{harvested description}\n\n**Operational note:** {overlay text}"

Keep both Oracle's text (for accuracy) and our notes (for usefulness).

#### Live samples
Every endpoint should reference a live sample from `samples/{version}/...`.
For 4d:
- Define how samples link to schemas (probably via `x-weblogic-sample-paths`
  pointing to files under `samples/`).
- Decide whether samples become OpenAPI `examples` blocks (verbose but
  standard) or stay as separate files (lighter spec, but less
  self-contained).

### Phase 4e — Coverage expansion (session 5+)

With the generator working, add the areas we hadn't covered manually:
JTA, WLDF, work managers, mail sessions, security runtime, JMS
per-destination, deployments, etc. Each is essentially "run the generator
against more MBean YAMLs".

The README `## Project Status and Roadmap` section already lists the
expected expansion areas; they materialize automatically in 4e once the
pipeline (4b + 4c + 4d) is in place.

## Risks and stop conditions

### Risk: generated output is technically correct but unusable
If the harvested YAMLs produce valid OpenAPI that doesn't actually help
clients (too verbose, missing semantic info, duplicates that confuse
tooling), the approach fails. Mitigation: validate output against
real OpenAPI tooling (Swagger UI, openapi-generator-cli for client
generation) at the end of every phase.

### Risk: divergence between Oracle's harvested YAMLs and actual API behavior
The YAMLs are harvested from MBean introspection. The REST API surface
is *generated dynamically from those MBeans at runtime* — but with extra
gates and quirks (CSRF on serverRuntimes, JDBC POST 400, etc.) that exist
at the REST framework level, not at the MBean level. Therefore the YAMLs
will document properties accurately but won't capture REST-level oddities.
Mitigation: keep manual overlays for these (covered in 4d).

### Risk: licensing
Remote Console is UPL 1.0 / Apache 2.0 (verify exact license on the harvested
YAMLs). We're consuming the YAMLs as data, not redistributing them.
Generated OpenAPI is Apache 2.0 like the rest of our repo. Add explicit
attribution to Remote Console in the generated specs and in the README.

### Risk: Phase 4d backlog growing unmanageable
Every new edge case discovered during 4a/4b/4c gets dropped into 4d.
Mitigation: before starting 4d, triage the list. Some items may be
trivial (sibling description on $ref) and some may not be worth doing
(restart-needed semantic on runtime beans is harmless). The exhaustive
list above is a checklist, not a mandate to implement every item.

### Stop conditions
- If 4a shows the generated schema is significantly worse than hand-written,
  stop and reassess. Don't pour more work into a bad approach.
- If license review reveals constraints, stop and consult before publishing.
- If Oracle dramatically changes the harvested YAML format in a future
  release, the generator may need ongoing maintenance — accepted risk.

## Narrative impact

The repo's character changes from "manually verified spec" to
"transformation of Oracle's internal catalog into open standard format
+ empirical validation layer".

This is more honest given the discovery and arguably more useful to the
ecosystem. Manual contributions stay valuable: quirks, samples,
operations, and the transformer itself.

LinkedIn post #2 narrative becomes: "I was hand-writing an OpenAPI
spec for WebLogic when I noticed Oracle's open-source Remote Console
already contains the catalog Oracle wouldn't publish as OpenAPI. I built
a transformer. The result is a spec that's both more complete and more
maintainable than what I was producing manually." This is a stronger
post than the one we had drafted.

## License attribution

Add to README and to every generated spec file:

> Schema definitions in this specification are derived from
> Oracle WebLogic Remote Console's harvested MBean YAMLs
> (https://github.com/oracle/weblogic-remote-console),
> licensed under the Universal Permissive License (UPL) 1.0.
> Manual overlays, operations definitions, quirks documentation,
> validation samples, and the transformation tooling itself are
> copyright the contributors of this project, licensed under
> Apache License 2.0.
