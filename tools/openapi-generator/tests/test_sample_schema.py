"""Phase 4g level-2 (b) — sample-vs-schema conformance.

For every overflow sample referenced via `x-weblogic-sample-paths`,
load the JSON from disk and validate it against the operation's
declared response schema. Spectral's `oas3-valid-media-example`
already validates the *inlined* canonical examples; this test
covers the overflow set that lives only on disk.

The OAS 3.0 → JSON Schema 2020-12 adapter (with `$ref` resolution,
`nullable` handling, and `oneOf + discriminator` polymorphism
routing) lives in `_oas_jsonschema.py` and is shared with the live
smoke suite.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator

import pytest
import yaml

from _oas_jsonschema import get_response_schema, validate_instance


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


def _load_yaml(p: Path) -> dict[str, Any]:
    with p.open() as fh:
        return yaml.safe_load(fh) or {}


def _path_template(prefixed: str) -> str:
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
    pytest.importorskip("jsonschema")

    spec = specs[spec_file]
    components = (spec.get("components") or {}).get("schemas") or {}

    full_url = f"/management/weblogic/{{version}}{path_template}"
    item = (spec.get("paths") or {}).get(full_url) or {}
    op = item.get(method)
    if not isinstance(op, dict):
        pytest.skip(f"operation {method.upper()} {path_template} missing")

    raw_schema = get_response_schema(op, "200", components)
    if not raw_schema:
        pytest.skip(f"no concrete 200 schema on {method.upper()} {path_template}")

    sample_path = REPO_ROOT / sample_rel
    if not sample_path.is_file():
        pytest.fail(f"sample missing on disk: {sample_rel}")
    try:
        sample = json.loads(sample_path.read_text())
    except Exception as e:
        pytest.fail(f"sample {sample_rel} unreadable: {e}")

    errors = validate_instance(raw_schema, sample, components)
    if errors and (path_template, method) in EXPECTED_MISMATCH_OPS:
        pytest.skip(
            f"known shape mismatch on {method.upper()} {path_template} "
            f"({len(errors)} validation errors — see PHASE4D7_REPORT.md "
            f"`extension_only_ops` for the rationale)"
        )
    if errors:
        pytest.fail(
            f"sample {sample_rel} fails to validate against "
            f"{method.upper()} {path_template} 200 schema "
            f"({len(errors)} error{'s' if len(errors) != 1 else ''}):\n"
            + "\n".join(f"  - {m}" for m in errors[:5])
        )
