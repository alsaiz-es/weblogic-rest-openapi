"""Transitive-closure drop of schemas that nothing references.

Bulk generation (Phase 4e) emits a schema for every harvested MBean.
A subset of those — internal-only beans, legacy tagging interfaces,
runtime types that the REST projection does not expose — never appear
as a `$ref` target anywhere in the spec: not from a path, not from
another schema's `allOf` / `oneOf` / `properties`, not from any
component (parameters, responses, requestBodies). Spectral flags each
as `oas3-unused-component`.

This module runs at the very end of the pipeline. It computes the set
of reachable schemas (seeded from `paths` and from non-schema
components, expanded via `$ref` walks through the schema graph) and
drops the unreachable ones.

Polymorphic subtypes are kept iff their discriminator parent is
reachable: the parent's `oneOf` array carries `$ref` entries to each
subtype, so the standard graph walk picks them up. Subtypes whose
parent is itself unreachable are correctly dropped (cascade).

This step does not invent paths or expose anything new. It is purely
a cleanup of bulk-generated schemas that have no consumer.
"""
from __future__ import annotations

from typing import Any


def _collect_schema_refs(node: object, refs: set[str]) -> None:
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/components/schemas/"):
            refs.add(ref.rsplit("/", 1)[-1])
        # Discriminator mapping values are JSON-Reference strings but
        # use plain string values, not the `$ref` keyword. Pick them up
        # explicitly so polymorphic subtypes aren't dropped if they're
        # only referenced via the mapping.
        disc = node.get("discriminator")
        if isinstance(disc, dict):
            mapping = disc.get("mapping") or {}
            for v in mapping.values():
                if isinstance(v, str) and v.startswith("#/components/schemas/"):
                    refs.add(v.rsplit("/", 1)[-1])
        for v in node.values():
            _collect_schema_refs(v, refs)
    elif isinstance(node, list):
        for v in node:
            _collect_schema_refs(v, refs)


def prune_unused_schemas(doc: dict[str, Any]) -> dict[str, Any]:
    """Mutate `doc` in place. Returns stats."""
    components = doc.get("components", {})
    schemas = components.get("schemas", {})
    if not isinstance(schemas, dict) or not schemas:
        return {"dropped": [], "kept": 0, "before": 0}

    before = len(schemas)
    reachable: set[str] = set()

    # Seed from everything outside `components.schemas`.
    seed = {
        "paths": doc.get("paths", {}),
        "info": doc.get("info", {}),
        "_other_components": {
            k: v for k, v in components.items() if k != "schemas"
        },
    }
    _collect_schema_refs(seed, reachable)

    # Transitive closure: keep walking newly-reached schemas until
    # the set stops growing.
    frontier = set(reachable)
    while frontier:
        next_frontier: set[str] = set()
        for name in frontier:
            s = schemas.get(name)
            if s is None:
                continue
            local: set[str] = set()
            _collect_schema_refs(s, local)
            for r in local:
                if r not in reachable:
                    reachable.add(r)
                    next_frontier.add(r)
        frontier = next_frontier

    dropped = sorted(n for n in schemas if n not in reachable)
    for n in dropped:
        del schemas[n]

    return {
        "dropped": dropped,
        "dropped_count": len(dropped),
        "kept": len(schemas),
        "before": before,
    }
