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


# Action-parameter and return-type Java-type → OpenAPI fragment.
# Delegates to `schema_builder._java_to_openapi_type` so the same
# expanded type table (Date, JNI arrays, opaque objects) applies here.
def _java_to_oas(java_type: str) -> dict[str, Any]:
    if not java_type or java_type == "void":
        return {}
    # Bare class name without package — extension.yaml writes some
    # actions this way (`type: "ServerLifeCycleTaskRuntimeMBean"`).
    if "." not in java_type and not java_type.endswith("[]") and not java_type.startswith("["):
        # Primitive token?
        from schema_builder import _java_to_openapi_type as _impl
        # _impl handles the unqualified primitive case.
        return _impl(java_type)
    from schema_builder import _java_to_openapi_type as _impl
    return _impl(java_type)


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


def _variant_schema_for(action: dict[str, Any], refs: list[str]) -> dict[str, Any]:
    """Body schema for a single action's parameter list.

    Mutates `refs` to append referenced schema names.
    """
    parameters = action.get("parameters") or []
    if not parameters:
        # `additionalProperties: false` is required so the no-args
        # variant of an overloaded action (e.g. `start()` alongside
        # `start_targets_deploymentOptions(...)`) is exclusive in
        # the merged `oneOf`. Without it both branches match the
        # parameterised body and `oas3-valid-media-example` fails.
        return {"type": "object", "additionalProperties": False}
    body_props: dict[str, Any] = {}
    required: list[str] = []
    for p in parameters:
        inner = _java_to_oas(p["type"])
        if "$ref" in inner:
            refs.append(inner["$ref"].rsplit("/", 1)[-1])
        # Honor `array: true` from extension.yaml. WLS rejects
        # scalar values for these fields with HTTP 400 — verified
        # empirically against 14.1.2 on `start`/`stop` of
        # `AppDeploymentRuntime` (the `targets` parameter).
        if p.get("array"):
            body_props[p["name"]] = {"type": "array", "items": inner}
        else:
            body_props[p["name"]] = inner
        required.append(p["name"])
    schema: dict[str, Any] = {"type": "object", "properties": body_props}
    if required:
        schema["required"] = required
    return schema


