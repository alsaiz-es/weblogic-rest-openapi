"""Derive OpenAPI paths from harvested MBean containment graphs.

Each tree (domainRuntime, edit, ...) has a root MBean and a URL prefix.
We walk `properties[]` looking for `relationship: containment` entries
and emit paths recursively. Cycle detection is by schema name: each
MBean type is walked at most once per tree.

For the WLS REST framework's synthetic collections (most notably
`/domainRuntime/serverRuntimes`, which is not a JMX containment of
`DomainRuntimeMBean` but is exposed by the REST layer), we declare
synthetic edges in `SYNTHETIC_COLLECTIONS`.
"""
from __future__ import annotations

from typing import Any

from harvested_loader import HarvestedLoader
from schema_builder import normalize_schema_name, _name_to_property


# --- Configuration --------------------------------------------------------

TREE_CONFIG: dict[str, dict[str, Any]] = {
    "domainRuntime": {
        "root_mbean": "DomainRuntimeMBean",
        "root_schema": "DomainRuntime",
        "url_root": "/domainRuntime",
        "writable": False,
        "tags": ["domainRuntime"],
    },
    "edit": {
        "root_mbean": "DomainMBean",
        "root_schema": "Domain",
        "url_root": "/edit",
        "writable": True,
        "tags": ["edit"],
    },
}

# Synthetic edges: (tree, parent_url_path, prop_name, child_mbean_type).
# Used for collections that the WLS REST framework exposes but that are
# not a containment property in harvested. Verified empirically against
# the manual specs.
SYNTHETIC_COLLECTIONS: list[tuple[str, str, str, str]] = [
    ("domainRuntime", "", "serverRuntimes", "ServerRuntimeMBean"),
]

# Depth cap. The full graph has cycles only conceptually; visited-set
# by schema name terminates correctly. The cap is defensive.
MAX_DEPTH = 8


def _is_excluded(prop: dict[str, Any]) -> bool:
    if prop.get("supported") is False:
        return True
    if prop.get("exclude") is True:
        return True
    if prop.get("excludeFromRest") is True:
        return True
    if "restInternal" in prop:
        return True
    return False


# --- Builder --------------------------------------------------------------


