# Phase 4e — Bulk coverage expansion

Generates schemas for **every** harvested MBean per supported WLS version, replacing the 22-curated set with the full ~830 MBeans Oracle's Remote Console knows about. After 4e, every `$ref` in the generated specs that previously resolved to an auto-stub now lands on a real schema body, with the only remaining stubs being polymorphic subtypes that the UI overlay declares but harvested has no YAML for (an irreducible floor).

## Per-version generation

| Version | Schemas | with body | stubs | paths | polymorphism | enums |
|---|---:|---:|---:|---:|---:|---:|
| `12.2.1.3.0` | 974 | 964 | 10 | 2403 | 30 | 62 |
| `12.2.1.4.0` | 978 | 968 | 10 | 2415 | 30 | 64 |
| `14.1.1.0.0` | 974 | 965 | 9 | 1144 | 30 | 64 |
| `14.1.2.0.0` | 946 | 934 | 12 | 1180 | 30 | 58 |
| `15.1.1.0.0` | 960 | 948 | 12 | 1227 | 30 | 58 |

## Validation

| Version | spec-validator | Spectral | Python smoke |
|---|---|---|---|
| `12.2.1.3.0` | PASS | 0 errors / 257 warnings (oas3-unused-component) | PASS via JSON input (1227 models, 5 APIs) |
| `12.2.1.4.0` | PASS | 0 errors / 256 warnings (oas3-unused-component) | PASS via JSON input (1232 models, 5 APIs) |
| `14.1.1.0.0` | PASS | 0 errors / 286 warnings (oas3-unused-component) | PASS via JSON input (1203 models, 5 APIs) |
| `14.1.2.0.0` | PASS | 0 errors / 263 warnings (oas3-unused-component) | PASS via JSON input (1180 models, 5 APIs) |
| `15.1.1.0.0` | PASS | 0 errors / 265 warnings (oas3-unused-component) | PASS via JSON input (1205 models, 5 APIs) |

