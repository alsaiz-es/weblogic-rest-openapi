# Phase 4f — Manual specs/ replacement and merge to main

## Goal

Bridge the `feat/openapi-generator` branch to `main` by:

1. Replacing the manual `specs/` directory with the generator-produced
   equivalent.
2. Tagging a release on the branch.
3. Opening and merging the PR to main.
4. Preparing the README and CHANGELOG for the second LinkedIn post.

After 4f, `main` contains the generator-based spec as v0.4.0. The
manual v0.3.1 spec remains accessible via git tag for anyone who needs
the historical reference.

Alfredo's choice for this sub-phase: option C — replace `specs/` in
main, v0.3.1 accessible via tag, README explains the transition.

## Out of scope

- Continuing development on the branch after merge (that becomes
  Phase 5 work — ToolSpec/MCP integration for the second LinkedIn
  post is a separate effort, with its own plan when ready).
- Deleting the v0.3.1 git tag (it stays forever for historical access).
- Changing the repo's URL, name, or top-level identity.

## Pre-merge checklist

Before opening the PR, verify everything is ready:

### 1. All previous sub-phases complete

Check `REMAINING_WORK.md`. The "What remains pending" section should
contain only this sub-phase (4f). If others are pending and Alfredo
chose to defer them, update REMAINING_WORK to reflect that.

### 2. Validators green

Per version, on the branch:

- `openapi-spec-validator` strict PASS.
- `openapi-generator-cli generate -g python` smoke PASS.
- `spectral lint` 0 errors. Warnings either zero or with documented
  rationale.

### 3. Generator pipeline reproducible

Anyone cloning the branch should be able to regenerate all 5 specs
from harvested YAMLs + overlays with a single command. Document the
command in `tools/openapi-generator/README.md` if not already.

### 4. License attribution complete

- README acknowledges Oracle's `weblogic-remote-console` repo as the
  source of harvested YAMLs.
- License section mentions UPL 1.0 (harvested) + Apache 2.0 (this
  project).
- Generated specs each carry a license note at the top of `info.description`.

## Tasks

### 1. Final spec generation

On the branch, regenerate all 5 specs from current harvested + overlays
state. Verify outputs match what the latest commit shows. This is a
sanity check: if a recent overlay change wasn't fully integrated, the
regen will catch it.

### 2. Replace specs/ with generated content

Decide on the structure:

- **Option A.** `specs/` becomes `specs/generated/` with one
  subdirectory per version (`specs/generated/12.2.1.4.0.yaml`, etc.).
  The old manual `specs/domain-runtime/`, `specs/edit/`, etc. are
  deleted entirely.
- **Option B.** `specs/` keeps its current structure but each file is
  replaced by the generator's output for the canonical version
  (14.1.2). Multi-version specs live elsewhere.
- **Option C.** `specs/` is deleted. The generator output becomes the
  spec; consumers point to `tools/openapi-generator/out/spec-<version>.yaml`.

Recommended: **Option A** — clean, mirrors the multi-version reality
of the spec, doesn't pretend the manual structure still applies.

Apply the chosen structure. Delete the old hand-written files.

### 3. README rewrite

The README's "Project Status and Roadmap" section, added before the
generator existed, needs a full rewrite reflecting the new project
shape:

- Lead with: spec is generated from Oracle's harvested MBean catalog
  with manual overlays for quirks, samples, descriptions, and 12
  manually authored polymorphic subtypes.
- Coverage: ~950 schemas per version, 5 versions covered, ~1100-2400
  paths per version (varies by version due to MT deprecation).
- Manual layer: list quirks count, samples count, description
  overlays count, manual schema bodies count.
- License: Apache 2.0 + UPL 1.0 attribution.
- Breaking change note: v0.4.0 supersedes v0.3.1's hand-written specs.
  v0.3.1 remains via git tag.
- How to consume: which spec file for which version, link to
  Swagger UI rendering instructions, link to client generation
  instructions.

The "Known API Quirks" section keeps its content but the link
target changes from the manual specs to the generator-emitted ones.

The "Coverage Status" table also needs full rewrite or removal —
it was a hand-curated checklist. With ~950 schemas it's not
maintainable in that form. Replace with a summary paragraph and a
link to `VERSION_DELTAS.md` for cross-version specifics.

