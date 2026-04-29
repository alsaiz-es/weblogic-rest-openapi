# Phase 4d-9 — Path expansion to resolve unused-component warnings

## Goal

Resolve the 256–286 `oas3-unused-component` warnings appearing across
the 5 versions. The warnings indicate schemas with bodies that no path
in the spec returns. Two valid resolutions exist depending on root cause:

- **Reachability fix.** If the schema is genuinely a sub-resource of a
  bean that the path-builder doesn't currently reach, extend
  path-builder traversal rules.
- **Filter fix.** If the schema represents an internal-only MBean that
  Oracle does not expose via REST, exclude from emission instead of
  forcing a fake path.

After 4d-9, the spec has zero `oas3-unused-component` warnings (or a
small documented residual) and either richer path coverage or cleaner
schema set.

## Out of scope

- Adding paths for endpoints Oracle doesn't actually serve. If a
  schema is for an internal-only MBean, the right answer is to exclude
  it, not invent a path.
- New traversal modes beyond what the harvested catalog supports
  (e.g. inferring paths from naming conventions). The generator
  remains data-driven.

## Investigation plan (do this before any code change)

Investigation is the bulk of this sub-phase. Code changes follow only
after the categorization is clear.

### 1. List the unused schemas

Per version, dump the names of schemas that trigger the
`oas3-unused-component` warning. Cross-reference across versions to
find the stable set.

### 2. Categorize each unused schema

For each unused schema, check:

- Does the corresponding harvested MBean YAML have any property with
  `relationship: containment` pointing to it from a reachable parent?
  If yes → the path-builder is missing a traversal rule.
- Does the MBean have annotations like `restInternal: true`, an
  internal package path, or any harvested signal that it's not a
  user-facing REST resource? If yes → exclude from emission.
- Does the MBean only appear as a `relationship: reference` target
  (not containment)? Reference-only MBeans don't create paths by
  design — they're returned as `Identity` arrays in their referencer
  schemas. They can be unused as schemas if no caller dereferences
  them. → Likely filter case.
- Is the MBean a polymorphic subtype where the parent's `oneOf`
  references it but no path returns it directly? → Acceptable
  unused; the discriminator wiring justifies its existence.

### 3. Build a categorization table

Output a table: schema → category → recommended action. Per category:

- **Reachable but missed.** Path-builder needs a new traversal rule.
- **Internal/excluded.** Filter from emission.
- **Reference-only target.** Filter from emission unless explicitly
  needed.
- **Polymorphic-only.** Keep as-is; warning is a false positive in
  this context.

### 4. Prioritize

Don't fix everything at once. Pick the categories representing the
highest count of warnings and fix them first. The other categories
may resolve as a side effect or stay documented.

## Tasks (after investigation)

### 1. Extend path-builder for "reachable but missed"

If category 1 has significant count, add the missing traversal rules.
Common candidates discovered during earlier phases:

- Sub-resources reachable through `relationship: containment` but
  via non-canonical parent (e.g. a runtime bean inside a config bean).
- Sub-resources of polymorphic subtypes that aren't visited by the
  current recursion logic.

Each new rule should be conservative: only emit a path if the
containment is unambiguous and the parent is already reachable.

### 2. Filter pass for internal/excluded

Apply the same filter logic the generator already has for
`supported: false`, extending it with new criteria found during
investigation.

If a filtered schema has no other purpose (no `$ref` from anywhere),
it can be removed from emission entirely. If it's still referenced as
a polymorphic subtype, keep the schema body but mark it with a custom
extension `x-weblogic-internal-only: true` so consumers know it
won't appear via REST.

### 3. Polymorphic-only acceptance

For schemas that exist solely to support a discriminator's `oneOf`
list, the warning is structural and acceptable. Either:

- Suppress the warning at Spectral config level for these specific
  cases.
- Add a no-op path that returns the discriminator parent (which
  references all subtypes) — this dilutes the warning meaning and
  isn't recommended.
- Accept the residual warnings for these and document them.

Accept residual is the cleanest option.

### 4. Validation

- `openapi-spec-validator` strict — must remain PASS.
- `openapi-generator-cli generate -g python` smoke test — must remain
  PASS. May produce slightly different model count.
- `spectral lint` — target: warnings drop substantially. Document the
  residual count and which categories produce it.

### 5. Report

`tools/openapi-generator/out/PHASE4D9_REPORT.md`:

- Categorization table with counts.
- Resolutions applied per category.
- Warnings before / after per version.
- Schemas filtered from emission with rationale.
- New traversal rules added to path-builder.
- Residual warnings: count and category.
- Edge cases.

### 6. Commit

On `feat/openapi-generator`. Commit message reflects: warnings down
from N → M, X new traversal rules, Y schemas filtered as
internal/excluded. After commit, update `REMAINING_WORK.md`.

## Stop conditions

- Investigation reveals categorization isn't clean (a single schema
  fits two or more categories ambiguously) → stop and report; we may
  need to refine the categorization criteria.
- Path-builder extension breaks the existing path count or quirks
  attachment → stop; the new rule is too aggressive.
- Filtering schemas breaks `$ref` resolution from elsewhere in the
  spec → stop; the schema is referenced more than expected.
- Warnings count goes up (not down) after the fix → stop; the change
  introduces new issues.

## Editorial notes

- This sub-phase is the only one where the goal is "make warnings go
  away", which is suspect framing. The real goal is correctness:
  every schema in the spec should either be reachable via a documented
  path, exist for a structural OpenAPI reason (polymorphism), or be
  removed.
- Investigation comes first. Don't write code to fix something we
  haven't characterized. Earlier sub-phases occasionally hit edge
  cases by jumping to fixes; here we explicitly avoid that.
- Some residual warnings are acceptable and even informative (e.g. a
  Spectral config note that says "12 polymorphic subtype schemas
  exist as discriminator targets — see PHASE4E3 for body fidelity").
