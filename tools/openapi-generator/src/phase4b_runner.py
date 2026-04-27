"""Phase 4b — generate schemas for the MBeans we cover manually,
compare each against the manual spec, and write a consolidated report.

Output (under tools/openapi-generator/out/):
    schemas/<MBean>.generated.yaml      (per-MBean generated fragment)
    PHASE4B_REPORT.md                   (consolidated report)
"""
from __future__ import annotations

import sys
from io import StringIO
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

from harvested_loader import HarvestedLoader
import schema_builder
from schema_builder import build_component_schema
from manual_loader import effective_properties, get_schema, SPECS_ROOT

OUT_ROOT = Path(__file__).resolve().parents[1] / "out"
SCHEMAS_OUT = OUT_ROOT / "schemas"
SCHEMAS_OUT.mkdir(parents=True, exist_ok=True)
REPORT = OUT_ROOT / "PHASE4B_REPORT.md"

# Target list. Each entry: (mbean_name_in_harvested, manual_spec_relpath, manual_schema_name, group)
# When the harvested name does not exist (e.g. JDBCResource), we substitute
# the descriptor-bean equivalent.
TARGETS: list[tuple[str, str, str, str]] = [
    # Monitoring
    ("ServerRuntimeMBean",                "domain-runtime/servers.yaml",      "ServerRuntime",                "monitoring"),
    ("ThreadPoolRuntimeMBean",            "domain-runtime/threading.yaml",    "ThreadPoolRuntime",            "monitoring"),
    ("JVMRuntimeMBean",                   "domain-runtime/jvm.yaml",          "JVMRuntime",                   "monitoring"),
    ("JDBCServiceRuntimeMBean",           "domain-runtime/jdbc.yaml",         "JDBCServiceRuntime",           "monitoring"),
    ("JDBCDataSourceRuntimeMBean",        "domain-runtime/jdbc.yaml",         "JDBCDataSourceRuntime",        "monitoring"),
    ("ApplicationRuntimeMBean",           "domain-runtime/applications.yaml", "ApplicationRuntime",           "monitoring"),
    ("ComponentRuntimeMBean",             "domain-runtime/components.yaml",   "ComponentRuntimeBase",         "monitoring"),
    ("WebAppComponentRuntimeMBean",       "domain-runtime/components.yaml",   "WebAppComponentRuntime",       "monitoring"),
    ("EJBComponentRuntimeMBean",          "domain-runtime/components.yaml",   "EJBComponentRuntime",          "monitoring"),
    ("ConnectorComponentRuntimeMBean",    "domain-runtime/components.yaml",   "ConnectorComponentRuntime",    "monitoring"),
    ("AppClientComponentRuntimeMBean",    "domain-runtime/components.yaml",   "AppClientComponentRuntime",    "monitoring"),
    ("ServerChannelRuntimeMBean",         "domain-runtime/channels.yaml",     "ServerChannelRuntime",         "monitoring"),
    ("JMSRuntimeMBean",                   "domain-runtime/jms.yaml",          "JMSRuntime",                   "monitoring"),
    ("JMSServerRuntimeMBean",             "domain-runtime/jms.yaml",          "JMSServerRuntime",             "monitoring"),
    # Edit tree
    ("ServerMBean",                       "edit/servers.yaml",                "Server",                       "edit"),
    ("ClusterMBean",                      "edit/clusters.yaml",               "Cluster",                      "edit"),
    ("JDBCSystemResourceMBean",           "edit/datasources.yaml",            "JDBCSystemResource",           "edit"),
    # The next four are descriptor beans (no `M`).
    ("JDBCDataSourceBean",                "edit/datasources.yaml",            "JDBCResource",                 "edit"),
    ("JDBCDataSourceParamsBean",          "edit/datasources.yaml",            "JDBCDataSourceParams",         "edit"),
    ("JDBCDriverParamsBean",              "edit/datasources.yaml",            "JDBCDriverParams",             "edit"),
    ("JDBCConnectionPoolParamsBean",      "edit/datasources.yaml",            "JDBCConnectionPoolParams",     "edit"),
    # Lifecycle
    ("ServerLifeCycleRuntimeMBean",       "lifecycle/lifecycle.yaml",         "ServerLifeCycleRuntime",       "lifecycle"),
    # Change manager — has no MBean, virtual REST endpoint. Skipped from generation
    # but recorded in the report.
]


