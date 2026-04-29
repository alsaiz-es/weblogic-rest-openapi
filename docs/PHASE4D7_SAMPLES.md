# Phase 4d-7 — Live samples linking

## Goal

Reference the verbatim JSON samples under `samples/{version}/` from the
generated spec, so consumers can see real responses alongside the
schemas. Hybrid format: native OpenAPI `examples` for canonical samples,
`x-weblogic-sample-paths` extension pointing to file paths for the rest.

After 4d-7, the generated spec's operations include real example
responses for the most useful operations, and link to the broader
sample corpus for everything else.

## Out of scope

- Samples for schemas covered by 4e bulk that have no recorded samples
  in `samples/`. They stay sample-less.
- Generating new samples by exercising live WebLogic instances. That
  is empirical work outside this sub-phase's scope.
- Cross-version sample reconciliation (showing 12.2.1.4 sample on
  14.1.2 endpoint when shapes match). Treat each version's samples
  as belonging only to that version's spec.

## Format decision

Two emission modes per operation:

**Native `examples` block (canonical):** an inline OpenAPI 3.0
`examples` keyword under the operation's response, with the JSON
content embedded. Verbose but standard; every OpenAPI tool understands
them. Use for the single most representative sample per operation.

**`x-weblogic-sample-paths` extension (overflow):** a list of file
paths pointing into `samples/{version}/`, allowing tooling that
understands the extension to fetch additional samples. Use for the
remaining samples per operation when there are multiple.

If an operation has only one sample, use native exclusively. If an
operation has many samples (e.g. several datasource captures), pick
one as canonical and put the rest in the extension.

## Tasks

### 1. Inventory existing samples

Walk `samples/12.2.1.4/` and `samples/14.1.2/` (and any other version
directories present). For each JSON file, classify by:

- Path it represents (derive from filename and content).
- Schema it represents (from the response shape).
- Version.

Build a mapping `(path, method, version) → list of sample files`.

### 2. Sample-to-operation mapping

Cross-reference the inventory against the operations in the generated
spec. For each generated operation, identify which samples (if any)
correspond.

Mapping rules:

- A sample for `domainRuntime/serverRuntimes/AdminServer` maps to the
  `GET /domainRuntime/serverRuntimes/{serverName}` operation in the
  matching version's spec.
- A sample of a JDBC datasource maps to the appropriate JDBCDataSourceRuntime
  endpoint.
- Lifecycle action samples (start, suspend) map to the corresponding
  POST operation.

Skip samples that don't cleanly map (e.g. raw error responses captured
during exploration that don't correspond to any documented behavior).

### 3. Canonical selection per operation

For operations with multiple samples, pick the one that best
represents the typical successful response. Prefer:

- AdminServer over managed servers (more universal).
- Healthy state samples over error states.
- Samples with rich content over minimal ones.

Document the selection criteria in the report so future samples can
be added consistently.

### 4. Generator emission change

Extend the generator's path emission to:

- Load sample inventory from `samples/{version}/` for the target
  version.
- Look up samples per operation.
- Inject canonical sample as native `examples` block under the
  operation's appropriate response (200 typically).
- Inject overflow sample paths as `x-weblogic-sample-paths` array
  alongside.

Sample paths in the extension are relative to repo root
(`samples/14.1.2/serverRuntime_AdminServer.json`).

### 5. Validation

- `openapi-spec-validator` strict — must remain PASS.
- `openapi-generator-cli generate -g python` smoke test — must
  remain PASS. Native `examples` may add to the model size.
- `spectral lint` — must remain 0 errors. New warning class
  `oas3-valid-media-example` may appear if any sample doesn't
  validate against its schema; report and fix where it indicates a
  real schema/sample mismatch.

### 6. Spot-check

Open the generated spec for 14.1.2 and inspect 3 operations with
samples:

- A read endpoint with one sample (e.g. JVMRuntime).
- A read endpoint with multiple samples (e.g. JDBC datasource
  collection).
- A lifecycle action (e.g. suspend).

Verify the native `examples` block renders correctly and the
extension paths point to existing files.

### 7. Report

`tools/openapi-generator/out/PHASE4D7_REPORT.md`:

- Sample inventory: count per version, per category.
- Operations with samples vs without (in the 22 curated set).
- Canonical selections made per operation with multiple candidates.
- Validation results.
- Any sample-vs-schema mismatches discovered (sample doesn't validate
  against its mapped schema).
- Edge cases.

### 8. Commit

On `feat/openapi-generator`. Commit message reflects scope and the
hybrid format. After commit, update `REMAINING_WORK.md`.

## Stop conditions

- Many samples fail to validate against their target schemas → stop;
  either the schemas are wrong (regression vs harvested data) or the
  samples have rotted (saved before a generator change). Investigate
  before continuing.
- Native `examples` injection blows up the spec size dramatically
  (more than 50% growth) → stop; reconsider whether to embed natively
  or use only the extension.
- Sample-to-operation mapping is too ambiguous to automate → stop and
  document; may need explicit annotation in sample filenames.

## Editorial notes

- Samples are the strongest evidence of empirical validation. Linking
  them ties the spec to ground truth in a way no mechanical generator
  can.
- Samples for schemas from 4e bulk coverage do not exist. That is a
  feature: those schemas come from Oracle's catalog, so claiming
  empirical validation we don't have would be wrong.
- The hybrid format protects against `examples` blocks growing the
  spec into unwieldy size while keeping the most useful samples
  immediately visible.