def _success_response(action: dict[str, Any], refs: list[str]) -> dict[str, Any]:
    return_type = action.get("type", "void") or "void"
    if return_type in ("void", ""):
        return {"204": {"description": "Action completed."}}
    rs = _java_to_oas(return_type)
    if "$ref" in rs:
        refs.append(rs["$ref"].rsplit("/", 1)[-1])
    return {
        "200": {
            "description": "Action result.",
            "content": {"application/json": {"schema": rs}},
        }
    }


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

    parameters = action.get("parameters") or []
    request_schema = _variant_schema_for(action, refs)
    success = _success_response(action, refs)

    schema_name = normalize_schema_name(mbean_name)
    action_name = action["name"]
    harvested_desc = _strip_html(action.get("descriptionHTML"))
    summary_template = f"{action_name} on {schema_name}"
    description = (
        harvested_desc
        if harvested_desc
        else f"Invoke the `{action_name}` operation on `{schema_name}`. Requires `X-Requested-By`."
    )
    op = {
        "operationId": f"{action_name}__{_url_to_op_id(op_path)}",
        "tags": tags,
        "summary": summary_template,
        "description": description,
        "parameters": [
            {"$ref": version_param_ref},
            {"$ref": x_requested_by_ref},
        ],
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": request_schema,
                    "example": {p["name"]: _example_for_param(p) for p in parameters} if parameters else {},
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


def _action_op_merged(
    group: list[dict[str, Any]],
    mbean_name: str,
    parent_url: str,
    tags: list[str],
    x_requested_by_ref: str,
    version_param_ref: str,
) -> tuple[str, dict[str, Any], list[str]]:
    """Emit a single POST whose body is `oneOf` over every overload sharing
    this URL.

    extension.yaml routinely declares multiple Java overloads under the
    same `remoteName` — `redeploy(targets, applicationPath, plan,
    deploymentOptions)` and `redeploy(SourcePath, PlanPath)` both mount
    at `/redeploy`. The earlier behaviour was last-write-wins, which
    silently dropped half the surface and mismatched the live WLS
    runtime's accepted signatures (verified empirically on 14.1.2:
    POSTing the SourcePath/PlanPath body returns 400 with
    "valid signatures are: redeploy(targets: [string], applicationPath:
    string, plan: string, deploymentOptions: {...}), redeploy(targets:
    [string], plan: string, deploymentOptions: {...}), redeploy().").

    `requestBody.required` is set to false for merged endpoints because
    WLS commonly exposes a no-arg overload at runtime even when
    extension.yaml only declares the parameterised ones.
    """
    refs: list[str] = []
    url_name = group[0].get("remoteName") or group[0]["name"]
    op_path = f"{parent_url}/{url_name}"

    variant_schemas: list[dict[str, Any]] = []
    examples: dict[str, dict[str, Any]] = {}
    success_per_action: list[dict[str, Any]] = []
    description_lines: list[str] = []

    for a in group:
        variant = _variant_schema_for(a, refs)
        variant["title"] = a["name"]
        variant_schemas.append(variant)
        params = a.get("parameters") or []
        examples[a["name"]] = {
            "summary": a["name"],
            "value": {p["name"]: _example_for_param(p) for p in params} if params else {},
        }
        success_per_action.append(_success_response(a, refs))
        d = _strip_html(a.get("descriptionHTML"))
        if params:
            sig = ", ".join(f"{p['name']}: {p['type']}{'[]' if p.get('array') else ''}" for p in params)
            sig_str = f"({sig})"
        else:
            sig_str = "()"
        suffix = f" — {d}" if d else ""
        description_lines.append(f"- `{a['name']}{sig_str}`{suffix}")

    schema_name = normalize_schema_name(mbean_name)
    summary = f"{url_name} on {schema_name} (overloaded; {len(group)} variants)"
    description = (
        f"Invoke the `{url_name}` operation on `{schema_name}`. "
        f"Requires `X-Requested-By`.\n\n"
        f"This URL exposes {len(group)} declared overloads. Submit a body "
        f"matching one of the variants below, or POST with no body to invoke "
        f"the no-argument runtime overload (verified against WLS 14.1.2):\n\n"
        + "\n".join(description_lines)
    )

    # Pick the first non-empty 200 response among the variants. If none
    # of them carries a payload, fall back to the first 204.
    success: dict[str, Any] = next(
        (s for s in success_per_action if "200" in s),
        success_per_action[0],
    )

    op = {
        "operationId": f"{url_name}__{_url_to_op_id(op_path)}",
        "tags": tags,
        "summary": summary,
        "description": description,
        "parameters": [
            {"$ref": version_param_ref},
            {"$ref": x_requested_by_ref},
        ],
        "requestBody": {
            "required": False,
            "content": {
                "application/json": {
                    "schema": {"oneOf": variant_schemas},
                    "examples": examples,
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


def _example_for_param(p: dict[str, Any]) -> Any:
    """Example value for an action parameter, honoring `array: true`."""
    base = _example_for(p["type"])
    if p.get("array"):
        # Empty array satisfies every `oas3-valid-media-example` check
        # for `type: array` regardless of the inner item schema.
        return []
    return base


def _example_for(java_type: str) -> Any:
    """Generate an example value matching the OpenAPI schema for the type."""
    if java_type in ("int", "long", "short", "byte"):
        return 0
    if java_type == "boolean":
        return False
    if java_type in ("float", "double"):
        return 0.0
    if java_type in ("java.lang.String", "String", "char", "java.lang.Character"):
        return ""
    if java_type in ("java.util.Date", "java.sql.Date", "java.sql.Timestamp"):
        return "1970-01-01T00:00:00Z"
    if java_type.endswith("[]") or java_type.startswith("[L") or java_type.startswith("[J"):
        return []
    if java_type == "java.util.List":
        return []
    # Anything that maps to an object schema in OpenAPI (Properties, Map,
    # opaque WLS types, $ref to a bean…) → an empty object satisfies all
    # `oas3-valid-media-example` checks for these shapes.
    return {}


def _url_to_op_id(url: str) -> str:
    """Bounded-length operationId fragment (matches path_builder helper)."""
    import hashlib

    parts = []
    for seg in url.strip("/").split("/"):
        if seg.startswith("{") and seg.endswith("}"):
            parts.append("by_" + seg[1:-1])
        else:
            parts.append(seg)
    full = "_".join(parts)
    if len(full) <= 80:
        return full
    h = hashlib.sha1(url.encode()).hexdigest()[:8]
    head = "_".join(parts[:2])
    tail = "_".join(parts[-2:])
    return f"{head}__{tail}_{h}"


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

    # Group actions by URL: extension.yaml may declare several Java
    # overloads sharing the same `remoteName` (e.g. AppDeploymentRuntime
    # has two `redeploy` actions). Last-write-wins drops information;
    # collapse collisions into a single POST with `oneOf` body schema.
    grouped: dict[str, list[dict[str, Any]]] = {}
    for a in actions:
        if not a.get("name"):
            continue
        url_name = a.get("remoteName") or a["name"]
        url = f"{parent_url}/{url_name}"
        grouped.setdefault(url, []).append(a)

    paths: dict[str, dict[str, Any]] = {}
    refs: list[str] = []
    for url, group in grouped.items():
        if len(group) == 1:
            _, op, op_refs = _action_op(
                group[0], mbean_name, parent_url, tags, x_requested_by_ref, version_param_ref
            )
        else:
            _, op, op_refs = _action_op_merged(
                group, mbean_name, parent_url, tags, x_requested_by_ref, version_param_ref
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
