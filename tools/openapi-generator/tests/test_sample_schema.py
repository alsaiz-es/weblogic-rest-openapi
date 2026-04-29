"""Phase 4g level-2 (b) — sample-vs-schema conformance.

For every overflow sample referenced via `x-weblogic-sample-paths`,
load the JSON from disk and validate it against the operation's
declared response schema. Spectral's `oas3-valid-media-example`
already validates the *inlined* canonical examples; this test
covers the overflow set that lives only on disk.

Builds a minimal OpenAPI 3.0 → JSON Schema converter:
- `$ref: '#/components/schemas/X'` → inline expansion with cycle
  protection (cycles short-circuit to `{}` — accept anything).
- `nullable: true` + `type: T` → `type: [T, "null"]`.
- Strips OpenAPI-only keys (`xml`, `discriminator`, `example`,
  `readOnly`, `writeOnly`, `deprecated`, `externalDocs`, `x-*`).
- Recurses through `properties`, `items`, `additionalProperties`,
  `oneOf`, `anyOf`, `allOf`.

Validates with `jsonschema.Draft202012Validator`.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator

import pytest
import yaml


REPO_ROOT = Path(__file__).resolve().parents[3]
SPECS_DIR = REPO_ROOT / "specs" / "generated"

SPEC_FILES = sorted(SPECS_DIR.glob("*.yaml")) if SPECS_DIR.is_dir() else []

# Path templates whose canonical sample is intentionally routed
# through `x-weblogic-sample-paths` (instead of an inlined `examples`
# block) because of known schema/sample shape mismatches the spec
# acknowledges. Documented in `sample_loader.py:extension_only_ops`
# and PHASE4D7_REPORT.md.
EXPECTED_MISMATCH_OPS: set[tuple[str, str]] = {
    ("/edit/servers", "get"),
    ("/edit/servers/{serverName}", "get"),
    ("/edit/JDBCSystemResources/{systemResourceName}/JDBCResource", "get"),
    ("/edit/clusters/{clusterName}", "get"),
}


# --- OpenAPI 3.0 → JSON Schema 2020-12 ----------------------------------


_OAS_STRIP = frozenset({
    "xml",
    "discriminator",
    "example",
    "readOnly",
    "writeOnly",
    "deprecated",
    "externalDocs",
})


def _convert(node: Any, components: dict[str, Any], stack: tuple[str, ...] = ()) -> Any:
    if isinstance(node, list):
        return [_convert(v, components, stack) for v in node]
    if not isinstance(node, dict):
        return node

    # Resolve $ref to a components schema by inline expansion.
    ref = node.get("$ref")
    if isinstance(ref, str) and ref.startswith("#/components/schemas/"):
        name = ref.rsplit("/", 1)[-1]
        if name in stack:
            # Cycle — accept anything to break recursion.
            return {}
        target = components.get(name, {})
        return _convert(target, components, stack + (name,))

    out: dict[str, Any] = {}
    for k, v in node.items():
        if k in _OAS_STRIP or k.startswith("x-"):
            continue
        if k == "$ref":
            # Already handled above; leave through if not a components ref.
            out[k] = v
            continue
        if k == "nullable":
            continue  # absorbed into type below
        out[k] = _convert(v, components, stack)

    # OAS 3.0 nullable → JSON Schema 2020-12 type-list with "null".
    if node.get("nullable") is True:
        t = out.get("type")
        if isinstance(t, str):
            out["type"] = [t, "null"]
        elif isinstance(t, list) and "null" not in t:
            out["type"] = list(t) + ["null"]
        elif t is None:
            # No `type`: usually means oneOf/$ref-style. Wrap.
            return {"anyOf": [out, {"type": "null"}]}

    return out


def _resolve_discriminator(
    schema: dict[str, Any], instance: Any, components: dict[str, Any]
) -> dict[str, Any] | None:
    """If `schema` is a polymorphic parent (`oneOf` + `discriminator`),
    pick the concrete subtype branch matching the instance's
    discriminator value. Returns the converted-and-resolved subtype
    schema, or None if not applicable.

    OAS 3.0 polymorphism is `oneOf + discriminator`. Generic JSON
    Schema validators check `oneOf` literally ("exactly one branch
    matches"), which fails when subtypes share fields. Honoring the
    discriminator routes validation to the single correct subtype.
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
        # No explicit mapping but the value matches a component name.
        target_name = value
    if not target_name:
        return None
    target_raw = components.get(target_name)
    if not target_raw:
        return None
    return _convert(target_raw, components)


def _validate_collection_polymorphic(
    schema: dict[str, Any], items: list[Any], components: dict[str, Any]
) -> list[str]:
    """Validate a `{items: [...]}` collection where each item is
    polymorphic. Routes per-item via the discriminator."""
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
        sub = _resolve_discriminator(raw_item, instance, components)
        if sub is None:
            sub = _convert(raw_item, components)
        for e in Draft202012Validator(sub).iter_errors(instance):
            errors.append(f"items[{i}].{'.'.join(str(p) for p in e.absolute_path)}: {e.message}")
    return errors


def _make_schema(operation: dict[str, Any], status: str, components: dict[str, Any]) -> dict[str, Any] | None:
    response = (operation.get("responses") or {}).get(status)
    if not isinstance(response, dict):
        return None
    if "$ref" in response:
        # Shared response (e.g. `Unauthorized`); skip — we only care
        # about responses with concrete schemas the operation owns.
        return None
    content = (response.get("content") or {}).get("application/json")
    if not content:
        return None
    raw = content.get("schema")
    if not raw:
        return None
    return _convert(raw, components)


# --- Test cases ---------------------------------------------------------


def _load_yaml(p: Path) -> dict[str, Any]:
    with p.open() as fh:
        return yaml.safe_load(fh) or {}


def _path_template(prefixed: str) -> str:
    """Strip the `/management/weblogic/{version}` prefix used in path keys."""
    prefix = "/management/weblogic/{version}"
    return prefixed[len(prefix):] if prefixed.startswith(prefix) else prefixed


def _iter_operations(spec: dict[str, Any]) -> Iterator[tuple[str, str, dict[str, Any]]]:
    for url, item in (spec.get("paths") or {}).items():
        if not isinstance(item, dict):
            continue
        for verb in ("get", "post", "put", "delete", "patch"):
            op = item.get(verb)
            if isinstance(op, dict):
                yield url, verb, op


def _iter_overflow_samples(spec: dict[str, Any]) -> Iterator[tuple[str, str, str]]:
    """Yield (path_template_unprefixed, method, repo_relative_path) per overflow sample."""
    for url, verb, op in _iter_operations(spec):
        for entry in op.get("x-weblogic-sample-paths") or []:
            if isinstance(entry, dict) and isinstance(entry.get("path"), str):
                yield _path_template(url), verb, entry["path"]


def _build_cases() -> list[tuple[Path, str, str, str]]:
    cases: list[tuple[Path, str, str, str]] = []
    for spec_file in SPEC_FILES:
        spec = _load_yaml(spec_file)
        for tmpl, method, sample_rel in _iter_overflow_samples(spec):
            cases.append((spec_file, tmpl, method, sample_rel))
    return cases


_CASES = _build_cases()


@pytest.fixture(scope="session")
def specs() -> dict[Path, dict[str, Any]]:
    return {p: _load_yaml(p) for p in SPEC_FILES}


@pytest.mark.skipif(not SPEC_FILES, reason="no specs/generated/")
@pytest.mark.parametrize(
    "spec_file,path_template,method,sample_rel",
    _CASES,
    ids=lambda v: v.stem if isinstance(v, Path) else str(v),
)
def test_overflow_sample_validates_against_response_schema(
    spec_file: Path,
    path_template: str,
    method: str,
    sample_rel: str,
    specs: dict[Path, dict[str, Any]],
) -> None:
    """Every overflow sample must validate against its operation's
    200 response schema (the exception list captures known shape
    mismatches the spec acknowledges)."""
    pytest.importorskip("jsonschema")
    from jsonschema import Draft202012Validator

    spec = specs[spec_file]
    components = (spec.get("components") or {}).get("schemas") or {}

    full_url = f"/management/weblogic/{{version}}{path_template}"
    item = (spec.get("paths") or {}).get(full_url) or {}
    op = item.get(method)
    if not isinstance(op, dict):
        pytest.skip(f"operation {method.upper()} {path_template} missing")

    sample_path = REPO_ROOT / sample_rel
    if not sample_path.is_file():
        pytest.fail(f"sample missing on disk: {sample_rel}")
    try:
        sample = json.loads(sample_path.read_text())
    except Exception as e:
        pytest.fail(f"sample {sample_rel} unreadable: {e}")

    # Resolve schema with discriminator awareness. Two cases:
    # (a) instance is a single polymorphic object (`{type: "X", ...}`)
    #     and the operation's 200 response schema has oneOf.
    # (b) instance is a `{items: [...]}` collection of polymorphic
    #     objects — the operation returns a paged list.
    response = (op.get("responses") or {}).get("200") or {}
    raw_schema = ((response.get("content") or {}).get("application/json") or {}).get("schema")
    if not raw_schema:
        pytest.skip(f"no concrete 200 schema on {method.upper()} {path_template}")
    if "$ref" in raw_schema:
        name = raw_schema["$ref"].rsplit("/", 1)[-1]
        raw_schema = components.get(name, {})

    sub = _resolve_discriminator(raw_schema, sample, components)
    if sub is not None:
        errors = list(Draft202012Validator(sub).iter_errors(sample))
    elif (
        isinstance(sample, dict)
        and isinstance(sample.get("items"), list)
        and isinstance((raw_schema.get("properties") or {}).get("items"), dict)
    ):
        # Polymorphic collection: route each item via discriminator.
        msg_list = _validate_collection_polymorphic(raw_schema, sample["items"], components)
        if msg_list:
            if (path_template, method) in EXPECTED_MISMATCH_OPS:
                pytest.skip(f"known shape mismatch on {method.upper()} {path_template}")
            pytest.fail(
                f"sample {sample_rel} fails to validate against "
                f"{method.upper()} {path_template} 200 schema "
                f"({len(msg_list)} error{'s' if len(msg_list) != 1 else ''}):\n"
                + "\n".join(f"  - {m}" for m in msg_list[:5])
            )
        return
    else:
        sub = _convert(raw_schema, components)
        errors = list(Draft202012Validator(sub).iter_errors(sample))
    if errors and (path_template, method) in EXPECTED_MISMATCH_OPS:
        pytest.skip(
            f"known shape mismatch on {method.upper()} {path_template} "
            f"({len(errors)} validation errors — see PHASE4D7_REPORT.md "
            f"`extension_only_ops` for the rationale)"
        )
    if errors:
        msgs = "\n".join(
            f"  - {'.'.join(str(p) for p in e.absolute_path)}: {e.message}"
            for e in errors[:5]
        )
        pytest.fail(
            f"sample {sample_rel} fails to validate against "
            f"{method.upper()} {path_template} 200 schema "
            f"({len(errors)} error{'s' if len(errors) != 1 else ''}):\n{msgs}"
        )
