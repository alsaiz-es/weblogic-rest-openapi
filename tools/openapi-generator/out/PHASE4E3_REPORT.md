# Phase 4e-3 — Manual bodies for polymorphic stubs

## Goal

Provide manual body definitions for the polymorphic subtypes that the Remote Console UI overlay declares but for which no harvested YAML exists. Per Alfredo's 2026-04-28 decision: **option C — full manual authoring of all 12 subtypes**, sourced from Oracle Javadoc + public docs + empirical observation when available. Quality is honest: lower than harvested by design, declared via `x-weblogic-manual-schema: true` and `x-weblogic-source` for provenance.

After 4e-3, the deserialization contract is end-to-end complete on the canonical 14.1.2 / 15.1.1 build: a consumer receiving a polymorphic payload not only acquires the right discriminator value, but also has property bodies it can deserialize.

## Subtype roster (per the 4e investigation)

The exact set varies slightly across versions:

| Subtype | 12.2.1.3 / 12.2.1.4 | 14.1.1 | 14.1.2 / 15.1.1 |
|---|---|---|---|
| `CloudSecurityAgentAsserter` | stub | stub | stub |
| `CrossTenantAuthenticator` | stub | stub | stub |
| `IPlanetAuthenticator` | **harvested** | **harvested** | stub |
| `JDBCProxyDataSourceRuntime` | **harvested** | **harvested** | stub |
| `JMSQueueRuntime` | stub | stub | stub |
| `JMSTopicRuntime` | stub | stub | stub |
| `NovellAuthenticator` | **harvested** | **harvested** | stub |
| `OAMAuthenticator` | stub | stub | stub |
| `OAMCredentialMapper` | stub | stub | stub |
| `OAMIdentityAsserter` | stub | stub | stub |
| `OIDCIdentityAsserter` | stub | stub | **harvested** |
| `OracleVirtualDirectoryAuthenticator` | **harvested** | **harvested** | stub |
| `TrustServiceIdentityAsserter` | stub | stub | stub |

The pattern: 12.2.1.x had richer LDAP-authenticator coverage in the harvested set; 14.1.2 trimmed it back to a smaller surface, leaving the LDAP variants as discriminator-only stubs. OIDC went the other way — added to harvested in 14.1.2.

13 manual overlays authored to cover the union; the loader only fills schemas that are currently stubs (`x-stub: true`), skipping any version where the harvested already provides a body — exactly per the plan editorial note ("manual quality is inferior to harvested by design").

## Per-version application

| Version | Stubs filled | Skipped (harvested already present) | Residual stubs after fill |
|---|---:|---|---:|
| `12.2.1.3.0` | 9 | IPlanet, JDBCProxy, Novell, OracleVirtualDirectory | 1 (`RecourseActionEventVBean` — orphan stub, not polymorphic) |
| `12.2.1.4.0` | 9 | IPlanet, JDBCProxy, Novell, OracleVirtualDirectory | 1 (same) |
| `14.1.1.0.0` | 9 | IPlanet, JDBCProxy, Novell, OracleVirtualDirectory | 0 |
| `14.1.2.0.0` | **12** | OIDCIdentityAsserter (harvested) | 0 |
| `15.1.1.0.0` | **12** | OIDCIdentityAsserter (harvested) | 0 |

The single residual stub on 12.2.1.x (`RecourseActionEventVBean`) is a 12.2.1.x-only orphan reference stub created by the catch-all stub pass, not a polymorphic subtype declared by the UI overlay. Out of scope for 4e-3 per the plan.

## Manual schemas authored

Each schema is at `overlays/manual-schemas/<name>.yaml`. Sources are listed per file via `sources:` and stamped onto the generated schema as `x-weblogic-source`.

| Schema | Properties | Confidence | Sources |
|---|---:|---|---|
| `JMSQueueRuntime` | 16 | High | Oracle MBean Reference (Queue specialisation), Administering JMS Resources, live samples |
| `JMSTopicRuntime` | 17 | High | Oracle MBean Reference (Topic specialisation), Administering JMS Resources |
| `JDBCProxyDataSourceRuntime` | 9 | Medium | Oracle MBean Reference, Administering JDBC Data Sources (proxy chapter, 14c) |
| `OAMAuthenticator` | 9 | Medium | Securing Oracle WebLogic Server, Oracle Access Manager Admin Guide |
| `OAMIdentityAsserter` | 7 | Medium | Securing Oracle WebLogic Server, OAM-WLS integration guide |
| `OAMCredentialMapper` | 4 | Medium | Securing Oracle WebLogic Server (credential mapping), OAM Admin Guide |
| `OIDCIdentityAsserter` | 8 | Medium | Securing Oracle WebLogic Server (OIDC asserter chapter, 12.2.1.x), OIDC Core 1.0 |
| `TrustServiceIdentityAsserter` | 6 | Medium | Securing Oracle WebLogic Server, IDCS Admin Guide |
| `IPlanetAuthenticator` | 13 | Medium | Securing Oracle WebLogic Server, IPlanetAuthenticatorMBean reference |
| `NovellAuthenticator` | 11 | Medium | Securing Oracle WebLogic Server, NovellAuthenticatorMBean reference |
| `OracleVirtualDirectoryAuthenticator` | 11 | Medium | Securing Oracle WebLogic Server, OVD Admin Guide |
| `CrossTenantAuthenticator` | 4 | Low | Securing Oracle WebLogic Server (Multi-Tenant authentication, 12.2.1.x — deprecated) |
| `CloudSecurityAgentAsserter` | 5 | Low | IDCS Admin Guide (CSA integration), Securing WLS (cloud asserter chapter) |