### 4. CHANGELOG update

Add v0.4.0 entry summarizing the transformation:

- The spec is now generated from Oracle's `weblogic-remote-console`
  harvested MBean YAMLs.
- 22 manual schemas → ~950 schemas across 5 versions.
- 14 quirks migrated to structured overlays.
- New: live samples linked, description overlays for 22 curated +
  N from 4e-2 subsystems, 12 manually authored polymorphic subtypes.
- Breaking: spec file paths under `specs/` have changed. v0.3.1 is
  still tagged for anyone needing the old layout.

The CHANGELOG should be readable as the changelog of the next
LinkedIn post — the wording will inform that post's draft.

### 5. Tag the branch

```
git tag -a v0.4.0-rc1 -m "v0.4.0 release candidate — generator-based spec"
```

The release candidate tag exists so we can bump to v0.4.0 final after
the merge sanity check.

### 6. Open the PR

PR description summarizes:

- Branch contains Phase 4 (4a through 4e-3).
- Spec is now generator-produced with manual overlays.
- All 5 versions validated with three independent tools.
- Manual v0.3.1 specs replaced; v0.3.1 remains via git tag.
- Closes the original issue/intent of providing a complete
  unofficial OpenAPI spec for WebLogic.

Reviewers: just Alfredo since this is a personal project. Self-review
checklist:

- All commits have descriptive messages.
- No commit was force-pushed in a way that lost history.
- Generated specs match the latest overlay/code state.
- README reflects the new reality.
- CHANGELOG is honest and complete.

### 7. Merge

Once self-review passes:

```
git checkout main
git merge --no-ff feat/openapi-generator
git tag -a v0.4.0 -m "v0.4.0 — generator-based spec from Remote Console catalog"
git push origin main --tags
```

Use `--no-ff` to preserve the branch history visibly. The merge commit
is the canonical record of the transformation.

### 8. Post-merge

- Verify GitHub renders README correctly.
- Verify the v0.3.1 tag is still browsable on GitHub.
- Verify the `feat/openapi-generator` branch can be deleted (it's
  fully merged) — but consider keeping it for one more cycle in case
  any post-merge issues need to reference it.
- Update `REMAINING_WORK.md` final time: 4f closed, no more pending
  sub-phases.

## Stop conditions

- Pre-merge checklist reveals validators failing on main candidate →
  stop, fix on the branch, re-run before continuing.
- README rewrite reveals coverage claims that don't match generated
  reality → stop, reconcile before merging.
- A reviewer (Alfredo) finds something fundamental wrong in the PR
  → stop, fix on the branch, refresh the PR.

## Editorial notes

- This sub-phase is the bridge to public visibility. The README is
  what visitors see. Take it seriously.
- The CHANGELOG entry for v0.4.0 will likely become source material
  for the second LinkedIn post. Write it knowing that.
- Merging is technical but the cultural moment matters: the project
  passes from "Alfredo's hand-curated experiment" to "an
  automated transformation of Oracle's catalog with quality
  overlays". The README's framing should celebrate that without
  overpromising.
- v0.4.0 is the right version bump. Major project shape change
  (generator vs manual) justifies it. v0.4.0 also signals that v1.0
  is on the horizon (when the project's scope and audience
  stabilize).

## What comes after 4f

This document does not plan post-merge work. Suggested follow-ups
exist but they belong to separate plans:

- **Second LinkedIn post.** Use v0.4.0 as the anchor. Tone: "I
  finished the transformation I started a few weeks ago." Highlight
  the catalog discovery, the manual overlay layer, and the
  cross-version diff as new contributions.
- **Phase 5 — ToolSpec / MCP integration.** Build a ToolSpec
  descriptor from the v0.4.0 spec, demo MCP-based agentic operation
  of WebLogic. This is the original narrative arc of the project.
- **Coverage expansion to additional WLS versions.** When Oracle
  ships 15.1.2 or beyond, run the generator against new harvested.
- **Maintenance.** Track Oracle's `weblogic-remote-console` repo for
  upstream changes that affect the generator.
