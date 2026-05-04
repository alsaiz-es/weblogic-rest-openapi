"""Apply harvested-gap overlays — properties present in live REST responses
but absent from Oracle's harvested MBean catalog.

The harvested catalog under
`/tmp/wrc/weblogic-bean-types/src/main/resources/harvestedWeblogicBeanTypes/`
is the source of truth for component schemas in this generator. Some
runtime-only properties are exposed by the live REST projection but
are not declared in the harvested YAML — they get discovered
empirically (`?fields=<name>` probes, sample diffing). This module
splices those into the generated schemas so consumers see them.

Each entry mutates the schema's `properties` map (resolving allOf
wrappers) and stamps `x-weblogic-empirically-verified-versions` on
the injected fragment for provenance.
"""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parents[3]
OVERLAY_PATH = REPO_ROOT / "overlays" / "harvested-gaps.yaml"


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


def apply_harvested_gaps(doc: dict[str, Any]) -> dict[str, Any]:
    """Mutate `doc.components.schemas[*]` to inject missing-property fragments."""
    if not OVERLAY_PATH.is_file():
        return {"applied": [], "skipped_schema_not_found": [], "skipped_already_present": []}

    with OVERLAY_PATH.open() as fh:
        data = yaml.safe_load(fh) or {}

    additions = data.get("additions", [])
    schemas = doc.get("components", {}).get("schemas", {})

    applied: list[dict[str, Any]] = []
    skipped_schema: list[str] = []
    skipped_already: list[dict[str, str]] = []

    for entry in additions:
        schema_name = entry.get("schema")
        prop_name = entry.get("property")
        fragment = entry.get("fragment") or {}
        verified = entry.get("verified_versions") or []

        schema = schemas.get(schema_name)
        if schema is None:
            skipped_schema.append(schema_name)
            continue
        props = _props_of(schema)
        if props is None:
            skipped_schema.append(schema_name)
            continue
        if prop_name in props:
            # Already present (harvested caught up, or another overlay
            # already injected it). Don't clobber — the harvested side
            # carries description, units, deprecation flags this overlay
            # would lose.
            skipped_already.append({"schema": schema_name, "property": prop_name})
            continue

        injected = copy.deepcopy(fragment)
        if verified:
            injected["x-weblogic-empirically-verified-versions"] = list(verified)
        injected["x-weblogic-source"] = "harvested-gaps overlay (not in oracle/weblogic-remote-console catalog)"
        props[prop_name] = injected
        applied.append({"schema": schema_name, "property": prop_name})

    return {
        "applied": applied,
        "skipped_schema_not_found": skipped_schema,
        "skipped_already_present": skipped_already,
    }
