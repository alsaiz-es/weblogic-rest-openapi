"""Detect duplicate inline enums in component schemas and extract them.

Detection: walk every schema in `components.schemas`, recording every
inline `enum` along with the (schema_name, property_path, base_type)
context. Group by signature = (sorted values, type).

Extraction: any signature appearing in ≥ 2 distinct (schema, property)
locations becomes a named schema; every occurrence is replaced with
`$ref`. Single-occurrence enums stay inline.

Naming policy follows the table in docs/PHASE4D3_TYPES.md.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

# Values considered canonical for each well-known enum. Used as a
# *content fingerprint*: when a detected signature is a subset/superset
# of one of these, we apply the corresponding name. The lists are
# deliberately conservative — only the values that uniquely identify
# the enum's conceptual category.
_FINGERPRINTS: dict[str, set[str]] = {
    "ServerState": {"RUNNING", "ADMIN", "STANDBY", "STARTING", "SHUTDOWN"},
    "JDBCDataSourceState": {"Running", "Suspended", "Shutdown", "Unhealthy", "Overloaded"},
    "DeploymentState": {"UNPREPARED", "PREPARED", "ACTIVATED", "NEW"},
    "DeploymentStateInt": {"0", "1", "2", "3"},
    "JMSPausedState": {"paused", "active", "unknown"},
    "WebLogicProtocol": {"t3", "t3s", "http", "https", "iiop", "iiops"},
}


@dataclass
class EnumOccurrence:
    schema_name: str
    property_path: tuple[str, ...]
    values: tuple[Any, ...]
    base_type: str
    # Reference to the enclosing dict so we can mutate during extraction.
    container: dict[str, Any] = field(repr=False)


def _walk_for_enums(
    node: Any,
    schema_name: str,
    path: tuple[str, ...],
    out: list[EnumOccurrence],
) -> None:
    if not isinstance(node, dict):
        return

    # Detect an enum declaration on a scalar node.
    if "enum" in node and isinstance(node["enum"], list):
        scalar_type = node.get("type")
        if scalar_type in ("string", "integer", "number", "boolean"):
            out.append(
                EnumOccurrence(
                    schema_name=schema_name,
                    property_path=path,
                    values=tuple(node["enum"]),
                    base_type=scalar_type,
                    container=node,
                )
            )

    # Recurse into nested structures.
    for key in ("properties", "patternProperties"):
        if isinstance(node.get(key), dict):
            for pname, pschema in node[key].items():
                _walk_for_enums(pschema, schema_name, path + (pname,), out)

    if isinstance(node.get("items"), dict):
        _walk_for_enums(node["items"], schema_name, path + ("[]",), out)

    for key in ("allOf", "oneOf", "anyOf"):
        if isinstance(node.get(key), list):
            for i, piece in enumerate(node[key]):
                _walk_for_enums(piece, schema_name, path + (f"{key}[{i}]",), out)

    if isinstance(node.get("additionalProperties"), dict):
        _walk_for_enums(node["additionalProperties"], schema_name, path + ("*",), out)


def find_inline_enums(schemas: dict[str, Any]) -> list[EnumOccurrence]:
    out: list[EnumOccurrence] = []
    for name, schema in schemas.items():
        _walk_for_enums(schema, name, (), out)
    return out


# --- Naming -------------------------------------------------------------


def _classify_by_fingerprint(values: tuple[Any, ...]) -> str | None:
    sval = {str(v) for v in values}
    for name, fp in _FINGERPRINTS.items():
        if fp.issubset(sval):
            return name
    return None


def _pascal(name: str) -> str:
    if not name:
        return name
    if name[0].isupper():
        return name
    return name[0].upper() + name[1:]


def _last_property_name(occ: EnumOccurrence) -> str:
    for seg in reversed(occ.property_path):
        if seg in ("[]", "*"):
            continue
        if seg.startswith("allOf[") or seg.startswith("oneOf[") or seg.startswith("anyOf["):
            continue
        return seg
    return occ.schema_name


def _derive_enum_name(occs: list[EnumOccurrence]) -> str:
    """Apply the naming policy table for a group of occurrences."""
    values = occs[0].values

    # 1) Fingerprint match wins.
    by_fp = _classify_by_fingerprint(values)
    if by_fp:
        # DeploymentStateInt is the integer flavor of DeploymentState — coalesce.
        if by_fp == "DeploymentStateInt":
            return "DeploymentState"
        return by_fp

    # 2) Property-name based heuristics for common patterns.
    prop_names = [_last_property_name(o) for o in occs]
    schemas = [o.schema_name for o in occs]
    common_prop = max(set(prop_names), key=prop_names.count)

    # `pausedState` properties on JMS-prefixed schemas → JMSPausedState.
    if "PausedState" in common_prop or "pausedState" in common_prop:
        if any(s.startswith("JMS") for s in schemas):
            return "JMSPausedState"
        return _pascal(common_prop)

    # 3) PascalCase of the most common property name.
    return _pascal(common_prop)


# --- Detection / extraction passes --------------------------------------


@dataclass
class ExtractionResult:
    extracted: dict[str, dict[str, Any]]  # name -> {values, base_type, occurrences}
    inline_kept: list[EnumOccurrence]
    divergences: list[dict[str, Any]]


def detect(schemas: dict[str, Any]) -> ExtractionResult:
    occs = find_inline_enums(schemas)

    # Group by signature.
    by_sig: dict[tuple, list[EnumOccurrence]] = {}
    for o in occs:
        sig = (tuple(sorted(str(v) for v in o.values)), o.base_type)
        by_sig.setdefault(sig, []).append(o)

    extracted: dict[str, dict[str, Any]] = {}
    inline_kept: list[EnumOccurrence] = []

    # Track divergences: same property name across schemas with different value sets.
    by_property: dict[str, list[tuple[tuple, list[EnumOccurrence]]]] = {}
    for sig, group in by_sig.items():
        for o in group:
            pn = _last_property_name(o)
            by_property.setdefault(pn, []).append((sig, group))

    divergences: list[dict[str, Any]] = []
    for pn, sig_groups in by_property.items():
        seen_sigs = {sg[0] for sg in sig_groups}
        if len(seen_sigs) <= 1:
            continue
        # Skip cases where every signature is a single-element enum.
        # Those are discriminator constraints (one per subtype), not
        # divergent semantics on the same conceptual property.
        if all(len(sig[0]) == 1 for sig in seen_sigs):
            continue
        divergences.append(
            {
                "property": pn,
                "value_sets": [list(sig[0]) for sig in seen_sigs],
                "schemas_per_set": {
                    str(sig): sorted({o.schema_name for o in group})
                    for sig, group in sig_groups
                },
            }
        )

    for sig, group in by_sig.items():
        if len(group) < 2:
            inline_kept.extend(group)
            continue
        # Multiple occurrences: extract.
        enum_name = _derive_enum_name(group)
        # If we've already named one with this name (different sig), append a
        # disambiguator.
        if enum_name in extracted and tuple(sorted(extracted[enum_name]["values"])) != sig[0]:
            base = enum_name
            i = 2
            while f"{base}{i}" in extracted:
                i += 1
            enum_name = f"{base}{i}"
        extracted[enum_name] = {
            "values": list(sig[0]),
            "base_type": sig[1],
            "occurrences": group,
        }

    return ExtractionResult(
        extracted=extracted, inline_kept=inline_kept, divergences=divergences
    )


def apply_extraction(
    schemas: dict[str, Any], result: ExtractionResult
) -> int:
    """Mutate `schemas` to replace each extracted occurrence with $ref.

    Returns the number of inline enum occurrences replaced.
    """
    replaced = 0
    for enum_name, info in result.extracted.items():
        # Create the named schema.
        schemas[enum_name] = {
            "type": info["base_type"],
            "enum": _sort_for_output(info["values"], info["base_type"]),
            "description": f"Shared enum extracted by Phase 4d-3 from {len(info['occurrences'])} occurrences.",
        }
        for occ in info["occurrences"]:
            container = occ.container
            # Strip the inline enum/type and replace with $ref.
            sibling_keys = {
                k: v
                for k, v in container.items()
                if k not in ("enum", "type", "format")
            }
            container.clear()
            ref = {"$ref": f"#/components/schemas/{enum_name}"}
            if sibling_keys:
                # Wrap with allOf to preserve description / readOnly / x-* siblings.
                container["allOf"] = [ref]
                container.update(sibling_keys)
            else:
                container.update(ref)
            replaced += 1
    return replaced


def _sort_for_output(values: Iterable[Any], base_type: str) -> list[Any]:
    vals = list(values)
    if base_type == "integer":
        # Detection stringified the values; coerce back to int and sort.
        try:
            return sorted(int(v) for v in vals)
        except (TypeError, ValueError):
            return sorted(vals, key=str)
    if base_type == "number":
        try:
            return sorted(float(v) for v in vals)
        except (TypeError, ValueError):
            return sorted(vals, key=str)
    if base_type == "boolean":
        return sorted(vals, key=str)
    return sorted(vals, key=str)
