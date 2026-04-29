"""Apply OpenAPI 3.0 discriminator + mapping for polymorphic MBean hierarchies.

Detection: walk every parent MBean we generate; load its UI overlay
(`/tmp/wrc/resources/.../<MBean>/type.yaml`) and check for
`subTypeDiscriminatorProperty` + `subTypes:`. Each entry gives a concrete
subtype FQN and the discriminator value that identifies it.

Generation:

- The parent schema becomes a `oneOf` over all subtypes (NOT including
  the parent's own concrete shape) plus `discriminator: { propertyName,
  mapping }`.
- The original concrete shape of the parent is renamed to
  `<Parent>Base` (already done for `ComponentRuntime` in 4d-1; we
  generalize the pattern here).
- Each subtype schema becomes `allOf: [{$ref: <Parent>Base}, {<own
  properties>}]` and constrains the discriminator property to a
  single-element `enum: [<discriminator_value>]`.
- Subtypes declared in the overlay but NOT generated yet get a stub
  schema with the same `allOf` shape; the body is just the discriminator
  constraint and an `x-stub: true` marker so 4e can fill them in.

The discriminator property is always the result of `_name_to_property`
on the overlay's `subTypeDiscriminatorProperty` (typically `Type` →
`type` in REST projection).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from schema_builder import _name_to_property, normalize_schema_name

UI_OVERLAY_ROOT = Path("/tmp/wrc/resources/src/main/resources")


def _load_overlay(mbean_name: str) -> dict[str, Any] | None:
    path = UI_OVERLAY_ROOT / mbean_name / "type.yaml"
    if not path.is_file():
        return None
    with path.open() as fh:
        return yaml.safe_load(fh) or {}


def detect_hierarchies(
    mbean_names: list[str],
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """Return (`hierarchies`, `skipped`) for the given MBean list.

    `hierarchies[parent_mbean_name]` carries `discriminatorPropertyJava`,
    `discriminatorPropertyRest`, `subtypes`.

    `skipped` records hierarchies where the discriminator property is a
    **nested path** (contains `.`) — OAS 3.0's `discriminator.propertyName`
    must be a top-level property, so we can't represent the contract
    cleanly. Reported in the phase report; not emitted into the spec.
    """
    out: dict[str, dict[str, Any]] = {}
    skipped: list[dict[str, Any]] = []
    for mbean in mbean_names:
        overlay = _load_overlay(mbean)
        if not overlay:
            continue
        prop = overlay.get("subTypeDiscriminatorProperty")
        subtypes = overlay.get("subTypes") or []
        if not prop or not subtypes:
            continue

        if "." in prop:
            # Nested-path discriminator (e.g. `JDBCResource.DatasourceType`
            # on JDBCSystemResourceMBean). OAS 3.0 cannot model this; the
            # contract requires a flat property on the discriminated
            # schema. Skip + report.
            skipped.append(
                {
                    "parent": normalize_schema_name(mbean),
                    "discriminatorProperty": prop,
                    "reason": "nested discriminator path is not representable in OAS 3.0",
                    "subtypeCount": len(subtypes),
                }
            )
            continue

        rest_prop = _name_to_property(prop)
        clean_subtypes: list[dict[str, str]] = []
        for s in subtypes:
            stype = s.get("type")
            value = s.get("value")
            if not stype or not value:
                continue
            simple = stype.rsplit(".", 1)[-1]
            clean_subtypes.append(
                {
                    "value": value,
                    "subtypeMBean": simple,
                    "subtypeSchema": normalize_schema_name(simple),
                }
            )
        if not clean_subtypes:
            continue
        out[mbean] = {
            "parentSchema": normalize_schema_name(mbean),
            "discriminatorPropertyJava": prop,
            "discriminatorPropertyRest": rest_prop,
            "subtypes": clean_subtypes,
        }
    return out, skipped


def apply_polymorphism(
    components_schemas: dict[str, Any],
    hierarchies: dict[str, dict[str, Any]],
    stub_factory,
) -> dict[str, Any]:
    """Mutate components_schemas to install discriminator + mapping per hierarchy.

    Multi-pass to keep cross-hierarchy interactions sane:

    Pass A — Move every parent's concrete shape to `<Parent>Base`.
    Pass B — For each parent, augment / stub each subtype using the now-stable
             `<Parent>Base` ref. Self-referencing subtypes (the parent
             listed as a subtype of itself) get synthesized as
             `<Parent>Default` to avoid the parent oneOf containing
             a circular reference to itself.
    Pass C — Replace each parent schema with `oneOf` + discriminator + mapping.

    `stub_factory(name)` returns a stub schema dict for subtypes whose
    schema body is not yet generated. (Currently unused — we synthesize
    discriminator-aware stubs ourselves.)

    Returns a structured stats dict for reporting.
    """
    stats: dict[str, Any] = {}

    # --- Pass A: move parents to <Parent>Base ----------------------------
    base_for: dict[str, str] = {}  # parent_schema_name -> base_name
    for parent_mbean, info in hierarchies.items():
        parent_schema_name = info["parentSchema"]
        if parent_schema_name not in components_schemas:
            continue
        base_name = f"{parent_schema_name}Base"
        if base_name not in components_schemas:
            components_schemas[base_name] = components_schemas[parent_schema_name]
        base_for[parent_schema_name] = base_name

    # --- Pass B: augment / stub / synthesize-Default ---------------------
    # Build a final mapping for each parent (value -> schema_name) and
    # rewrite subtype names where we synthesized a Default for the
    # self-reference case.
    final_mappings: dict[str, dict[str, str]] = {}
    final_subtypes: dict[str, list[str]] = {}
    pass_b_stats: dict[str, dict[str, Any]] = {}

    for parent_mbean, info in hierarchies.items():
        parent_schema_name = info["parentSchema"]
        if parent_schema_name not in base_for:
            continue
        base_name = base_for[parent_schema_name]
        rest_prop = info["discriminatorPropertyRest"]
        subtypes = info["subtypes"]

        generated_subtypes: list[str] = []
        stub_subtypes: list[str] = []
        default_subtype: str | None = None
        mapping: dict[str, str] = {}
        oneof_targets: list[str] = []

        for st in subtypes:
            schema_name = st["subtypeSchema"]
            value = st["value"]

            if schema_name == parent_schema_name:
                # Self-reference: the "default concrete" form. Synthesize a
                # <Parent>Default schema so the oneOf can reference it
                # without pointing back at the parent itself.
                default_name = f"{parent_schema_name}Default"
                components_schemas[default_name] = {
                    "allOf": [
                        {"$ref": f"#/components/schemas/{base_name}"},
                        {
                            "type": "object",
                            "description": (
                                f"Concrete `{parent_schema_name}` (no further "
                                "subtype specialization)."
                            ),
                            "properties": {
                                rest_prop: {
                                    "type": "string",
                                    "enum": [value],
                                }
                            },
                            "required": [rest_prop],
                        },
                    ],
                }
                mapping[value] = f"#/components/schemas/{default_name}"
                oneof_targets.append(default_name)
                default_subtype = default_name
                continue

            # Resolve nested polymorphism: if `schema_name` is itself another
            # parent in `hierarchies`, its base will be promoted in pass C
            # and the parent name will become a oneOf. Pointing the mapping
            # at the parent name is fine — clients walk the nested
            # discriminator. But we must NOT mutate that parent's flat
            # schema (which has been moved to <Parent>Base by pass A).
            is_other_parent = (
                schema_name in base_for and schema_name != parent_schema_name
            )

            if is_other_parent:
                # Don't augment; mapping points at the to-be-built oneOf.
                mapping[value] = f"#/components/schemas/{schema_name}"
                oneof_targets.append(schema_name)
                generated_subtypes.append(schema_name)
                continue

            existing = components_schemas.get(schema_name)
            if not existing or existing.get("x-stub"):
                # Not generated yet — synthesize a discriminator-aware stub.
                components_schemas[schema_name] = _stub_subtype(
                    schema_name, base_name, rest_prop, value
                )
                stub_subtypes.append(schema_name)
            else:
                # Already-generated subtype: rebase + add discriminator constraint.
                _augment_subtype(existing, base_name, rest_prop, value)
                generated_subtypes.append(schema_name)
            mapping[value] = f"#/components/schemas/{schema_name}"
            oneof_targets.append(schema_name)

        final_mappings[parent_schema_name] = mapping
        final_subtypes[parent_schema_name] = oneof_targets
        pass_b_stats[parent_schema_name] = {
            "discriminatorProperty": rest_prop,
            "subtypeCount": len(subtypes),
            "generatedSubtypes": sorted(generated_subtypes),
            "stubSubtypes": sorted(stub_subtypes),
            "defaultSubtype": default_subtype,
            "mapping": mapping,
            "baseName": base_name,
        }

    # --- Pass C: rewrite parent schemas as polymorphic unions ------------
    for parent_schema_name, mapping in final_mappings.items():
        rest_prop = next(
            info["discriminatorPropertyRest"]
            for _, info in hierarchies.items()
            if info["parentSchema"] == parent_schema_name
        )
        components_schemas[parent_schema_name] = {
            "oneOf": [
                {"$ref": f"#/components/schemas/{name}"}
                for name in final_subtypes[parent_schema_name]
            ],
            "discriminator": {
                "propertyName": rest_prop,
                "mapping": mapping,
            },
            "description": (
                f"Polymorphic `{parent_schema_name}` — the concrete subtype is "
                f"selected by the `{rest_prop}` discriminator property. "
                f"Common base properties live in "
                f"`{base_for[parent_schema_name]}`."
            ),
        }
        stats[parent_schema_name] = pass_b_stats[parent_schema_name]

    return stats


def _augment_subtype(
    subtype_schema: dict[str, Any],
    base_name: str,
    rest_prop: str,
    discriminator_value: str,
) -> None:
    """Add the base ref + discriminator-property single-element enum to a subtype.

    The subtype is currently shaped as `allOf: [{$ref: EnvelopeBase}, {type:
    object, properties: {...}}]`. We:

    - Replace the EnvelopeBase ref with a ref to <Parent>Base (which itself
      `allOf`s EnvelopeBase already).
    - Add a `type` (or whatever the discriminator property is) to the
      properties dict with a single-element enum and add it to `required`.
    """
    if "allOf" not in subtype_schema:
        # Defensive: subtype isn't shaped as we expect. Wrap it.
        subtype_schema["allOf"] = [{"$ref": f"#/components/schemas/{base_name}"}]
        return

    pieces = subtype_schema["allOf"]

    # Find and replace the EnvelopeBase $ref piece (parent base already
    # composes EnvelopeBase, so subtypes only need the parent base).
    new_pieces: list[Any] = []
    replaced_envelope = False
    for piece in pieces:
        if (
            isinstance(piece, dict)
            and piece.get("$ref") == "#/components/schemas/EnvelopeBase"
        ):
            new_pieces.append({"$ref": f"#/components/schemas/{base_name}"})
            replaced_envelope = True
        else:
            new_pieces.append(piece)
    if not replaced_envelope:
        new_pieces.insert(0, {"$ref": f"#/components/schemas/{base_name}"})

    # Add discriminator constraint to the inline-properties piece.
    inline_piece = None
    for piece in new_pieces:
        if isinstance(piece, dict) and "properties" in piece:
            inline_piece = piece
            break
    if inline_piece is None:
        inline_piece = {"type": "object", "properties": {}}
        new_pieces.append(inline_piece)

    props = inline_piece.setdefault("properties", {})
    # If `type` already exists (frequent — inherited via WebLogicMBean), its
    # original definition is a free-form string. Replace with the constrained
    # enum.
    props[rest_prop] = {
        "type": "string",
        "enum": [discriminator_value],
        "description": (
            f"Discriminator. Always `{discriminator_value}` for this subtype."
        ),
    }
    required = inline_piece.setdefault("required", [])
    if rest_prop not in required:
        required.append(rest_prop)

    subtype_schema["allOf"] = new_pieces


def _stub_subtype(
    schema_name: str, base_name: str, rest_prop: str, discriminator_value: str
) -> dict[str, Any]:
    return {
        "allOf": [
            {"$ref": f"#/components/schemas/{base_name}"},
            {
                "type": "object",
                "description": (
                    f"Stub schema for subtype `{schema_name}`. Body deferred "
                    "to Phase 4e coverage expansion."
                ),
                "properties": {
                    rest_prop: {
                        "type": "string",
                        "enum": [discriminator_value],
                    },
                },
                "required": [rest_prop],
            },
        ],
        "x-stub": True,
    }
