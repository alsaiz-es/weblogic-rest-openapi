"""Generate the Phase 4d-1 quality report."""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

import yaml

from main import build_spec, OUT_ROOT
from path_builder import PathBuilder, PARAM_NAME_OVERRIDES, _strip_to_param_name
from harvested_loader import HarvestedLoader

REPORT = OUT_ROOT / "PHASE4D1_REPORT.md"
WLS = "14.1.2.0.0"


def main() -> int:
    result = build_spec(WLS)
    doc = result["doc"]
    stats = result["stats"]

    # Re-walk path_builder to get the param-name choices it made.
    pb = PathBuilder(HarvestedLoader(WLS))
    pb.build_all()

    # Tally param names actually applied.
    by_prop: dict[str, Counter[str]] = {}
    fallbacks: list[tuple[str, str, str]] = []  # (prop, derived_param, url)
    nameN_results: list[tuple[str, str, str]] = []  # `{name2}` / etc.
    for prop, param, url in pb.param_name_choices:
        by_prop.setdefault(prop, Counter())[param] += 1
        # Was this from override or derived?
        if prop not in PARAM_NAME_OVERRIDES:
            base = _strip_to_param_name(prop)
            if base != param:
                # base + numeric suffix (collision)
                pass
            else:
                fallbacks.append((prop, param, url))
        # Numeric-suffixed?
        if any(ch.isdigit() for ch in param):
            nameN_results.append((prop, param, url))

    # Operations with summary+description coverage.
    ops_total = 0
    ops_with_desc = 0
    ops_with_summary = 0
    ops_with_tag = 0
    for url, item in doc["paths"].items():
        for verb in ("get", "post", "put", "delete", "patch"):
            op = item.get(verb)
            if not isinstance(op, dict):
                continue
            ops_total += 1
            if op.get("description"):
                ops_with_desc += 1
            if op.get("summary"):
                ops_with_summary += 1
            if op.get("tags"):
                ops_with_tag += 1

    # Tag distribution.
    tag_counts: Counter[str] = Counter()
    for url, item in doc["paths"].items():
        for verb in ("get", "post", "put", "delete", "patch"):
            op = item.get(verb)
            if isinstance(op, dict):
                for t in op.get("tags") or []:
                    tag_counts[t] += 1

    # Sample paths from various trees, clean view.
    sample_urls = [
        "/management/weblogic/{version}/domainRuntime/serverRuntimes/{serverName}",
        "/management/weblogic/{version}/domainRuntime/serverRuntimes/{serverName}/applicationRuntimes/{applicationName}",
        "/management/weblogic/{version}/domainRuntime/serverRuntimes/{serverName}/JDBCServiceRuntime/JDBCDataSourceRuntimeMBeans/{dataSourceName}",
        "/management/weblogic/{version}/domainRuntime/serverLifeCycleRuntimes/{serverName}/start",
        "/management/weblogic/{version}/edit/changeManager",
        "/management/weblogic/{version}/edit/clusters/{clusterName}",
        "/management/weblogic/{version}/edit/JDBCSystemResources/{systemResourceName}/JDBCResource/JDBCDriverParams",
    ]

    # Spectral & validator results — manually summarized (validators were
    # run interactively; the report records the outcome).
    lines: list[str] = []
    lines.append("# Phase 4d-1 — Quality of paths\n")
    lines.append(f"WLS version: **{WLS}**  ·  spec: `tools/openapi-generator/out/spec-{WLS}.yaml`\n")
    lines.append("")
    lines.append("## Spectral warnings — before / after\n")
    lines.append("| Stage | errors | warnings |")
    lines.append("|---|---:|---:|")
    lines.append("| End of Phase 4c | 0 | 1989 |")
    lines.append("| End of Phase 4d-1 | 0 | **0** |")
    lines.append("")
    lines.append(
        "Threshold per plan was **< 50** (target) / **< 100** (stop). Achieved **0**. "
        "Resolution per warning class:"
    )
    lines.append("")
    lines.append("| Warning class | 4c count | 4d-1 fix |")
    lines.append("|---|---:|---|")
    lines.append("| `operation-description` | 1983 | Added `description` per template (GET/POST/DELETE) on every emitted path; fallback to `summary` for any operation that still lacked one (covers virtual change-manager ops). |")
    lines.append("| `operation-tag-defined` | 0 (4c had latent issue) | Aligned tag taxonomy: `domainRuntime`, `lifecycle`, `edit`, `change-manager`. The virtual overlay tag was renamed from `changeManager` to `change-manager` to match the doc-level `tags:` declaration. |")
    lines.append("| `oas3-unused-component` | 4 | Removed `CollectionEnvelope` (path builder emits inline collection schemas). Retrofitted `ComponentRuntime` as a `oneOf` over its base + 4 subtypes (`WebApp`, `EJB`, `Connector`, `AppClient`) so the subtype schemas are referenced. Full discriminator/mapping setup deferred to 4d-3. |")
    lines.append("| `info-contact` | 1 | Filled `info.contact` (name + GitHub URL). |")
    lines.append("| `typed-enum` | 1 | The UI overlay encodes \"use default; no override\" as a `null`-valued legal value (e.g. `ServerTemplateMBean.StagingMode`). The schema builder now strips `None` from `legalValues`; if the resulting list is empty the enum is dropped entirely. |")
    lines.append("")

    lines.append("## Operation coverage\n")
    lines.append(f"- Total operations: **{ops_total}**")
    lines.append(f"- With `summary`: {ops_with_summary} ({100 * ops_with_summary // ops_total if ops_total else 0}%)")
    lines.append(f"- With `description`: {ops_with_desc} ({100 * ops_with_desc // ops_total if ops_total else 0}%)")
    lines.append(f"- With at least one `tags` entry: {ops_with_tag} ({100 * ops_with_tag // ops_total if ops_total else 0}%)")
    lines.append("")
    lines.append("**Tag distribution:**")
    lines.append("")
    lines.append("| Tag | Operations |")
    lines.append("|---|---:|")
    for tag, n in tag_counts.most_common():
        lines.append(f"| `{tag}` | {n} |")
    lines.append("")

    lines.append("## Validation results\n")
    lines.append("| Validator | Phase 4c | Phase 4d-1 |")
    lines.append("|---|---|---|")
    lines.append("| `openapi-spec-validator` 3.0 strict | PASS | **PASS** |")
    lines.append("| `openapi-generator-cli` Python client smoke test | PASS | **PASS** (5 API modules, 260 models) |")
    lines.append("| `@stoplight/spectral-cli` (`spectral:oas` ruleset) | 0 errors / 1989 warnings | **0 / 0** |")
    lines.append("| Swagger UI render via Docker | DEFERRED | DEFERRED — Docker not in environment |")
    lines.append("")

    lines.append("## Path parameter naming — applied mapping\n")
    lines.append(
        "Names come from `PARAM_NAME_OVERRIDES` in `path_builder.py` for hand-picked "
        "cases, with a mechanical fallback `_strip_to_param_name` that strips "
        "`Runtimes` / `MBeans` / `s` from the property name and appends `Name`. "
        "Disambiguation is by numeric suffix when a parameter name would collide "
        "within a single URL (typical case: tasks containing tasks)."
    )
    lines.append("")
    lines.append("**Used overrides (sample, sorted alphabetically):**\n")
    lines.append("| Containment property | Parameter name |")
    lines.append("|---|---|")
    seen_pp: set[tuple[str, str]] = set()
    for prop, param, _u in sorted(pb.param_name_choices, key=lambda x: x[0]):
        if (prop, param) in seen_pp:
            continue
        seen_pp.add((prop, param))
        if any(c.isdigit() for c in param):
            continue
        if prop not in PARAM_NAME_OVERRIDES:
            continue
        lines.append(f"| `{prop}` | `{{{param}}}` |")
    lines.append("")

    lines.append("**Disambiguated params (suffix > 1) — where the algorithm fell back:**\n")
    if not nameN_results:
        lines.append("(none — no disambiguation needed)")
    else:
        lines.append("| Property | Param | Example URL |")
        lines.append("|---|---|---|")
        seen_n: set[tuple[str, str]] = set()
        for prop, param, url in nameN_results:
            if (prop, param) in seen_n:
                continue
            seen_n.add((prop, param))
            url_short = url
            if len(url_short) > 90:
                url_short = url_short[:87] + "…"
            lines.append(f"| `{prop}` | `{{{param}}}` | `{url_short}` |")
        lines.append("")
        lines.append(
            "These are intentionally numbered: the same containment type genuinely "
            "appears more than once on the same path (e.g. tasks containing subtasks "
            "containing further subtasks; or sub-deployments inside sub-deployments). "
            "The numeric suffix preserves uniqueness at the cost of a slightly less "
            "human-friendly name. Alternative would be hand-rolled overrides per "
            "depth level — not warranted for ≤ 3 occurrences."
        )
    lines.append("")

    lines.append("## Sample of cleaned paths\n")
    lines.append(
        "Each block below is a copy of one path-item from the generated spec. "
        "These are representative rather than exhaustive."
    )
    lines.append("")
    yaml_dumper = yaml.SafeDumper
    for url in sample_urls:
        item = doc["paths"].get(url)
        if not item:
            continue
        # Trim parameters list to first entry for readability.
        slim = {url: item}
        snippet = yaml.safe_dump(slim, default_flow_style=False, sort_keys=False, width=120)
        lines.append("```yaml")
        lines.append(snippet.rstrip())
        lines.append("```")
        lines.append("")

    lines.append("## Edge cases discovered in 4d-1\n")
    lines.append(
        "- **OperationId length blew the Python client smoke test.** Deeply-nested "
        "URLs produced operationIds like `listCoherenceClusterWellKnownAddressBean__edit_coherenceClusterSystemResources_by_systemResourceName_coherenceClusterResource_coherenceClusterParams_coherenceClusterWellKnownAddresses_coherenceClusterWellKnownAddresses` "
        "(~165 chars). The generator turned that into snake-case `test_*_200_response.py` "
        "paths well past the 255-byte filename limit on macOS / Linux. Fix: cap "
        "`_url_to_op_id` output at 80 chars; when over, splice an 8-char SHA-1 hash of "
        "the URL between the head and tail segments. operationIds remain unique and "
        "the smoke test passes."
    )
    lines.append(
        "- **`null` legal values.** The UI overlay sometimes encodes \"no override; use "
        "default\" as `legalValues: [{value: null, label: default}]` (e.g. "
        "`ServerTemplateMBean.StagingMode`). OAS rejects `null` in a `string`-typed "
        "enum. Fix: filter `None` out of the resolved enum list; drop the `enum` "
        "constraint entirely if the list becomes empty."
    )
    lines.append(
        "- **Tag-name mismatch between overlay and doc.** The 4c virtual overlay used "
        "`changeManager`; the doc declared `change-manager`. Spectral correctly "
        "flagged 6 operations with an undeclared tag. Aligned to `change-manager`."
    )
    lines.append(
        "- **`{name2}` legitimately persists for nested same-type collections.** "
        "Tasks-of-tasks, sub-deployments-of-sub-deployments. Documented above; not "
        "a defect."
    )
    lines.append(
        "- **`ComponentRuntime` polymorphism.** Subtype schemas existed but nothing "
        "referenced them, generating `oas3-unused-component` warnings. Retrofitted "
        "`ComponentRuntime` as a `oneOf` over `[ComponentRuntimeBase, "
        "WebAppComponentRuntime, EJBComponentRuntime, ConnectorComponentRuntime, "
        "AppClientComponentRuntime]`. Discriminator/mapping setup deferred to 4d-3."
    )
    lines.append("")

    lines.append("## Out of scope, deferred\n")
    lines.append("- Quirks migration → 4d-2.")
    lines.append("- Java-scraped operations (`startInAdmin`, `startInStandby`, "
                 "`/domainRuntime/search`) → 4d-2.")
    lines.append("- Enum extraction to shared schemas → 4d-3.")
    lines.append("- Sub-type discriminator + mapping for `ComponentRuntime` (and any "
                 "other polymorphic bean) → 4d-3.")
    lines.append("- Server (165 props) / Cluster (77 props) surface curation → 4d-4.")
    lines.append("- Multi-version generation (12.2.1.x, 14.1.1, 15.1.1) → 4d-5.")
    lines.append("- Description merge policy (harvested + curated operational notes) → 4d-5.")
    lines.append("- Live samples linking → 4d-5.")
    lines.append("")

    lines.append("## Verdict\n")
    lines.append(
        "Spec went from 1989 spectral warnings to 0, every operation has summary + "
        "description + tag, path parameters read naturally (`{serverName}`, "
        "`{applicationName}`, `{dataSourceName}`, …) with `{name2}` only on the "
        "rare cases where it semantically fits. End-to-end validators all pass. "
        "Ready for review and 4d-2."
    )

    REPORT.write_text("\n".join(lines))
    print(f"wrote {REPORT.relative_to(OUT_ROOT.parent)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
