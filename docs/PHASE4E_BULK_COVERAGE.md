# Phase 4e — Bulk coverage expansion

## Goal

Process every harvested MBean (not just the 22 manually curated ones) so
that every `$ref` in the generated specs resolves to a real schema
instead of an auto-stub.

The objective is **cuantitativa coverage**, not editorial polish. After
4e, the generated spec stops being "22 detailed schemas plus 392 stubs"
and becomes "every MBean Oracle's Remote Console knows about, with the
properties Oracle harvests for it". Curation of which MBeans deserve
richer descriptions, additional examples, or curated operational notes
is an editorial decision that comes after, not before, having the data.

This sub-phase is mechanical execution. The interesting findings will
be the edge cases that surface only when the input set jumps from 22 to
~850 MBeans.

## Out of scope for 4e

- **Editorial curation** of any newly covered subsystem (JTA, WLDF,
  work managers, JMS detail, security, deployments, etc.). Those
  decisions come in follow-up sub-phases after we see what the bulk
  generation produces.
- **Server / Cluster surface curation** (4d-4) — still pending,
  unrelated to bulk coverage.
- **Description merge policy** (curated operational notes appended to
  harvested descriptions) — deferred until we know which schemas
  warrant it.
- **Live samples linking** — deferred similarly.
- **Manual `specs/` directory** — untouched. Its fate remains the
  merge-to-main conversation.

If something out-of-scope becomes blocking, document it and defer.

## Tasks

### 1. Enumerate the full MBean set

For each supported WLS version:

- Walk `/tmp/wrc/weblogic-bean-types/src/main/resources/harvestedWeblogicBeanTypes/<version>/`.
- Collect every `<MBeanName>.yaml` file.
- The resulting set is the input to bulk generation for that version.

Expected counts per version (from the discovery report):

- 12.2.1.3.0 → 857 files
- 12.2.1.4.0 → 859 files
- 14.1.1.0.0 → 856 files
- 14.1.2.0.0 → 831 files
- 15.1.1.0.0 → 845 files

These are upper bounds. Some MBeans may be filtered out as internal,
deprecated, or otherwise unsuitable (the existing `supported: false`,
`excluded: true`, `restInternal: true`, `excludeFromRest: true`
filters apply).

### 2. Run the generator over the full set

Adjust `tools/openapi-generator/src/main.py` (or whatever the
orchestrator entry point is) to accept a `--all-mbeans` flag that
ingests every harvested MBean for the target version, not just the
curated subset.

The existing pipeline (loader → schema_builder → path_builder →
operations → overlays) should already handle this correctly. The 22
curated MBeans were a list, not a constraint built into the generator
logic. Verify this assumption early in the session — if it turns out
the generator has hidden assumptions about the set being small, fix
them before scaling.

For each version, produce a fresh `out/spec-<version>.yaml` with the
bulk-generated content. The previous specs are overwritten.

### 3. Per-version validation

Each bulk-generated spec must pass:

- `openapi-spec-validator` strict.
- `openapi-generator-cli generate -g python` smoke test (with the
  YAML→JSON conversion workaround documented in 4d-5 if needed).
- `spectral lint` 0 errors. Warnings tolerated only if all of them
  fall into known-benign categories already documented from prior
  sub-phases. Any new warning class must be reported.

If a version fails validation while others pass, that is a finding —
likely a harvested shape that breaks an assumption. Stop and report
the specific MBean(s) involved.

### 4. Discriminator and enum extraction at full scale

Phases 4d-3 detected polymorphic hierarchies and duplicated enums
within the 22 curated schemas. With ~850 schemas in scope, both
detections will surface significantly more candidates:

- **Enum extraction.** New duplicates will appear (e.g. enums like
  `Severity`, `Direction`, `Persistence` that appeared in only one
  curated schema may now appear in many). Run the same detection +
  extraction pass on the full set.
- **Polymorphic hierarchies.** New parent MBeans with overlay
  `subTypeDiscriminatorProperty` will be discovered. The detection
  logic from 4d-3 should pick them up automatically; verify and
  report each new hierarchy.

For both, the same rules from 4d-3 apply unchanged. Do not invent new
naming policies in 4e — if a case doesn't fit cleanly, defer it.

### 5. Quirks overlay re-application

The 14 quirks in `overlays/quirks/<id>.yaml` continue to apply. After
bulk generation, re-run the quirks injection and verify each quirk's
attachment point still resolves. Some quirks attach to schemas that
were stubs before and are now real bodies; the attachment should now
land on a richer target. Spot-check at least:

- Quirk 5 (`HealthState.subsystemName`) — was attaching to a promoted
  HealthState in 4d-2; should still attach correctly.
- Quirk 14 (`JDBCDataSourceParamsBean.properties`) — verify the
  property is now part of a real schema with the `properties` field
  resolving correctly.

If any quirk's attachment fails post-bulk, it is a finding. The
expected outcome is that all 14 still resolve, possibly with richer
context now.

### 6. Cross-version diff regeneration

The `VERSION_DELTAS.md` from 4d-5 was computed against the curated
subset. With bulk coverage, the diffs will be much larger and cover
schemas that didn't exist before. Regenerate `VERSION_DELTAS.md` with
the bulk-generated specs.

Two ways the diff could blow up:

- Real subsystem changes that we now see (e.g. WLDF additions in 14.1.x
  that we couldn't detect before because WLDFRuntime was a stub).
- Diff algorithm artifacts (e.g. spurious "added" entries because a
  schema name normalization differs between versions).

If the diffs are pathologically large in a way that suggests an
artifact rather than a real change, stop and investigate.

### 7. Coverage metrics

Compute and report, per version:

- Total schemas with bodies (was 22 curated + N enum/discriminator
  derivations; now should be ~830+ N).
- Stubs remaining (should be near 0; any non-zero is worth
  understanding).
- Auto-stubs introduced by `$ref` to non-existent MBeans (vs auto-stubs
  for MBeans we just chose not to process — the latter should be 0
  after 4e).

The "$ref orphans" count from 4b/4c (94 schemas referenced but not
generated) should drop to near 0. Anything above 0 is a finding and
should be investigated. Likely candidates:

- `$ref` to descriptor beans whose harvested file doesn't exist
  (`SettableBean` and similar — these are real harvested-set gaps,
  not bugs).
- `$ref` to MBeans the filter dropped (`supported: false` etc.) — if
  these are truly unsupported, the originating `$ref` should ideally
  not exist either; investigate the propagating MBean.

### 8. Path explosion check

The path generator was previously bounded by the containment graph
reachable from the 22 curated MBean roots. With the full set, every
MBean becomes potentially reachable from some path, but paths are
still rooted at the four trees (`domainRuntime`, `serverRuntime`,
`edit`, `serverConfig` / `domainConfig`).

Expected outcome: path counts grow modestly because the existing
containment graph already drove the path generation in 4c. Most of
the new schemas attach as `$ref` from existing paths' response bodies,
not as new paths.

If path counts double or triple, something is wrong — likely the
containment recursion is now finding cycles or new graph entries that
weren't reachable before. Investigate before continuing.

### 9. Report

`tools/openapi-generator/out/PHASE4E_REPORT.md`:

- Per-version stats: MBeans processed, schemas with bodies, stubs
  remaining, paths, operations, polymorphic hierarchies detected,
  enums extracted, validation results.
- Coverage delta vs 4d-5: schemas with bodies before/after, $ref
  orphans before/after.
- New polymorphic hierarchies discovered (if any), with their
  discriminator and subtype mappings.
- New extracted enums (if any), with their occurrence counts.
- Quirks re-injection check: all 14 still resolve, any contextual
  changes worth noting.
- Cross-version diff summary regenerated. Highlight subsystems that
  emerged in this pass (likely candidates: JTA, WLDF, work managers,
  JMS detail, deployments, security).
- Edge cases discovered during bulk processing.
- Anything deferred to follow-up sub-phases (editorial curation per
  subsystem, descriptions merge, samples).

### 10. Commit

On the same branch (`feat/openapi-generator`), commit:

```
feat(generator): Phase 4e — bulk coverage expansion to full harvested set

Generates schemas for every harvested MBean across all five supported
WLS versions, not just the 22 curated ones. The generator now produces
rich bodies for every $ref previously resolving to an auto-stub.

Coverage delta:
- Schemas with bodies: 22 curated + N derivations → ~830 per version.
- $ref orphans: ~94 per version → near 0.
- Polymorphic hierarchies: 2 → see report for the new total.
- Extracted enums: 3 → see report for the new total.

The 14 quirks continue to inject correctly post-bulk; some now attach
to richer targets (e.g. HealthState, JDBCDataSourceParamsBean).
VERSION_DELTAS.md regenerated against the bulk-generated specs;
cross-version diffs now reflect every MBean change Oracle ships, not
just changes within the curated subset.

Editorial curation per newly covered subsystem (JTA, WLDF, work
managers, JMS detail, security, deployments) remains for follow-up
sub-phases. This sub-phase delivers cuantitativa coverage; quality of
descriptions and operational notes per schema is unchanged from
harvested source.
```

Do not push yet (per usual). Wait for review of the report before pushing.

## Stop conditions

- A version fails validation while others pass → stop and report the
  specific MBean(s) involved.
- $ref orphans count does not drop near 0 → stop and investigate why
  the filter is dropping referenced MBeans.
- Path counts grow pathologically (3x or more) → stop; the containment
  recursion is finding cycles or unexpected entries.
- Cross-version diffs grow pathologically in ways that suggest a
  diff algorithm artifact rather than real changes → stop and
  investigate before regenerating VERSION_DELTAS.md.
- Quirks injection fails on any of the 14 attachments → stop;
  bulk-generated schemas should not break previously-working
  attachments.
- Discriminator detection finds hierarchies that the generator can't
  represent cleanly (a subtype declares conflicting parent properties,
  or an overlay declares a discriminator that doesn't fit OAS 3.0
  semantics) → stop and report. Per 4d-3 precedent: skip cleanly,
  document, do not fudge.
- Spec size per version exceeds practical limits in a way that breaks
  a tool we care about beyond the SnakeYAML codepoint case already
  documented → stop and report.

## Editorial notes

- Phase 4e is the largest single mechanical scale-up in the project.
  Most of the work is the generator doing what it already does, on
  more inputs. The interesting findings will be the cases where
  scaling reveals an assumption that wasn't a problem at small scale.
- After 4e, the spec covers the API surface as Oracle's MBean catalog
  defines it. Any remaining gaps are gaps in Oracle's catalog (e.g.
  the virtual `/domainRuntime/search` endpoint) or REST framework
  behaviors not modeled at the MBean level (e.g. the conditional CSRF
  gate on `serverRuntimes`). Those are already handled in overlays.
- Editorial curation of newly covered subsystems is genuinely
  optional. If a subsystem like JTA emerges from 4e with adequate
  harvested descriptions and clean schemas, no manual layer may be
  needed. Decide per subsystem after the data is in.
- The follow-up sub-phases (per-subsystem curation, descriptions
  merge, samples) become more about "which subsystems to invest more
  in" and less about "what to generate". Different conversation.
