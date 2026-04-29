"""Load harvested MBean YAMLs, with optional baseType inheritance resolution."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

HARVESTED_ROOT = Path(
    "/tmp/wrc/weblogic-bean-types/src/main/resources/harvestedWeblogicBeanTypes"
)


def _simple_name(java_fqn: str) -> str:
    """`weblogic.management.runtime.ServerRuntimeMBean` -> `ServerRuntimeMBean`."""
    return java_fqn.rsplit(".", 1)[-1] if "." in java_fqn else java_fqn


def _yaml_path(mbean_name: str, wls_version: str) -> Path:
    return HARVESTED_ROOT / wls_version / f"{mbean_name}.yaml"


class HarvestedLoader:
    """Caching loader for harvested MBean YAMLs.

    Each instance is scoped to one WLS version. `load(name)` returns the raw
    parsed dict; `load_with_inheritance(name)` returns a merged view plus a
    breakdown of which baseType in the chain contributed which properties.
    """

    def __init__(self, wls_version: str = "14.1.2.0.0") -> None:
        self.wls_version = wls_version
        self._cache: dict[str, dict[str, Any]] = {}

    # --- raw load ---------------------------------------------------------

    def load(self, mbean_name: str) -> dict[str, Any]:
        if mbean_name in self._cache:
            return self._cache[mbean_name]
        path = _yaml_path(mbean_name, self.wls_version)
        if not path.is_file():
            raise FileNotFoundError(f"harvested YAML not found: {path}")
        with path.open() as fh:
            data = yaml.safe_load(fh)
        if not isinstance(data, dict):
            raise ValueError(f"unexpected harvested YAML shape at {path}")
        data.setdefault("properties", [])
        self._cache[mbean_name] = data
        return data

    def try_load(self, mbean_name: str) -> dict[str, Any] | None:
        try:
            return self.load(mbean_name)
        except FileNotFoundError:
            return None

    # --- inheritance ------------------------------------------------------

    def _inheritance_chain(self, mbean_name: str) -> list[str]:
        """Return the chain from `mbean_name` up to the root.

        The list is ordered most-derived first, least-derived last:
        e.g. ['ServerRuntimeMBean', 'RuntimeMBean', 'WebLogicMBean'].
        Stops at any baseType whose YAML cannot be loaded (e.g. types
        outside the harvested set, like `weblogic.descriptor.SettableBean`).
        """
        chain: list[str] = []
        seen: set[str] = set()
        current: str | None = mbean_name
        while current and current not in seen:
            seen.add(current)
            chain.append(current)
            data = self.try_load(current)
            if data is None:
                break
            base_types = data.get("baseTypes") or []
            if not base_types:
                break
            # The harvested YAMLs we've inspected only ever declare a single
            # baseType per file. If multiple are ever declared we follow the
            # first and warn the caller via the chain length staying short.
            current = _simple_name(base_types[0])
        return chain

    def load_with_inheritance(self, mbean_name: str) -> dict[str, Any]:
        """Load `mbean_name` with all inherited properties merged.

        Child properties override parent properties of the same name.

        Returns a dict with:
            name:          FQN of the leaf MBean
            baseTypes:     leaf's baseTypes (raw, unmodified)
            descriptionHTML
            properties:    merged list (child wins on name collisions)
            inheritanceChain:    [most-derived, ..., least-derived]
            propertiesPerLevel:  {level_name: int}  for reporting
        """
        chain = self._inheritance_chain(mbean_name)

        merged: dict[str, dict[str, Any]] = {}
        per_level: dict[str, int] = {}
        # Walk least-derived to most-derived so child properties overwrite parents.
        for level in reversed(chain):
            data = self.try_load(level)
            if data is None:
                per_level[level] = 0
                continue
            level_props = data.get("properties", [])
            per_level[level] = len(level_props)
            for p in level_props:
                merged[p["name"]] = p

        leaf = self.load(mbean_name)
        return {
            "name": leaf.get("name"),
            "baseTypes": leaf.get("baseTypes"),
            "descriptionHTML": leaf.get("descriptionHTML", ""),
            "properties": list(merged.values()),
            "inheritanceChain": chain,
            "propertiesPerLevel": per_level,
        }


# Backwards-compatible function-style API for the older entry points.
def load_mbean(mbean_name: str, wls_version: str = "14.1.2.0.0") -> dict[str, Any]:
    return HarvestedLoader(wls_version).load(mbean_name)


if __name__ == "__main__":
    import json
    import sys

    name = sys.argv[1] if len(sys.argv) > 1 else "ServerRuntimeMBean"
    version = sys.argv[2] if len(sys.argv) > 2 else "14.1.2.0.0"
    loader = HarvestedLoader(version)
    merged = loader.load_with_inheritance(name)
    print(f"chain: {merged['inheritanceChain']}")
    print(f"per-level property counts: {merged['propertiesPerLevel']}")
    print(f"merged properties: {len(merged['properties'])}")
    print(json.dumps(merged["properties"][:2], indent=2))
