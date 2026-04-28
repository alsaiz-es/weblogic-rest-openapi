"""Convert a harvested MBean dict into an OpenAPI 3.0 component schema fragment.

Phase 4a iteration 2: includes baseType inheritance, UI-overlay enums, and
schema-name normalization (drops the trailing `MBean` from component names
and `$ref`s).
"""
from __future__ import annotations

import re
from typing import Any

from harvested_loader import HarvestedLoader
from overlays import load_type_overlay, overlay_legal_values

# --- Schema name normalization -------------------------------------------

# Bidirectional mapping populated as we encounter Java class names. Keeps
# trace info around in case we need to go OpenAPI -> Java later.
_JAVA_TO_SCHEMA: dict[str, str] = {}
_SCHEMA_TO_JAVA: dict[str, str] = {}


def normalize_schema_name(java_simple_name: str) -> str:
    """Drop the trailing `MBean` suffix from a class name.

    `ServerRuntimeMBean` -> `ServerRuntime`
    `JDBCDataSourceRuntimeMBean` -> `JDBCDataSourceRuntime`
    `WebLogicMBean` -> `WebLogic` (degenerate but consistent)

    Class names that don't end in `MBean` are returned unchanged
    (e.g. `JDBCDataSourceBean` -> `JDBCDataSourceBean`). Some descriptor
    beans use `Bean` instead of `MBean`; we leave those alone because
    stripping `Bean` would clash with names like `WebLogic`.
    """
    schema = java_simple_name[:-5] if java_simple_name.endswith("MBean") else java_simple_name
    _JAVA_TO_SCHEMA[java_simple_name] = schema
    _SCHEMA_TO_JAVA.setdefault(schema, java_simple_name)
    return schema


def schema_name_mapping() -> dict[str, str]:
    """Snapshot of the Java -> OpenAPI name map populated so far."""
    return dict(_JAVA_TO_SCHEMA)


# --- Type mapping ---------------------------------------------------------

PRIMITIVE_MAP: dict[str, tuple[str, str | None]] = {
    "boolean": ("boolean", None),
    "java.lang.Boolean": ("boolean", None),
    "byte": ("integer", "int32"),
    "java.lang.Byte": ("integer", "int32"),
    "short": ("integer", "int32"),
    "java.lang.Short": ("integer", "int32"),
    "int": ("integer", "int32"),
    "java.lang.Integer": ("integer", "int32"),
    "long": ("integer", "int64"),
    "java.lang.Long": ("integer", "int64"),
    "float": ("number", "float"),
    "java.lang.Float": ("number", "float"),
    "double": ("number", "double"),
    "java.lang.Double": ("number", "double"),
    "char": ("string", None),
    "java.lang.Character": ("string", None),
    "java.lang.String": ("string", None),
    "java.lang.Object": ("string", None),
    "java.util.Date": ("string", "date-time"),
    "java.sql.Date": ("string", "date-time"),
    "java.sql.Timestamp": ("string", "date-time"),
    "java.util.Properties": ("object", None),
    "java.util.Map": ("object", None),
    "java.util.Collection": ("object", None),
    # Java SDK exception hierarchy — opaque exception JSON. Tests for these
    # types appear on `error`, `taskError`, `lastException` fields.
    "java.lang.Throwable": ("object", None),
    "java.lang.Exception": ("object", None),
    "java.lang.RuntimeException": ("object", None),
    # `java.util.List` without a generic parameter — treat as opaque array.
    # The harvested YAMLs use the `array: true` flag separately for typed
    # arrays, so a bare `List` here means generic-erased.
    "java.util.List": ("array", None),
}

# JMX / WLS internal types that surface in harvested data but are not
# part of the harvested MBean set themselves. We map them to opaque
# objects rather than auto-stubs for cleanliness.
OPAQUE_OBJECT_TYPES: set[str] = {
    # JMX standard types — represented by the framework, not harvested.
    "javax.management.openmbean.CompositeData",
    "javax.management.openmbean.TabularData",
    "javax.management.ObjectName",
    "java.io.InputStream",
    "java.io.OutputStream",
    "java.io.Reader",
    # WLS internal types referenced from harvested MBeans but without
    # their own harvested YAMLs. Treat as opaque objects rather than
    # auto-stubbing.
    "weblogic.management.deploy.DeploymentData",
    "weblogic.management.deploy.TargetStatus",
    "weblogic.diagnostics.accessor.ColumnInfo",
    "weblogic.management.runtime.SecurityValidationWarningVBean",
    "weblogic.management.configuration.DeterminerCandidateResourceInfoVBean",
}


# JNI-style array binary descriptors map to OpenAPI `array<...>`. The
# pattern `[L<binaryName>;` denotes an array of object instances; the
# pattern `[<descriptor>` (`[J`, `[I`, …) denotes a primitive array.
_JNI_PRIMITIVE: dict[str, str] = {
    "[B": "byte",
    "[S": "short",
    "[I": "int",
    "[J": "long",
    "[F": "float",
    "[D": "double",
    "[C": "char",
    "[Z": "boolean",
}


