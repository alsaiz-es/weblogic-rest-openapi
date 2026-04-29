"""UI overlay loader for property-level enums and tweaks.

Overlays live at /tmp/wrc/resources/src/main/resources/<MBeanName>/type.yaml
and supplement the harvested YAMLs with information that exists only at
the UI definition layer (notably `legalValues` for runtime properties whose
JMX getter returns a plain String).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

UI_OVERLAY_ROOT = Path("/tmp/wrc/resources/src/main/resources")


def load_type_overlay(mbean_name: str) -> dict[str, dict[str, Any]]:
    """Return a mapping {property_name: overlay_dict} for the given MBean.

    `property_name` matches the Java spelling used in harvested YAMLs
    (e.g. "State", "WeblogicVersion"). Returns {} when no overlay exists.
    """
    path = UI_OVERLAY_ROOT / mbean_name / "type.yaml"
    if not path.is_file():
        return {}
    with path.open() as fh:
        data = yaml.safe_load(fh) or {}
    out: dict[str, dict[str, Any]] = {}
    for prop in data.get("properties", []) or []:
        if "name" in prop:
            out[prop["name"]] = prop
    return out


def overlay_legal_values(overlay_entry: dict[str, Any]) -> list[Any] | None:
    """Extract enum values from an overlay entry, if any.

    UI overlays declare `legalValues` as a list of `{value, label}` dicts;
    we only need the `value` side for OpenAPI enums.
    """
    legal = overlay_entry.get("legalValues")
    if not legal:
        return None
    values: list[Any] = []
    for lv in legal:
        if isinstance(lv, dict):
            values.append(lv.get("value", lv))
        else:
            values.append(lv)
    return values


if __name__ == "__main__":
    import json
    import sys

    name = sys.argv[1] if len(sys.argv) > 1 else "ServerRuntimeMBean"
    o = load_type_overlay(name)
    print(f"overlay properties: {sorted(o)}")
    if "State" in o:
        print(json.dumps(overlay_legal_values(o["State"]), indent=2))
