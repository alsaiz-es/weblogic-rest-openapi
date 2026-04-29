"""Load and inject description overlays (operational notes).

Each overlay lives at `overlays/descriptions/<schema>.yaml`:

    schema: <SchemaName>
    schema_level:
      operational_note: |
        markdown text
    properties:
      <propertyName>:
        operational_note: |
          markdown text

Notes are appended to the existing description as
`**Operational note:** <text>`, separated by a blank line. Runs after
`apply_quirks`, so the chain is: harvested → quirk append →
description overlay append.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parents[3]
DESCRIPTIONS_DIR = REPO_ROOT / "overlays" / "descriptions"


def load_overlays() -> list[dict[str, Any]]:
    if not DESCRIPTIONS_DIR.is_dir():
        return []
    out: list[dict[str, Any]] = []
    for path in sorted(DESCRIPTIONS_DIR.glob("*.yaml")):
        with path.open() as fh:
            data = yaml.safe_load(fh) or {}
        if not data.get("schema"):
            data["schema"] = path.stem
        out.append(data)
    return out


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


def _append_note(node: dict[str, Any], note: str) -> None:
    suffix = f"**Operational note:** {note.rstrip()}"
    existing = node.get("description") or ""
    if existing:
        node["description"] = f"{existing.rstrip()}\n\n{suffix}"
    else:
        node["description"] = suffix
    node["x-weblogic-description-overlay"] = True


def apply_descriptions(doc: dict[str, Any]) -> dict[str, Any]:
    """Mutate `doc` to apply every description overlay. Returns stats."""
    overlays = load_overlays()
    schemas = doc.get("components", {}).get("schemas", {})

    applied: list[dict[str, Any]] = []
    skipped_schema_not_found: list[str] = []
    skipped_property_not_found: list[dict[str, Any]] = []

    for overlay in overlays:
        schema_name = overlay["schema"]
        schema = schemas.get(schema_name)
        if schema is None:
            skipped_schema_not_found.append(schema_name)
            continue

        attached_schema_level = False
        attached_properties: list[str] = []

        schema_level = overlay.get("schema_level") or {}
        note = schema_level.get("operational_note")
        if note:
            _append_note(schema, note)
            attached_schema_level = True

        for prop_name, prop_overlay in (overlay.get("properties") or {}).items():
            note = (prop_overlay or {}).get("operational_note")
            if not note:
                continue
            props = _props_of(schema)
            if props is None or prop_name not in props:
                skipped_property_not_found.append(
                    {"schema": schema_name, "property": prop_name}
                )
                continue
            _append_note(props[prop_name], note)
            attached_properties.append(prop_name)

        if attached_schema_level or attached_properties:
            applied.append(
                {
                    "schema": schema_name,
                    "schema_level": attached_schema_level,
                    "properties": attached_properties,
                }
            )

    return {
        "applied": applied,
        "skipped_schema_not_found": skipped_schema_not_found,
        "skipped_property_not_found": skipped_property_not_found,
    }
