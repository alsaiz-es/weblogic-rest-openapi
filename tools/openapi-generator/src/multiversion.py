"""Multi-version orchestrator and cross-version diff.

`build_all_versions()` runs `main.build_spec()` once per supported WLS
version, writing each output to `out/spec-<version>.yaml` and validating
inline.

`compute_diffs()` produces the cross-version delta between adjacent pairs
for `VERSION_DELTAS.md`.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Any

from openapi_spec_validator import validate
from ruamel.yaml import YAML

import main
from main import build_spec, OUT_ROOT


VERSIONS: list[str] = [
    "12.2.1.3.0",
    "12.2.1.4.0",
    "14.1.1.0.0",
    "14.1.2.0.0",
    "15.1.1.0.0",
]

# Adjacent-pair diff order — Oracle's release lineage.
PAIRS: list[tuple[str, str]] = [
    ("12.2.1.3.0", "12.2.1.4.0"),
    ("12.2.1.4.0", "14.1.1.0.0"),
    ("14.1.1.0.0", "14.1.2.0.0"),
    ("14.1.2.0.0", "15.1.1.0.0"),
]


@dataclass
class VersionResult:
    version: str
    spec_path: Path
    doc: dict[str, Any]
    stats: dict[str, Any]
    validator_pass: bool
    validator_msg: str


def _ordered_yaml() -> YAML:
    yaml = YAML()
    yaml.default_flow_style = False
    yaml.width = 120
    yaml.indent(mapping=2, sequence=2, offset=0)
    return yaml


def _customize_info(doc: dict[str, Any], version: str) -> None:
    """Adjust info block so each per-version spec is self-describing."""
    info = doc.setdefault("info", {})
    info["title"] = (
        "WebLogic REST Management API — Generated Specification "
        f"({version})"
    )
    info["version"] = version


def build_all_versions(
    versions: list[str] = VERSIONS, bulk: bool = False
) -> list[VersionResult]:
    yaml = _ordered_yaml()
    results: list[VersionResult] = []
    for v in versions:
        sys.stdout.write(f"  building {v}{' (bulk)' if bulk else ''} ... ")
        sys.stdout.flush()
        result = build_spec(v, bulk=bulk)
        doc = result["doc"]
        _customize_info(doc, v)

        try:
            validate(doc)
            ok = True
            msg = "PASS"
        except Exception as e:  # noqa: BLE001
            ok = False
            msg = f"FAIL: {type(e).__name__}: {e}"

        spec_path = OUT_ROOT / f"spec-{v}.yaml"
        buf = StringIO()
        yaml.dump(doc, buf)
        spec_path.write_text(buf.getvalue())
        sys.stdout.write(
            f"schemas={result['stats']['total_schemas']} "
            f"paths={result['stats']['total_paths']} "
            f"validator={msg}\n"
        )
        results.append(
            VersionResult(
                version=v,
                spec_path=spec_path,
                doc=doc,
                stats=result["stats"],
                validator_pass=ok,
                validator_msg=msg,
            )
        )
    return results


# --- Cross-version diff --------------------------------------------------


def _walk_effective_props(node: Any, _seen: set | None = None) -> dict[str, Any]:
    """Return the effective property map for a schema (resolving allOf)."""
    if _seen is None:
        _seen = set()
    if not isinstance(node, dict):
        return {}
    out: dict[str, Any] = {}
    if "allOf" in node:
        for piece in node["allOf"]:
            out.update(_walk_effective_props(piece, _seen))
    out.update(node.get("properties") or {})
    return out


def _prop_signature(p: Any) -> str:
    if not isinstance(p, dict):
        return "?"
    if "$ref" in p:
        return f"$ref:{p['$ref'].rsplit('/', 1)[-1]}"
    if "allOf" in p and isinstance(p["allOf"], list) and p["allOf"]:
        first = p["allOf"][0]
        if isinstance(first, dict) and "$ref" in first:
            return f"$ref:{first['$ref'].rsplit('/', 1)[-1]}"
    t = p.get("type", "?")
    if t == "array":
        items = p.get("items", {})
        return f"array<{_prop_signature(items)}>"
    fmt = p.get("format")
    return f"{t}({fmt})" if fmt else t


def _is_real_schema(schema_name: str, schema: dict[str, Any]) -> bool:
    """Filter out auto-stubs from substantive comparison.

    We still report stub presence/absence in the gross schema-set diff
    (since a stub appearing in one version means a referenced MBean
    type that exists there), but we exclude stubs from
    "properties changed" detail.
    """
    return not schema.get("x-stub")


def diff_pair(a: VersionResult, b: VersionResult) -> dict[str, Any]:
    """Return a structured diff a → b."""
    sa = a.doc.get("components", {}).get("schemas", {}) or {}
    sb = b.doc.get("components", {}).get("schemas", {}) or {}
    pa = a.doc.get("paths", {}) or {}
    pb_paths = b.doc.get("paths", {}) or {}

    schema_names_a = set(sa)
    schema_names_b = set(sb)

    schemas_added = sorted(schema_names_b - schema_names_a)
    schemas_removed = sorted(schema_names_a - schema_names_b)

    real_a = {n for n in sa if _is_real_schema(n, sa[n])}
    real_b = {n for n in sb if _is_real_schema(n, sb[n])}

    schemas_added_real = sorted(real_b - real_a)
    schemas_removed_real = sorted(real_a - real_b)

    shared_real = sorted((real_a & real_b))
    properties_added: list[tuple[str, str]] = []
    properties_removed: list[tuple[str, str]] = []
    type_changes: list[tuple[str, str, str, str]] = []

    for name in shared_real:
        propsA = _walk_effective_props(sa[name])
        propsB = _walk_effective_props(sb[name])
        for p in sorted(set(propsB) - set(propsA)):
            properties_added.append((name, p))
        for p in sorted(set(propsA) - set(propsB)):
            properties_removed.append((name, p))
        for p in sorted(set(propsA) & set(propsB)):
            sa_sig = _prop_signature(propsA[p])
            sb_sig = _prop_signature(propsB[p])
            if sa_sig != sb_sig:
                type_changes.append((name, p, sa_sig, sb_sig))

    paths_added = sorted(set(pb_paths) - set(pa))
    paths_removed = sorted(set(pa) - set(pb_paths))

    return {
        "from": a.version,
        "to": b.version,
        "schemas_total_from": len(sa),
        "schemas_total_to": len(sb),
        "schemas_added_total": schemas_added,
        "schemas_removed_total": schemas_removed,
        "schemas_added_real": schemas_added_real,
        "schemas_removed_real": schemas_removed_real,
        "properties_added": properties_added,
        "properties_removed": properties_removed,
        "type_changes": type_changes,
        "paths_added": paths_added,
        "paths_removed": paths_removed,
    }


def compute_diffs(results: list[VersionResult]) -> list[dict[str, Any]]:
    by_version: dict[str, VersionResult] = {r.version: r for r in results}
    out: list[dict[str, Any]] = []
    for from_v, to_v in PAIRS:
        if from_v not in by_version or to_v not in by_version:
            continue
        out.append(diff_pair(by_version[from_v], by_version[to_v]))
    return out


# --- Quirks-by-version table --------------------------------------------


def quirks_table(results: list[VersionResult]) -> dict[str, dict[str, bool]]:
    """{quirk_id: {version: applied?}}."""
    table: dict[str, dict[str, bool]] = {}
    for r in results:
        applied = {a["id"] for a in r.stats.get("quirks", {}).get("applied", [])}
        skipped_v = set(r.stats.get("quirks", {}).get("skipped_version", []))
        all_quirks = applied | skipped_v
        for qid in all_quirks:
            table.setdefault(qid, {})[r.version] = qid in applied
    return table


if __name__ == "__main__":
    results = build_all_versions()
    diffs = compute_diffs(results)
    print()
    for d in diffs:
        print(
            f"{d['from']} → {d['to']}: "
            f"schemas +{len(d['schemas_added_real'])} -{len(d['schemas_removed_real'])}  "
            f"props +{len(d['properties_added'])} -{len(d['properties_removed'])}  "
            f"type-changes {len(d['type_changes'])}  "
            f"paths +{len(d['paths_added'])} -{len(d['paths_removed'])}"
        )
