# Phase 4d-1 — Quality of paths

## Goal

Take the spec generated in Phase 4c and clean it visually and semantically:

- Eliminate the ~1989 Spectral warnings (almost all are
  `operation-description` and `operation-tag-defined`).
- Replace generic `{name}` / `{name2}` / `{name3}` path parameters with
  semantic names (`{serverName}`, `{clusterName}`, `{dataSourceName}`).
- Add minimal descriptions to every generated operation.
- Add tags to operations so they group sensibly in Swagger UI.
- Resolve the small set of issues that don't need a full overlay engine
  yet (info.contact, the 4 unused-component warnings).

After 4d-1 the generated spec is something that can be opened in Swagger UI
and looked at without flinching. It is **not** publication-ready (quirks,
samples, enum extraction, surface curation, multi-version are still pending
in 4d-2 through 4d-5), but it is presentable internally.

## Out of scope for 4d-1

These remain for later sub-phases:

- Quirks migration to `overlays/quirks/<id>.yaml` → 4d-2
- Enum extraction, sub-type discriminators, $ref allOf wrapping refinement → 4d-3
- Server / Cluster surface curation (165 vs 27 props decision) → 4d-4
- Multi-version specs (12.2.1.3, 12.2.1.4, 14.1.1, 15.1.1) → 4d-5
- Description merge policy (harvested + curated operational notes) → 4d-5
- Live samples linking → 4d-5
- Java scraping for `startInAdmin` / `startInStandby` → either 4d-2 or 4d-5
- `/domainRuntime/search` virtual endpoint definition → 4d-2 (it's
  effectively a quirk overlay since there's no MBean for it)

If during 4d-1 something out-of-scope becomes blocking, document it and
defer rather than expanding scope.

## Tasks

### 1. Path parameter naming

The path generator currently emits `{name}`, `{name2}`, `{name3}` for
nested paths because OpenAPI prohibits duplicate parameter names. Replace
with semantic names derived from the bean type at each containment level.

Rules:

- For a path segment like `/serverRuntimes/{X}/applicationRuntimes/{Y}`,
  X is the parent bean's identifier (`serverName`), Y is the child's
  (`applicationName`).
- Derive the parameter name from the containment property's element type:
  - `serverRuntimes` → `serverName`
  - `applicationRuntimes` → `applicationName`
  - `componentRuntimes` → `componentName`
  - `JDBCDataSourceRuntimeMBeans` → `dataSourceName`
  - `serverChannelRuntimes` → `channelName`
  - etc.
- Strategy: maintain a mapping table `containment_property → param_name`.
  Default fallback: take the property name, strip trailing `Runtimes` /
  `MBeans` / `s`, append `Name`. So `clusterRuntimes` → `clusterName`,
  `JMSServers` → `JMSServerName`. Most cases fall out cleanly from this rule.
- For the few collisions where two containment levels resolve to the
  same param name (rare but possible in deep nesting), suffix with the
  bean type abbreviation: `{serverName}` and `{cluster_serverName}` are
  ugly; better to keep the rule simple and accept that the second
  occurrence is `{name2}` only when the deduplication algorithm can't find
  a sensible distinct name.

Verification: every path in `out/spec-14.1.2.0.0.yaml` should have
parameter names that read naturally. Spot-check the manual spec under
`specs/` for the expected names of paths it covers; the generated should
match or be consistent with manual conventions.

### 2. Operation descriptions

Every operation (GET, POST, DELETE) needs a `description` field. Rules:

- **GET on a singleton resource:** `"Retrieve the {schemaName} resource."`
- **GET on a collection:** `"List all {pluralized schemaName} resources."`
- **POST on a collection (create):**
  `"Create a new {schemaName} resource within this collection."`
- **POST on an item (update):** `"Update an existing {schemaName} resource."`
- **DELETE on an item:** `"Delete this {schemaName} resource."`
- **POST on an action endpoint (e.g. `/start`, `/shutdown`):**
  - Read the action's description from `extension.yaml` if present.
  - Otherwise: `"Invoke the {actionName} operation on {schemaName}."`

Where `schemaName` is the normalized name (`ServerRuntime`, not
`ServerRuntimeMBean`).

When the harvested YAML provides an action description (for instance via
the action's `descriptionHTML` field, if present), use that — it will be
richer than the generic template. The templates above are the fallback.

Also add `summary` (a short one-liner) for every operation. Same templates
shorter:

- GET singleton: `"Get {schemaName}"`
- GET collection: `"List {schemaName}"`
- POST create: `"Create {schemaName}"`
- POST update: `"Update {schemaName}"`
- DELETE: `"Delete {schemaName}"`
- POST action: `"{actionName} on {schemaName}"`

### 3. Tags

Group operations so Swagger UI / Redocly render them in sensible
sections. Suggested tag taxonomy:

- One tag per top-level bean tree: `domainRuntime`, `serverRuntime`,
  `edit`, `serverConfig`, `domainConfig`, `lifecycle`,
  `change-manager`.
- A second tag for the immediate sub-tree where it adds clarity, e.g.
  `domainRuntime/serverRuntimes`, `edit/JDBCSystemResources`. Optional;
  start with single-tag and only add the second if Swagger UI navigation
  feels noisy.

Apply tags consistently. Every operation has at least one tag. Define
tags at document level (`tags:` array at the root of the spec) with a
short description per tag, so Swagger UI shows tag-level sections with
context.

### 4. Document-level metadata

Fix the small `info.contact` warning and similar:

- `info.title`: "WebLogic REST Management API — Generated Specification"
- `info.description`: a short paragraph noting that schemas are derived
  from Oracle's Remote Console harvested YAMLs (UPL 1.0) and link to
  the source, plus a note that this is the generated spec and that
  manual overlays for quirks/samples are pending.
- `info.version`: track the WLS version being generated (e.g. `14.1.2.0.0`).
- `info.contact`: name + url pointing to the GitHub repo.
- `info.license`: Apache 2.0 + UPL 1.0 attribution note.
- `servers`: array with the standard WebLogic admin server URL pattern
  with `host`, `port`, and `version` as variables, same way the manual
  specs do.

### 5. Unused components

The 4 unused-component warnings from Spectral are likely envelope schemas
referenced indirectly or schemas generated as stubs but never linked.
Identify each and either:

- Remove if genuinely unused.
- Add a `$ref` from somewhere if it should be used but isn't being.

Do not paper over by suppressing the rule.

### 6. Validation

After all changes, regenerate the spec and run:

- `openapi-spec-validator` strict — must remain PASS.
- `openapi-generator-cli generate -g python` smoke test — must remain PASS.
- `spectral lint` — target: warnings count drops from ~1989 to **under 50**.
  Remaining warnings should all be of types we don't address in 4d-1
  (e.g. info-contact-url-format edge cases, or warnings from the auto-stubs).

If Spectral warnings stay above ~100, stop and report — something is wrong
in the templates above and broad-fix won't work.

### 7. Report

`tools/openapi-generator/out/PHASE4D1_REPORT.md`:

- Spectral warnings before / after.
- Operation count with descriptions.
- Param-name mapping table actually applied (so we can review the
  rules against reality).
- Any path where the deduplication algorithm fell back to `{name2}` or
  `{name3}` (and why).
- Edge cases discovered.
- Sample of 5–10 cleaned paths copy-pasted from the spec, to eyeball
  quality.

### 8. Commit

On the same branch (`feat/openapi-generator`), commit with message:

```
feat(generator): Phase 4d-1 — descriptions, tags, semantic path params

Cleans the generated spec for visual and semantic consumption:
- Every operation has a summary and description (template-based with
  per-action overrides where harvested provides one).
- Path parameters renamed from {name}/{name2}/{name3} to semantic forms
  derived from containment property types ({serverName}, {applicationName},
  ...).
- Operations grouped under tags by bean tree.
- info-block populated (title, description, version, contact, license).

Spectral warnings reduced from ~1989 to <50. Remaining warnings are out
of scope for 4d-1 (auto-stub-related, addressed when surface expands in
later sub-phases).

Manual overlays for quirks, samples, enum extraction, sub-type
discriminators, multi-version generation, and surface curation remain
pending in PHASE4D2-5 plans.
```

Do not push yet. Wait for review of the report.

## Stop conditions

- Spectral warnings remain above ~100 after the planned fixes → stop and
  report; the templates may need rethinking.
- Param-name deduplication produces ugly results in many places → stop
  and report; we may need a better naming algorithm before continuing.
- Generator client smoke test starts failing → stop and report; semantic
  param renaming may have broken `$ref`s somewhere.

## Editorial notes

- The descriptions added here are templates, not curated prose. They
  raise the spec from "machine-generated" to "human-readable". The
  curated operational notes (the real value of the manual layer) come
  in 4d-5 with the description merge policy.
- Tags chosen here are deliberately coarse. If Swagger UI navigation
  is awkward we can refine in 4d-2 or 4d-3 — not in 4d-1.
- The point of 4d-1 is that someone opening the spec in Swagger UI says
  "this is a real spec", not "this is a 65k-line YAML dump". Visual
  threshold, not feature completeness.
