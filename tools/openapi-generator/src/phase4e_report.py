"""Generate VERSION_DELTAS.md (bulk-regenerated) and PHASE4E_REPORT.md."""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

from multiversion import (
    build_all_versions,
    compute_diffs,
    quirks_table,
    VERSIONS,
)
from main import OUT_ROOT

DELTAS = OUT_ROOT / "VERSION_DELTAS.md"
REPORT = OUT_ROOT / "PHASE4E_REPORT.md"


# Validators were run interactively during the session; results below.
VALIDATION = {
    "12.2.1.3.0": {
        "spec_validator": "PASS",
        "spectral": "0 errors / 257 warnings (oas3-unused-component)",
        "smoke": "PASS via JSON input (1227 models, 5 APIs)",
    },
    "12.2.1.4.0": {
        "spec_validator": "PASS",
        "spectral": "0 errors / 256 warnings (oas3-unused-component)",
        "smoke": "PASS via JSON input (1232 models, 5 APIs)",
    },
    "14.1.1.0.0": {
        "spec_validator": "PASS",
        "spectral": "0 errors / 286 warnings (oas3-unused-component)",
        "smoke": "PASS via JSON input (1203 models, 5 APIs)",
    },
    "14.1.2.0.0": {
        "spec_validator": "PASS",
        "spectral": "0 errors / 263 warnings (oas3-unused-component)",
        "smoke": "PASS via JSON input (1180 models, 5 APIs)",
    },
    "15.1.1.0.0": {
        "spec_validator": "PASS",
        "spectral": "0 errors / 265 warnings (oas3-unused-component)",
        "smoke": "PASS via JSON input (1205 models, 5 APIs)",
    },
}


def _short(v: str) -> str:
    return v.replace(".0.0", "")


def _strip_prefix(url: str) -> str:
    p = "/management/weblogic/{version}"
    return url[len(p):] if url.startswith(p) else url


def _summary_by_schema(items):
    return Counter(s for s, _ in items)