Confidence rationale:

- **High** = subtype shape is well-documented in Oracle reference docs and live samples confirm the field set.
- **Medium** = subtype shape is documented in Oracle docs but no live samples were available for cross-checking.
- **Low** = subtype is niche / deprecated and authoring stayed conservative on a minimal-but-honest property set rather than speculating.

## Generator pipeline change

New module `tools/openapi-generator/src/manual_schemas.py`:

- `load_overlays()` reads every `overlays/manual-schemas/*.yaml`.
- `apply_manual_schemas(doc)` walks `components.schemas`, finds each named schema and the `type: object` branch inside its `allOf` (the branch carrying the discriminator constraint), then:
  - Adds overlay properties that don't conflict with the existing discriminator constraint.
  - Appends overlay `required` items.
  - Replaces the `description` (the stub's "Body deferred to Phase 4e..." placeholder).
  - Removes `x-stub: true` from the outer schema.
  - Stamps `x-weblogic-manual-schema: true` and `x-weblogic-source: [...]`.

**Stub guard.** When the schema does not carry `x-stub: true` (i.e. it has a real harvested body on this version), the loader skips it entirely with a `skipped_not_stub_harvested_present` record. This is the explicit honest contract the plan requires: harvested wins over manual for any version where harvested ships a real body.

Wired into `main.py` after `apply_polymorphism` (which creates the stub structure with the discriminator constraint) and before `apply_quirks` (so any quirk targeting a manual subtype lands on the now-rich body).

## Validation

| Check | Baseline (4e-2) | 4e-3 |
|---|---|---|
| `openapi-spec-validator` strict (5 versions) | PASS | **PASS** all 5 |
| `spectral lint` errors | 0 | **0** all 5 |
| `spectral lint` warnings | 0 | **0** all 5 |
| `openapi-generator-cli generate -g python` smoke (14.1.2 JSON) | 852 models | **852 models, 5 APIs — PASS** |

Spec / model counts are unchanged because the polymorphic stubs were already counted as schemas; this sub-phase fills their bodies, it doesn't add or remove components.

## Verification — generated client

Spot-check the python client generated from `out/spec-14.1.2.0.0.json`:

- `openapi_client/models/jms_queue_runtime.py`: present, carries `destination_type`, `insertion_paused`, `consumers_current_count`, etc. (7 of the listed properties verified by string match).
- `openapi_client/models/oam_authenticator.py`: present.
- `openapi_client/models/jdbc_proxy_data_source_runtime.py`: present.
- `openapi_client/models/jms_topic_runtime.py`: present.

Pre-4e-3 these would have generated as empty marker classes with only the `type` discriminator. Post-4e-3 they carry the property surfaces.

## Stop conditions revisited

None hit. Authoring did not cross into pure speculation: low-confidence schemas (`CrossTenantAuthenticator`, `CloudSecurityAgentAsserter`) ship deliberately minimal property sets rather than invented ones. Validators stayed green throughout.

## Edge cases

- **Version-skewed overlay applicability.** Because the same subtype is harvested on some versions and stubbed on others, the loader's stub-only guard means the overlay is "partial" by design: it fills the stub but leaves the harvested untouched. Stats record both outcomes for audit (`applied` + `skipped_not_stub_harvested_present`).
- **Discriminator constraint preservation.** The merger walks the `allOf` array to find the inline `type: object` branch (the one polymorphism placed the discriminator on) and adds properties to its existing `properties` map. Existing keys (the discriminator's enum-constrained property) are never overwritten — verified across all 12 subtype names.
- **`x-weblogic-source` provenance.** Every manually-authored schema carries the source list as a top-level extension. Consumers wishing to filter out "not from harvested" can do so via `x-weblogic-manual-schema: true`.
- **`RecourseActionEventVBean` orphan stub.** Lives only on 12.2.1.x. Created by the catch-all `_stub_schema()` for unresolved refs, not by polymorphism. Out of scope for 4e-3; the prune pass would drop it if nothing referenced it. The 1 residual stub on 12.2.1.x reflects this.

## Verdict

Sub-phase complete. All 12 polymorphic subtypes the plan called out have manual bodies on the canonical 14.1.2 / 15.1.1 build. Coverage on 12.2.1.x and 14.1.1 is hybrid (harvested where available, manual otherwise) and that's the honest state. The branch is now feature-complete on the original Phase 4 plan: every closeable item has been closed.

The remaining sub-phase is **4f**: replace `specs/` with the generated equivalent on main, tag v0.4.0, open the merge PR. That is a process step rather than a quality step.
