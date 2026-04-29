# Phase 4e-2 — Editorial curation per subsystem

## Goal

Add curated operational descriptions to subsystems newly covered by 4e
bulk generation. Subsystems chosen by Alfredo: Deployments, JMS detail,
Work Managers, with JTA and WLDF as opportunistic extensions.

After 4e-2, the subsystems most demanded by typical WebLogic admins
have descriptions that go beyond Oracle's harvested text where the
harvested is generic or insufficient.

## Out of scope

- Authoring complete subsystem documentation. This is curation, not
  rewriting Oracle's docs. Add operational notes only where they add
  real value beyond harvested.
- Body fidelity for the 12 polymorphic stubs (e.g. JMSQueueRuntime,
  JMSTopicRuntime). Those are 4e-3.
- Subsystems not in scope: security, mail sessions, Coherence,
  Tuxedo, partitions, etc. Acceptable as harvested-only.

## Scope and prioritization

Alfredo chose four subsystems with implicit priority by listing
order: Deployments, JMS detail, Work Managers, plus JTA and WLDF as
"also interesting". This sub-phase pragmatically interprets that as:

**Priority A (must complete):** Deployments, JMS detail.
**Priority B (complete if reasonable progress on A):** Work Managers.
**Priority C (opportunistic):** JTA, WLDF.

Per subsystem, the scope is description overlays only, mirroring 4d-6
format (`overlays/descriptions/<schema>.yaml`). No new schemas, no
new paths, no new operations.

## Tasks per subsystem

For each subsystem in priority order:

### 1. Identify schemas in scope

Walk the generated spec for the target version (14.1.2 as canonical)
and identify schemas belonging to the subsystem. Examples:

- **Deployments.** AppDeploymentRuntime, LibDeploymentRuntime,
  DeploymentManager, DeploymentProgressObject, AppRuntimeStateRuntime,
  ConfiguredDeployment, AppDeployment, Library.
- **JMS detail.** Per-destination beans not in the curated set:
  JMSQueueRuntime, JMSTopicRuntime, JMSDestinationRuntime,
  JMSConsumerRuntime, JMSProducerRuntime, JMSConnectionRuntime,
  JMSSessionRuntime, JMSMessageManagementRuntime, plus their config
  counterparts (JMSSystemResource, JMSResource, modules).
- **Work managers.** WorkManagerRuntime, WorkManagerHogger,
  RequestClassRuntime, MaxThreadsConstraint, MinThreadsConstraint,
  Capacity, ContextRequestClass, FairShareRequestClass,
  ResponseTimeRequestClass.
- **JTA.** JTARuntime, TransactionResourceRuntime,
  TransactionRecoveryRuntime, NonXAResourceRuntime, JTAStatistics
  collections.
- **WLDF.** WLDFAccessRuntime, WLDFRuntime, WLDFHarvesterRuntime,
  WLDFWatchNotificationRuntime, WLDFArchiveRuntime,
  WLDFInstrumentationRuntime, image runtime.

For schemas with bodies that are stubs (overlap with 4e-3), skip — they
get bodies and descriptions in 4e-3.

### 2. Identify properties needing curation

Per schema in scope, scan harvested descriptions. A property needs an
overlay note when:

- Harvested description is generic or terse and operational guidance
  exists in publicly known practice (e.g. "use this in conjunction
  with X for Y").
- Harvested description doesn't mention sensitivity (e.g. credential
  fields, internal-state-only properties).
- Harvested description doesn't mention performance implications
  (e.g. heavy properties that should be excluded from frequent polls).
- A property has cross-property semantics not captured in harvested
  (e.g. Capacity's behavior depends on whether MinThreadsConstraint
  is set).

A property does NOT need an overlay when:

- Harvested is already clear and complete.
- The note would just paraphrase harvested.
- The point is already covered by an existing quirk overlay.

### 3. Author overlays

Following the format from 4d-6, write
`overlays/descriptions/<schema>.yaml` for each schema with curation
content.

Source material for the curated text:

- Alfredo's experience as a middleware engineer (primary).
- Public Oracle WebLogic documentation (cross-reference, don't copy).
- Oracle MBean Reference Javadoc HTML (cross-reference for clarification).
- Empirical observation from samples in `samples/{version}/` where
  applicable.

The text should be terse and operational. Avoid restating Oracle's
text. Aim for 1-3 sentences per `operational_note`.

### 4. Validation per subsystem

After each subsystem's overlays are added:

- `openapi-spec-validator` strict — must remain PASS.
- `openapi-generator-cli generate -g python` smoke test — must remain
  PASS.
- `spectral lint` — must remain at 0 errors.
- Spot-check 3 schemas of the subsystem: harvested + operational note
  appear correctly chained.

### 5. Per-subsystem mini-report

Append to `tools/openapi-generator/out/PHASE4E2_REPORT.md`:

- Subsystem name and priority.
- Schemas in scope: count.
- Schemas with overlays: count.
- Properties with operational notes: count.
- Notes intentionally skipped: count + sample rationale.
- Validation result.

## Decision points during execution

The sub-phase's session can stop at any of these points and still
deliver value:

- After Priority A (Deployments + JMS detail): commit and consider
  whether to continue.
- After Priority B (+ Work Managers): commit and consider whether to
  continue.
- After Priority C (+ JTA + WLDF): full scope complete.

If at the end of any priority the work feels saturated (overlays
becoming forced or low-value), stop. Document the cutoff in the
report.

## Final report

`tools/openapi-generator/out/PHASE4E2_REPORT.md` consolidates all
mini-reports plus:

- Total schemas covered across all subsystems.
- Total operational notes added.
- Subsystems intentionally not covered with rationale (security,
  mail, etc.).
- Validation results across all 5 versions.
- Edge cases discovered.

## Commit strategy

Multiple commits, one per subsystem completed. Each commit's message
reflects the subsystem name and the priority level. After each commit,
update `REMAINING_WORK.md` if the sub-phase is partially done — adding
a note to the 4e-2 entry listing which subsystems are complete vs
deferred.

When all chosen subsystems are done, `REMAINING_WORK.md` moves the
4e-2 entry to "What is closed".

## Stop conditions

- Overlay authoring becomes forced (notes that just paraphrase
  harvested) → stop, current priority cutoff is the right place.
- Validators fail after a subsystem's overlays are added → stop, the
  overlay structure may have a bug.
- A subsystem reveals it needs body fidelity work, not just
  descriptions (e.g. JMSQueueRuntime is a stub) → defer that schema's
  body to 4e-3 and continue with the description-only schemas.
- Session energy/context runs short → commit current progress, stop,
  resume in a fresh session by re-reading this plan and
  `REMAINING_WORK.md`.

## Editorial notes

- This is the most editorial sub-phase. The quality of the curation
  is what matters, not the count. A handful of well-written notes per
  subsystem is better than dozens of forced notes.
- Curation should be operationally honest. If a property's behavior
  is genuinely well-described by harvested text, leaving it harvested
  is the right call — adding an overlay just to add an overlay is
  noise.
- The four chosen subsystems are the highest-demand ones for typical
  WebLogic admins. Investing curation here has the highest return per
  unit effort.
- Subsystems left as harvested-only (security, mail, Coherence, etc.)
  remain consumable. Their consumers can rely on Oracle's text. That
  is acceptable, not a project gap.
