"""Compare generated ServerRuntime schema vs hand-written one."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import yaml

from schema_builder import build_component_schema, schema_name_mapping

REPO_ROOT = Path(__file__).resolve().parents[3]
MANUAL_SPEC = REPO_ROOT / "specs" / "domain-runtime" / "servers.yaml"
COMMON_SPEC = REPO_ROOT / "specs" / "common" / "schemas.yaml"


def _load_schema(path: Path, schema_name: str) -> dict[str, Any]:
    with path.open() as fh:
        spec = yaml.safe_load(fh)
    return spec["components"]["schemas"][schema_name]


def _resolve_local_ref(name: str, local: dict[str, Any]) -> dict[str, Any]:
    """If `local[name]` is in the same file, return it. Else {}."""
    return local.get(name, {})


def _type_signature(prop_schema: dict[str, Any]) -> str:
    if "$ref" in prop_schema:
        return f"$ref:{prop_schema['$ref'].rsplit('/', 1)[-1]}"
    if "allOf" in prop_schema:
        return _type_signature(prop_schema["allOf"][0])
    t = prop_schema.get("type", "?")
    if t == "array":
        items = prop_schema.get("items", {})
        return f"array<{_type_signature(items)}>"
    fmt = prop_schema.get("format")
    if "enum" in prop_schema:
        return f"{t}({fmt})/enum" if fmt else f"{t}/enum"
    return f"{t}({fmt})" if fmt else t


def _resolve_ref_for_enum(prop_schema: dict[str, Any], local_schemas: dict[str, Any]) -> list[Any] | None:
    """For a property that is `$ref` or `allOf:[$ref]` to a schema in the
    same file, return the enum if any."""
    target = None
    if "$ref" in prop_schema:
        target = prop_schema["$ref"]
    elif "allOf" in prop_schema and isinstance(prop_schema["allOf"][0], dict):
        target = prop_schema["allOf"][0].get("$ref")
    if not target:
        return prop_schema.get("enum")
    if not target.startswith("#/components/schemas/"):
        return None
    name = target.rsplit("/", 1)[-1]
    return local_schemas.get(name, {}).get("enum")


def main() -> int:
    out = build_component_schema("ServerRuntimeMBean", "14.1.2.0.0")
    generated = out["schema"]
    skipped = out["skipped"]
    chain = out["chain"]
    per_level = out["perLevel"]
    schema_name = out["schemaName"]

    with MANUAL_SPEC.open() as fh:
        manual_doc = yaml.safe_load(fh)
    manual_schemas = manual_doc["components"]["schemas"]
    manual = manual_schemas["ServerRuntime"]

    gen_props: dict[str, Any] = generated.get("properties", {})
    man_props: dict[str, Any] = manual.get("properties", {})

    gen_names = set(gen_props)
    man_names = set(man_props)

    only_gen = sorted(gen_names - man_names)
    only_man = sorted(man_names - gen_names)
    in_both = sorted(gen_names & man_names)

    type_mismatches = []
    desc_stats = {"both": 0, "gen_only": 0, "man_only": 0, "neither": 0}
    for n in in_both:
        gsig = _type_signature(gen_props[n])
        msig = _type_signature(man_props[n])
        if gsig != msig:
            type_mismatches.append((n, gsig, msig))
        gd = bool(gen_props[n].get("description"))
        md = bool(man_props[n].get("description"))
        if gd and md:
            desc_stats["both"] += 1
        elif gd:
            desc_stats["gen_only"] += 1
        elif md:
            desc_stats["man_only"] += 1
        else:
            desc_stats["neither"] += 1

    print("=" * 72)
    print(f"{schema_name} — generated (harvested 14.1.2 + overlays) vs manual")
    print("=" * 72)
    print()
    print("--- inheritance ---")
    print(f"  chain: {' -> '.join(chain)}")
    for level in chain:
        print(f"    {level}: {per_level.get(level, 0)} properties")
    print()
    print("--- counts ---")
    print(f"  generated schema properties     : {len(gen_props)}")
    print(f"  manual schema properties        : {len(man_props)}")
    print(f"  properties in both              : {len(in_both)}")
    print(f"  properties only in generated    : {len(only_gen)}")
    print(f"  properties only in manual       : {len(only_man)}")
    print(f"  filtered out (skipped)          : {len(skipped)}")
    print(f"  type signature mismatches       : {len(type_mismatches)}")
    print()

    print("--- properties ONLY in manual ---")
    for n in only_man:
        print(f"  - {n} :: {_type_signature(man_props[n])}")
    if not only_man:
        print("  (none — manual is fully covered by generated)")
    print()

    print(f"--- properties ONLY in generated (sample, {min(20, len(only_gen))} of {len(only_gen)}) ---")
    for n in only_gen[:20]:
        print(f"  + {n} :: {_type_signature(gen_props[n])}")
    if len(only_gen) > 20:
        print(f"  ... +{len(only_gen) - 20} more")
    print()

    print("--- type mismatches (in both, signature differs) ---")
    for n, g, m in type_mismatches:
        print(f"  ! {n}: gen={g}  manual={m}")
    if not type_mismatches:
        print("  (none)")
    print()

    print("--- description coverage on shared properties ---")
    print(f"  both have description       : {desc_stats['both']}")
    print(f"  only generated has desc     : {desc_stats['gen_only']}")
    print(f"  only manual has desc        : {desc_stats['man_only']}")
    print(f"  neither has desc            : {desc_stats['neither']}")
    print()

    # State enum comparison.
    print("--- `state` enum: generated vs manual ServerState ---")
    state_gen = gen_props.get("state", {})
    gen_enum = state_gen.get("enum") or []
    manual_state_enum = manual_schemas.get("ServerState", {}).get("enum") or []
    print(f"  generated values ({len(gen_enum)}): {sorted(gen_enum)}")
    print(f"  manual ServerState ({len(manual_state_enum)}): {sorted(manual_state_enum)}")
    only_in_gen_enum = sorted(set(gen_enum) - set(manual_state_enum))
    only_in_man_enum = sorted(set(manual_state_enum) - set(gen_enum))
    print(f"  values only in generated: {only_in_gen_enum}")
    print(f"  values only in manual   : {only_in_man_enum}")
    print()

    print("--- skipped by filter (sample) ---")
    for n, why in skipped[:10]:
        print(f"  x {n} ({why})")
    if len(skipped) > 10:
        print(f"  ... +{len(skipped) - 10} more")
    print()

    print("--- schema name normalization (sample of refs in output) ---")
    mapping = schema_name_mapping()
    sample = [(k, v) for k, v in sorted(mapping.items())][:8]
    for java, normalized in sample:
        marker = " (renamed)" if java != normalized else ""
        print(f"  {java} -> {normalized}{marker}")
    print(f"  total entries in mapping: {len(mapping)}")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
