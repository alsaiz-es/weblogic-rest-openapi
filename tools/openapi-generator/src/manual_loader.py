"""Load manual OpenAPI schemas from specs/ for comparison.

Resolves `allOf` and local `$ref` so we get the effective property set of
schemas like `WebAppComponentRuntime` that compose via `allOf` from a
`ComponentRuntimeBase`.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
SPECS_ROOT = REPO_ROOT / "specs"


_FILE_CACHE: dict[Path, dict[str, Any]] = {}


def _load_file(path: Path) -> dict[str, Any]:
    if path in _FILE_CACHE:
        return _FILE_CACHE[path]
    with path.open() as fh:
        data = yaml.safe_load(fh) or {}
    _FILE_CACHE[path] = data
    return data


def _resolve_local_ref(spec_path: Path, ref: str) -> tuple[Path, str] | None:
    """Resolve a $ref like `#/components/schemas/Foo` or
    `../common/schemas.yaml#/components/schemas/Foo` to (file_path, schema_name).
    """
    if "#" not in ref:
        return None
    rel, frag = ref.split("#", 1)
    target_file = (spec_path.parent / rel).resolve() if rel else spec_path
    if frag.startswith("/components/schemas/"):
        return target_file, frag.rsplit("/", 1)[-1]
    return None


def get_schema(spec_path: Path, schema_name: str) -> dict[str, Any]:
    spec = _load_file(spec_path)
    return spec.get("components", {}).get("schemas", {}).get(schema_name, {})


def effective_properties(spec_path: Path, schema_name: str, _seen: set | None = None) -> dict[str, Any]:
    """Return the merged property dict for a schema, resolving allOf+$ref.

    Local schemas only (we don't follow $ref into common/schemas.yaml deeply
    beyond pulling in nested properties when those happen to live there).
    """
    if _seen is None:
        _seen = set()
    key = (spec_path, schema_name)
    if key in _seen:
        return {}
    _seen.add(key)

    schema = get_schema(spec_path, schema_name)
    if not schema:
        return {}

    out: dict[str, Any] = {}
    if "allOf" in schema:
        for piece in schema["allOf"]:
            if isinstance(piece, dict) and "$ref" in piece:
                resolved = _resolve_local_ref(spec_path, piece["$ref"])
                if resolved:
                    f, n = resolved
                    out.update(effective_properties(f, n, _seen))
            elif isinstance(piece, dict):
                out.update(piece.get("properties") or {})
    out.update(schema.get("properties") or {})
    return out


def load_root_doc(spec_path: Path) -> dict[str, Any]:
    return _load_file(spec_path)
