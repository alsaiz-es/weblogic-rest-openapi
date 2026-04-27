"""Ingest MBean operations from Remote Console `extension.yaml` files.

For each MBean we generate, look up
`/tmp/wrc/resources/src/main/resources/<MBeanName>/extension.yaml`. When
it declares an `actions:` list, emit a POST endpoint per action mounted
under the parent path of the MBean.

Java-scraped operations (Phase 4c stop-condition: brittle) are out of
scope here. Only `extension.yaml` ingest happens in this module; other
non-declarative operations are deferred to a manual overlay in 4d.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from schema_builder import normalize_schema_name, _name_to_property

EXTENSIONS_ROOT = Path("/tmp/wrc/resources/src/main/resources")


# Java-type -> OpenAPI type fragment (subset; extension.yaml only uses a few).
_TYPE_MAP: dict[str, dict[str, str]] = {
    "void": {},
    "int": {"type": "integer", "format": "int32"},
    "long": {"type": "integer", "format": "int64"},
    "boolean": {"type": "boolean"},
    "java.lang.String": {"type": "string"},
    "String": {"type": "string"},
    "double": {"type": "number", "format": "double"},
    "float": {"type": "number", "format": "float"},
}


def _java_to_oas(java_type: str) -> dict[str, Any]:
    if java_type in _TYPE_MAP:
        return dict(_TYPE_MAP[java_type])
    if java_type.endswith("[]"):
        return {"type": "array", "items": _java_to_oas(java_type[:-2])}
    if "." in java_type:
        simple = java_type.rsplit(".", 1)[1]
        return {"$ref": f"#/components/schemas/{normalize_schema_name(simple)}"}
    if java_type:
        # Bare class name without package (extension.yaml does this often).
        return {"$ref": f"#/components/schemas/{normalize_schema_name(java_type)}"}
    return {"type": "object"}


def _strip_html(html: str | None) -> str:
    if not html:
        return ""
    s = html
    s = re.sub(r"</?p\s*/?>", "\n\n", s, flags=re.I)
    s = re.sub(r"<code>(.*?)</code>", r"`\1`", s, flags=re.I | re.S)
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\s+\n", "\n", s).strip()


def load_extension(mbean_name: str) -> dict[str, Any] | None:
    path = EXTENSIONS_ROOT / mbean_name / "extension.yaml"
    if not path.is_file():
        return None
    with path.open() as fh:
        return yaml.safe_load(fh) or {}


def _action_op(
    action: dict[str, Any],
    mbean_name: str,
    parent_url: str,
    tags: list[str],
    x_requested_by_ref: str,
    version_param_ref: str,
) -> tuple[str, dict[str, Any], list[str]]:
    """Return (path_url, post_op, referenced_schemas)."""
    refs: list[str] = []

    # Action name: extension.yaml allows compound names like
    # `shutdown_timeout_ignoreSessions` with a `remoteName: "shutdown"`
    # override. Use remoteName for the URL when present.
    url_name = action.get("remoteName") or action["name"]
    op_path = f"{parent_url}/{url_name}"

    # Request body from parameters[].
    parameters = action.get("parameters") or []
    if parameters:
        body_props: dict[str, Any] = {}
        required: list[str] = []
        for p in parameters:
            schema = _java_to_oas(p["type"])
            if "$ref" in schema:
                refs.append(schema["$ref"].rsplit("/", 1)[-1])
            body_props[p["name"]] = schema
            required.append(p["name"])
        request_schema: dict[str, Any] = {
            "type": "object",
            "properties": body_props,
        }
        if required:
            request_schema["required"] = required
        body_required = True
    else:
        request_schema = {"type": "object"}
        body_required = True  # WLS still wants the empty {} body.

    # Response shape from `type:`.
    return_type = action.get("type", "void") or "void"
    if return_type in ("void", ""):
        success: dict[str, Any] = {
            "204": {"description": "Action completed."}
        }
    else:
        rs = _java_to_oas(return_type)
        if "$ref" in rs:
            refs.append(rs["$ref"].rsplit("/", 1)[-1])
        success = {
            "200": {
                "description": "Action result.",
                "content": {"application/json": {"schema": rs}},
            }
        }

    summary = _strip_html(action.get("descriptionHTML")) or f"Invoke `{action['name']}`."
    op = {
        "operationId": f"{action['name']}__{_url_to_op_id(op_path)}",
        "tags": tags,
        "summary": summary[:120].splitlines()[0] if summary else f"Invoke {action['name']}",
        "description": summary,
        "parameters": [
            {"$ref": version_param_ref},
            {"$ref": x_requested_by_ref},
        ],
        "requestBody": {
            "required": body_required,
            "content": {
                "application/json": {
                    "schema": request_schema,
                    "example": {p["name"]: _example_for(p["type"]) for p in parameters} if parameters else {},
                },
            },
        },
        "responses": {
            **success,
            "400": {"$ref": "#/components/responses/EditError"},
            "401": {"$ref": "#/components/responses/Unauthorized"},
            "404": {"$ref": "#/components/responses/NotFound"},
        },
    }
    return op_path, op, refs


def _example_for(java_type: str) -> Any:
    if java_type in ("int", "long", "short", "byte"):
        return 0
    if java_type in ("boolean",):
        return False
    if java_type in ("float", "double"):
        return 0.0
    return ""


def _url_to_op_id(url: str) -> str:
    parts = []
    for seg in url.strip("/").split("/"):
        if seg.startswith("{") and seg.endswith("}"):
            parts.append("byName")
        else:
            parts.append(seg)
    return "_".join(parts)


def collect_actions_for(
    mbean_name: str,
    parent_url: str,
    tags: list[str],
    x_requested_by_ref: str = "#/components/parameters/XRequestedByHeader",
    version_param_ref: str = "#/components/parameters/VersionPathParam",
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Return ({path_url: {post: op}}, [referenced_schema_names])."""
    ext = load_extension(mbean_name)
    if not ext:
        return {}, []
    actions = ext.get("actions") or []
    if not actions:
        return {}, []

    paths: dict[str, dict[str, Any]] = {}
    refs: list[str] = []
    for a in actions:
        if not a.get("name"):
            continue
        url, op, op_refs = _action_op(
            a, mbean_name, parent_url, tags, x_requested_by_ref, version_param_ref
        )
        paths.setdefault(url, {})["post"] = op
        refs.extend(op_refs)
    return paths, refs


if __name__ == "__main__":
    p, refs = collect_actions_for(
        "ServerLifeCycleRuntimeMBean",
        "/management/weblogic/{version}/domainRuntime/serverLifeCycleRuntimes/{name}",
        ["lifecycle"],
    )
    import json
    print(f"paths: {list(p)}")
    print(f"refs: {refs}")