def _is_excluded(prop: dict[str, Any]) -> bool:
    if prop.get("supported") is False:
        return True
    if prop.get("exclude") is True:
        return True
    if prop.get("excludeFromRest") is True:
        return True
    if "restInternal" in prop:
        return True
    return False


def _strip_html(html: str) -> str:
    if not html:
        return ""
    s = html
    s = re.sub(r"</?p\s*/?>", "\n\n", s, flags=re.I)
    s = re.sub(r"</?br\s*/?>", "\n", s, flags=re.I)
    s = re.sub(r"</?li\s*/?>", "\n- ", s, flags=re.I)
    s = re.sub(r"</?ul\s*/?>", "\n", s, flags=re.I)
    s = re.sub(r"</?ol\s*/?>", "\n", s, flags=re.I)
    s = re.sub(r"<code>(.*?)</code>", r"`\1`", s, flags=re.I | re.S)
    s = re.sub(r"<[^>]+>", "", s)
    s = s.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&").replace("&quot;", '"')
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n[ \t]+", "\n", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def _java_to_openapi_type(java_type: str) -> dict[str, Any]:
    if java_type in PRIMITIVE_MAP:
        t, fmt = PRIMITIVE_MAP[java_type]
        if t == "array":
            return {"type": "array", "items": {"type": "object"}}
        out: dict[str, Any] = {"type": t}
        if fmt:
            out["format"] = fmt
        return out
    if java_type in OPAQUE_OBJECT_TYPES:
        return {"type": "object"}
    if java_type.endswith("[]"):
        return {"type": "array", "items": _java_to_openapi_type(java_type[:-2])}
    # JNI-style array binary descriptors. Examples:
    #   `[Ljava.lang.Long;`  → array of Long
    #   `[J`                 → long[]
    if java_type.startswith("[L") and java_type.endswith(";"):
        elem = java_type[2:-1]
        return {"type": "array", "items": _java_to_openapi_type(elem)}
    if java_type in _JNI_PRIMITIVE:
        return {"type": "array", "items": _java_to_openapi_type(_JNI_PRIMITIVE[java_type])}
    if "." in java_type:
        simple = java_type.rsplit(".", 1)[1]
        return {"$ref": f"#/components/schemas/{normalize_schema_name(simple)}"}
    return {"type": "string"}


def _name_to_property(java_name: str) -> str:
    """Java property name -> REST projection name."""
    if not java_name:
        return java_name
    if len(java_name) >= 2 and java_name[0].isupper() and java_name[1].isupper():
        return java_name
    return java_name[0].lower() + java_name[1:]


def _is_runtime_mbean(mbean_obj: dict[str, Any]) -> bool:
    base_types = mbean_obj.get("baseTypes") or []
    if any("RuntimeMBean" in bt for bt in base_types):
        return True
    name = mbean_obj.get("name") or ""
    return name.endswith("RuntimeMBean")


# --- Property -> schema entry --------------------------------------------