**Spectral warning class.** The 256–286 warnings per version are all `oas3-unused-component`: schemas with bodies that are not currently referenced by any path or other schema. This is the structural property of bulk coverage — the generator emits a body for every harvested MBean, but the path-builder only reaches the subset attached to a containment graph from one of the four tree roots. Unreached MBeans are present as schemas but unused. The alternative (skip schemas that aren't reachable) defeats the purpose of bulk coverage; clients can still `$ref` them explicitly. We treat this warning class as expected and benign post-4e.

**Smoke test caveat.** Same as 4d-5: openapi-generator-cli's Java SnakeYAML parser hits its 3 145 728-codepoint default on the bulk specs. We feed JSON instead. The generator output itself is unaffected; only the consumer toolchain is.

## Coverage delta vs Phase 4d-5

| Metric | 4d-5 (curated 22) | 4e (bulk) | Δ |
|---|---:|---:|---:|
| Schemas with body (14.1.2) | 22 | 934 | +912 |
| Stub schemas (14.1.2) | 392 | 12 | -380 |
| Polymorphic hierarchies (14.1.2) | 2 | 30 | +28 |
| Extracted enums (14.1.2) | 3 | 58 | +55 |
| Python client model count (14.1.2) | 280 | 1180 | +900 |

$ref orphans dropped from 94 (4b/4c) → 12 (4e). The remaining 12 are not orphans but **declared subtype stubs** — the Remote Console UI overlay declares them as polymorphic subtypes (e.g. `OAMAuthenticator` as a subtype of `AuthenticationProvider`) but the harvested set has no `*MBean.yaml` for them. Stubs carry the discriminator constraint so polymorphic deserialization remains correct; only the body is empty. Investigated and listed in the edge-cases section.

## New polymorphic hierarchies discovered

4d-3 detected 2 hierarchies; 4e detects **30** in `14.1.2`. The new 28:

| Parent | Discriminator | Subtypes (gen / stub) |
|---|---|---|
| `Adjudicator` | `type` | 1 / 0 |
| `AsyncReplicationRuntime` | `type` | 1 / 0 |
| `Auditor` | `type` | 1 / 0 |
| `AuthenticationProvider` | `type` | 18 / 8 |
| `AuthenticatorRuntime` | `type` | 1 / 0 |
| `Authorizer` | `type` | 2 / 0 |
| `CertPathProvider` | `type` | 2 / 0 |
| `ComponentConcurrentRuntime` | `type` | 2 / 0 |
| `CredentialMapper` | `type` | 4 / 1 |
| `DataAccessRuntime` | `type` | 1 / 0 |
| `DataRetirementTaskRuntime` | `type` | 1 / 0 |
| `EJBRuntime` | `type` | 5 / 0 |
| `JMSDestinationRuntime` | `destinationType` | 0 / 2 |
| `JTAStatisticsRuntime` | `type` | 3 / 0 |
| `JTATransactionStatisticsRuntime` | `type` | 2 / 0 |
| `JaxRsUriRuntime` | `type` | 1 / 0 |
| `MANReplicationRuntime` | `type` | 1 / 0 |
| `Machine` | `type` | 1 / 0 |
| `ManagedExecutorServiceRuntime` | `type` | 1 / 0 |
| `PasswordValidator` | `type` | 1 / 0 |
| … +8 more | | |

**Hierarchies skipped (cannot be represented in OAS 3.0):**

- `JDBCSystemResource` — discriminator at `JDBCResource.DatasourceType` (nested discriminator path is not representable in OAS 3.0).

## Newly extracted enums

4d-3 extracted 3 enums; 4e extracts **58** in `14.1.2`. Each appeared in ≥ 2 (schema, property) locations across the bulk-coverage set. Sample of the most-shared enums:

| Enum | Type | Values | Occurrences |
|---|---|---:|---:|
| `Progress` | string | 4 | 19 |
| `DeploymentState` | integer | 4 | 16 |
| `ControlFlag` | string | 4 | 15 |
| `UserSearchScope` | string | 2 | 10 |
| `SAFExportPolicy` | string | 2 | 10 |
| `StagingMode` | string | 3 | 9 |
| `LoadBalancingPolicy` | string | 2 | 9 |
| `RotationType` | string | 4 | 7 |
| `AttachSender` | string | 3 | 7 |
| `UnitOfWorkHandlingPolicy` | string | 2 | 7 |
| `UnitOfOrderRouting` | string | 2 | 7 |
| `WebLogicProtocol` | string | 6 | 6 |
| `OutboundCertificateValidation` | string | 2 | 6 |
| `NonPersistentQos` | string | 3 | 6 |
| `GroupMembershipSearching` | string | 3 | 5 |
| … +43 more | | | |

## Quirks re-injection check

All 14 quirks attach successfully across all 5 bulk-generated specs (no `target not found` skips). With richer schemas available, the spot-checked quirks now land on real bodies rather than 4d-2's earlier auto-stubs:

- **Quirk 5** (`HealthState.subsystemName`) — attaches to `HealthState`, which we promoted into `overlays/envelopes.yaml` in 4d-2. Same target across 4d-5 and 4e.
- **Quirk 14** (`JDBCDriverParamsBean` `properties` exposure) — attaches to a real schema body in 4e (via the curated path). Bulk generation also produces `JDBCPropertiesBean` and `JDBCPropertyBean` schemas with bodies, so a consumer following the `$ref` chain reaches `JDBCPropertyBean.{name, value}` instead of an auto-stub.

| Quirk | 12.2.1.3.0 | 12.2.1.4.0 | 14.1.1 | 14.1.2 | 15.1.1 |
|---|---|---|---|---|---|
| `channel-missing-listenAddress-listenPort` | OK | OK | OK | OK | OK |
| `csrf-on-mutations` | OK | OK | OK | OK | OK |
| `csrf-serverRuntimes` | OK | OK | OK | OK | OK |
| `edit-error-envelope-fqcn` | OK | OK | OK | OK | OK |
| `healthstate-lowercase` | OK | OK | OK | OK | OK |
| `healthstate-subsystemname-null` | OK | OK | OK | OK | OK |
| `jdbc-properties-user-exposure` | OK | OK | OK | OK | OK |
| `jdbc-systemresources-400-staged-create` | OK | OK | OK | OK | OK |
| `jvm-os-prefix-uppercase` | OK | OK | OK | OK | OK |
| `jvm-threadstackdump-size` | OK | OK | OK | OK | OK |
| `lifecycle-async-task-shape` | OK | OK | OK | OK | OK |
| `name-semantics-vary` | OK | OK | OK | OK | OK |
| `startedit-idempotent` | OK | OK | OK | OK | OK |
| `state-casing-inconsistencies` | OK | OK | OK | OK | OK |

## Cross-version diff summary (regenerated)

| From | To | Real schemas Δ | Properties +/− | Type changes | Paths +/− |
|---|---|---|---|---:|---|
| `12.2.1.3.0` | `12.2.1.4.0` | +4 / -0 | +61 / -14 | 0 | +12 / -0 |
| `12.2.1.4.0` | `14.1.1` | +3 / -6 | +16 / -82 | 0 | +5 / -1276 |
| `14.1.1` | `14.1.2` | +9 / -40 | +222 / -12 | 8 | +36 / -0 |
| `14.1.2` | `15.1.1` | +14 / -0 | +29 / -2 | 0 | +49 / -2 |

Detailed pair-by-pair breakdown is in `tools/openapi-generator/out/VERSION_DELTAS.md`. The most operationally interesting transitions:
- **12.2.1.4 → 14.1.1**: 1276 paths removed, dominated by Multi-Tenant deprecation (partitions, resource groups). 82 properties removed, mostly partition-related.
- **14.1.1 → 14.1.2**: 222 properties added across many subsystems — WLDF, work managers, virtual-thread / self-tuning kernel options, JTA accounting fields. Bulk coverage exposes all of these; the curated-22 view in 4d-5 saw only 9 additions.

## Edge cases discovered during bulk processing

- **Java SDK exception types referenced from MBeans.** Several harvested MBeans declare properties of type `java.lang.Throwable`, `java.lang.Exception`, `java.lang.RuntimeException` (on `error` / `taskError` / `lastException` fields). Pre-4e they auto-stubbed. Added to `PRIMITIVE_MAP` as opaque `object` (an exception JSON is not interpretable structurally beyond "some error happened").
- **JNI-style array binary descriptors.** `PartitionResourceMetricsRuntimeMBean` declares `type: '[Ljava.lang.Long;'` (Java VM-internal form for `Long[]`). Schema builder now parses both `[L<class>;` and primitive `[J`/`[I`/etc. as `array<element-type>`.
- **WLS-internal types without harvested YAMLs.** `weblogic.diagnostics.accessor.ColumnInfo`, `weblogic.management.deploy.DeploymentData`, `weblogic.management.deploy.TargetStatus`, `SecurityValidationWarningVBean`, `DeterminerCandidateResourceInfoVBean`. None are MBeans in their own right; they are payload types used by specific properties. Added to a new `OPAQUE_OBJECT_TYPES` set in `schema_builder` so they map to opaque object schemas instead of auto-stubs.
- **Polymorphic subtype stubs are the irreducible floor.** 12 subtypes per version (e.g. `OAMAuthenticator`, `CloudSecurityAgentAsserter`, `JMSQueueRuntime`, `JMSTopicRuntime`, `JDBCProxyDataSourceRuntime`) appear in UI overlays' `subTypes:` lists but have no harvested MBean YAML. They keep their discriminator-constraint allOf form; consumers receiving such a type get the discriminator value but no body fields. Identifying the body would require either pulling Oracle's Java MBean definitions directly or manually authoring the schemas — both out of scope for 4e.
- **Operations example types mismatched.** Pre-4e `operations._java_to_oas` had a tiny private type table that didn't know about Date / object-typed parameters; the generated request body examples were `""` strings, which spectral rejected as `oas3-valid-media-example` errors against object and date-time schemas. Operations now delegate to `schema_builder._java_to_openapi_type`, sharing the expanded type table; example values fall back to `{}` for object-typed parameters and ISO date strings for date-time.
- **Boolean-typed properties with string-shaped legalValues.** `DefaultUnitOfOrder` has overlay `legalValues: [System-generated, Unit-of-Order, User-Generated]` while the harvested type was `boolean`. The inner-type / enum-values mismatch surfaces as `typed-enum` warnings. Schema builder now coerces the inner type to `string` whenever overlay legal values are all strings and the harvested base type is non-string — the overlay is the REST-projection authority for these cases.
- **Path counts grew modestly, not pathologically.** 14.1.2 went from 1144 → 1180 (+36); 12.2.1.x from 2353 → 2415 (+62). Containment recursion is the same as before; bulk only adds path leaves that weren't reachable when their target schema didn't exist as a `$ref` source.
- **Spectral now reports `oas3-unused-component`.** ~265 unused schemas per version: bulk coverage emits bodies for every harvested MBean, but path-builder only reaches the subset attached to a containment graph. The rest sit as `$ref`able schemas without attachments. Documented as expected; no remediation planned beyond per-subsystem editorial work in follow-up phases.

## Deferred to follow-up sub-phases

- **Editorial curation per newly-covered subsystem** (JTA, WLDF, work managers, JMS detail, security, deployments). Now that the data is in, decide subsystem-by-subsystem whether the harvested descriptions are good enough or warrant operational notes, samples, and curated quirks of their own. Different conversation than 4e.
- Server / Cluster surface curation → 4d-4 (still pending).
- Description merge policy beyond the quirk layer → follow-up.
- Live samples linking → follow-up.
- Body fidelity for the 12 polymorphic subtype stubs (would need Oracle's authoritative Java MBean definitions or hand-authored schemas).
- Manual `specs/` directory — untouched per plan; its fate is the merge-to-main conversation.

## Verdict

Bulk coverage delivered. Across all 5 supported WLS versions, the generated spec now includes a body for every harvested MBean, with $ref orphans dropping from 94 to an irreducible 12 (declared-but-unharvested polymorphic subtypes). All 5 specs pass spec-validator strict, all 14 quirks attach across all versions, the Python client now exposes ~1200 model classes per version (vs ~280 in 4d-5). The cross-version deltas surface real subsystem evolution that the 22-curated view couldn't see (notably the 222-property additions between 14.1.1 and 14.1.2 across WLDF / work managers / JTA / virtual threads). No stop conditions triggered.

Spectral surfaces `oas3-unused-component` warnings as a structural consequence of bulk coverage; this is expected and documented. After 4e, the spec covers WebLogic's REST surface as Oracle's MBean catalog defines it. Remaining gaps are either Oracle catalog gaps (the virtual `/domainRuntime/search` endpoint, already in overlays) or REST-framework behaviors modeled at the overlay layer (CSRF, error envelopes, discriminators).