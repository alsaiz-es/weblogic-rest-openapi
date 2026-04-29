"""Phase 4c orchestrator: emit a complete OpenAPI 3.0 spec for one WLS version.

Pipeline:
  schemas (Phase 4b targets, generated)
+ stubs   (referenced schemas not in target list)
+ envelope overlays (overlays/envelopes.yaml)
+ virtual operations (overlays/operations-virtual.yaml)
+ paths (path_builder, full containment walk under each tree)
+ extension.yaml-derived MBean operations (operations.py)
= out/spec-{version}.yaml  (validated against openapi-spec-validator)
"""
from __future__ import annotations

import sys
from io import StringIO
from pathlib import Path
from typing import Any

from openapi_spec_validator import validate
from ruamel.yaml import YAML

from harvested_loader import HarvestedLoader
from operations import collect_actions_for
from path_builder import PathBuilder, TREE_CONFIG
from phase4b_runner import TARGETS as PHASE4B_TARGETS
import schema_builder
from schema_builder import build_component_schema, normalize_schema_name


REPO_ROOT = Path(__file__).resolve().parents[3]
OVERLAYS = REPO_ROOT / "overlays"
OUT_ROOT = Path(__file__).resolve().parents[1] / "out"
OUT_ROOT.mkdir(exist_ok=True)


def _load_overlay(name: str) -> dict[str, Any]:
    path = OVERLAYS / f"{name}.yaml"
    yaml = YAML(typ="safe")
    with path.open() as fh:
        return yaml.load(fh) or {}


def _ordered_yaml() -> YAML:
    yaml = YAML()
    yaml.default_flow_style = False
    yaml.width = 120
    yaml.indent(mapping=2, sequence=2, offset=0)
    return yaml


def _stub_schema(name: str) -> dict[str, Any]:
    return {
        "type": "object",
        "description": (
            f"Stub schema for `{name}`. Full schema not yet generated; "
            "expand coverage via Phase 4e by adding the source MBean to "
            "`tools/openapi-generator/src/phase4b_runner.py:TARGETS`."
        ),
        "x-stub": True,
    }


def list_all_mbeans(wls_version: str) -> list[str]:
    """Enumerate every harvested MBean YAML for the given WLS version."""
    from harvested_loader import HARVESTED_ROOT

    path = HARVESTED_ROOT / wls_version
    if not path.is_dir():
        raise FileNotFoundError(f"harvested directory not found: {path}")
    return sorted(p.stem for p in path.glob("*.yaml"))


