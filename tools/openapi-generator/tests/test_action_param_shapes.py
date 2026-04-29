"""Phase 4g level-1 regression: action-parameter shape conformance.

For every MBean action declared in `<wrc>/resources/.../extension.yaml`,
verify the generated spec's request body schema for that action matches
what the live WebLogic runtime expects:

- A parameter declared with `array: true` must surface as
  `type: array` (with an `items:` sub-schema), not a scalar.
- A scalar parameter must surface as a non-array schema.

This caught the post-v0.4.0 bug where `_action_op` ignored
`array: true` and emitted `targets: type: string` for
`AppDeploymentRuntimeMBean.start` / `stop` — WebLogic 14.1.2 then
returned HTTP 400 because it expects `targets: array<string>`.

Runs against every regenerated spec in `specs/generated/` so the
check covers all 5 WLS versions in one shot.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Iterator

import pytest
import yaml


REPO_ROOT = Path(__file__).resolve().parents[3]
WRC_ROOT = Path(os.environ.get("WRC_ROOT", "/tmp/wrc"))
RESOURCES_ROOT = WRC_ROOT / "resources" / "src" / "main" / "resources"
SPECS_DIR = REPO_ROOT / "specs" / "generated"

# WLS versions to verify. The action surface is largely the same across
# versions, but we run the check against every spec to catch any
# version-specific generator drift.
SPEC_FILES = sorted(SPECS_DIR.glob("*.yaml")) if SPECS_DIR.is_dir() else []


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open() as fh:
        return yaml.safe_load(fh) or {}


def _iter_extension_actions() -> Iterator[tuple[str, dict[str, Any]]]:
    """Yield (mbean_dir_name, action) for every action in every harvested extension.yaml."""
    if not RESOURCES_ROOT.is_dir():
        return
    for ext_path in sorted(RESOURCES_ROOT.glob("*/extension.yaml")):
        data = _load_yaml(ext_path)
        for action in data.get("actions") or []:
            if not isinstance(action, dict):
                continue
            yield ext_path.parent.name, action


def _find_action_op(
    spec: dict[str, Any], action_url_name: str
) -> list[dict[str, Any]]:
    """Find every POST operation under a path ending in `/<action_url_name>`.

    A given action_name may be exposed via multiple parent paths
    (e.g. `start` exists on both `AppDeploymentRuntime` reachable via
    several routes); we return all of them so the assertion runs
    against each.
    """
    found: list[dict[str, Any]] = []
    suffix = f"/{action_url_name}"
    for url, item in (spec.get("paths") or {}).items():
        if not url.endswith(suffix):
            continue
        if not isinstance(item, dict):
            continue
        post = item.get("post")
        if isinstance(post, dict):
            found.append(post)
    return found


def _body_schema_props(post: dict[str, Any]) -> dict[str, Any]:
    """Return the request body's `properties` map, or {}."""
    body = (post.get("requestBody") or {}).get("content") or {}
    media = body.get("application/json") or {}
    schema = media.get("schema") or {}
    return schema.get("properties") or {}


def _is_array_schema(schema: dict[str, Any]) -> bool:
    if not isinstance(schema, dict):
        return False
    if schema.get("type") == "array":
        return True
    # Nullable arrays from overlay/quirks layers may serialise as
    # allOf [{$ref: ...Identity}] — but action-parameter types never
    # go through that path. Plain `type: array` check is sufficient.
    return False


# Build the parameter-level cases up front so pytest reports each
# (spec, mbean, action, parameter) failure individually.
def _cases() -> list[tuple[Path, str, str, str, str, bool]]:
    cases: list[tuple[Path, str, str, str, str, bool]] = []
    for mbean, action in _iter_extension_actions():
        url_name = action.get("remoteName") or action.get("name")
        if not url_name:
            continue
        params = action.get("parameters") or []
        for p in params:
            pname = p.get("name")
            if not pname:
                continue
            ptype = p.get("type") or ""
            is_array = bool(p.get("array"))
            for spec_file in SPEC_FILES:
                cases.append((spec_file, mbean, url_name, pname, ptype, is_array))
    return cases


_CASES = _cases()


@pytest.fixture(scope="session")
def specs() -> dict[Path, dict[str, Any]]:
    return {p: _load_yaml(p) for p in SPEC_FILES}


@pytest.mark.skipif(not SPEC_FILES, reason="no specs/generated/ files present")
@pytest.mark.skipif(not RESOURCES_ROOT.is_dir(), reason=f"WRC resources not at {RESOURCES_ROOT}")
@pytest.mark.parametrize(
    "spec_file,mbean,action,param,java_type,is_array",
    _CASES,
    ids=lambda v: str(v) if not isinstance(v, Path) else v.stem,
)
def test_action_parameter_array_flag(
    spec_file: Path,
    mbean: str,
    action: str,
    param: str,
    java_type: str,
    is_array: bool,
    specs: dict[Path, dict[str, Any]],
) -> None:
    """Every action parameter's array-ness in extension.yaml must match
    the request body schema in the generated spec."""
    spec = specs[spec_file]
    posts = _find_action_op(spec, action)
    if not posts:
        # The action is declared in extension.yaml but the path-builder
        # didn't emit a path for it on this version — typical when the
        # owning MBean isn't reachable from a tree root for this version.
        # Not a generator bug; just skip silently.
        pytest.skip(f"no path emits {action} on {spec_file.stem}")

    # The same action_url_name may match siblings from different MBeans
    # that happen to share an action verb (e.g. multiple beans expose
    # `start`). Without unique back-pointers we conservatively assert
    # the param-shape invariant on every match: if any one is wrong
    # the spec is wrong somewhere.
    relevant = [p for p in posts if param in _body_schema_props(p)]
    if not relevant:
        pytest.skip(
            f"no POST under {spec_file.stem} for {action} carries `{param}` "
            f"(action exists on a different MBean's path)"
        )

    for post in relevant:
        props = _body_schema_props(post)
        schema = props[param]
        actual_array = _is_array_schema(schema)
        assert actual_array == is_array, (
            f"{mbean}.{action}.{param} on {spec_file.stem}: "
            f"extension.yaml declares array={is_array} (java type {java_type!r}), "
            f"but spec emits schema={schema!r}"
        )
