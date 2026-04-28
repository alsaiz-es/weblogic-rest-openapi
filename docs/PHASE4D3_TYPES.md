# Phase 4d-3 — Enum extraction and sub-type discriminator

## Goal

Close the two remaining technical contract issues from earlier phases:

1. **Enum extraction.** The 10 inline enums identified in Phase 4b that
   our manual spec had externalized as named schemas (`ServerState`,
   `JDBCDataSourceState`, `DeploymentState`, `JMSPausedState`, etc.) need
   to live in `components/schemas/` as named types and be referenced
   from every property that uses them.

2. **Sub-type discriminator.** The `oneOf` retrofit applied to
   `ComponentRuntime` in Phase 4d-1 silenced the unused-component
   warning but the deserialization contract is incomplete — there is no
   `discriminator` declaration, so a client receiving a polymorphic
   payload cannot decide which subtype to instantiate.

After 4d-3, the generated spec deserializes polymorphic payloads correctly
and shares enum types across schemas. The Python smoke test continues
passing not just by chance but because the contract is sound.

## Out of scope for 4d-3

- Quirks migration → 4d-2
- Server / Cluster surface curation → 4d-4
- Multi-version, description merge policy, samples linking → 4d-5
- Java scraping for `startInAdmin` / `startInStandby` → 4d-2
- `/domainRuntime/search` virtual endpoint → 4d-2
- Any new editorial decisions about which enums to share or which
  hierarchies to model — only the cases identified in earlier reports

If something out-of-scope becomes blocking, document it and defer.

## Tasks

### 1. Enum extraction

#### Detection pass

Walk every emitted schema looking for inline enums on string-typed
properties. For each enum:

- Compute a stable signature: sorted tuple of `(values, type)`.
- Build an inverse index `signature → list of (schema_name, property_name)`.

Any signature that appears in **two or more** distinct
`(schema, property)` locations is a candidate for extraction.

#### Naming policy

A shared enum must have a stable, predictable name. Rules:

- If all occurrences share the same property name, the enum name is the
  PascalCase form of that property name. Example: `state` appearing on
  `ServerRuntime`, `JDBCDataSourceRuntime`, etc. → enum name `State`.
  But this collides with too-generic names; resolve by suffixing the
  conceptual category.
- Apply this concrete naming table for the cases identified in earlier
  phases:

  | Property occurrences | Enum name |
  |---|---|
  | `state` on `ServerRuntime`, `ServerLifeCycleRuntime`, … | `ServerState` |
  | `state` on `JDBCDataSourceRuntime`, `JDBCConnectionPool…` | `JDBCDataSourceState` |
  | `activeVersionState`, `state` on `ApplicationRuntime`, `ComponentRuntime`, … | `DeploymentState` |
  | `pausedState` on `JMSDestinationRuntime`, `JMSServerRuntime`, … | `JMSPausedState` |
  | `healthState.state` (within the `HealthState` schema only) | leave inline; it is already inside a named schema |
  | Any other duplicated enum | name = PascalCase(property) — e.g. `consumptionPausedState` → `ConsumptionPausedState` |

- Single-occurrence enums stay inline. Do not extract enums that appear
  only once.

- If the harvested + overlay layers produce diverging value sets for what
  is conceptually the same enum across schemas, **do not merge**. Treat
  them as different enums and report the divergence in the phase report.
  Forced merging would silently lose values.

#### Extraction pass

For every signature with ≥2 occurrences:

1. Create a named schema under `components/schemas/<EnumName>` with
   `type: string` and the sorted enum values.
2. Replace every inline occurrence with `{ $ref: '#/components/schemas/<EnumName>' }`.
3. If the original property had a `description`, `default`, `readOnly`,
   `deprecated`, or `x-*` extension, wrap the `$ref` with
   `allOf: [{$ref: ...}]` plus the sibling fields, following the same
   pattern already used for `overallHealthState` in earlier phases.
4. Preserve enum description/title from the harvested or overlay source
   if available; otherwise leave the schema description empty.

#### Verification

- Re-run the comparison from Phase 4b: the 10 inline-vs-$ref mismatches
  should drop to **0** for the enum types we externalize. Any remaining
  mismatch must be a case the report explicitly justifies (e.g. the
  enum was declared with different value sets at the source).
- The Python smoke test must still PASS. If client generation now
  produces a richer set of enum classes, that is the expected outcome.

### 2. Sub-type discriminator

#### Background recap

Phase 4d-1 turned `ComponentRuntime` into a `oneOf` over its base plus
four subtypes (`WebAppComponentRuntime`, `EJBComponentRuntime`,
`ConnectorComponentRuntime`, `AppClientComponentRuntime`). The schema is
valid OpenAPI 3.0 but the discriminator is missing, so a client cannot
mechanically select the subtype. Today it works on the smoke test
because nothing in the generator's tests actually deserializes a
polymorphic payload.

The discriminator metadata exists in the UI overlay layer of the parent
MBean: `resources/.../ComponentRuntimeMBean/type.yaml` declares
`subTypeDiscriminatorProperty: type` (or similar) and a `subTypes:` map
listing each concrete type with its discriminator value.

#### Detection pass

For every parent MBean, look for an overlay file at
`/tmp/wrc/resources/src/main/resources/<MBeanName>/type.yaml`. If it
declares both `subTypeDiscriminatorProperty` and `subTypes:`, this is a
polymorphic hierarchy. Capture:

- discriminator property name (`type` for `ComponentRuntime`; verify in
  the actual file).
- mapping of discriminator value → bean type FQN.
- After name normalization (`MBean` stripping), produce the OpenAPI
  mapping value → schema name.