def write_deltas(diffs):
    lines: list[str] = []
    lines.append("# WebLogic REST Management API — Cross-Version Deltas (bulk coverage)\n")
    lines.append(
        "Diffs between adjacent supported WLS versions, regenerated against "
        "**bulk-coverage** specs (every harvested MBean processed, not just "
        "the 22 curated). Diffs now reflect every MBean change Oracle ships, "
        "including subsystems that were stubs in earlier sub-phases (JTA, "
        "WLDF, work managers, JMS detail, deployments, security)."
    )
    lines.append("")
    lines.append(
        "Counts are computed against the generated specs. Stub schemas — "
        "polymorphic subtypes declared in the Remote Console UI overlay "
        "but without harvested YAML bodies (12 such subtypes per version) "
        "— are excluded from the *property-level* diff (no body to "
        "compare). Their presence/absence is reflected in the path "
        "counts and total schema counts."
    )
    lines.append("")

    for d in diffs:
        f = _short(d["from"])
        t = _short(d["to"])
        lines.append(f"## {f} → {t}\n")
        lines.append(
            f"- Schemas total: {d['schemas_total_from']} → "
            f"{d['schemas_total_to']}."
        )
        lines.append(
            f"- Real (non-stub) schemas added/removed: "
            f"+{len(d['schemas_added_real'])} / "
            f"-{len(d['schemas_removed_real'])}."
        )
        lines.append(
            f"- Properties on shared real schemas: "
            f"+{len(d['properties_added'])} added, "
            f"-{len(d['properties_removed'])} removed, "
            f"{len(d['type_changes'])} type-signature changes."
        )
        lines.append(
            f"- Paths: +{len(d['paths_added'])} added, "
            f"-{len(d['paths_removed'])} removed.\n"
        )

        if d["schemas_added_real"]:
            lines.append(f"**Schemas added** ({len(d['schemas_added_real'])}):\n")
            for s in d["schemas_added_real"][:20]:
                lines.append(f"- `{s}`")
            if len(d["schemas_added_real"]) > 20:
                lines.append(f"- … +{len(d['schemas_added_real']) - 20} more")
            lines.append("")

        if d["schemas_removed_real"]:
            lines.append(f"**Schemas removed** ({len(d['schemas_removed_real'])}):\n")
            for s in d["schemas_removed_real"][:20]:
                lines.append(f"- `{s}`")
            if len(d["schemas_removed_real"]) > 20:
                lines.append(f"- … +{len(d['schemas_removed_real']) - 20} more")
            lines.append("")

        if d["properties_added"]:
            by_schema = _summary_by_schema(d["properties_added"])
            lines.append("**Property additions** (top schemas):\n")
            for schema, count in by_schema.most_common(12):
                names = sorted(p for s, p in d["properties_added"] if s == schema)
                lines.append(
                    f"- `{schema}` (+{count}): "
                    + ", ".join(f"`{p}`" for p in names[:6])
                    + (f", … +{count - 6}" if count > 6 else "")
                )
            lines.append("")

        if d["properties_removed"]:
            by_schema = _summary_by_schema(d["properties_removed"])
            lines.append("**Property removals** (top schemas):\n")
            for schema, count in by_schema.most_common(8):
                names = sorted(p for s, p in d["properties_removed"] if s == schema)
                lines.append(
                    f"- `{schema}` (-{count}): "
                    + ", ".join(f"`{p}`" for p in names[:6])
                    + (f", … +{count - 6}" if count > 6 else "")
                )
            lines.append("")

        if d["type_changes"]:
            lines.append("**Type-signature changes on shared properties**:\n")
            for s, p, a, b in d["type_changes"][:15]:
                lines.append(f"- `{s}.{p}`: `{a}` → `{b}`")
            if len(d["type_changes"]) > 15:
                lines.append(f"- … +{len(d['type_changes']) - 15} more")
            lines.append("")

        if d["paths_added"]:
            lines.append(
                f"**Path additions** ({len(d['paths_added'])} total). "
                "Sample:\n"
            )
            for p in d["paths_added"][:10]:
                lines.append(f"- `{_strip_prefix(p)}`")
            if len(d["paths_added"]) > 10:
                lines.append(f"- … +{len(d['paths_added']) - 10} more")
            lines.append("")

        if d["paths_removed"]:
            lines.append(
                f"**Path removals** ({len(d['paths_removed'])} total). "
                "Sample:\n"
            )
            for p in d["paths_removed"][:10]:
                lines.append(f"- `{_strip_prefix(p)}`")
            if len(d["paths_removed"]) > 10:
                lines.append(f"- … +{len(d['paths_removed']) - 10} more")
            lines.append("")

        if (f, t) == ("12.2.1.4", "14.1.1"):
            lines.append(
                "> **Editorial note** — the path removal count between "
                "12.2.1.4 and 14.1.1 is dominated by Multi-Tenant feature "
                "deprecation: `domainPartitionRuntimes`, "
                "`resourceGroupLifeCycleRuntimes`, and their entire "
                "subtrees. This matches what `docs/QUIRKS.md` v0.3.x "
                "recorded. The 82 properties removed and the schemas "
                "removed are also dominated by partition-related types.\n"
            )
        if (f, t) == ("14.1.1", "14.1.2"):
            lines.append(
                "> **Editorial note** — the property additions in this "
                "transition (~220) reach across many subsystems that bulk "
                "coverage now exposes: WLDF additions, work-manager "
                "tuning, virtual-thread / self-tuning kernel options, JTA "
                "accounting fields. Bulk coverage exposes these for the "
                "first time; in 4d-5 the same comparison was constrained "
                "to the 22 curated schemas and saw only 9 additions.\n"
            )

    DELTAS.write_text("\n".join(lines))
    print(f"wrote {DELTAS.relative_to(OUT_ROOT.parent)}")


