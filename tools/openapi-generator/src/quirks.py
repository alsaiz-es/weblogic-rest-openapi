"""Load and inject editorial quirk overlays into the generated spec.

Each quirk lives at `overlays/quirks/<id>.yaml` and is structured as:

    id: <short-id>
    title: "<one-line-summary>"
    applies_to_versions: ["12.2.1.4.0", "14.1.2.0.0", ...]
    attachments:
      - type: path | schema | property | global
        # path-specific keys:
        path: "/management/weblogic/{version}/...."
        method: get | post | delete | put | patch     # optional; default: all verbs
        # schema-specific keys:
        schema: ServerRuntime
        # property-specific keys:
        schema: HealthState
        property: state                                # dotted path, can be "a.b.c"
    inject:
      description_append: |
        ...markdown text...
      description_replace: ...
      x_extensions:
        x-weblogic-csrf-conditional: { ... }
      parameters_add:
        - { ... OpenAPI parameter object ... }
      responses_add:
        "400":
          description: ...
    external_doc: docs/QUIRKS.md#1

`description_append` is the most common — it appends to the description
without losing the harvested or generated text. `description_replace`
should be used sparingly (only when harvested is genuinely wrong).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parents[3]
QUIRKS_DIR = REPO_ROOT / "overlays" / "quirks"


def load_quirks() -> list[dict[str, Any]]:
    """Read every overlays/quirks/*.yaml. Returns sorted-by-id list."""
    if not QUIRKS_DIR.is_dir():
        return []
    out: list[dict[str, Any]] = []
    for path in sorted(QUIRKS_DIR.glob("*.yaml")):
        with path.open() as fh:
            data = yaml.safe_load(fh) or {}
        if not data.get("id"):
            data["id"] = path.stem
        out.append(data)
    return out


def _matches_version(quirk: dict[str, Any], wls_version: str) -> bool:
    versions = quirk.get("applies_to_versions")
    if not versions:
        return True
    return wls_version in versions


# --- Attachment resolvers ------------------------------------------------


def _find_schema(components_schemas: dict[str, Any], name: str) -> dict[str, Any] | None:
    return components_schemas.get(name)


def _walk_properties(schema: dict[str, Any], dotted: str) -> dict[str, Any] | None:
    """Resolve a dotted property path inside a schema, walking allOf branches.

    Works on:
    - flat schemas with a top-level `properties` map.
    - allOf-wrapped schemas (schema_builder emits these for every bean):
      we walk the inline branch with `properties`.
    """
    parts = dotted.split(".")
    node = schema
    for i, part in enumerate(parts):
        candidate = _props_of(node)
        if candidate is None or part not in candidate:
            return None
        node = candidate[part]
        # If this is a $ref or allOf, we don't auto-resolve cross-schema —
        # only intra-schema dotted paths. Document that limitation.
    return node


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


def _find_path_item(paths: dict[str, Any], target_path: str) -> tuple[str, dict[str, Any]] | None:
    if target_path in paths:
        return target_path, paths[target_path]
    # Allow attachment.path to be written without the global prefix.
    prefix = "/management/weblogic/{version}"
    if not target_path.startswith(prefix):
        candidate = f"{prefix}{target_path}"
        if candidate in paths:
            return candidate, paths[candidate]
    return None


# --- Injectors -----------------------------------------------------------


def _inject_description(node: dict[str, Any], inject: dict[str, Any]) -> None:
    if "description_replace" in inject:
        node["description"] = inject["description_replace"]
        return
    if "description_append" in inject:
        existing = node.get("description") or ""
        suffix = inject["description_append"]
        if existing:
            node["description"] = f"{existing.rstrip()}\n\n{suffix.rstrip()}"
        else:
            node["description"] = suffix.rstrip()


def _inject_x_extensions(node: dict[str, Any], inject: dict[str, Any]) -> None:
    for key, value in (inject.get("x_extensions") or {}).items():
        node[key] = value


def _inject_parameters_add(node: dict[str, Any], inject: dict[str, Any]) -> None:
    add = inject.get("parameters_add") or []
    if not add:
        return
    existing = node.setdefault("parameters", [])
    existing.extend(add)


def _inject_responses_add(node: dict[str, Any], inject: dict[str, Any]) -> None:
    add = inject.get("responses_add") or {}
    if not add:
        return
    existing = node.setdefault("responses", {})
    for code, resp in add.items():
        existing.setdefault(code, resp)


def _apply_to_node(node: dict[str, Any], inject: dict[str, Any]) -> None:
    _inject_description(node, inject)
    _inject_x_extensions(node, inject)


# --- Public entrypoint ---------------------------------------------------


def apply_quirks(doc: dict[str, Any], wls_version: str) -> dict[str, Any]:
    """Mutate `doc` to apply every applicable quirk overlay.

    Returns a stats dict suitable for the report:
        {
            "applied": [...],
            "skipped_attachment_not_found": [...],
            "skipped_version": [...],
            "by_kind": {...},
        }
    """
    quirks = load_quirks()
    components = doc.setdefault("components", {})
    schemas = components.setdefault("schemas", {})
    paths = doc.setdefault("paths", {})
    info = doc.setdefault("info", {})

    applied: list[dict[str, Any]] = []
    skipped_version: list[str] = []
    skipped_not_found: list[dict[str, Any]] = []
    by_kind: dict[str, int] = {}

    for q in quirks:
        if not _matches_version(q, wls_version):
            skipped_version.append(q["id"])
            continue
        attachments = q.get("attachments") or ([q["attachment"]] if q.get("attachment") else [])
        inject = q.get("inject") or {}
        any_ok = False
        for att in attachments:
            kind = att.get("type")
            by_kind[kind] = by_kind.get(kind, 0) + 1
            ok = _attach_single(q, att, inject, schemas, paths, info)
            if ok:
                any_ok = True
            else:
                skipped_not_found.append(
                    {"id": q["id"], "attachment": att, "reason": "target not found"}
                )
        if any_ok:
            applied.append(
                {
                    "id": q["id"],
                    "title": q.get("title"),
                    "attachments": len(attachments),
                    "external_doc": q.get("external_doc"),
                }
            )

    return {
        "applied": applied,
        "skipped_version": skipped_version,
        "skipped_not_found": skipped_not_found,
        "by_kind": by_kind,
    }


def _attach_single(
    quirk: dict[str, Any],
    attachment: dict[str, Any],
    inject: dict[str, Any],
    schemas: dict[str, Any],
    paths: dict[str, Any],
    info: dict[str, Any],
) -> bool:
    kind = attachment.get("type")
    if kind == "global":
        # Append to info.description; also allow x-extensions on the doc root
        # via inject.x_extensions placed under info.
        _apply_to_node(info, inject)
        # Stamp a small marker so we can audit which quirks have global scope.
        markers = info.setdefault("x-quirks-global", [])
        if quirk["id"] not in markers:
            markers.append(quirk["id"])
        return True

    if kind == "schema":
        schema = _find_schema(schemas, attachment.get("schema"))
        if schema is None:
            return False
        _apply_to_node(schema, inject)
        _stamp_quirk(schema, quirk)
        return True

    if kind == "property":
        schema = _find_schema(schemas, attachment.get("schema"))
        if schema is None:
            return False
        node = _walk_properties(schema, attachment.get("property", ""))
        if node is None:
            return False
        _apply_to_node(node, inject)
        _stamp_quirk(node, quirk)
        return True

    if kind == "path":
        found = _find_path_item(paths, attachment.get("path", ""))
        if not found:
            return False
        _, item = found
        method = attachment.get("method")
        if method:
            op = item.get(method)
            if not isinstance(op, dict):
                return False
            _apply_to_node(op, inject)
            _inject_parameters_add(op, inject)
            _inject_responses_add(op, inject)
            _stamp_quirk(op, quirk)
        else:
            for v in ("get", "post", "put", "delete", "patch"):
                op = item.get(v)
                if isinstance(op, dict):
                    _apply_to_node(op, inject)
                    _inject_parameters_add(op, inject)
                    _inject_responses_add(op, inject)
                    _stamp_quirk(op, quirk)
        return True

    return False


def _stamp_quirk(node: dict[str, Any], quirk: dict[str, Any]) -> None:
    """Add a small `x-weblogic-quirks` marker so consumers can audit which
    quirks affected a given node and follow the external_doc link."""
    if not isinstance(node, dict):
        return
    marker = node.setdefault("x-weblogic-quirks", [])
    if not isinstance(marker, list):
        return
    entry = {"id": quirk["id"]}
    if quirk.get("external_doc"):
        entry["doc"] = quirk["external_doc"]
    marker.append(entry)
