"""Phase 4e-3: merge manually-authored bodies into polymorphic-stub schemas.

The Remote Console UI overlay declares ~12 polymorphic subtypes per
WLS version (`OAMAuthenticator`, `JMSQueueRuntime`, etc.) for which
the harvested set has no `*MBean.yaml`. The polymorphism module emits
them as stubs that carry the discriminator constraint (`type` or
`destinationType` enum) plus an `allOf [<Parent>]` reference but an
empty body.

This module loads `overlays/manual-schemas/*.yaml` and merges
property + description content into each stub, preserving:

- The discriminator property's `enum: [<value>]` constraint.
- The `allOf [<Parent>]` inheritance.
- Any quirks attached later in the pipeline.

Stamps `x-weblogic-manual-schema: true` and `x-weblogic-source` on
the affected schema so consumers can audit the provenance.

Overlay file format:

    schema: OAMAuthenticator
    description: |
      Replacement description.
    sources:
      - "Oracle MBean Reference Javadoc"
      - "Oracle Fusion Middleware Securing Oracle WebLogic Server"
    properties:
      OAMServerHost:
        type: string
        description: ...
      OAMServerPort:
        type: integer
        format: int32
        description: ...
    required:
      - OAMServerHost
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parents[3]
OVERLAYS_DIR = REPO_ROOT / "overlays" / "manual-schemas"


def load_overlays() -> list[dict[str, Any]]:
    if not OVERLAYS_DIR.is_dir():
        return []
    out: list[dict[str, Any]] = []
    for path in sorted(OVERLAYS_DIR.glob("*.yaml")):
        with path.open() as fh:
            data = yaml.safe_load(fh) or {}
        if not data.get("schema"):
            data["schema"] = path.stem
        out.append(data)
    return out


def _find_inline_branch(schema: dict[str, Any]) -> dict[str, Any] | None:
    """Return the inline `type: object` branch of the schema's `allOf`.

    A polymorphic-stub schema has shape:

        Subtype:
          allOf:
            - $ref: '#/components/schemas/Parent'
            - type: object
              description: ...
              properties:
                <discriminator>: { type: string, enum: [<value>] }
              required: [<discriminator>]
          x-stub: true

    We mutate the inline branch in place so the discriminator
    constraint stays where polymorphism placed it.
    """
    if not isinstance(schema, dict):
        return None
    branches = schema.get("allOf")
    if not isinstance(branches, list):
        return None
    for branch in branches:
        if (
            isinstance(branch, dict)
            and not branch.get("$ref")
            and isinstance(branch.get("properties"), dict)
        ):
            return branch
    return None


def apply_manual_schemas(doc: dict[str, Any]) -> dict[str, Any]:
    """Mutate `doc` in place. Returns stats."""
    overlays = load_overlays()
    schemas = doc.get("components", {}).get("schemas", {})

    applied: list[dict[str, Any]] = []
    skipped_schema: list[str] = []
    skipped_not_stub: list[str] = []
    skipped_no_branch: list[str] = []

    for overlay in overlays:
        name = overlay["schema"]
        schema = schemas.get(name)
        if schema is None:
            skipped_schema.append(name)
            continue
        # Only fill stubs. If the schema has a harvested body
        # (no `x-stub: true`), the overlay would overwrite
        # description and add lower-quality properties — exactly
        # what the plan explicitly avoids ("manual quality is
        # inferior to harvested by design"). Skip with a record.
        if not schema.get("x-stub"):
            skipped_not_stub.append(name)
            continue
        branch = _find_inline_branch(schema)
        if branch is None:
            skipped_no_branch.append(name)
            continue

        added_props: list[str] = []
        added_required: list[str] = []

        existing_props = branch.setdefault("properties", {})
        for prop_name, prop_def in (overlay.get("properties") or {}).items():
            if prop_name in existing_props:
                # Discriminator's enum-constrained property — don't
                # overwrite it. A manual schema shouldn't redefine the
                # discriminator constraint.
                continue
            existing_props[prop_name] = prop_def
            added_props.append(prop_name)

        existing_required = branch.setdefault("required", [])
        for req in overlay.get("required") or []:
            if req not in existing_required:
                existing_required.append(req)
                added_required.append(req)

        if "description" in overlay:
            branch["description"] = overlay["description"].rstrip()

        # Outer-level metadata.
        if "x-stub" in schema:
            del schema["x-stub"]
        schema["x-weblogic-manual-schema"] = True
        sources = overlay.get("sources") or []
        if sources:
            schema["x-weblogic-source"] = sources

        applied.append(
            {
                "schema": name,
                "properties_added": added_props,
                "required_added": added_required,
                "sources": sources,
            }
        )

    return {
        "applied": applied,
        "skipped_schema_not_found": skipped_schema,
        "skipped_not_stub_harvested_present": skipped_not_stub,
        "skipped_no_inline_branch": skipped_no_branch,
    }
