"""Phase 4g level-2 (a) — sample provenance integrity.

For every sample reference in the generated specs:

- `x-weblogic-sample-source` (on inlined `examples.<key>` blocks):
  the referenced file must exist, and its parsed JSON must match
  the inlined `value`. Catches drift between the live capture on
  disk and the bytes the generator embedded.
- `x-weblogic-sample-paths.path` (on operations as the overflow
  pointer): the referenced file must exist on disk. Content is not
  cross-checked here — the schema-conformance test handles that.

No external dependencies; no VM required. Runs against every spec
under `specs/generated/`.
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


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open() as fh:
        return yaml.safe_load(fh) or {}


def _walk(node: object) -> Iterator[tuple[list[Any], object]]:
    """Depth-first walk yielding (path, node) pairs."""
    stack: list[tuple[list[Any], object]] = [([], node)]
    while stack:
        path, n = stack.pop()
        yield path, n
        if isinstance(n, dict):
            for k, v in n.items():
                stack.append((path + [k], v))
        elif isinstance(n, list):
            for i, v in enumerate(n):
                stack.append((path + [i], v))


def _collect_sample_sources(spec: dict[str, Any]) -> list[tuple[list[Any], str, Any]]:
    """Find every example carrying `x-weblogic-sample-source`.

    Returns (json_path, sample_repo_relative_path, inlined_value).
    """
    out: list[tuple[list[Any], str, Any]] = []
    for path, node in _walk(spec):
        if isinstance(node, dict) and "x-weblogic-sample-source" in node:
            out.append((path, node["x-weblogic-sample-source"], node.get("value")))
    return out


def _collect_sample_paths(spec: dict[str, Any]) -> list[tuple[list[Any], str]]:
    out: list[tuple[list[Any], str]] = []
    for path, node in _walk(spec):
        if isinstance(node, dict) and isinstance(node.get("x-weblogic-sample-paths"), list):
            for i, entry in enumerate(node["x-weblogic-sample-paths"]):
                if isinstance(entry, dict) and isinstance(entry.get("path"), str):
                    out.append((path + ["x-weblogic-sample-paths", i], entry["path"]))
    return out


@pytest.fixture(scope="session")
def specs() -> dict[Path, dict[str, Any]]:
    return {p: _load_yaml(p) for p in SPEC_FILES}


@pytest.mark.skipif(not SPEC_FILES, reason="no specs/generated/")
def test_x_weblogic_sample_source_files_exist_and_match(specs: dict[Path, dict[str, Any]]) -> None:
    failures: list[str] = []
    for spec_path, spec in specs.items():
        for json_path, sample_rel, inlined in _collect_sample_sources(spec):
            disk = REPO_ROOT / sample_rel
            if not disk.is_file():
                failures.append(f"{spec_path.stem}: {sample_rel} referenced but not on disk")
                continue
            try:
                disk_value = json.loads(disk.read_text())
            except Exception as e:
                failures.append(f"{spec_path.stem}: {sample_rel} unreadable as JSON: {e}")
                continue
            if disk_value != inlined:
                failures.append(
                    f"{spec_path.stem}: {sample_rel} on disk drifted from inlined value "
                    f"(at {'.'.join(str(p) for p in json_path)})"
                )
    if failures:
        pytest.fail("\n".join(failures))


@pytest.mark.skipif(not SPEC_FILES, reason="no specs/generated/")
def test_x_weblogic_sample_paths_files_exist(specs: dict[Path, dict[str, Any]]) -> None:
    failures: list[str] = []
    for spec_path, spec in specs.items():
        for json_path, sample_rel in _collect_sample_paths(spec):
            disk = REPO_ROOT / sample_rel
            if not disk.is_file():
                failures.append(
                    f"{spec_path.stem}: {sample_rel} listed in "
                    f"x-weblogic-sample-paths but not on disk"
                )
    if failures:
        pytest.fail("\n".join(failures))
