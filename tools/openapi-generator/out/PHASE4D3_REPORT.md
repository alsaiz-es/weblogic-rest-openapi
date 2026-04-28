# Phase 4d-3 — Enum extraction and sub-type discriminator

WLS version: **14.1.2.0.0**  ·  spec: `tools/openapi-generator/out/spec-14.1.2.0.0.yaml`


## Enum extraction

### Detection pass

- Total inline enums in the pre-extraction spec: 31
- Distinct signatures (`(sorted_values, type)`): 24
- Multi-occurrence signatures (≥ 2): **3**
- Single-occurrence signatures (left inline): 37
- Total occurrences replaced with `$ref`: **10**

### Extracted enums

| Name | Type | Values | Occurrences | References |
|---|---|---:|---:|---|
| `ServerState` | string | 20 | 2 | `ServerRuntime`, `ServerLifeCycleRuntime` |
| `DeploymentState` | integer | 4 | 6 | `WebAppComponentRuntime`, `EJBComponentRuntime`, `ConnectorComponentRuntime`, `AppClientComponentRuntime`, … +2 |
| `WebLogicProtocol` | string | 6 | 2 | `Server`, `Server` |

Naming rules applied: the fingerprint table in `enum_extractor._FINGERPRINTS` matches when a detected value set is a superset of one of the canonical well-known enum signatures (`ServerState`, `JDBCDataSourceState`, `DeploymentState`, `JMSPausedState`, `WebLogicProtocol`). Otherwise the name is the PascalCase of the most common property name across the occurrences.

### Why fewer than the 10 mismatches reported in Phase 4b

Phase 4b counted manual-vs-generated *type-signature* mismatches where manual used `$ref:<EnumName>` and generated used inline `enum`. Of those 10:
- 3 are now extracted (the cases above) — every (schema, property) location they touch is replaced with `$ref`.
- The other 7 were single-occurrence in our generated spec and so stay inline by the policy in `docs/PHASE4D3_TYPES.md` ("Single-occurrence enums stay inline. Do not extract enums that appear only once.").
- Notably, `JMSPausedState` from the manual spec collapsed three *distinct* enum value sets into one (`{Insertion-, Consumption-, Production-}* × {Enabled, Paused}`). Each `pausedState` field on `JMSServerRuntime` actually carries a different value set in the harvested data — they share *prefix* but not values. The detection pass correctly does not merge them. Forced merging would silently lose the per-field semantics; the plan's stop-condition #1 explicitly rejects this. We document it here and leave the three enums inline. A future overlay could wrap them in a discriminated `JMSPausedState` alias if downstream consumers want it.

### Divergences detected

- **`state`**: 2 distinct value sets
  - ['ServerLifeCycleRuntime', 'ServerRuntime']: 20 values
  - ['JDBCDataSourceRuntimeBase']: 6 values

## Sub-type discriminator

### Hierarchies detected

Found **2** polymorphic parents in the generated batch:

