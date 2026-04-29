"""Apply property-level nullability overrides for harvested-vs-live mismatches.

The harvested MBean YAMLs declare some fields as non-nullable that the
live REST projection returns as `null`. This module reads
`overlays/nullability.yaml` and sets `nullable: true` on each listed
`(schema, property)` pair so the spec accurately reflects observed
behavior.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parents[3]
OVERLAY_PATH = REPO_ROOT / "overlays" / "nullability.yaml"


def _props_of(node: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(node, dict):
        return None
    if isinstance(node.get("properties"), dict):
        return node["properties"]
    for key in ("allOf", "oneOf", "anyOf"):
        if isinstance(node.get(key), list):
            for piece in node[key]:
                if isinstance(piece, dict) and isinstance(piece.get("properties"), dict):
                    return piece["properties"]
    return None


def apply_nullability(doc: dict[str, Any]) -> dict[str, Any]:
    """Mutate `doc.components.schemas[*]` to set nullable: true on listed props."""
    if not OVERLAY_PATH.is_file():
        return {"applied": [], "skipped_schema_not_found": [], "skipped_property_not_found": []}

    with OVERLAY_PATH.open() as fh:
        data = yaml.safe_load(fh) or {}

    overrides = data.get("overrides", [])
    schemas = doc.get("components", {}).get("schemas", {})

    applied: list[dict[str, str]] = []
    skipped_schema: list[str] = []
    skipped_prop: list[dict[str, str]] = []

    for entry in overrides:
        schema_name = entry.get("schema")
        prop_name = entry.get("property")
        schema = schemas.get(schema_name)
        if schema is None:
            skipped_schema.append(schema_name)
            continue
        props = _props_of(schema)
        if props is None or prop_name not in props:
            skipped_prop.append({"schema": schema_name, "property": prop_name})
            continue
        props[prop_name]["nullable"] = True
        applied.append({"schema": schema_name, "property": prop_name})

    return {
        "applied": applied,
        "skipped_schema_not_found": skipped_schema,
        "skipped_property_not_found": skipped_prop,
    }