def build_spec(wls_version: str = "14.1.2.0.0", bulk: bool = False) -> dict[str, Any]:
    loader = HarvestedLoader(wls_version)

    # Pick the input MBean set. The 22-bean curated list is the default;
    # `bulk=True` ingests every harvested MBean for the version (Phase 4e).
    if bulk:
        mbean_names = list_all_mbeans(wls_version)
        target_tuples: list[tuple[str, str | None, str | None, str]] = [
            (n, None, None, "bulk") for n in mbean_names
        ]
    else:
        target_tuples = list(PHASE4B_TARGETS)

    # 1) Generate schemas for every target MBean.
    generated_schemas: dict[str, dict[str, Any]] = {}
    skipped_per_target: dict[str, list[tuple[str, str]]] = {}
    for mbean, _spec_rel, _manual, _group in target_tuples:
        try:
            built = build_component_schema(mbean, wls_version, loader=loader)
        except FileNotFoundError:
            continue
        # Compose with EnvelopeBase mixin (identity + links) for *runtime
        # bean schemas only — config/edit beans don't have envelope links
        # in the same way (their envelope is the parent's wrapper). For
        # Phase 4c we wrap everything for consistency, since manual
        # ServerRuntime etc. carry both `identity` and `links` fields.
        composed = {
            "allOf": [
                {"$ref": "#/components/schemas/EnvelopeBase"},
                built["schema"],
            ],
            "description": built["schema"].get("description", ""),
        }
        # Preserve the description on the wrapping schema; the inner can
        # keep its own too (validators are permissive).
        generated_schemas[built["schemaName"]] = composed
        skipped_per_target[built["schemaName"]] = built["skipped"]

    # 2) Build paths for the whole containment graph.
    pb = PathBuilder(loader)
    pb.build_all()

    # 3) Add MBean operations from extension.yaml.
    operations_added = []  # (mbean, action_count)
    operations_paths: dict[str, dict[str, Any]] = {}
    operation_referenced_schemas: list[str] = []

    # Build a (mbean -> [parent_url(s)]) map by walking the generated paths.
    # A given MBean schema may appear at multiple paths; mount each action at
    # every path that has its `200 GET` returning that schema.
    mbean_to_paths: dict[str, list[str]] = {}
    for url, item in pb.paths.items():
        get_op = item.get("get")
        if not get_op:
            continue
        ok = get_op.get("responses", {}).get("200", {})
        if not ok or "content" not in ok:
            continue
        ref = ok["content"]["application/json"]["schema"].get("$ref")
        if not ref or not ref.startswith("#/components/schemas/"):
            continue
        schema = ref.rsplit("/", 1)[-1]
        # Only mount actions on item paths (singletons), not on collection URLs.
        if url.endswith("}"):  # ends with `{name}`
            mbean_to_paths.setdefault(schema, []).append(url)
        # Also for top-level singletons (not collection items).
        elif "/" in url and not url.endswith("s"):
            mbean_to_paths.setdefault(schema, []).append(url)

    # Iterate over the same target list — the MBeans we actually generate.
    for mbean, _spec_rel, _manual, group in target_tuples:
        try:
            schema_name = normalize_schema_name(mbean)
        except Exception:
            continue
        parent_paths = mbean_to_paths.get(schema_name, [])
        if not parent_paths:
            # Skip — no path mounts this MBean (e.g. JDBCDataSourceBean is
            # accessed via the JDBCResource synthetic, not directly by name).
            continue
        # Determine tag based on the URL prefix (matches PathBuilder logic).
        for parent_path in parent_paths:
            if parent_path.startswith("/edit/changeManager"):
                tags = ["change-manager"]
            elif parent_path.startswith("/domainRuntime/serverLifeCycleRuntimes"):
                tags = ["lifecycle"]
            elif parent_path.startswith("/edit"):
                tags = ["edit"]
            else:
                tags = ["domainRuntime"]
            actions, refs = collect_actions_for(mbean, parent_path, tags)
            if not actions:
                continue
            for url, ops in actions.items():
                operations_paths.setdefault(url, {}).update(ops)
            operations_added.append((mbean, parent_path, len(actions)))
            operation_referenced_schemas.extend(refs)

    # 4) Load overlays.
    envelopes = _load_overlay("envelopes")
    virtual = _load_overlay("operations-virtual")

    # 5) Compose the OpenAPI document.
    components: dict[str, Any] = {
        "schemas": {},
        "parameters": {},
        "responses": {},
        "headers": {},
        "securitySchemes": {},
    }

    # Envelope overlays first (provides EnvelopeBase, ErrorResponse, params).
    for section in ("schemas", "parameters", "responses", "securitySchemes"):
        components[section].update(envelopes.get("components", {}).get(section, {}))

    # Generated schemas — these depend on EnvelopeBase being already present.
    components["schemas"].update(generated_schemas)

    # Virtual schemas (ChangeManagerState).
    for section in ("schemas",):
        components[section].update(virtual.get("components", {}).get(section, {}))

    # Phase 4d-3: discriminator-based polymorphism. Replaces the 4d-1
    # `oneOf` retrofit for ComponentRuntime and extends to any other
    # parent MBean whose UI overlay declares `subTypeDiscriminatorProperty`.
    from polymorphism import detect_hierarchies, apply_polymorphism

    target_mbean_names = [t[0] for t in target_tuples]
    hierarchies, polymorphism_skipped = detect_hierarchies(target_mbean_names)
    polymorphism_stats = apply_polymorphism(
        components["schemas"], hierarchies, _stub_schema
    )

    # Phase 4d-3: enum extraction. Extract any inline enum that appears in
    # ≥2 (schema, property) locations to a named schema and replace
    # occurrences with $ref. Runs AFTER polymorphism so single-element
    # discriminator enums aren't candidates.
    from enum_extractor import detect as detect_enums, apply_extraction as apply_enum_extraction

    enum_result = detect_enums(components["schemas"])
    enums_replaced = apply_enum_extraction(components["schemas"], enum_result)

    # 6) Stubs for any orphan reference. Compute by walking the
    # whole document we've assembled so far + paths.
    referenced = _collect_all_refs({
        "components": components,
        "paths_pb": pb.paths,
        "paths_ops": operations_paths,
        "paths_virtual": virtual.get("paths", {}),
    })
    for name in sorted(referenced):
        if name not in components["schemas"]:
            components["schemas"][name] = _stub_schema(name)

    # 7) Paths: tree-prefix everything from path_builder + operations + virtual.
    paths_out: dict[str, Any] = {}
    prefix_pattern = "/management/weblogic/{version}"
    # path_builder paths are not prefixed; add the prefix.
    for url, item in pb.paths.items():
        paths_out[f"{prefix_pattern}{url}"] = item
    # operations paths: already absolute? Check by inspecting.
    for url, item in operations_paths.items():
        # operations.collect_actions_for got parent_path that came from pb.paths
        # (relative to tree root, but with /domainRuntime/... prefix already).
        # We need to add the management prefix.
        full_url = f"{prefix_pattern}{url}" if url.startswith("/") else url
        if full_url in paths_out:
            paths_out[full_url].update(item)
        else:
            paths_out[full_url] = item
    # Virtual paths: add prefix.
    for url, item in (virtual.get("paths") or {}).items():
        full_url = f"{prefix_pattern}{url}"
        if full_url in paths_out:
            paths_out[full_url].update(item)
        else:
            paths_out[full_url] = item

    # 7.4) Ensure every operation has a `description`. The virtual overlay
    # carries `summary` only on some change-manager ops; fall back to summary
    # when description is missing so spectral's `operation-description` rule
    # is satisfied.
    for url, item in paths_out.items():
        for verb in ("get", "post", "put", "delete", "patch"):
            op = item.get(verb)
            if not isinstance(op, dict):
                continue
            if not op.get("description"):
                op["description"] = op.get("summary") or f"`{verb.upper()}` on `{url}`."

    # 7.5) Inject path-item-level parameter declarations for any {name*}
    # placeholder. The {version} parameter is already referenced via $ref in
    # every operation; only the collection-item name placeholders need
    # path-level declarations to satisfy OAS uniqueness rules.
    import re as _re
    for url, item in paths_out.items():
        placeholders = _re.findall(r"\{([^}]+)\}", url)
        path_params: list[dict[str, Any]] = []
        seen_names: set[str] = set()
        for ph in placeholders:
            if ph == "version" or ph in seen_names:
                continue
            seen_names.add(ph)
            path_params.append({
                "name": ph,
                "in": "path",
                "required": True,
                "description": f"Identifier of the parent collection item (`{ph}`).",
                "schema": {"type": "string"},
            })
        if path_params:
            existing = item.setdefault("parameters", [])
            # Deduplicate against any pre-existing entries (operations may
            # already declare some).
            existing_names = {
                p.get("name") for p in existing if isinstance(p, dict) and "name" in p
            }
            for p in path_params:
                if p["name"] not in existing_names:
                    existing.append(p)

    # 8) Final document.
    info_description = (
        f"Generated OpenAPI 3.0 specification for WebLogic Server {wls_version}.\n\n"
        "Schemas are derived mechanically from Oracle's WebLogic Remote Console "
        "harvested MBean YAMLs ([weblogic-remote-console](https://github.com/oracle/weblogic-remote-console), "
        "UPL 1.0). UI overlays from the same source provide enums and read-only "
        "hints; the rest of the structure is computed from JMX containment.\n\n"
        "This is a Phase 4d-1 build: generated paths, generated schemas, and a "
        "minimal envelope/error overlay. Quirks documentation, curated descriptions, "
        "live samples, sub-type discriminators, enum extraction, and surface "
        "curation are pending in PHASE4D2 through PHASE4D5.\n\n"
        "**Tooling**: `tools/openapi-generator/` (Python + uv, ruamel.yaml, "
        "openapi-spec-validator). Branch: `feat/openapi-generator`."
    )
    doc = {
        "openapi": "3.0.3",
        "info": {
            "title": "WebLogic REST Management API — Generated Specification",
            "description": info_description,
            "version": wls_version,
            "contact": {
                "name": "weblogic-rest-openapi (unofficial)",
                "url": "https://github.com/alsaiz-es/weblogic-rest-openapi",
            },
            "license": {
                "name": "Apache-2.0 (generator + overlays); UPL-1.0 (harvested schemas)",
                "url": "https://www.apache.org/licenses/LICENSE-2.0",
            },
        },
        "servers": [
            {
                "url": "http://{host}:{port}",
                "description": "WebLogic Administration Server (HTTP).",
                "variables": {
                    "host": {"default": "localhost"},
                    "port": {"default": "7001"},
                },
            },
            {
                "url": "https://{host}:{port}",
                "description": "WebLogic Administration Server (HTTPS).",
                "variables": {
                    "host": {"default": "localhost"},
                    "port": {"default": "7002"},
                },
            },
        ],
        "security": [{"basicAuth": []}],
        "tags": [
            {
                "name": "domainRuntime",
                "description": "Read-only domain-wide runtime monitoring (`/domainRuntime`).",
            },
            {
                "name": "lifecycle",
                "description": "Server lifecycle actions (start, suspend, shutdown, …).",
            },
            {
                "name": "edit",
                "description": "Edit-tree configuration mutations (`/edit`). Wrap mutations between `startEdit` and `activate`.",
            },
            {
                "name": "change-manager",
                "description": "Edit-session lifecycle: `startEdit`, `activate`, `cancelEdit`, `safeResolve`, `forceResolve`.",
            },
        ],
        "paths": dict(sorted(paths_out.items())),
        "components": components,
    }

    # Phase 4d-2: apply editorial quirk overlays. Runs after the document is
    # fully assembled so it can target schemas, paths, properties, or the
    # global info block.
    from quirks import apply_quirks

    quirks_stats = apply_quirks(doc, wls_version)

    # Phase 4d-6: append operational-note description overlays from
    # overlays/descriptions/*.yaml. Runs after quirks so the chain is
    # harvested → quirk append → description overlay append.
    from descriptions import apply_descriptions

    descriptions_stats = apply_descriptions(doc)

    # Phase 4d-7: empirical nullability overrides for fields the
    # harvested set declares as non-nullable but the live REST
    # projection returns as null. Must run before sample injection so
    # `oas3-valid-media-example` accepts the live null values.
    from nullability import apply_nullability

    nullability_stats = apply_nullability(doc)

    # Phase 4d-7: link live JSON samples from samples/<version>/ onto
    # operations. Canonical sample → native examples block on the
    # appropriate response; overflow + unmatched-status samples →
    # x-weblogic-sample-paths extension on the operation.
    from sample_loader import apply_samples

    samples_stats = apply_samples(doc, wls_version)

    # Phase 4d-9: transitive-closure drop of schemas that nothing
    # references. Runs last so every other layer (paths, polymorphism,
    # quirks, descriptions, nullability, samples) has already
    # contributed its $refs into the reachable set.
    from prune_unused import prune_unused_schemas

    prune_stats = prune_unused_schemas(doc)

    return {
        "doc": doc,
        "stats": {
            "generated_schemas": len(generated_schemas),
            "stub_schemas": sum(
                1 for s in components["schemas"].values() if s.get("x-stub")
            ),
            "total_schemas": len(components["schemas"]),
            "total_paths": len(paths_out),
            "paths_per_tree": pb.path_count_by_tree,
            "operations_added": len(operations_added),
            "operations_detail": operations_added,
            "warnings": pb.warnings,
            "polymorphism": polymorphism_stats,
            "polymorphism_skipped": polymorphism_skipped,
            "quirks": quirks_stats,
            "descriptions": descriptions_stats,
            "nullability": nullability_stats,
            "samples": samples_stats,
            "prune": prune_stats,
            "enum_extraction": {
                "extracted": {
                    name: {
                        "values": info["values"],
                        "occurrences": [
                            (o.schema_name, ".".join(o.property_path))
                            for o in info["occurrences"]
                        ],
                    }
                    for name, info in enum_result.extracted.items()
                },
                "replacements_count": enums_replaced,
                "inline_kept_count": len(enum_result.inline_kept),
                "divergences": enum_result.divergences,
            },
        },
    }


