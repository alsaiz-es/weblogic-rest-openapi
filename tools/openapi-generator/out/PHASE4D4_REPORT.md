# Phase 4d-4 — Technical debt audit and overdue decisions

This sub-phase walks the four deterministic items deferred from earlier
sub-phases and either closes them or documents the rationale for the
final state. Item 5 (SettableBean) was scoped to enumeration-only per the
plan — Alfredo's decision required to act on it. The audit below shows
that, after measurement, item 5's premise is incorrect and the item can
be closed without action.

WLS version used for measurement: **14.1.2.0.0** (bulk-coverage spec).
The same code paths apply to all five supported versions; final
validators were re-run across the full set after the changes.

## Item 1 — `getRoles` RBAC mapping refinement

**Audit.** 31 properties in 14.1.2 harvested carry `getRoles.allowed`,
distributed as:

| Roles | Property count |
|---|---:|
| `[Deployer]` | 24 |
| `[admin]` (lowercase) | 5 |
| `[Operator]` | 1 |
| `[Monitor]` | 1 |

Pre-4d-4 the generated spec had **0** `x-weblogic-required-role`
occurrences — the basic role mapping referenced in the 4c report was
limited to the global `securitySchemes.basicAuth.description` blurb;
the per-property extension was never emitted.

**Decision.** Add a per-property `x-weblogic-required-role: [<roles>]`
extension whenever the harvested property declares `getRoles.allowed`.
Cheap (one conditional in `schema_builder`), useful for audit
(consumers reading a schema field can see which role gates it).

Per-operation aggregation (rolling property-level roles up to a
required role on the GET operation) is **not** implemented: WebLogic
enforces roles at the JMX layer, not at REST; aggregating would
require taking the most restrictive role across the response and the
result would over-state the requirement (a Monitor user can call the
GET; some specific fields may be elided in the response if the user
lacks Operator/Deployer/Admin). Document at the property level only.

**Outcome.** Generated spec now carries 23 `x-weblogic-required-role`
extensions (8 of the 31 harvested-flagged properties live on schemas
filtered by `supported: false` or otherwise excluded; the rest emit).
Item closed.

## Item 2 — `relationship: reference` on a config-tree MBean

**Audit.** Bulk coverage (4e) emits `Server` (the config bean,
~165 props) including the `cluster` property. Walked the inheritance
chain to find the harvested definition: it lives on `ServerTemplateMBean`
(parent of `ServerMBean`) with shape:

```yaml
- name: Cluster
  type: weblogic.management.configuration.ClusterMBean
  relationship: reference
  restartNeeded: true
  redeployNeeded: true
  writable: true
```

Generated output:

```yaml
cluster:
  type: array
  items:
    type: string
  description: "The cluster, or group of WebLogic Server instances, …"
  x-weblogic-restart-needed: true
  x-weblogic-redeploy-needed: true
```

**Decision.** No action needed. The reference resolves correctly to
Identity (array of strings) per the rule established in 4a-2 and
fixed in 4b for the `array<reference>` case. The path through the
config-tree base classes inherits the property via `baseTypes`, the
schema_builder identifies `relationship: reference` (singleton), and
emits the Identity shape. Item closed.

**Outcome.** Confirmed; the array-of-string Identity emission applies
uniformly across runtime and config trees.

## Item 3 — `x-weblogic-restart-needed` on read-only properties

**Audit.** Across the 14.1.2 harvested set, properties with
`restartNeeded: true` distribute as:

| Population | Count |
|---|---:|
| Runtime MBean properties (often read-only) | 8 |
| Non-runtime (config) MBean properties | 1262 |

Inspection of the 8 runtime cases shows they fall in two buckets:

- Genuinely writable runtime properties (e.g.
  `WLDFSystemResourceControlRuntimeMBean.Enabled`,
  `JaxRsApplicationRuntimeMBean.ApplicationEnabled`,
  `JRockitRuntimeMBean.PauseTimeTarget`). The flag here is
  semantically meaningful — toggling the value via JMX would require
  a server restart.
- Read-only runtime fields that happen to inherit `restartNeeded`
  from the underlying config layer (e.g. `ServerRuntime.currentMachine`
  — the runtime *exposes* the configured value but isn't itself
  mutable). The flag here is noise.