#### Generation pass

For each polymorphic parent:

1. Define the parent schema as `oneOf: [<list of subtypes>]` plus
   `discriminator: { propertyName: <prop>, mapping: { <val>: '#/components/schemas/<sub>', … } }`.
2. Each subtype schema must have the discriminator property as a
   required string with `enum: [<value>]` (single-element enum).
   This is needed because OpenAPI's discriminator semantics expect the
   subtype to constrain the discriminator value.
3. The subtype schemas inherit the parent's properties via `allOf:
   [{$ref: '#/components/schemas/<Parent>'}, {<subtype-specific
   properties>}]` if the subtype actually adds properties; otherwise
   `allOf` containing just the parent ref plus the discriminator
   constraint.

#### Specific case — ComponentRuntime

Verify:

- `subTypeDiscriminatorProperty` is `type` (per harvested observations).
- `subTypes` lists at minimum `WebAppComponentRuntime`,
  `EJBComponentRuntime`, `ConnectorComponentRuntime`,
  `AppClientComponentRuntime`. If the overlay declares more types not
  present in our generated batch (likely — there is also
  `WebServiceComponentRuntime` and others), include them in the mapping
  but emit a placeholder schema with the discriminator constraint and
  flag in the report as "subtype declared, schema body deferred to 4e
  coverage expansion".

The `type` property's discriminator constraint enum supersedes the
manual spec's `enum: [WebAppComponentRuntime]` form. The four mismatches
identified in the Phase 4b report should be resolved.

#### Other polymorphic hierarchies

Apply the same detection across all generated parent schemas. Likely
candidates beyond `ComponentRuntime` (verify by scanning the overlays):

- `RuntimeMBean` itself? — no, this is the root abstract type, not a
  discriminated union in the REST sense.
- Anything ending in `Runtime` with subtypes is suspect; let the
  detection pass identify them.

If the detection pass reveals polymorphic hierarchies the manual spec
did not document, treat them as new coverage and emit the discriminator
correctly. Report each new hierarchy in the phase report.

### 3. Validation

After both passes:

- `openapi-spec-validator` strict — must remain PASS.
- `openapi-generator-cli generate -g python` smoke test — must remain
  PASS. The generated client should now have:
  - Enum classes for `ServerState`, `JDBCDataSourceState`,
    `DeploymentState`, `JMSPausedState`, and any others the detection
    pass found.
  - Polymorphic deserialization wired correctly for `ComponentRuntime`
    (the generated Python code should include the discriminator logic).
- `spectral lint` — should remain at 0 errors and 0 warnings (or report
  any new warnings introduced by the changes).

### 4. Report

`tools/openapi-generator/out/PHASE4D3_REPORT.md`:

- Detection pass results: list of enum signatures found, occurrence counts,
  whether each was extracted or kept inline (with reason).
- Extraction outcome: enums extracted with their final names, locations
  where each is now referenced.
- Polymorphic hierarchies detected: parent schema, discriminator property,
  subtype mapping. Note any subtypes referenced but with deferred schema
  bodies.
- Verification: count of inline-vs-$ref mismatches before / after (should
  drop to 0 or near-0 for the targeted cases).
- Validation results.
- Edge cases discovered.
- Anything deferred to later sub-phases that surfaced during this work.

### 5. Commit

On the same branch (`feat/openapi-generator`), commit with message:

```
feat(generator): Phase 4d-3 — enum extraction and sub-type discriminator

Closes the two remaining technical contract issues from earlier phases.

Enum extraction: enums appearing in ≥2 (schema, property) locations are
now externalized as named schemas under components/schemas/ and referenced
via $ref. Includes ServerState, JDBCDataSourceState, DeploymentState,
JMSPausedState, and any other duplicates discovered by the detection
pass. Single-occurrence enums remain inline.

Sub-type discriminator: polymorphic hierarchies now declare an OpenAPI
discriminator with a complete mapping. ComponentRuntime resolves to
WebApp/EJB/Connector/AppClient subtypes (plus any additional subtypes
declared in the overlay but not yet generated, flagged for 4e). Subtype
schemas constrain the discriminator property via single-element enum,
matching OpenAPI 3.0 polymorphism semantics.

The Python client smoke test continues passing, this time with correct
polymorphic deserialization rather than by absence of test coverage.
```

Do not push yet. Wait for review of the report.

## Stop conditions

- Enum detection produces signatures that look wrong (e.g. accidentally
  merging two semantically different enums because they happen to share
  values) → stop and report; the naming policy may need to be refined.
- Discriminator detection finds hierarchies the generator can't represent
  cleanly (e.g. a subtype that declares conflicting parent properties)
  → stop and report.
- Python smoke test starts failing after discriminator addition → stop;
  the discriminator wiring may be syntactically valid but semantically
  wrong for `openapi-generator-cli`.
- After both passes, the generated spec grows pathologically (e.g. the
  `oneOf` constructs explode beyond a sensible size) → stop and report.

## Editorial notes

- Enum extraction is mechanical. The naming policy table is the only
  place where editorial judgment enters. Do not invent enum names
  beyond what the table prescribes; defer hard cases to a follow-up
  decision.
- Sub-type discriminator is contract-level. Once correct, downstream
  consumers benefit immediately. The case for prioritizing this over
  quirks migration was: contract correctness compounds, editorial
  polish does not.
- This sub-phase does not touch quirks (`overlays/quirks/`),
  curated descriptions, or surface curation. Resist the temptation to
  fix unrelated issues even if obvious — those have their own sub-phase.