def _type_signature(prop_schema: dict[str, Any]) -> str:
    if not isinstance(prop_schema, dict):
        return "?"
    if "$ref" in prop_schema:
        return f"$ref:{prop_schema['$ref'].rsplit('/', 1)[-1]}"
    if "allOf" in prop_schema:
        first = prop_schema["allOf"][0]
        if isinstance(first, dict):
            return _type_signature(first)
        return "?"
    t = prop_schema.get("type", "?")
    if t == "array":
        items = prop_schema.get("items", {})
        return f"array<{_type_signature(items)}>"
    fmt = prop_schema.get("format")
    if "enum" in prop_schema:
        return f"{t}({fmt})/enum" if fmt else f"{t}/enum"
    return f"{t}({fmt})" if fmt else t


def _dump_yaml(obj: dict[str, Any]) -> str:
    yaml = YAML()
    yaml.default_flow_style = False
    yaml.width = 120
    buf = StringIO()
    yaml.dump(obj, buf)
    return buf.getvalue()


def _collect_orphan_refs(node: object, target_schema_names: set[str]) -> set[str]:
    refs: set[str] = set()

    def walk(n: object) -> None:
        if isinstance(n, dict):
            r = n.get("$ref")
            if isinstance(r, str) and r.startswith("#/components/schemas/"):
                name = r.rsplit("/", 1)[-1]
                if name not in target_schema_names:
                    refs.add(name)
            for v in n.values():
                walk(v)
        elif isinstance(n, list):
            for v in n:
                walk(v)

    walk(node)
    return refs


def main() -> int:
    loader = HarvestedLoader("14.1.2.0.0")

    # Compute the set of normalized schema names we *will* emit, so orphan
    # detection can distinguish "ref to a schema we haven't generated" from
    # "ref to a schema that is in this batch".
    target_schema_names = {schema_builder.normalize_schema_name(t[0]) for t in TARGETS}

    rows: list[dict[str, Any]] = []
    all_orphans: dict[str, set[str]] = {}
    edge_cases: list[str] = []

    for mbean, spec_rel, manual_name, group in TARGETS:
        spec_path = SPECS_ROOT / spec_rel
        try:
            built = build_component_schema(mbean, "14.1.2.0.0", loader=loader)
        except FileNotFoundError as e:
            edge_cases.append(f"{mbean}: harvested YAML not found ({e})")
            continue
        schema = built["schema"]
        gen_props: dict[str, Any] = schema.get("properties") or {}

        # Manual side: resolve allOf to get effective props.
        man_props = effective_properties(spec_path, manual_name)

        gen_names = set(gen_props)
        man_names = set(man_props)
        in_both = sorted(gen_names & man_names)
        only_gen = sorted(gen_names - man_names)
        only_man = sorted(man_names - gen_names)

        type_mismatches: list[tuple[str, str, str]] = []
        for n in in_both:
            gsig = _type_signature(gen_props[n])
            msig = _type_signature(man_props[n])
            if gsig != msig:
                type_mismatches.append((n, gsig, msig))

        coverage = (len(in_both) / len(man_names) * 100.0) if man_names else 0.0

        # Orphans inside the generated schema.
        orphans = _collect_orphan_refs(schema, target_schema_names)
        for o in orphans:
            all_orphans.setdefault(o, set()).add(built["schemaName"])

        # Inheritance chain notes.
        chain_outside_harvested = []
        for level in built["chain"][1:]:
            if loader.try_load(level) is None:
                chain_outside_harvested.append(level)

        rows.append(
            {
                "group": group,
                "mbean": mbean,
                "schemaName": built["schemaName"],
                "manualName": manual_name,
                "specRel": spec_rel,
                "gen": len(gen_props),
                "man": len(man_props),
                "in_both": len(in_both),
                "only_gen": only_gen,
                "only_man": only_man,
                "mismatches": type_mismatches,
                "coverage": coverage,
                "skipped": built["skipped"],
                "chain": built["chain"],
                "perLevel": built["perLevel"],
                "chainOutsideHarvested": chain_outside_harvested,
            }
        )

        # Per-MBean YAML output.
        out_path = SCHEMAS_OUT / f"{built['schemaName']}.generated.yaml"
        out_path.write_text(_dump_yaml({built["schemaName"]: schema}))

        # Stop condition: coverage < 50 %  AND we have a non-empty manual side.
        if rows[-1]["man"] > 0 and rows[-1]["coverage"] < 50.0:
            edge_cases.append(
                f"⚠ STOP-CONDITION: {built['schemaName']} coverage "
                f"{rows[-1]['coverage']:.1f} % (<50 %). gen={rows[-1]['gen']} man={rows[-1]['man']}"
            )

    write_report(rows, all_orphans, edge_cases, target_schema_names)
    return 0