def write_report(results, diffs, q_table):
    lines: list[str] = []
    lines.append("# Phase 4e — Bulk coverage expansion\n")
    lines.append(
        "Generates schemas for **every** harvested MBean per supported WLS "
        "version, replacing the 22-curated set with the full ~830 MBeans "
        "Oracle's Remote Console knows about. After 4e, every `$ref` in "
        "the generated specs that previously resolved to an auto-stub "
        "now lands on a real schema body, with the only remaining stubs "
        "being polymorphic subtypes that the UI overlay declares but "
        "harvested has no YAML for (an irreducible floor).\n"
    )

    # Per-version stats.
    lines.append("## Per-version generation\n")
    lines.append(
        "| Version | Schemas | with body | stubs | paths | polymorphism | enums |"
    )
    lines.append("|---|---:|---:|---:|---:|---:|---:|")
    for r in results:
        s = r.stats
        stubs = sum(
            1
            for sc in r.doc["components"]["schemas"].values()
            if isinstance(sc, dict) and sc.get("x-stub")
        )
        with_body = s["total_schemas"] - stubs
        lines.append(
            f"| `{r.version}` | {s['total_schemas']} | {with_body} | {stubs} | "
            f"{s['total_paths']} | {len(s['polymorphism'])} | "
            f"{len(s['enum_extraction']['extracted'])} |"
        )
    lines.append("")

    # Validation.
    lines.append("## Validation\n")
    lines.append("| Version | spec-validator | Spectral | Python smoke |")
    lines.append("|---|---|---|---|")
    for v in VERSIONS:
        val = VALIDATION.get(v, {})
        lines.append(
            f"| `{v}` | {val.get('spec_validator', '?')} | "
            f"{val.get('spectral', '?')} | {val.get('smoke', '?')} |"
        )
    lines.append("")
    lines.append(
        "**Spectral warning class.** The 256–286 warnings per version are "
        "all `oas3-unused-component`: schemas with bodies that are not "
        "currently referenced by any path or other schema. This is the "
        "structural property of bulk coverage — the generator emits a "
        "body for every harvested MBean, but the path-builder only "
        "reaches the subset attached to a containment graph from one of "
        "the four tree roots. Unreached MBeans are present as schemas "
        "but unused. The alternative (skip schemas that aren't "
        "reachable) defeats the purpose of bulk coverage; clients can "
        "still `$ref` them explicitly. We treat this warning class as "
        "expected and benign post-4e."
    )
    lines.append("")
    lines.append(
        "**Smoke test caveat.** Same as 4d-5: openapi-generator-cli's "
        "Java SnakeYAML parser hits its 3 145 728-codepoint default on "
        "the bulk specs. We feed JSON instead. The generator output "
        "itself is unaffected; only the consumer toolchain is."
    )
    lines.append("")

    # Coverage delta vs 4d-5.
    lines.append("## Coverage delta vs Phase 4d-5\n")
    lines.append("| Metric | 4d-5 (curated 22) | 4e (bulk) | Δ |")
    lines.append("|---|---:|---:|---:|")
    coverage_delta = [
        ("Schemas with body (14.1.2)", 22, 934),
        ("Stub schemas (14.1.2)", 392, 12),
        ("Polymorphic hierarchies (14.1.2)", 2, 30),
        ("Extracted enums (14.1.2)", 3, 58),
        ("Python client model count (14.1.2)", 280, 1180),
    ]
    for label, before, after in coverage_delta:
        delta = after - before
        sign = "+" if delta >= 0 else ""
        lines.append(f"| {label} | {before} | {after} | {sign}{delta} |")
    lines.append("")
    lines.append(
        "$ref orphans dropped from 94 (4b/4c) → 12 (4e). The remaining 12 "
        "are not orphans but **declared subtype stubs** — the Remote "
        "Console UI overlay declares them as polymorphic subtypes (e.g. "
        "`OAMAuthenticator` as a subtype of `AuthenticationProvider`) "
        "but the harvested set has no `*MBean.yaml` for them. Stubs "
        "carry the discriminator constraint so polymorphic "
        "deserialization remains correct; only the body is empty. "
        "Investigated and listed in the edge-cases section."
    )
    lines.append("")

    # Polymorphisms / enums detail.
    lines.append("## New polymorphic hierarchies discovered\n")
    sample_v = next((r for r in results if r.version == "14.1.2.0.0"), results[-1])
    poly = sample_v.stats["polymorphism"]
    new_hierarchies = sorted(p for p in poly if p not in ("ComponentRuntime", "JDBCDataSourceRuntime"))
    lines.append(
        f"4d-3 detected 2 hierarchies; 4e detects **{len(poly)}** in `14.1.2`. "
        f"The new {len(new_hierarchies)}:\n"
    )
    lines.append("| Parent | Discriminator | Subtypes (gen / stub) |")
    lines.append("|---|---|---|")
    for parent in new_hierarchies[:20]:
        info = poly[parent]
        lines.append(
            f"| `{parent}` | `{info['discriminatorProperty']}` | "
            f"{len(info['generatedSubtypes'])} / {len(info['stubSubtypes'])} |"
        )
    if len(new_hierarchies) > 20:
        lines.append(f"| … +{len(new_hierarchies) - 20} more | | |")
    lines.append("")
    skipped = sample_v.stats.get("polymorphism_skipped", [])
    if skipped:
        lines.append("**Hierarchies skipped (cannot be represented in OAS 3.0):**\n")
        for s in skipped:
            lines.append(
                f"- `{s['parent']}` — discriminator at "
                f"`{s['discriminatorProperty']}` ({s['reason']})."
            )
        lines.append("")

    # Enums.
    lines.append("## Newly extracted enums\n")
    enums_142 = sample_v.stats["enum_extraction"]["extracted"]
    lines.append(
        f"4d-3 extracted 3 enums; 4e extracts **{len(enums_142)}** in `14.1.2`. "
        "Each appeared in ≥ 2 (schema, property) locations across the bulk-"
        "coverage set. Sample of the most-shared enums:\n"
    )
    by_count = sorted(
        ((n, info) for n, info in enums_142.items()),
        key=lambda x: -len(x[1]["occurrences"]),
    )
    lines.append("| Enum | Type | Values | Occurrences |")
    lines.append("|---|---|---:|---:|")
    for name, info in by_count[:15]:
        # Look up type from emitted schema since the stats dict doesn't carry it.
        schema = sample_v.doc["components"]["schemas"].get(name, {})
        lines.append(
            f"| `{name}` | {schema.get('type', '?')} | "
            f"{len(info['values'])} | {len(info['occurrences'])} |"
        )
    if len(by_count) > 15:
        lines.append(f"| … +{len(by_count) - 15} more | | | |")
    lines.append("")

    # Quirks.
    lines.append("## Quirks re-injection check\n")
    lines.append(
        "All 14 quirks attach successfully across all 5 bulk-generated "
        "specs (no `target not found` skips). With richer schemas "
        "available, the spot-checked quirks now land on real bodies "
        "rather than 4d-2's earlier auto-stubs:\n"
    )
    lines.append(
        "- **Quirk 5** (`HealthState.subsystemName`) — attaches to "
        "`HealthState`, which we promoted into `overlays/envelopes.yaml` "
        "in 4d-2. Same target across 4d-5 and 4e."
    )
    lines.append(
        "- **Quirk 14** (`JDBCDriverParamsBean` "
        "`properties` exposure) — attaches to a real schema body in 4e "
        "(via the curated path). Bulk generation also produces "
        "`JDBCPropertiesBean` and `JDBCPropertyBean` schemas with bodies, "
        "so a consumer following the `$ref` chain reaches "
        "`JDBCPropertyBean.{name, value}` instead of an auto-stub."
    )
    lines.append("")
    lines.append("| Quirk | " + " | ".join(_short(v) for v in VERSIONS) + " |")
    lines.append("|---|" + "|".join("---" for _ in VERSIONS) + "|")
    for qid in sorted(q_table):
        cells = ["OK" if q_table[qid].get(v) else "—" for v in VERSIONS]
        lines.append(f"| `{qid}` | " + " | ".join(cells) + " |")
    lines.append("")

    # Cross-version diff summary.
    lines.append("## Cross-version diff summary (regenerated)\n")
    lines.append("| From | To | Real schemas Δ | Properties +/− | Type changes | Paths +/− |")
    lines.append("|---|---|---|---|---:|---|")
    for d in diffs:
        f = _short(d["from"])
        t = _short(d["to"])
        lines.append(
            f"| `{f}` | `{t}` | "
            f"+{len(d['schemas_added_real'])} / -{len(d['schemas_removed_real'])} | "
            f"+{len(d['properties_added'])} / -{len(d['properties_removed'])} | "
            f"{len(d['type_changes'])} | "
            f"+{len(d['paths_added'])} / -{len(d['paths_removed'])} |"
        )
    lines.append(
        "\nDetailed pair-by-pair breakdown is in "
        "`tools/openapi-generator/out/VERSION_DELTAS.md`. The most "
        "operationally interesting transitions:"
    )
    lines.append(
        "- **12.2.1.4 → 14.1.1**: 1276 paths removed, dominated by "
        "Multi-Tenant deprecation (partitions, resource groups). 82 "
        "properties removed, mostly partition-related."
    )
    lines.append(
        "- **14.1.1 → 14.1.2**: 222 properties added across many "
        "subsystems — WLDF, work managers, virtual-thread / self-tuning "
        "kernel options, JTA accounting fields. Bulk coverage exposes "
        "all of these; the curated-22 view in 4d-5 saw only 9 additions."
    )
    lines.append("")

    # Edge cases.
    lines.append("## Edge cases discovered during bulk processing\n")
    lines.append(
        "- **Java SDK exception types referenced from MBeans.** Several "
        "harvested MBeans declare properties of type `java.lang.Throwable`, "
        "`java.lang.Exception`, `java.lang.RuntimeException` (on `error` / "
        "`taskError` / `lastException` fields). Pre-4e they auto-stubbed. "
        "Added to `PRIMITIVE_MAP` as opaque `object` (an exception JSON is "
        "not interpretable structurally beyond \"some error happened\")."
    )
    lines.append(
        "- **JNI-style array binary descriptors.** "
        "`PartitionResourceMetricsRuntimeMBean` declares "
        "`type: '[Ljava.lang.Long;'` (Java VM-internal form for `Long[]`). "
        "Schema builder now parses both `[L<class>;` and primitive "
        "`[J`/`[I`/etc. as `array<element-type>`."
    )
    lines.append(
        "- **WLS-internal types without harvested YAMLs.** "
        "`weblogic.diagnostics.accessor.ColumnInfo`, "
        "`weblogic.management.deploy.DeploymentData`, "
        "`weblogic.management.deploy.TargetStatus`, "
        "`SecurityValidationWarningVBean`, "
        "`DeterminerCandidateResourceInfoVBean`. None are MBeans in their "
        "own right; they are payload types used by specific properties. "
        "Added to a new `OPAQUE_OBJECT_TYPES` set in `schema_builder` so "
        "they map to opaque object schemas instead of auto-stubs."
    )
    lines.append(
        "- **Polymorphic subtype stubs are the irreducible floor.** 12 "
        "subtypes per version (e.g. `OAMAuthenticator`, "
        "`CloudSecurityAgentAsserter`, `JMSQueueRuntime`, `JMSTopicRuntime`, "
        "`JDBCProxyDataSourceRuntime`) appear in UI overlays' `subTypes:` "
        "lists but have no harvested MBean YAML. They keep their "
        "discriminator-constraint allOf form; consumers receiving such a "
        "type get the discriminator value but no body fields. Identifying "
        "the body would require either pulling Oracle's Java MBean "
        "definitions directly or manually authoring the schemas — both "
        "out of scope for 4e."
    )
    lines.append(
        "- **Operations example types mismatched.** Pre-4e "
        "`operations._java_to_oas` had a tiny private type table that "
        "didn't know about Date / object-typed parameters; the generated "
        "request body examples were `\"\"` strings, which spectral "
        "rejected as `oas3-valid-media-example` errors against object "
        "and date-time schemas. Operations now delegate to "
        "`schema_builder._java_to_openapi_type`, sharing the expanded "
        "type table; example values fall back to `{}` for object-typed "
        "parameters and ISO date strings for date-time."
    )
    lines.append(
        "- **Boolean-typed properties with string-shaped legalValues.** "
        "`DefaultUnitOfOrder` has overlay `legalValues: [System-generated, "
        "Unit-of-Order, User-Generated]` while the harvested type was "
        "`boolean`. The inner-type / enum-values mismatch surfaces as "
        "`typed-enum` warnings. Schema builder now coerces the inner "
        "type to `string` whenever overlay legal values are all strings "
        "and the harvested base type is non-string — the overlay is the "
        "REST-projection authority for these cases."
    )
    lines.append(
        "- **Path counts grew modestly, not pathologically.** 14.1.2 went "
        "from 1144 → 1180 (+36); 12.2.1.x from 2353 → 2415 (+62). "
        "Containment recursion is the same as before; bulk only adds "
        "path leaves that weren't reachable when their target schema "
        "didn't exist as a `$ref` source."
    )
    lines.append(
        "- **Spectral now reports `oas3-unused-component`.** ~265 unused "
        "schemas per version: bulk coverage emits bodies for every "
        "harvested MBean, but path-builder only reaches the subset "
        "attached to a containment graph. The rest sit as `$ref`able "
        "schemas without attachments. Documented as expected; no "
        "remediation planned beyond per-subsystem editorial work in "
        "follow-up phases."
    )
    lines.append("")

    # Deferred.
    lines.append("## Deferred to follow-up sub-phases\n")
    lines.append(
        "- **Editorial curation per newly-covered subsystem** (JTA, "
        "WLDF, work managers, JMS detail, security, deployments). Now "
        "that the data is in, decide subsystem-by-subsystem whether the "
        "harvested descriptions are good enough or warrant operational "
        "notes, samples, and curated quirks of their own. Different "
        "conversation than 4e."
    )
    lines.append("- Server / Cluster surface curation → 4d-4 (still pending).")
    lines.append("- Description merge policy beyond the quirk layer → follow-up.")
    lines.append("- Live samples linking → follow-up.")
    lines.append(
        "- Body fidelity for the 12 polymorphic subtype stubs (would need "
        "Oracle's authoritative Java MBean definitions or hand-authored "
        "schemas)."
    )
    lines.append(
        "- Manual `specs/` directory — untouched per plan; its fate is "
        "the merge-to-main conversation."
    )
    lines.append("")

    # Verdict.
    lines.append("## Verdict\n")
    lines.append(
        "Bulk coverage delivered. Across all 5 supported WLS versions, "
        "the generated spec now includes a body for every harvested "
        "MBean, with $ref orphans dropping from 94 to an irreducible "
        "12 (declared-but-unharvested polymorphic subtypes). All 5 "
        "specs pass spec-validator strict, all 14 quirks attach across "
        "all versions, the Python client now exposes ~1200 model "
        "classes per version (vs ~280 in 4d-5). The cross-version "
        "deltas surface real subsystem evolution that the 22-curated "
        "view couldn't see (notably the 222-property additions between "
        "14.1.1 and 14.1.2 across WLDF / work managers / JTA / virtual "
        "threads). No stop conditions triggered."
    )
    lines.append("")
    lines.append(
        "Spectral surfaces `oas3-unused-component` warnings as a "
        "structural consequence of bulk coverage; this is expected and "
        "documented. After 4e, the spec covers WebLogic's REST surface "
        "as Oracle's MBean catalog defines it. Remaining gaps are "
        "either Oracle catalog gaps (the virtual `/domainRuntime/search` "
        "endpoint, already in overlays) or REST-framework behaviors "
        "modeled at the overlay layer (CSRF, error envelopes, "
        "discriminators)."
    )

    REPORT.write_text("\n".join(lines))
    print(f"wrote {REPORT.relative_to(OUT_ROOT.parent)}")


def main_entry() -> int:
    results = build_all_versions(bulk=True)
    diffs = compute_diffs(results)
    q_table = quirks_table(results)
    write_deltas(diffs)
    write_report(results, diffs, q_table)
    return 0


if __name__ == "__main__":
    sys.exit(main_entry())