def _collect_all_refs(node: object) -> set[str]:
    refs: set[str] = set()

    def walk(n: object) -> None:
        if isinstance(n, dict):
            r = n.get("$ref")
            if isinstance(r, str) and r.startswith("#/components/schemas/"):
                refs.add(r.rsplit("/", 1)[-1])
            for v in n.values():
                walk(v)
        elif isinstance(n, list):
            for v in n:
                walk(v)

    walk(node)
    return refs


def main() -> int:
    wls_version = "14.1.2.0.0"
    result = build_spec(wls_version)
    doc = result["doc"]
    stats = result["stats"]

    out = OUT_ROOT / f"spec-{wls_version}.yaml"
    yaml = _ordered_yaml()
    buf = StringIO()
    yaml.dump(doc, buf)
    out.write_text(buf.getvalue())

    # Validate.
    try:
        validate(doc)
        validation_msg = "PASS"
        rc = 0
    except Exception as e:
        validation_msg = f"FAIL: {type(e).__name__}: {e}"
        rc = 1

    print(f"wrote {out.relative_to(OUT_ROOT.parent)}")
    print(f"openapi-spec-validator: {validation_msg}")
    print()
    print(f"  schemas:    {stats['total_schemas']} ({stats['generated_schemas']} generated, {stats['stub_schemas']} stubs)")
    print(f"  paths:      {stats['total_paths']}")
    for t, n in stats["paths_per_tree"].items():
        print(f"    {t}: {n}")
    print(f"  ops added:  {stats['operations_added']}")
    if stats["warnings"]:
        print(f"  warnings:   {len(stats['warnings'])}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