def write_report(rows, all_orphans, edge_cases, target_schema_names) -> None:
    lines: list[str] = []
    lines.append("# Phase 4b — Consolidated generator report\n")
    lines.append(f"WLS version: 14.1.2.0.0  ·  MBeans attempted: {len(rows)}\n")
    lines.append("")

    # Summary table.
    lines.append("## Summary\n")
    lines.append(
        "| Group | Schema | gen | man | both | only_gen | only_man | mismatches | coverage |"
    )
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|---:|")
    for r in rows:
        lines.append(
            f"| {r['group']} | `{r['schemaName']}` ← `{r['mbean']}` "
            f"| {r['gen']} | {r['man']} | {r['in_both']} | {len(r['only_gen'])} "
            f"| {len(r['only_man'])} | {len(r['mismatches'])} | {r['coverage']:.0f} % |"
        )
    # Aggregate.
    total_gen = sum(r["gen"] for r in rows)
    total_man = sum(r["man"] for r in rows)
    total_both = sum(r["in_both"] for r in rows)
    coverage_agg = (total_both / total_man * 100.0) if total_man else 0.0
    lines.append(
        f"| **TOTAL** | — | **{total_gen}** | **{total_man}** | **{total_both}** "
        f"| — | — | — | **{coverage_agg:.0f} %** |"
    )
    lines.append("")

    # Skipped MBean: ChangeManager.
    lines.append("## MBeans skipped from harvested generation\n")
    lines.append(
        "- `ChangeManagerMBean` — does **not** exist as a harvested MBean. "
        "The change-manager REST surface (`/edit/changeManager` + actions) is a "
        "virtual endpoint generated by the WLS REST framework, not an MBean. "
        "Manual schemas in `specs/edit/change-manager.yaml` "
        "(`ChangeManagerState`, `EditErrorDetail`, `EditErrorResponse`) must "
        "remain hand-written.\n"
    )

    # Where generated does NOT cover manual.
    lines.append("## MBeans where generated does NOT improve manual\n")
    no_improve = [r for r in rows if r["only_man"] and r["man"] > 0]
    if not no_improve:
        lines.append("(none — every comparison either improves or matches the manual)\n")
    else:
        for r in no_improve:
            lines.append(f"### `{r['schemaName']}` ← `{r['mbean']}`")
            lines.append(
                f"- coverage **{r['coverage']:.0f} %**  ({r['in_both']}/{r['man']})  ·  "
                f"manual props: {r['man']}  ·  generated props: {r['gen']}"
            )
            lines.append(f"- only-in-manual ({len(r['only_man'])}):")
            for n in r["only_man"]:
                lines.append(f"  - `{n}`")
            if r["mismatches"]:
                lines.append(f"- type mismatches ({len(r['mismatches'])}):")
                for n, g, m in r["mismatches"][:8]:
                    lines.append(f"  - `{n}`: gen=`{g}` manual=`{m}`")
            lines.append("")

    # Pattern analysis on mismatches.
    lines.append("## Mismatch patterns\n")
    pat_int_size = []   # int32<->int64 disagreements
    pat_enum_ref = []   # gen enum vs manual $ref to a sibling enum schema
    pat_enum_str = []   # gen enum vs manual plain string (gen strictly better)
    pat_ref_str_arr = []  # gen array<string> vs manual array<object>/object
    pat_other = []
    for r in rows:
        for n, g, m in r["mismatches"]:
            sample = (r["schemaName"], n, g, m)
            if g.startswith("integer(int") and m.startswith("integer(int") and g != m:
                pat_int_size.append(sample)
            elif g.endswith("/enum") and m.startswith("$ref:"):
                pat_enum_ref.append(sample)
            elif g.endswith("/enum") and m in ("string", "integer(int32)", "integer(int64)"):
                pat_enum_str.append(sample)
            elif g in ("array<string>",) and m in ("array<object>", "object", "array<array<string>>"):
                pat_ref_str_arr.append(sample)
            else:
                pat_other.append(sample)

    def _emit_pattern(title: str, items: list, note: str) -> None:
        lines.append(f"### {title} ({len(items)})")
        lines.append(note)
        if items:
            lines.append("")
            for s, n, g, m in items[:25]:
                lines.append(f"- `{s}.{n}`: gen=`{g}` manual=`{m}`")
            if len(items) > 25:
                lines.append(f"- … +{len(items) - 25} more")
        lines.append("")

    _emit_pattern(
        "int32 ↔ int64 size disagreements",
        pat_int_size,
        "Java getter signature is the source of truth (`long` → int64, `int` → int32). "
        "When manual disagrees with harvested, **harvested wins** — these are real fixes "
        "where our hand-written spec guessed the size. Recommend adopting the harvested "
        "size in the generated output.",
    )
    _emit_pattern(
        "Inline enum (generated) vs `$ref` to sibling enum (manual)",
        pat_enum_ref,
        "Stylistic. Manual extracts repeated enums (`ServerState`, `JDBCDataSourceState`, "
        "`DeploymentState`, `JMSPausedState`) into shared schemas; generator emits them "
        "inline. Pure shape-equivalence, deferred to Phase 4d enum extraction pass.",
    )
    _emit_pattern(
        "Inline enum (generated) vs plain `string` (manual)",
        pat_enum_str,
        "Generator is **strictly better** here: it adds `enum` constraints from the "
        "harvested layer + UI overlays that the manual spec never declared. Adopt as-is.",
    )
    _emit_pattern(
        "`array<string>` (generated) vs `array<object>` / `object` (manual)",
        pat_ref_str_arr,
        "Generator follows the harvested Java type (e.g. `String[]` for Xid arrays in "
        "JMS). Manual modelled them loosely as object. Generator is more precise.",
    )
    _emit_pattern(
        "Other mismatches",
        pat_other,
        "Not classified. Inspect individually.",
    )

    # Type mismatches summary across all rows.
    lines.append("## Type mismatches across all MBeans (raw)\n")
    any_mm = False
    for r in rows:
        if r["mismatches"]:
            any_mm = True
            lines.append(f"### `{r['schemaName']}` ({len(r['mismatches'])} mismatches)")
            for n, g, m in r["mismatches"]:
                lines.append(f"- `{n}`: gen=`{g}` manual=`{m}`")
            lines.append("")
    if not any_mm:
        lines.append("(none)\n")

    # Edge cases discovered.
    lines.append("## Edge cases discovered while scaling\n")
    discovered = list(edge_cases)
    # baseTypes outside harvested
    bt_outside = [(r["schemaName"], r["chainOutsideHarvested"]) for r in rows if r["chainOutsideHarvested"]]
    if bt_outside:
        discovered.append("**`baseTypes` apuntando fuera del set harvested** (chain truncates cleanly, properties from non-harvested ancestors are absent):")
        for name, levels in bt_outside:
            discovered.append(f"  - `{name}`: missing levels = {levels}")
    # Empty manual schemas (cannot compare).
    empty_manual = [r["schemaName"] for r in rows if r["man"] == 0]
    if empty_manual:
        discovered.append(
            f"**Manual schemas con 0 propiedades efectivas** (puro discriminator/allOf placeholder): {', '.join(empty_manual)}. "
            "Coverage % se reporta como 0 — no es defecto del generator, es ausencia de superficie comparable en el manual."
        )
    # Inheritance chain length.
    long_chains = [(r["schemaName"], r["chain"]) for r in rows if len(r["chain"]) >= 3]
    if long_chains:
        discovered.append("**Cadenas de herencia profundas** (>=3 niveles), candidatas a deduplicar en post-proceso:")
        for name, chain in long_chains:
            discovered.append(f"  - `{name}`: {' -> '.join(chain)}")
    if not discovered:
        lines.append("(none)\n")
    else:
        for d in discovered:
            lines.append(f"- {d}")
        lines.append("")

    # Orphan references.
    lines.append("## Orphan `$ref`s (target schemas not in this batch)\n")
    if not all_orphans:
        lines.append("(none — every $ref resolves to a schema generated in this batch)\n")
    else:
        lines.append(
            "These appear as `$ref` in generated schemas but no MBean in the target list "
            "produces them. They will be either generated when we expand coverage in 4e, "
            "left as opaque object references, or replaced by primitive types in overlays."
        )
        lines.append("")
        lines.append("| Orphan schema | Referenced from |")
        lines.append("|---|---|")
        for orphan in sorted(all_orphans):
            sources = ", ".join(f"`{s}`" for s in sorted(all_orphans[orphan]))
            lines.append(f"| `{orphan}` | {sources} |")
        lines.append("")
        lines.append(f"**Total orphan schemas referenced: {len(all_orphans)}**\n")

    # Per-MBean inheritance breakdown.
    lines.append("## Inheritance chains per MBean\n")
    lines.append("| Schema | Chain (most-derived → root) | Properties per level |")
    lines.append("|---|---|---|")
    for r in rows:
        chain_str = " → ".join(r["chain"])
        per_level = ", ".join(f"{lvl}={r['perLevel'].get(lvl, 0)}" for lvl in r["chain"])
        lines.append(f"| `{r['schemaName']}` | {chain_str} | {per_level} |")
    lines.append("")

    # Verdict.
    lines.append("## Verdict\n")
    if coverage_agg >= 80:
        verdict = (
            f"Aggregate manual coverage **{coverage_agg:.0f} %** across {len(rows)} MBeans. "
            "Direction validated: the generator is a viable replacement for hand-written schemas "
            "in this corpus, with overlays still needed for envelopes, lifecycle request bodies, "
            "and quirks. No red flags for proceeding to 4c (paths) and 4d (overlay merge)."
        )
    elif coverage_agg >= 60:
        verdict = (
            f"Aggregate coverage **{coverage_agg:.0f} %** — usable, but several MBeans "
            "fall under 60 %. Investigate the worst offenders before scaling further."
        )
    else:
        verdict = (
            f"Aggregate coverage **{coverage_agg:.0f} %** is below the threshold for adopting "
            "the generator as the pipeline. Reassess strategy."
        )
    lines.append(verdict + "\n")

    REPORT.write_text("\n".join(lines))
    print(f"wrote {REPORT.relative_to(OUT_ROOT.parent)}")
    print(f"wrote {len(rows)} schemas under {SCHEMAS_OUT.relative_to(OUT_ROOT.parent)}/")
    print(f"aggregate coverage: {coverage_agg:.0f} % ({total_both}/{total_man})")


if __name__ == "__main__":
    sys.exit(main())
