# Phase 4d-5 — Multi-version generation

## Goal

Run the generator across all five WLS versions present in the harvested
YAMLs, producing one OpenAPI specification per version, and document the
cross-version differences that emerge.

After 4d-5, the branch's promise of multi-version coverage matches the
manual spec's claim ("verified against 12.2.1.4 and 14.1.2") and
extends it to the three additional versions Oracle ships
(12.2.1.3, 14.1.1, 15.1.1).

## Out of scope for this sub-phase

The original PHASE4_GENERATOR.md plan grouped multi-version,
description merge policy, and live samples linking under a single
"4d-5". Splitting them:

- **Description merge policy** (harvested base + curated operational
  notes appended) → deferred to a follow-up sub-phase if needed.
- **Live samples linking** (referencing files under `samples/` from the
  spec) → deferred similarly.
- **Server / Cluster surface curation** → still 4d-4.
- **Coverage expansion to JTA/WLDF/work managers** → still 4e.

This sub-phase focuses only on multi-version generation. The reasons
given when planning this order:

- Multi-version is the most visible promise broken by the branch
  today (the first LinkedIn post explicitly cited cross-version
  validation).
- It is pipeline work, not editorial.
- Running the generator across five versions is the most efficient
  way to surface structural problems with the generator (different
  shapes between versions, missing MBeans, divergent overlays) before
  investing in editorial sub-phases.

## Tasks

### 1. Generator orchestration for multiple versions

The generator already accepts a `wls_version` argument. Wire it so a
single invocation produces all five outputs:

- `tools/openapi-generator/out/spec-12.2.1.3.0.yaml`
- `tools/openapi-generator/out/spec-12.2.1.4.0.yaml`
- `tools/openapi-generator/out/spec-14.1.1.0.0.yaml`
- `tools/openapi-generator/out/spec-14.1.2.0.0.yaml`
- `tools/openapi-generator/out/spec-15.1.1.0.0.yaml`

`info.version` per spec carries the WLS version. `info.title` mentions
the version explicitly so Swagger UI tabs are distinguishable.

Quirks overlay `applies_to_versions` honored — a quirk only injects
into versions listed in its overlay. Spot-check at least one quirk
that should differ across versions (e.g. quirk 11 about edit error
envelope FQCN strip, which behaves differently on 12.2.1.4 vs 14.x).

### 2. Per-version validation

Each generated spec must independently pass:

- `openapi-spec-validator` strict.
- `openapi-generator-cli generate -g python` smoke test.
- `spectral lint` 0/0.

If any version fails validation while another passes, that is a
finding worth investigating — likely a harvested MBean shape that
differs structurally in that version. Stop and report rather than
papering over.

### 3. Cross-version diff

For each pair (12.2.1.3 vs 12.2.1.4, 12.2.1.4 vs 14.1.1, 14.1.1 vs
14.1.2, 14.1.2 vs 15.1.1), compute:

- Schemas added / removed / changed.
- Properties added / removed within shared schemas.
- Type changes on shared properties.
- Path additions / removals.
- Quirks injected vs not injected per version (driven by overlay
  `applies_to_versions`).

Output: `tools/openapi-generator/out/VERSION_DELTAS.md` with a
section per pair, intended for human reading. Do not try to be
exhaustive — focus on changes that a WebLogic admin migrating between
versions would care about (new properties on existing beans, new
collections, deprecations).

### 4. README update on the branch

Adjust `README.md` (on the branch only, do not touch main yet) to:

- Replace any "verified against 14.1.2" wording with "generated for
  12.2.1.3, 12.2.1.4, 14.1.1, 14.1.2, 15.1.1".
- Add a brief paragraph explaining how to consume a specific version
  spec (`out/spec-<version>.yaml`).
- Link `VERSION_DELTAS.md` from the README.

Do not yet update the manual `specs/` directory — that decision belongs
to the merge-to-main conversation, not to 4d-5.

### 5. Report

`tools/openapi-generator/out/PHASE4D5_REPORT.md`:

- Per-version: generation result, validation result, schema count,
  path count, operation count.
- Cross-version diff summary (high-level numbers; details in
  `VERSION_DELTAS.md`).
- Quirks injected per version (table — quirk × version → injected/skipped).
- Edge cases discovered (especially: any version where a structural
  generator assumption broke).
- Anything deferred to future sub-phases.

### 6. Commit

On the same branch (`feat/openapi-generator`), commit:

```
feat(generator): Phase 4d-5 — multi-version generation

Generates one OpenAPI specification per supported WLS version
(12.2.1.3, 12.2.1.4, 14.1.1, 14.1.2, 15.1.1) from the harvested YAMLs
of each version directory. Quirks overlays honor applies_to_versions
so version-specific quirks inject only where they apply.

Cross-version diffs documented in tools/openapi-generator/out/VERSION_DELTAS.md
covering schema additions/removals/changes, property changes, path
changes, and quirk-injection differences across the four version pairs.

All five generated specs pass openapi-spec-validator strict, the
openapi-generator-cli Python smoke test, and spectral lint 0/0.

README on the branch updated to reflect the multi-version scope.
The manual specs/ directory remains untouched — its fate is part of
the merge-to-main conversation, not of this sub-phase.

Description merge policy and live samples linking remain pending in
follow-up sub-phases. Server / Cluster surface curation remains 4d-4.
```

Do not push yet. Wait for review of the report.

## Stop conditions

- A version fails validation while others pass → stop and report; the
  generator may have a version-specific structural assumption.
- Cross-version diffs are pathologically large (e.g. thousands of
  property differences between adjacent patch versions like 14.1.1 and
  14.1.2) → stop; either the diff algorithm is wrong or the harvested
  YAMLs encode something we are not handling.
- Quirks overlay `applies_to_versions` filtering misbehaves (a quirk
  meant for 14.x leaks into 12.x or vice versa) → stop and fix the
  filtering logic before continuing.

## Editorial notes

- This sub-phase is mechanical. The interesting outputs are
  `VERSION_DELTAS.md` and any structural surprises in the report.
- Cross-version diffs are useful documentation in their own right — a
  WebLogic admin contemplating an upgrade benefits from seeing what
  the REST API surface gained or lost. Treat `VERSION_DELTAS.md` as a
  small public deliverable, not just a generator artifact.
- After 4d-5, the natural next decision points are:
  1. 4d-4 (Server/Cluster surface curation) — editorial.
  2. Merge to main — strategic.
  3. 4e (coverage expansion to JTA, WLDF, etc.) — scope expansion.
  Any of the three is defensible; none is forced by 4d-5's outcome.
