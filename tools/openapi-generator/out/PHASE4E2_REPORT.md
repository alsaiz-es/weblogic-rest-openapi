# Phase 4e-2 — Editorial curation per subsystem

## Goal

Add curated operational descriptions to subsystems newly covered by the 4e bulk expansion. Per Alfredo's 2026-04-28 decision: priority A Deployments + JMS detail; priority B Work Managers; priority C JTA + WLDF as opportunistic extensions. Description-overlay format only (mirrors 4d-6) — no new schemas, no new paths, no new operations.

After 4e-2, the four operationally-most-demanded subsystems carry editorial guidance beyond Oracle's harvested text.

## Scope summary

| Priority | Subsystem | Schemas curated | Status |
|---|---|---:|---|
| A | Deployments | 7 | complete |
| A | JMS detail | 7 | complete |
| B | Work Managers | 7 | complete |
| C | JTA | 4 | complete |
| C | WLDF | 4 | complete |

29 new description overlays added in this sub-phase, on top of the 21 from 4d-6.

## Priority A — Deployments

| Schema | scope of note |
|---|---|
| `AppDeployment` | `targets` tuple format, `deploymentOrder` library-first invariant, `moduleType` known values |
| `AppDeploymentRuntime` | per-application start/stop bean — vs `DeploymentManager` for redeploy |
| `AppRuntimeStateRuntime` | domain-wide aggregator answer to "is this app active across the cluster?" |
| `DeploymentManager` | role requirement (Deployer/Admin), JMX notification source |
| `DeploymentProgressObject` | AdminServer-only polling target for long-running deployments |
| `DeploymentRequestTaskRuntime` | prepare/commit phase split; per-target failure localisation |
| `LibDeploymentRuntime` | library version mismatch as startup-failure root cause |

Notes intentionally skipped: `Library` (`sourcePath` resolution rules already in harvested), `LibraryRuntime` (thin), `DeploymentTaskRuntime` (covered transitively by `DeploymentRequestTaskRuntime`), `AppDeployment` properties already documented elsewhere (`sourcePath`, `name`, etc.).

## Priority A — JMS detail

| Schema | scope of note |
|---|---|
| `JMSDestinationRuntimeBase` | counter conventions; `messageManagement` rel for peek/move/delete |
| `JMSConnectionRuntime` | session-leak signature pattern |
| `JMSDurableSubscriberRuntime` | stale-subscription cause of "topic that should be empty" |
| `JMSConnectionFactoryBean` | targeting mismatch as "destination not found" runtime cause |
| `JMSBridgeDestination` | per-leg transactional semantics depend on JCA adapter choice |
| `JMSSystemResource` | config/runtime split; no fast-path for module edits |
| `JMSServer` | migratable-target placement and store reachability |

Stubs explicitly skipped (4e-3 territory): `JMSQueueRuntime`, `JMSTopicRuntime`. They get bodies in 4e-3 and may receive notes there.

## Priority B — Work Managers

| Schema | scope of note |
|---|---|
| `WorkManager` | container concept — request class + constraints combinable, defaults |
| `WorkManagerRuntime` | bottleneck identification cross-reference (max-threads vs capacity) |
| `MaxThreadsConstraint` | external-resource ceiling; `connectionPoolName` autosizing |
| `MinThreadsConstraint` | priority-inversion / deadlock defense |
| `Capacity` | queue cap (independent of `MaxThreadsConstraint`); 503 rejection |
| `FairShareRequestClass` | relative-weight scheduling, default 50 |
| `ResponseTimeRequestClass` | SLO scheduling — averages, not per-request |

Notes intentionally skipped: `ContextRequestClass` (covered by harvested + the request-class triplet description on `WorkManager`), `RequestClassRuntime` (mostly aggregator).

## Priority C — JTA

| Schema | scope of note |
|---|---|
| `JTA` | domain tunables; per-server overrides via migratable target / DS config |
| `JTARuntime` | rollback subtotals; cumulative time as long-transaction signal |
| `JTARecoveryRuntime` | recovery delta as DBA-attention signal for in-doubt branches |
| `TransactionResourceRuntime` | heuristic counters as ACID-violation correctness incidents |

## Priority C — WLDF

| Schema | scope of note |
|---|---|
| `WLDFRuntime` | child-runtime taxonomy (harvester / access / watch / archive / instrumentation / image) |
| `WLDFHarvesterRuntime` | sampling-cost model; archive growth control via harvested set scope |
| `WLDFWatchNotificationRuntime` | renamed terminology (watch → policy); evaluation-vs-firing diagnosis |
| `WLDFImageRuntime` | diagnostic-image use case; capture frequency caveat |

## Validation

| Check | Baseline (4d-9) | 4e-2 |
|---|---|---|
| `openapi-spec-validator` strict (5 versions) | PASS | **PASS** all 5 |
| `spectral lint` errors | 0 | **0** all 5 |
| `spectral lint` warnings | 0 | **0** all 5 |
| `openapi-generator-cli generate -g python` smoke (14.1.2 JSON) | PASS, 852 models | **PASS, 852 models** |
| Description overlays applied per version | 21 | **50** |

50 overlays now apply per version (21 from 4d-6 + 29 from 4e-2). Skipped-property count remains constant (`JDBCConnectionPoolParamsBean.invokeBeginEndRequest` on 12.2.1.x where the field doesn't exist; `ApplicationRuntime.partitionName` on 14.1.x+ where the Multi-Tenant feature was removed).

## Subsystems intentionally not covered

- **Security (auth providers, identity stores, certs).** Out of scope per plan; consumers can rely on Oracle's documentation.
- **Mail sessions.** Low operational complexity; harvested is sufficient.
- **Coherence.** Specialised subsystem; correct curation needs Coherence-specific expertise outside this generator's scope.
- **Tuxedo / WTC.** Niche; not in the original 4 requested subsystems.
- **Multi-Tenant (partitions, resource groups).** Removed in 14.1.2; not worth curation effort given the deprecation.

## Edge cases

- **Polymorphic-parent schemas.** `JMSDestinationRuntime` is the polymorphic parent; the body lives in `JMSDestinationRuntimeBase`. The overlay targets the base so concrete subtypes (currently 4e-3 stubs) inherit the note when they're populated.
- **Config vs runtime split.** Several subsystems have parallel config + runtime beans (`JMSServer` vs `JMSServerRuntime`, `WorkManager` vs `WorkManagerRuntime`, `JTA` vs `JTARuntime`). Notes deliberately differentiate the two: config-side notes cover write-time concerns, runtime-side notes cover signal interpretation.
- **Cross-subsystem tie-ins.** Several notes deliberately reference siblings (Work Managers → ThreadPoolRuntime; Lifecycle → DeploymentManager; JMS → MigratableTarget). These are operational interactions that no single bean's description captures alone.

## Verdict

Sub-phase complete with all four chosen priorities (A + B + C) curated. 29 new operational notes shipped, validators stay green, schema and path counts unchanged. The branch retains clean spectral output (0 errors, 0 warnings) across all 5 versions.

Curation quality stayed honest: stop conditions did not fire because each subsystem had enough operationally-distinct content to make notes valuable rather than forced. Subsystems left as harvested-only remain consumable through Oracle's text.