class PathBuilder:
    def __init__(
        self,
        loader: HarvestedLoader,
        version_param_ref: str = "#/components/parameters/VersionPathParam",
        common_param_refs: list[str] | None = None,
        x_requested_by_ref: str = "#/components/parameters/XRequestedByHeader",
    ) -> None:
        self.loader = loader
        self.version_param_ref = version_param_ref
        self.common_param_refs = common_param_refs or [
            "#/components/parameters/FieldsParam",
            "#/components/parameters/ExcludeFieldsParam",
            "#/components/parameters/LinksParam",
            "#/components/parameters/ExcludeLinksParam",
        ]
        self.x_requested_by_ref = x_requested_by_ref
        # paths[url] = path_item (dict with verbs).
        self.paths: dict[str, dict[str, Any]] = {}
        # schemas referenced via $ref but that we may not be generating.
        self.referenced_schemas: set[str] = set()
        # stats
        self.path_count_by_tree: dict[str, int] = {}
        # warnings
        self.warnings: list[str] = []

    # ----- helpers -----

    def _ref_schema(self, mbean_name: str) -> dict[str, str]:
        schema_name = normalize_schema_name(mbean_name)
        self.referenced_schemas.add(schema_name)
        return {"$ref": f"#/components/schemas/{schema_name}"}

    def _envelope_with_items(self, mbean_name: str) -> dict[str, Any]:
        ref = self._ref_schema(mbean_name)
        return {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": ref,
                },
                "links": {
                    "type": "array",
                    "items": {"$ref": "#/components/schemas/Link"},
                },
            },
        }

    def _common_params(self) -> list[dict[str, str]]:
        return [{"$ref": self.version_param_ref}] + [
            {"$ref": r} for r in self.common_param_refs
        ]

    def _xrb(self) -> list[dict[str, str]]:
        return [{"$ref": self.x_requested_by_ref}]

    def _ensure(self, url: str) -> dict[str, Any]:
        return self.paths.setdefault(url, {})

    # ----- emit verbs -----

    def _emit_get_singleton(
        self, tree: str, url: str, mbean_name: str, summary: str
    ) -> None:
        op = {
            "operationId": f"get{normalize_schema_name(mbean_name)}__{_url_to_op_id(url)}",
            "tags": TREE_CONFIG[tree]["tags"],
            "summary": summary,
            "parameters": self._common_params(),
            "responses": {
                "200": {
                    "description": f"{normalize_schema_name(mbean_name)} bean.",
                    "content": {
                        "application/json": {
                            "schema": self._ref_schema(mbean_name),
                        },
                    },
                },
                "401": {"$ref": "#/components/responses/Unauthorized"},
                "404": {"$ref": "#/components/responses/NotFound"},
            },
        }
        self._ensure(url)["get"] = op

    def _emit_get_collection(
        self, tree: str, url: str, mbean_name: str, summary: str
    ) -> None:
        op = {
            "operationId": f"list{normalize_schema_name(mbean_name)}__{_url_to_op_id(url)}",
            "tags": TREE_CONFIG[tree]["tags"],
            "summary": summary,
            "parameters": self._common_params(),
            "responses": {
                "200": {
                    "description": f"Collection of {normalize_schema_name(mbean_name)}.",
                    "content": {
                        "application/json": {
                            "schema": self._envelope_with_items(mbean_name),
                        },
                    },
                },
                "401": {"$ref": "#/components/responses/Unauthorized"},
            },
        }
        self._ensure(url)["get"] = op

    def _emit_post_create(
        self, tree: str, url: str, mbean_name: str, summary: str
    ) -> None:
        op = {
            "operationId": f"create{normalize_schema_name(mbean_name)}__{_url_to_op_id(url)}",
            "tags": TREE_CONFIG[tree]["tags"],
            "summary": summary,
            "parameters": [{"$ref": self.version_param_ref}] + self._xrb(),
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": self._ref_schema(mbean_name),
                    },
                },
            },
            "responses": {
                "201": {
                    "description": f"{normalize_schema_name(mbean_name)} created.",
                    "content": {
                        "application/json": {
                            "schema": self._ref_schema(mbean_name),
                        },
                    },
                },
                "400": {"$ref": "#/components/responses/EditError"},
                "401": {"$ref": "#/components/responses/Unauthorized"},
            },
        }
        self._ensure(url)["post"] = op

    def _emit_post_update(
        self, tree: str, url: str, mbean_name: str, summary: str
    ) -> None:
        op = {
            "operationId": f"update{normalize_schema_name(mbean_name)}__{_url_to_op_id(url)}",
            "tags": TREE_CONFIG[tree]["tags"],
            "summary": summary,
            "parameters": [{"$ref": self.version_param_ref}] + self._xrb(),
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": self._ref_schema(mbean_name),
                    },
                },
            },
            "responses": {
                "200": {
                    "description": f"{normalize_schema_name(mbean_name)} updated.",
                    "content": {
                        "application/json": {
                            "schema": self._ref_schema(mbean_name),
                        },
                    },
                },
                "400": {"$ref": "#/components/responses/EditError"},
                "401": {"$ref": "#/components/responses/Unauthorized"},
                "404": {"$ref": "#/components/responses/NotFound"},
            },
        }
        self._ensure(url)["post"] = op

    def _emit_delete(self, tree: str, url: str, mbean_name: str, summary: str) -> None:
        op = {
            "operationId": f"delete{normalize_schema_name(mbean_name)}__{_url_to_op_id(url)}",
            "tags": TREE_CONFIG[tree]["tags"],
            "summary": summary,
            "parameters": [{"$ref": self.version_param_ref}] + self._xrb(),
            "responses": {
                "204": {"description": "Deleted."},
                "400": {"$ref": "#/components/responses/EditError"},
                "401": {"$ref": "#/components/responses/Unauthorized"},
                "404": {"$ref": "#/components/responses/NotFound"},
            },
        }
        self._ensure(url)["delete"] = op

    # ----- recursion -----

    def _walk(
        self,
        tree: str,
        mbean_name: str,
        parent_url: str,
        visited: set[str],
        depth: int,
    ) -> None:
        if depth > MAX_DEPTH:
            return
        try:
            merged = self.loader.load_with_inheritance(mbean_name)
        except FileNotFoundError:
            self.warnings.append(
                f"missing harvested YAML for {mbean_name} (referenced from {parent_url})"
            )
            return
        schema_name = normalize_schema_name(mbean_name)
        if schema_name in visited:
            return
        visited.add(schema_name)

        cfg = TREE_CONFIG[tree]
        for prop in merged["properties"]:
            if _is_excluded(prop):
                continue
            if prop.get("relationship") != "containment":
                continue
            child_java_type = prop["type"]
            if "." not in child_java_type:
                continue  # primitive containment, skip
            child_simple = child_java_type.rsplit(".", 1)[-1]
            child_url_segment = _name_to_property(prop["name"])
            child_url = f"{parent_url}/{child_url_segment}"
            is_collection = bool(prop.get("array"))

            if is_collection:
                self._emit_get_collection(
                    tree,
                    child_url,
                    child_simple,
                    f"List `{prop['name']}` under `{parent_url or '/'}`.",
                )
                if cfg["writable"]:
                    self._emit_post_create(
                        tree,
                        child_url,
                        child_simple,
                        f"Create a new `{normalize_schema_name(child_simple)}`.",
                    )
                # Use a unique name parameter per nesting level so OpenAPI's
                # uniqueness rule on path parameters is satisfied.
                existing_name_count = sum(
                    1
                    for seg in child_url.split("/")
                    if seg.startswith("{name") and seg.endswith("}")
                )
                name_param = "{name}" if existing_name_count == 0 else f"{{name{existing_name_count + 1}}}"
                item_url = f"{child_url}/{name_param}"
                self._emit_get_singleton(
                    tree,
                    item_url,
                    child_simple,
                    f"Read a single `{normalize_schema_name(child_simple)}` by name.",
                )
                if cfg["writable"]:
                    self._emit_post_update(
                        tree,
                        item_url,
                        child_simple,
                        f"Update a `{normalize_schema_name(child_simple)}`.",
                    )
                    self._emit_delete(
                        tree,
                        item_url,
                        child_simple,
                        f"Delete a `{normalize_schema_name(child_simple)}`.",
                    )
                # Recurse from item path.
                self._walk(tree, child_simple, item_url, set(visited), depth + 1)
            else:
                self._emit_get_singleton(
                    tree,
                    child_url,
                    child_simple,
                    f"Read singleton `{prop['name']}` under `{parent_url or '/'}`.",
                )
                if cfg["writable"]:
                    # Singletons under edit can be POSTed to (update) but not deleted.
                    self._emit_post_update(
                        tree,
                        child_url,
                        child_simple,
                        f"Update singleton `{normalize_schema_name(child_simple)}`.",
                    )
                self._walk(tree, child_simple, child_url, set(visited), depth + 1)

    # ----- top-level driver -----

    def build_all(self) -> None:
        for tree, cfg in TREE_CONFIG.items():
            url_root = cfg["url_root"]
            root_mbean = cfg["root_mbean"]
            # Emit a GET on the root itself when the root MBean has a known schema.
            self._emit_get_singleton(
                tree,
                url_root,
                root_mbean,
                f"Read the {tree} tree root.",
            )
            initial = self.paths.get(url_root, {})
            self._walk(tree, root_mbean, url_root, set(), 0)

            # Synthetic collections.
            for s_tree, s_parent, s_prop, s_child in SYNTHETIC_COLLECTIONS:
                if s_tree != tree:
                    continue
                coll_url = f"{url_root}{s_parent}/{s_prop}"
                self._emit_get_collection(
                    tree,
                    coll_url,
                    s_child,
                    f"List `{s_prop}` (REST-framework synthetic collection).",
                )
                item_url = f"{coll_url}/{{name}}"
                self._emit_get_singleton(
                    tree,
                    item_url,
                    s_child,
                    f"Read a single `{normalize_schema_name(s_child)}` by name.",
                )
                self._walk(tree, s_child, item_url, set(), 1)

            # Tally.
            tree_paths = [u for u in self.paths if u.startswith(url_root)]
            self.path_count_by_tree[tree] = len(tree_paths)


def _url_to_op_id(url: str) -> str:
    """Stable operationId fragment from a URL.

    `/serverRuntimes/{name}/applicationRuntimes/{name}` ->
    `serverRuntimes_byName_applicationRuntimes_byName`.
    """
    parts = []
    for seg in url.strip("/").split("/"):
        if seg.startswith("{") and seg.endswith("}"):
            parts.append("byName")
        else:
            parts.append(seg)
    return "_".join(parts) or "root"


if __name__ == "__main__":
    from harvested_loader import HarvestedLoader

    loader = HarvestedLoader("14.1.2.0.0")
    pb = PathBuilder(loader)
    pb.build_all()
    print(f"total paths: {len(pb.paths)}")
    for tree, n in pb.path_count_by_tree.items():
        print(f"  {tree}: {n}")
    print(f"referenced schemas: {len(pb.referenced_schemas)}")
    print(f"warnings: {len(pb.warnings)}")
