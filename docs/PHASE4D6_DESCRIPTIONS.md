# Phase 4d-6 — Description merge policy

## Goal

Migrate operational notes from the manual `specs/` directory and from
ad-hoc curated content into structured `overlays/descriptions/<schema>.yaml`
files. The generator appends those notes to harvested descriptions.

After 4d-6, every schema where the manual layer added operational guidance
beyond Oracle's harvested description carries that guidance in the
generated spec.

## Out of scope

- Curation of subsystems newly covered by 4e bulk (deployments, JMS
  detail, work managers, JTA, WLDF). Those go in 4e-2.
- Quirks: already migrated in 4d-2.

## Format

Each schema may have an overlay file at
`overlays/descriptions/<schema>.yaml`. The structure is:

The file has top-level `schema` (the schema name post-normalization),
optional `schema_level` block with an `operational_note` field, and
optional `properties` block mapping property names to objects with
their own `operational_note` field. The note text supports markdown.

The generator merges by appending `**Operational note:** {text}` after
the existing description, separated by a blank line.

If a property already has its description modified by a quirk overlay
in 4d-2, the description overlay appends after the quirk addition
(chained appends).

## Tasks

### 1. Inventory operational notes in manual specs/

Walk every YAML file under `specs/`. For each schema and property,
identify text in `description:` fields that goes beyond what Oracle's
harvested YAMLs contain. Categories worth migrating:

- Operational guidance (how to use in practice).
- Sample value formats or ranges.
- Cross-property semantics (how this property interacts with another).
- Quirk-adjacent notes that complement existing quirks but add a
  wrinkle worth preserving.

Skip:

- Notes that just paraphrase the harvested description.
- Notes already covered by quirks (avoid duplication).

The output of this task is a draft list, not yet a final overlay file.

### 2. Build overlays from inventory

For each schema where step 1 found content worth preserving, write
`overlays/descriptions/<schema>.yaml`. Apply the format above.

Schemas in scope (the 22 originally curated):

- ServerRuntime, ThreadPoolRuntime, JVMRuntime
- JDBCServiceRuntime, JDBCDataSourceRuntime
- ApplicationRuntime, ComponentRuntime + 4 subtypes
- ServerChannelRuntime
- JMSRuntime, JMSServerRuntime
- Server, Cluster, JDBCSystemResource (+ sub-beans)
- ServerLifeCycleRuntime
- ChangeManager (virtual)

If a schema's manual spec has no operational notes beyond harvested
content, skip — no overlay needed.

### 3. Generator pipeline change

Extend the generator to load `overlays/descriptions/*.yaml` after
quirks injection. Merge order:

1. Harvested description (base).
2. Quirks overlay descriptions (already in pipeline).
3. Description overlay operational notes (new).

Each layer appends a section to the previous, separated by a blank
line.

### 4. Validation

After overlays applied:

- `openapi-spec-validator` strict — must remain PASS.
- `openapi-generator-cli generate -g python` smoke test — must
  remain PASS. Generated docstrings now richer.
- `spectral lint` — should remain at 0 errors. Warnings count
  unchanged.

### 5. Spot-check

Open the generated spec and inspect 5 random schemas with overlays.
Verify:

- Harvested text is preserved verbatim.
- Operational note appears with the `**Operational note:**` prefix.
- If the property has both a quirk and a description overlay, both
  appear in the right order (harvested → quirk → description).

### 6. Report

`tools/openapi-generator/out/PHASE4D6_REPORT.md`:

- List of overlays created (count + per-schema).
- Operational notes migrated (per-schema with property count).
- Notes intentionally skipped (with rationale).
- Validation results.
- Edge cases.

### 7. Commit

On `feat/openapi-generator`. Commit message reflects scope: the 22
curated schemas only, deferring 4e-covered subsystems to 4e-2. After
commit, update `REMAINING_WORK.md` moving 4d-6 from "What remains
pending" to "What is closed".

## Stop conditions

- Generator's overlay pipeline produces text in wrong order or
  duplicate sections → stop and report.
- Spot-check reveals harvested text overwritten instead of appended →
  stop, fix the merge logic.
- Validators turn red after overlay application → stop, the overlay
  format may be malformed.

## Editorial notes

- The unique value of the manual layer is the operational knowledge.
  This sub-phase is what preserves it when the spec source of truth
  shifts to the generator.
- Quirks vs description overlays: a quirk is about anomalous
  behavior (something contradicting Oracle docs). A description
  overlay is about additive guidance (something that complements).
  When in doubt, prefer description overlay over quirk extension.
- Skip aggressively. A note that just paraphrases harvested text adds
  no value and dilutes attention from the notes that matter.