def build_property_schema(
    prop: dict[str, Any],
    parent_is_runtime: bool,
    overlay: dict[str, Any] | None = None,
) -> dict[str, Any]:
    java_type: str = prop["type"]
    relationship: str | None = prop.get("relationship")
    overlay = overlay or {}

    # 1) Inner type.
    if relationship == "reference":
        # WLS REST renders a single reference as Identity = array<string>
        # (path segments). An array of references becomes array<Identity>.
        identity = {"type": "array", "items": {"type": "string"}}
        if prop.get("array"):
            inner: dict[str, Any] = {"type": "array", "items": identity}
        else:
            inner = dict(identity)
            inner["description"] = "Identity of the referenced bean (path segments)."
    else:
        inner = _java_to_openapi_type(java_type)
        # 2) Array wrapper for non-reference values.
        if prop.get("array"):
            inner = {"type": "array", "items": inner}

    # 3) Enum: harvested first, then overlay (overlay wins because the
    #    runtime overlay is the authoritative UI source for `State` etc.).
    enum_values: list[Any] | None = None
    if prop.get("legalValues"):
        enum_values = []
        for lv in prop["legalValues"]:
            if isinstance(lv, dict):
                enum_values.append(lv.get("value", lv))
            else:
                enum_values.append(lv)
    overlay_enum = overlay_legal_values(overlay) if overlay else None
    if overlay_enum:
        enum_values = overlay_enum

    # WLS UI overlays sometimes encode "use default; no override" as a
    # null-valued legal value (e.g. ServerTemplateMBean.StagingMode). OAS
    # requires enum entries to match the schema type, so we strip nulls.
    if enum_values is not None:
        enum_values = [v for v in enum_values if v is not None]
        if not enum_values:
            enum_values = None

    if enum_values:
        # If the overlay declared string-shaped legal values but the
        # underlying Java type is non-string (e.g. boolean property whose
        # overlay carries free-text labels — `DefaultUnitOfOrder` lists
        # `System-generated`, `Unit-of-Order`, `User-Generated`), the
        # overlay wins on shape. The harvested type was the JMX getter
        # signature; the overlay represents the REST projection. Coerce
        # the inner type to match so spectral's `typed-enum` rule is
        # satisfied.
        if all(isinstance(v, str) for v in enum_values) and inner.get("type") in (
            "boolean",
            "integer",
            "number",
        ):
            inner = {"type": "string"}
        if "type" in inner and inner["type"] in {"string", "integer", "number", "boolean"}:
            inner["enum"] = enum_values
        elif inner.get("type") == "array" and isinstance(inner.get("items"), dict):
            inner["items"]["enum"] = enum_values

    # 4) Default value. Harvested wraps "no default" as `{}` and meta-defaults
    # like `{derivedDefault: true}` as dicts; both are markers, not real
    # values. Only emit scalar/list defaults.
    default = prop.get("defaultValue")
    if isinstance(default, dict):
        pass
    elif default is not None:
        inner["default"] = default

    # OAS 3.0 forbids siblings to `$ref`. Wrap whenever we add anything.
    def _ensure_writable(node: dict[str, Any]) -> dict[str, Any]:
        if "$ref" in node and len(node) == 1:
            return {"allOf": [node]}
        return node

    # 5) Description.
    desc = _strip_html(prop.get("descriptionHTML", ""))
    deprecated_note = prop.get("deprecated")
    if deprecated_note:
        inner = _ensure_writable(inner)
        inner["deprecated"] = True
        note = f"_Deprecated_: {deprecated_note.strip()}"
        desc = f"{desc}\n\n{note}".strip() if desc else note
    if desc:
        inner = _ensure_writable(inner)
        inner["description"] = desc

    # 6) Read-only.
    writable = prop.get("writable")
    overlay_writable = overlay.get("writable") if overlay else None
    if writable is False or overlay_writable in ("never", False):
        inner = _ensure_writable(inner)
        inner["readOnly"] = True
    elif writable is None and parent_is_runtime and "$ref" not in inner:
        inner["readOnly"] = True

    # 7) Custom extensions.
    if prop.get("restartNeeded") is True:
        inner = _ensure_writable(inner)
        inner["x-weblogic-restart-needed"] = True
    if prop.get("redeployNeeded") is True:
        inner = _ensure_writable(inner)
        inner["x-weblogic-redeploy-needed"] = True

    return inner


# --- Whole-bean schema ----------------------------------------------------


def build_component_schema(
    mbean_name: str,
    wls_version: str = "14.1.2.0.0",
    loader: HarvestedLoader | None = None,
) -> dict[str, Any]:
    """Build a single OpenAPI component schema for the given MBean.

    Returns a dict with:
        schemaName:  normalized OpenAPI name (e.g. "ServerRuntime")
        schema:      the schema object itself
        skipped:     [(prop_name, reason), ...]
        chain:       inheritance chain used
        perLevel:    properties contributed by each level
    """
    loader = loader or HarvestedLoader(wls_version)
    merged = loader.load_with_inheritance(mbean_name)

    parent_is_runtime = _is_runtime_mbean(merged)
    description = _strip_html(merged.get("descriptionHTML", ""))

    # Merge overlays along the inheritance chain (least-derived first so the
    # leaf's overlay takes precedence). Without this, subtypes lose enums
    # declared once on the parent overlay (e.g. DeploymentState on
    # ComponentRuntimeMBean is not redefined on WebAppComponentRuntimeMBean).
    overlay: dict[str, dict[str, Any]] = {}
    for level in reversed(merged["inheritanceChain"]):
        overlay.update(load_type_overlay(level))

    properties: dict[str, Any] = {}
    skipped: list[tuple[str, str]] = []

    for prop in merged["properties"]:
        if _is_excluded(prop):
            reason = next(
                (
                    k
                    for k in ("supported", "exclude", "excludeFromRest", "restInternal")
                    if k in prop and prop.get(k) not in (None, "")
                ),
                "excluded",
            )
            skipped.append((prop["name"], reason))
            continue
        java_name = prop["name"]
        rest_name = _name_to_property(java_name)
        properties[rest_name] = build_property_schema(
            prop, parent_is_runtime, overlay.get(java_name)
        )

    schema: dict[str, Any] = {"type": "object"}
    if description:
        schema["description"] = description
    schema["properties"] = properties

    schema_name = normalize_schema_name(mbean_name)

    return {
        "schemaName": schema_name,
        "schema": schema,
        "skipped": skipped,
        "chain": merged["inheritanceChain"],
        "perLevel": merged["propertiesPerLevel"],
    }


if __name__ == "__main__":
    import json
    import sys

    name = sys.argv[1] if len(sys.argv) > 1 else "ServerRuntimeMBean"
    version = sys.argv[2] if len(sys.argv) > 2 else "14.1.2.0.0"
    out = build_component_schema(name, version)
    print(f"schemaName: {out['schemaName']}", file=sys.stderr)
    print(f"chain: {out['chain']}", file=sys.stderr)
    print(f"perLevel: {out['perLevel']}", file=sys.stderr)
    print(f"skipped: {len(out['skipped'])}", file=sys.stderr)
    print(json.dumps(out["schema"], indent=2))
