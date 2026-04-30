"""Minimal OpenAPI 3.0 → JSON Schema 2020-12 adapter for response validation.

Used by `test_sample_schema.py` (offline, against captured samples) and
`test_live_smoke.py` (against live WLS responses). Not a full OpenAPI
implementation — intentionally narrow in scope:

- `$ref: '#/components/schemas/X'` → inline expansion with cycle
  protection (cycles short-circuit to `{}` — accept anything).
- `nullable: true` + `type: T` → `type: [T, "null"]`.
- Strips OpenAPI-only keys (`xml`, `discriminator`, `example`,
  `readOnly`, `writeOnly`, `deprecated`, `externalDocs`, `x-*`).
- Recurses through `properties`, `items`, `additionalProperties`,
  `oneOf`, `anyOf`, `allOf`.
- Honors `oneOf + discriminator` by routing to the matched subtype
  rather than relying on the validator's `oneOf` exact-match check.

Validate with `jsonschema.Draft202012Validator`.
"""
from __future__ import annotations

from typing import Any


_OAS_STRIP = frozenset({
    "xml",
    "discriminator",
    "example",
    "readOnly",
    "writeOnly",
    "deprecated",
    "externalDocs",
})


def convert(node: Any, components: dict[str, Any], stack: tuple[str, ...] = ()) -> Any:
    """Convert an OpenAPI 3.0 schema fragment to JSON Schema 2020-12."""
    if isinstance(node, list):
        return [convert(v, components, stack) for v in node]
    if not isinstance(node, dict):
        return node

    ref = node.get("$ref")
    if isinstance(ref, str) and ref.startswith("#/components/schemas/"):
        name = ref.rsplit("/", 1)[-1]
        if name in stack:
            return {}
        target = components.get(name, {})
        return convert(target, components, stack + (name,))

    out: dict[str, Any] = {}
    for k, v in node.items():
        if k in _OAS_STRIP or k.startswith("x-"):
            continue
        if k == "$ref":
            out[k] = v
            continue
        if k == "nullable":
            continue
        out[k] = convert(v, components, stack)

    if node.get("nullable") is True:
        t = out.get("type")
        if isinstance(t, str):
            out["type"] = [t, "null"]
        elif isinstance(t, list) and "null" not in t:
            out["type"] = list(t) + ["null"]
        elif t is None:
            return {"anyOf": [out, {"type": "null"}]}

    return out


def resolve_discriminator(
    schema: dict[str, Any], instance: Any, components: dict[str, Any]
) -> dict[str, Any] | None:
    """If `schema` has `oneOf + discriminator`, return the converted
    subtype that matches the instance's discriminator value, else None.

    Generic JSON Schema validators check `oneOf` exactly ("one branch
    matches"), which fails on OAS 3.0 polymorphism when subtypes share
    fields. Honoring the discriminator routes validation to the single
    correct subtype.
    """
    if not isinstance(schema, dict) or not isinstance(instance, dict):
        return None
    disc = schema.get("discriminator")
    if not isinstance(disc, dict):
        return None
    prop = disc.get("propertyName")
    if not isinstance(prop, str):
        return None
    value = instance.get(prop)
    if value is None:
        return None
    mapping = disc.get("mapping") or {}
    target_ref = mapping.get(value)
    target_name: str | None = None
    if isinstance(target_ref, str) and target_ref.startswith("#/components/schemas/"):
        target_name = target_ref.rsplit("/", 1)[-1]
    elif value in components:
        target_name = value
    if not target_name:
        return None
    target_raw = components.get(target_name)
    if not target_raw:
        return None
    return convert(target_raw, components)


def validate_collection_polymorphic(
    schema: dict[str, Any], items: list[Any], components: dict[str, Any]
) -> list[str]:
    """Validate a `{items: [...]}` collection where items are polymorphic.

    Returns a list of error messages (empty on success). Routes each
    item via the discriminator before validation.
    """
    from jsonschema import Draft202012Validator

    item_schema = (schema.get("properties") or {}).get("items", {}).get("items")
    if not isinstance(item_schema, dict):
        return []
    raw_item = item_schema
    if "$ref" in raw_item:
        name = raw_item["$ref"].rsplit("/", 1)[-1]
        raw_item = components.get(name, {})
    errors: list[str] = []
    for i, instance in enumerate(items):
        sub = resolve_discriminator(raw_item, instance, components)
        if sub is None:
            sub = convert(raw_item, components)
        for e in Draft202012Validator(sub).iter_errors(instance):
            errors.append(
                f"items[{i}].{'.'.join(str(p) for p in e.absolute_path)}: {e.message}"
            )
    return errors


def get_response_schema(
    op: dict[str, Any], status: str, components: dict[str, Any]
) -> dict[str, Any] | None:
    """Resolve the operation's `application/json` response schema for
    the given status. Returns the *raw* OAS schema (not yet converted),
    or None if absent / `$ref`-only response."""
    response = (op.get("responses") or {}).get(status)
    if not isinstance(response, dict) or "$ref" in response:
        return None
    media = (response.get("content") or {}).get("application/json")
    if not media:
        return None
    raw = media.get("schema")
    if not raw:
        return None
    if "$ref" in raw:
        name = raw["$ref"].rsplit("/", 1)[-1]
        return components.get(name)
    return raw


def validate_instance(
    raw_schema: dict[str, Any],
    instance: Any,
    components: dict[str, Any],
) -> list[str]:
    """Validate `instance` against an OAS schema (pre-conversion).

    Handles three shapes:
    1. Polymorphic parent (`oneOf + discriminator`) — route to subtype.
    2. Polymorphic-collection envelope `{items: [...]}` — route per item.
    3. Plain object/array — convert and validate directly.

    Returns a list of error messages, empty on success.
    """
    from jsonschema import Draft202012Validator

    if not isinstance(raw_schema, dict):
        return []

    sub = resolve_discriminator(raw_schema, instance, components)
    if sub is not None:
        return [
            f"{'.'.join(str(p) for p in e.absolute_path)}: {e.message}"
            for e in Draft202012Validator(sub).iter_errors(instance)
        ]

    if (
        isinstance(instance, dict)
        and isinstance(instance.get("items"), list)
        and isinstance((raw_schema.get("properties") or {}).get("items"), dict)
    ):
        return validate_collection_polymorphic(raw_schema, instance["items"], components)

    sub = convert(raw_schema, components)
    return [
        f"{'.'.join(str(p) for p in e.absolute_path)}: {e.message}"
        for e in Draft202012Validator(sub).iter_errors(instance)
    ]