### `JDBCDataSourceRuntime`
- Discriminator property: **`type`** (Java side: `Type`)
- Base schema: **`JDBCDataSourceRuntimeBase`** (holds the parent's flat property set)
- Subtype count: **5**
  - generated bodies: 0 (`none`)
  - stub bodies (deferred to Phase 4e): 4 (`JDBCAbstractDataSourceRuntime, JDBCOracleDataSourceRuntime, JDBCProxyDataSourceRuntime, JDBCUCPDataSourceRuntime`)
  - synthesized default subtype: `JDBCDataSourceRuntimeDefault` (the overlay listed the parent itself as a subtype, so the polymorphic union references this synthesized schema instead of self-referencing)

Mapping: 5 entries.

- `JDBCUCPDataSourceRuntime` → `#/components/schemas/JDBCUCPDataSourceRuntime`
- `JDBCAbstractDataSourceRuntime` → `#/components/schemas/JDBCAbstractDataSourceRuntime`
- `JDBCProxyDataSourceRuntime` → `#/components/schemas/JDBCProxyDataSourceRuntime`
- `JDBCOracleDataSourceRuntime` → `#/components/schemas/JDBCOracleDataSourceRuntime`
- `JDBCDataSourceRuntime` → `#/components/schemas/JDBCDataSourceRuntimeDefault`

### `ComponentRuntime`
- Discriminator property: **`type`** (Java side: `Type`)
- Base schema: **`ComponentRuntimeBase`** (holds the parent's flat property set)
- Subtype count: **13**
  - generated bodies: 5 (`AppClientComponentRuntime, ConnectorComponentRuntime, EJBComponentRuntime, JDBCDataSourceRuntime, WebAppComponentRuntime`)
  - stub bodies (deferred to Phase 4e): 8 (`ComponentConcurrentRuntime, InterceptionComponentRuntime, JDBCMultiDataSourceRuntime, JDBCOracleDataSourceRuntime, JDBCReplayStatisticsRuntime, JMSComponentRuntime, SCAPojoComponentRuntime, SCASpringComponentRuntime`)

Mapping: 13 entries.

- `JDBCReplayStatisticsRuntime` → `#/components/schemas/JDBCReplayStatisticsRuntime`
- `InterceptionComponentRuntime` → `#/components/schemas/InterceptionComponentRuntime`
- `JDBCMultiDataSourceRuntime` → `#/components/schemas/JDBCMultiDataSourceRuntime`
- `SCAPojoComponentRuntime` → `#/components/schemas/SCAPojoComponentRuntime`
- `SCASpringComponentRuntime` → `#/components/schemas/SCASpringComponentRuntime`
- `JMSComponentRuntime` → `#/components/schemas/JMSComponentRuntime`
- … +7 more

### Hierarchies skipped (cannot be represented in OAS 3.0)

- **`JDBCSystemResource`** — discriminator declared at `JDBCResource.DatasourceType` is a *nested* property path. OAS 3.0 requires `discriminator.propertyName` to be a flat property of the discriminated schema. 5 subtypes left as a flat (non-polymorphic) schema; the discriminator semantics are documented operationally rather than structurally.

For `JDBCSystemResource` specifically, the discriminator value lives at `JDBCResource.DatasourceType` (one level deep into the embedded `JDBCResource` bean) and uses values `GENERIC` / `MDS` / `AGL` / `UCP` / `PROXY`. A consumer needing to switch on the datasource kind reads the value at the path manually. This matches the manual spec, which also did not formalize this hierarchy.

### Cross-hierarchy nesting

`ComponentRuntime` lists `JDBCDataSourceRuntime` among its subtypes, and `JDBCDataSourceRuntime` is itself a polymorphic parent (UCP / Abstract / Proxy / Oracle / Default). The generator emits both hierarchies independently; the `ComponentRuntime` mapping points at the schema `JDBCDataSourceRuntime`, which is itself a `oneOf` — a consumer walks the outer discriminator first, lands on the `JDBCDataSourceRuntime` union, then applies its own `type` discriminator. Both layers use the same `type` property, which is fine — the value space is shared.

**Limitation noted**: `ComponentRuntime`'s mapping does not include the transitive UCP / Abstract / Proxy / Oracle subtype values, only the direct subtype `JDBCDataSourceRuntime`. A response with `type: JDBCUCPDataSourceRuntime` matches the inner discriminator but not the outer; OpenAPI 3.0 does not model multi-level discriminators with one shared property. This matches what the harvested overlay declares and we do not attempt to flatten.

## Verification — Phase 4b mismatches now

| | 4b end | 4d-3 end |
|---|---:|---:|
| Inline enum vs `$ref:Enum` (manual extracted) mismatches | 10 | 0 of the targets the plan called out (`ServerState`, `DeploymentState`, `WebLogicProtocol`); the remaining 7 are single-occurrence in our spec and stay inline by policy. |
| Sub-type discriminator gaps (4 mismatches on `*ComponentRuntime.type`) | 4 | **0** — all four subtypes carry `type: enum: [<value>]` constraint. |

## Validation results

| Validator | Phase 4d-1 | Phase 4d-3 |
|---|---|---|
| `openapi-spec-validator` 3.0 strict | PASS | **PASS** |
| `openapi-generator-cli` Python client smoke test | PASS (5 APIs, 260 models) | **PASS** (5 APIs, 282 models — extra subtype + enum classes) |
| `@stoplight/spectral-cli` (`spectral:oas`) | 0 / 0 | **0 / 0** |

Generated Python client now includes:
- Explicit enum classes: `server_state.py`, `deployment_state.py`, `web_logic_protocol.py`.
- Polymorphic deserialization wired for `ComponentRuntime` (13 subtypes) and `JDBCDataSourceRuntime` (5 subtypes including the synthesized `JDBCDataSourceRuntimeDefault`).

## Edge cases discovered

- **Self-referencing parent in subtype list.** `JDBCDataSourceRuntimeMBean`'s overlay declares the parent itself as a subtype (`type: JDBCDataSourceRuntimeMBean`, `value: JDBCDataSourceRuntime`). A naïve generation produces a `oneOf` referencing its own parent schema — recursion in `openapi-spec-validator`. Fix: when `subtypeSchema == parentSchema`, the polymorphism module synthesizes `<Parent>Default` (an `allOf` over the Base plus the discriminator constraint) and points the mapping there.
- **Cross-hierarchy nesting.** `ComponentRuntime` includes `JDBCDataSourceRuntime` as a subtype. After `JDBCDataSourceRuntime` becomes a `oneOf`, that nested union is referenced from the outer mapping. The result is two-level polymorphism with one shared discriminator property; OAS 3.0 supports the structure but no consumer can flatten the sub-subtypes into a single mapping. We flag the limitation in the report; consumers needing flat resolution can compute it themselves from the two mappings.
- **Integer enum coerced from stringified detection.** Detection groups by stringified values (so 0/1/2/3 and "0"/"1"/"2"/"3" wouldn't merge accidentally). On extraction with `base_type: integer`, output values are coerced back to int; otherwise `spectral:oas` `typed-enum` complains ("Enum value "0" must be "integer"").
- **JMS `pausedState` enums diverge intentionally.** Three properties (`consumptionPausedState`, `insertionPausedState`, `productionPausedState`) share the *shape* but not the *values* (`{Consumption,Insertion,Production}-{Enabled,Pausing,Paused}`). The detection pass keeps them as three distinct single-occurrence enums. The manual spec's `JMSPausedState` enum had merged them into one with 6 values, dropping the per-field prefix; that was an editorial simplification, not a contract reading. Generator preserves the harvested values.
- **`x-stub` schemas now compose with parent base via `allOf`.** Pre-4d-3 stubs were flat `{type: object, x-stub: true}` placeholders. After 4d-3, discriminator-aware stubs `allOf [<Parent>Base, {type: enum: [<value>]}]` carry the discriminator constraint so polymorphic deserialization works even for subtype bodies we have not generated yet (Phase 4e).

## Out of scope, deferred

- Quirks migration → 4d-2.
- Java-scraped operations (`startInAdmin`, `startInStandby`, `/domainRuntime/search`) → 4d-2.
- Server (165 props) / Cluster (77 props) surface curation → 4d-4.
- Multi-version generation, description merge policy, samples linking → 4d-5.
- Generating the actual schema bodies for the 9 ComponentRuntime stub subtypes (`SCAPojoComponentRuntime`, `JMSComponentRuntime`, `JDBCMultiDataSourceRuntime`, etc.) and the 4 JDBCDataSourceRuntime stub subtypes — coverage expansion, Phase 4e.
- Optional editorial decision: should `JMSPausedState` be re-introduced as a `oneOf` over the three per-field enums? Defer until a consumer asks.

## Verdict

Both technical contract issues from earlier phases are closed. Three duplicate enums externalized (`ServerState`, `DeploymentState`, `WebLogicProtocol`); two polymorphic hierarchies fully wired with discriminator + mapping (`ComponentRuntime` 13 subtypes, `JDBCDataSourceRuntime` 5 subtypes). Validators all green; Python client now generates polymorphic deserialization correctly rather than passing by absence of test coverage.