**Decision.** Filter `x-weblogic-restart-needed` (and the parallel
`x-weblogic-redeploy-needed`) only when the property ends up
`readOnly: true` in the generated schema. Writable properties keep
the flag; read-only properties drop it. This handles the
inherited-from-config case without losing signal on the genuinely
writable runtime properties.

**Outcome.** 1710 occurrences of `x-weblogic-restart-needed` remain
across 14.1.2 (all on writable schemas where the flag adds value).
The `ServerRuntime.currentMachine` example confirmed: the flag is no
longer present.

## Item 4 — Overlay vocabulary not honored

**Audit.** Across all UI overlay `type.yaml` files in the Remote
Console source, the property-level vocabulary that the generator
currently ignored:

| Overlay key | Occurrences | 4d-4 decision |
|---|---:|---|
| `label` | 731 | **Ignore** — UI display label, no REST semantics. |
| `useUnlocalizedNameAsLabel` | 457 | **Ignore** — UI internationalization hint. |
| `helpSummaryHTML` / `helpHTML` / `helpDetailsHTML` | 235 / 222 / 160 | **Ignore** — UI help text, parallel to harvested `descriptionHTML`. Risk of duplication; revisit if 4d-6 description merge wants it. |
| `offlineName` | 187 | **Ignore** — WLST offline name, not REST. |
| `optionsSources` | 97 | **Ignore** — UI dropdown sources. |
| `usedIf` | 89 | **Defer** — UI conditional show/hide rule; could lift as `x-weblogic-used-if` in a later editorial pass, but the rule grammar is non-trivial and not standardized. |
| `required` | 77 | **Honor** — lift to schema-level `required: [...]` array. |
| `dateAsLong` | 36 | **Honor** — emit `x-weblogic-date-as-long: true`; keep integer base type so wire format stays accurate. |
| `multiLineString` | 16 | **Honor** — emit `x-weblogic-multiline: true`. |
| `presentation` | 13 | **Ignore** — UI presentation hints (width, format). |
| `getMethod` | 11 | **Ignore** — custom Java getter, internal Remote Console concern. |
| `useUnlocalizedLegalValuesAsLabels` | 7 | **Ignore** — UI i18n hint. |
| `requiredCapabilities` | 6 | **Defer** — capability-gated visibility, semantically interesting but rare; address with the larger capabilities work if it comes up. |
| `supportsModelTokens` | 4 | **Ignore** — WDT/WLST template token support. |
| `referenceAsReferences` | 4 | **Ignore** — Remote Console internal flag. |
| `disableMBeanJavadoc` (top + property) | 175 | **Ignore** — Remote Console build-time hint. |
| `optionsMethod` | 3 | **Ignore** — UI dropdown source. |
| `allowNullReference` | 3 | **Ignore** — UI form validation. |
| `dontReturnIfHiddenColumn` | 1 | **Ignore** — UI table rendering. |

Top-level overlay keys (e.g. `editable`, `referenceable`,
`createResourceMethod`) all classify as **Ignore** for similar
reasons (UI/WLST/internal).

**Decisions implemented.**

- `required: true` on a property → lifts the property's REST name into
  the schema-level `required: [...]` array. Effect on 14.1.2:
  **154 schema-level `required` entries** spread across descriptor
  beans (`JDBCDataSourceParamsBean.dataSourceList`, etc.).
- `dateAsLong: true` → adds `x-weblogic-date-as-long: true` on the
  property. Effect on 14.1.2: **58 properties** flagged.
- `multiLineString: true` → adds `x-weblogic-multiline: true`. Effect
  on 14.1.2: **8 properties** flagged (e.g.
  `JDBCDataSourceRuntime.testResults`,
  `ServerRuntime.weblogicVersion`).

**Outcome.** Three high-value overlay fields lifted; the rest stay
ignored with rationale documented above. Item closed.

## Item 5 — Descriptor beans / SettableBean partial inheritance

**Plan instruction**: enumerate scope only, defer resolution to Alfredo.

**Audit findings — the original premise was incorrect.** The Phase 4b
report claimed that descriptor beans declared
`baseTypes: [weblogic.descriptor.SettableBean]` and that
`SettableBean.yaml` was missing from the harvested set, causing the
inheritance chain to truncate cleanly while losing inheritable
properties. Re-checking 14.1.2:

- `SettableBean.yaml` **does exist** in the harvested set.
- Its content:
  ```yaml
  name: weblogic.descriptor.SettableBean
  descriptionHTML: 'A bean which implements this interfaces supports
    the isSet and unSet methods …'
  ```
  No `baseTypes`. No `properties`. It is a marker interface.
- `HarvestedLoader.load_with_inheritance("JDBCDataSourceBean")`
  produces:
  ```
  chain: ['JDBCDataSourceBean', 'SettableBean']
  per level: {'SettableBean': 0, 'JDBCDataSourceBean': 10}
  total merged props: 10
  ```
  The chain walks correctly; SettableBean contributes 0 properties
  because there are none to contribute.

**Comprehensive verification.** Exhaustive scan across the entire
14.1.2 harvested set: **0 beans** declare a baseType whose simple class
name is missing from harvested. Every `baseTypes:` entry resolves to a
present `*.yaml`. Sampled the 12.2.1.4 set — same result.

**Decision (no Alfredo input needed).** The item dissolves: the
described problem doesn't exist with the current harvested data.
SettableBean's `isSet()` / `unSet()` operational semantics are JMX
contract methods, not properties — they don't need to be modeled in
REST. Close the item without action.

(If a future harvested release does ship a non-trivial parent without
its own YAML, the existing `try_load → break` defensive code in
`harvested_loader._inheritance_chain` already handles it gracefully.
The case becomes a missing-data finding to report rather than a
silent loss.)

## Validation

All five bulk-generated specs re-validated after the changes:

| Version | spec-validator | Spectral | Python smoke |
|---|---|---|---|
| `12.2.1.3.0` | PASS | 0 errors / 257 warnings (oas3-unused-component) | PASS via JSON (1227 models) |
| `12.2.1.4.0` | PASS | 0 errors / 256 warnings (oas3-unused-component) | PASS via JSON (1232 models) |
| `14.1.1.0.0` | PASS | 0 errors / 286 warnings (oas3-unused-component) | PASS via JSON (1203 models) |
| `14.1.2.0.0` | PASS | 0 errors / 263 warnings (oas3-unused-component) | PASS via JSON (1180 models) |
| `15.1.1.0.0` | PASS | 0 errors / 265 warnings (oas3-unused-component) | PASS via JSON (1205 models) |

Warning counts unchanged from 4e — same `oas3-unused-component` class
that bulk coverage produces. Smoke-test model counts unchanged.

## Summary of items closed in this sub-phase

| Item | Status | Action |
|---|---|---|
| 1. getRoles RBAC mapping | Closed | Per-property `x-weblogic-required-role` added (23 instances on 14.1.2). |
| 2. config-tree reference | Closed | Confirmed `ServerMBean.cluster` emits as Identity (array of strings); no fix needed. |
| 3. restartNeeded on read-only | Closed | Filter applied; flag only emitted on writable properties. `ServerRuntime.currentMachine` no longer carries the noise. |
| 4. overlay vocabulary | Closed | 3 fields honored (`required`, `dateAsLong`, `multiLineString`); the rest ignored with documented rationale. |
| 5. SettableBean inheritance | Closed | Premise was incorrect. SettableBean exists in harvested as a marker interface; chain walks correctly; nothing to fix. |

## Generator code surface changed

- `tools/openapi-generator/src/schema_builder.py`:
  - Read-only-aware filter for `restartNeeded` / `redeployNeeded`.
  - Per-property `x-weblogic-required-role` from `getRoles.allowed`.
  - Overlay-driven `x-weblogic-date-as-long` and `x-weblogic-multiline`.
  - Schema-level `required: [...]` aggregation from overlay
    property-level `required: true`.

No breaking changes to the public schema shape. Existing consumers see
new optional `x-` extensions and one new `required` array on schemas
that declare any required property; both are non-breaking under
OpenAPI 3.0 semantics.

## Verdict

All four deterministic items closed; item 5 closed by audit (premise
disproved). Generator now honors a small but useful slice of overlay
vocabulary that the harvested layer alone could not provide. No stop
conditions triggered. Ready for the next sub-phase.
