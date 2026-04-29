# Phase 4e-3 — Body fidelity for the 12 polymorphic stubs

## Goal

Provide manual body definitions for the 12 polymorphic subtypes that
Oracle's UI overlay declares but for which no harvested YAML exists.
These currently emit as stubs (the discriminator wiring is correct,
but the body is empty).

After 4e-3, the deserialization contract is end-to-end complete: a
client receiving a polymorphic payload not only acquires the right
subtype but can also deserialize the subtype's properties.

Alfredo's choice for this sub-phase: option C — full manual authoring
of all 12 subtypes.

## Out of scope

- Empirical validation of the manual bodies against running WebLogic
  instances. The bodies will be best-effort from public sources.
- Subsystems not represented by these 12 subtypes. They keep harvested
  content if 4e-2 covered them, harvested-only otherwise.
- Adding new polymorphic hierarchies beyond what 4d-3/4e detected.

## The 12 subtypes

Reported by 4e: subtypes declared in the Remote Console UI overlay
under `subTypeDiscriminatorProperty` + `subTypes` but absent from the
harvested YAML set. Approximate list (verify against 4e report):

- OAMAuthenticator (security domain)
- JMSQueueRuntime, JMSTopicRuntime, JMSDistributedQueueRuntime,
  JMSDistributedTopicRuntime (JMS detail)
- JDBCProxyDataSourceRuntime, JDBCUCPDataSourceRuntime,
  JDBCAbstractDataSourceRuntime, JDBCOracleDataSourceRuntime (JDBC
  variants)
- Plus 3-4 more covering specialized cases.

The exact count is 12 per the 4e report. Verify that list at the
start of this sub-phase before authoring.

## Sources for manual authoring

In rough order of preference:

1. **Oracle MBean Reference Javadoc HTML.** Oracle publishes Javadoc
   for the public MBean interfaces under
   `https://docs.oracle.com/en/middleware/standalone/weblogic-server/<version>/wlmbr/`.
   This is the most authoritative source for property names and types.
2. **Oracle public documentation.** WebLogic Administrator's Guide and
   subsystem-specific manuals describe what these MBeans expose.
3. **Empirical observation.** Where samples exist in `samples/`,
   they show real shapes that should match what we author.
4. **Oracle Remote Console source code.** The repo at
   `oracle/weblogic-remote-console` may have references to subtype
   properties even when the harvested YAML is missing.

Each authored body should include attribution to the source used,
either in the spec via `x-weblogic-source` extension or in the
generator's manual schema overlay file.

## Format

Manual schemas live in `overlays/manual-schemas/<SubtypeName>.yaml`.
The structure is a partial OpenAPI component schema:

The generator merges manual schemas into the spec the same way it
treats overlays — applied after harvested generation, before quirks
and descriptions, with the discriminator constraint enum already
present from 4d-3 preserved.

Per subtype:

- `properties` block listing manually authored properties with name,
  type, format, description.
- Inherits from parent via `allOf: [$ref to parent]` (the discriminator
  parent) — this part the generator emits automatically based on the
  discriminator wiring; manual schemas only contribute additional
  property bodies.
- `x-weblogic-manual-schema: true` marker so consumers know this
  body wasn't harvested.
- `x-weblogic-source` listing the source(s) used.

## Tasks

### 1. Verify the 12-subtype list

Re-read the 4e report and confirm the exact 12 subtypes. List by
discriminator parent and subtype name.

### 2. Source authoring per subtype

For each subtype, in priority order (JMS detail first since it's also
the most demanded):

1. Locate the source(s).
2. Author the property list. Aim for the user-facing properties
   (typical operator queries and modifications), not internal-only.
3. Type each property. Java types map to OpenAPI types per the
   conventions established in earlier phases.
4. Description per property. Best-effort but honest about source.
5. Save under `overlays/manual-schemas/<SubtypeName>.yaml`.

Aim for 5-15 properties per subtype. If a subtype has no public source
documenting properties, document it as "manual body deferred — no
public source" and leave the stub.

### 3. Generator pipeline change

Extend the generator to load `overlays/manual-schemas/*.yaml` after
harvested schema generation and before discriminator wiring runs.
Manual schemas merge into the existing stub schemas (which carry the
discriminator constraint), preserving:

- The discriminator property's `enum: [<value>]` constraint.
- The `allOf [<Parent>]` inheritance.
- Any quirks targeting the subtype.

Manual property additions append to whatever the stub already had.

### 4. Validation

- `openapi-spec-validator` strict — must remain PASS.
- `openapi-generator-cli generate -g python` smoke test — must remain
  PASS. Generated client now has real property classes for the 12
  subtypes instead of empty marker classes.
- `spectral lint` — must remain at 0 errors.

### 5. Polymorphic deserialization smoke test

Beyond the basic client smoke test, generate a small Python script
that:

- Creates an instance of each of the 12 subtypes via the generated
  client's model classes.
- Serializes to JSON.
- Deserializes back via the discriminator.

The point is to verify the discriminator wiring round-trips correctly
with non-empty bodies. The client generation should produce code that
handles this; the smoke script just confirms it.

If the round-trip fails for any subtype, the discriminator
constraint's enum value or the manual body structure has an issue —
fix and re-test.

### 6. Report

`tools/openapi-generator/out/PHASE4E3_REPORT.md`:

- The 12 subtypes confirmed list.
- Per subtype: properties authored, source(s) used, validation result.
- Subtypes where no public source was found and manual body deferred.
- Total properties added across all 12.
- Validation results.
- Round-trip smoke test results per subtype.
- Edge cases.

### 7. Commit

On `feat/openapi-generator`. Commit message: "feat(generator):
Phase 4e-3 — manual bodies for 12 polymorphic stubs". After commit,
update `REMAINING_WORK.md`.

## Stop conditions

- A subtype has no public source and manual authoring would be pure
  invention → stop authoring that subtype, document, leave as stub.
- The manual schema format breaks discriminator wiring → stop, fix
  the merge logic before continuing.
- Round-trip smoke fails for multiple subtypes → stop, the issue is
  systemic not per-subtype; debug before more authoring.
- Manual authoring is producing low-quality content (forced
  speculation, unclear types) → stop early, document incomplete
  state, accept the partial result rather than ship low-quality.

## Editorial notes

- This sub-phase is bonus polish. The core spec functions correctly
  with stubs. Don't sacrifice quality for completeness.
- Manual schemas are honest about provenance via the
  `x-weblogic-manual-schema` and `x-weblogic-source` extensions. A
  client that wants to filter out "not from harvested" can do so.
- For the JMS subtypes (queues, topics), Oracle's MBean Reference
  is fairly complete. For the security and JDBC variant subtypes,
  sources may be sparser — accept incomplete bodies and document.
- This is the only sub-phase where output quality is below harvested
  quality by design. Be transparent about that in the spec
  description.
