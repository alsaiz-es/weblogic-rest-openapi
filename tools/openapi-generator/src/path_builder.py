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
        "default_tag": "domainRuntime",
    },
    "edit": {
        "root_mbean": "DomainMBean",
        "root_schema": "Domain",
        "url_root": "/edit",
        "writable": True,
        "default_tag": "edit",
    },
}

# Synthetic edges: (tree, parent_url_path, prop_name, child_mbean_type).
SYNTHETIC_COLLECTIONS: list[tuple[str, str, str, str]] = [
    ("domainRuntime", "", "serverRuntimes", "ServerRuntimeMBean"),
]

# Path-segment-prefix → tag override. Longest-prefix match.
PATH_TAG_OVERRIDES: list[tuple[str, str]] = [
    ("/edit/changeManager", "change-manager"),
    ("/domainRuntime/serverLifeCycleRuntimes", "lifecycle"),
]

MAX_DEPTH = 8


# --- Path-parameter naming -----------------------------------------------

# Hand-picked overrides for collection property names whose semantic
# parameter name differs from the mechanical strip-and-suffix rule. The
# right-hand side is the parameter base name (without numeric disambiguator).
PARAM_NAME_OVERRIDES: dict[str, str] = {
    # Server-side
    "serverRuntimes": "serverName",
    "serverLifeCycleRuntimes": "serverName",
    "serverChannelRuntimes": "channelName",
    "servers": "serverName",
    # Cluster-side
    "clusters": "clusterName",
    "clusterRuntimes": "clusterName",
    # JDBC-side (manual convention)
    "JDBCDataSourceRuntimeMBeans": "dataSourceName",
    "JDBCDataSourceRuntimes": "dataSourceName",
    "JDBCMultiDataSourceRuntimes": "dataSourceName",
    "JDBCSystemResources": "systemResourceName",
    "JDBCDataSourceTaskRuntimes": "taskName",
    # Apps / components
    "applicationRuntimes": "applicationName",
    "componentRuntimes": "componentName",
    "libraryRuntimes": "libraryName",
    # JMS
    "JMSServers": "JMSServerName",
    "JMSDestinationRuntimes": "destinationName",
    "JMSConnectionRuntimes": "connectionName",
    "JMSSessionPoolRuntimes": "sessionPoolName",
    # Tasks (will frequently nest under themselves)
    "scalingTasks": "taskName",
    "subTasks": "taskName",
    "migrationTaskRuntimes": "taskName",
    "migrationDataRuntimes": "migrationName",
    "serviceMigrationDataRuntimes": "migrationName",
    "tasks": "taskName",
    "allWorkflows": "workflowName",
    "inactiveWorkflows": "workflowName",
    "stoppedWorkflows": "workflowName",
    # Deployment / lifecycle
    "subDeployments": "subDeploymentName",
    "appDeployments": "deploymentName",
    "appDeploymentRuntimes": "deploymentName",
    "libDeploymentRuntimes": "deploymentName",
    "deploymentProgressObjects": "deploymentProgressId",
    "DBClientDataDeploymentRuntimes": "deploymentName",
    "nodeManagerRuntimes": "nodeManagerName",
    "coherenceServerLifeCycleRuntimes": "serverName",
    "systemComponentLifeCycleRuntimes": "componentName",
    # Edit-tree common
    "machines": "machineName",
    "fileStores": "storeName",
    "JDBCStores": "storeName",
    "JMSSystemResources": "systemResourceName",
    "WLDFSystemResources": "systemResourceName",
    "coherenceClusterSystemResources": "systemResourceName",
    "appDeploymentRuntimes": "deploymentName",
    "callouts": "calloutName",
    "customResources": "resourceName",
    "domains": "domainName",
    "errorHandlings": "errorHandlingName",
    "fairShareRequestClasses": "requestClassName",
    "foreignJNDIProviders": "providerName",
    "logFilters": "filterName",
    "managedExecutorServiceTemplates": "templateName",
    "managedScheduledExecutorServiceTemplates": "templateName",
    "managedThreadFactoryTemplates": "templateName",
    "messagingBridges": "bridgeName",
    "migratableTargets": "targetName",
    "networkAccessPoints": "channelName",
    "partitions": "partitionName",
    "pathServices": "pathServiceName",
    "remoteSAFContexts": "contextName",
    "responseTimeRequestClasses": "requestClassName",
    "resourceGroups": "groupName",
    "resourceGroupTemplates": "templateName",
    "selfTuning": "tuningName",
    "serverTemplates": "templateName",
    "shutdownClasses": "className",
    "singletonServices": "serviceName",
    "snmpAgents": "agentName",
    "snmpProxies": "proxyName",
    "snmpTrapDestinations": "trapDestinationName",
    "startupClasses": "className",
    "targets": "targetName",
    "transitions": "transitionName",
    "virtualHosts": "hostName",
    "virtualTargets": "targetName",
    "workManagers": "workManagerName",
    "wsReliableDeliveryPolicies": "policyName",
    "wsRMConfigurations": "configurationName",
    "wsSecurities": "securityName",
    "WLDFArchives": "archiveName",
}


def _strip_to_param_name(prop_name: str) -> str:
    """Mechanical fallback: strip plural suffix, append `Name`.

    Applied when no override is present. Preserves acronym capitalization
    (consistent with `_name_to_property` in schema_builder).
    """
    base = prop_name
    for suffix in ("RuntimeMBeans", "MBeans", "Runtimes", "s"):
        if base.endswith(suffix):
            base = base[: -len(suffix)]
            break
    if not base:
        return prop_name + "Name"
    if len(base) >= 2 and base[0].isupper() and base[1].isupper():
        return base + "Name"
    return base[0].lower() + base[1:] + "Name"


def _derive_param_name(prop_name: str, used_names: set[str]) -> str:
    base = PARAM_NAME_OVERRIDES.get(prop_name) or _strip_to_param_name(prop_name)
    if base not in used_names:
        return base
    i = 2
    while f"{base}{i}" in used_names:
        i += 1
    return f"{base}{i}"


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


def _tag_for(tree: str, url: str) -> str:
    for prefix, tag in PATH_TAG_OVERRIDES:
        if url.startswith(prefix):
            return tag
    return TREE_CONFIG[tree]["default_tag"]


def _pluralize(name: str) -> str:
    """Pluralize a singular schema name for "List Foos" descriptions."""
    if not name:
        return name
    lower = name[-1].lower()
    if lower in ("s", "x"):
        return name + "es"
    if lower == "y" and len(name) > 1 and name[-2].lower() not in "aeiou":
        return name[:-1] + "ies"
    return name + "s"


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
        self.paths: dict[str, dict[str, Any]] = {}
        self.referenced_schemas: set[str] = set()
        self.path_count_by_tree: dict[str, int] = {}
        self.warnings: list[str] = []
        self.param_name_choices: list[tuple[str, str, str]] = []  # (prop_name, derived_param, url)

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

    # ----- emit verbs (templates) -----

    def _emit_get_singleton(self, tree: str, url: str, mbean_name: str) -> None:
        sn = normalize_schema_name(mbean_name)
        self._ensure(url)["get"] = {
            "operationId": f"get{sn}__{_url_to_op_id(url)}",
            "tags": [_tag_for(tree, url)],
            "summary": f"Get {sn}",
            "description": f"Retrieve the `{sn}` resource at this path.",
            "parameters": self._common_params(),
            "responses": {
                "200": {
                    "description": f"`{sn}` bean.",
                    "content": {"application/json": {"schema": self._ref_schema(mbean_name)}},
                },
                "401": {"$ref": "#/components/responses/Unauthorized"},
                "404": {"$ref": "#/components/responses/NotFound"},
            },
        }

    def _emit_get_collection(self, tree: str, url: str, mbean_name: str) -> None:
        sn = normalize_schema_name(mbean_name)
        plural = _pluralize(sn)
        self._ensure(url)["get"] = {
            "operationId": f"list{sn}__{_url_to_op_id(url)}",
            "tags": [_tag_for(tree, url)],
            "summary": f"List {sn}",
            "description": f"List all `{plural}` resources in this collection.",
            "parameters": self._common_params(),
            "responses": {
                "200": {
                    "description": f"Collection of `{sn}`.",
                    "content": {"application/json": {"schema": self._envelope_with_items(mbean_name)}},
                },
                "401": {"$ref": "#/components/responses/Unauthorized"},
            },
        }

    def _emit_post_create(self, tree: str, url: str, mbean_name: str) -> None:
        sn = normalize_schema_name(mbean_name)
        self._ensure(url)["post"] = {
            "operationId": f"create{sn}__{_url_to_op_id(url)}",
            "tags": [_tag_for(tree, url)],
            "summary": f"Create {sn}",
            "description": f"Create a new `{sn}` resource within this collection. Requires `X-Requested-By`.",
            "parameters": [{"$ref": self.version_param_ref}] + self._xrb(),
            "requestBody": {
                "required": True,
                "content": {"application/json": {"schema": self._ref_schema(mbean_name)}},
            },
            "responses": {
                "201": {
                    "description": f"`{sn}` created.",
                    "content": {"application/json": {"schema": self._ref_schema(mbean_name)}},
                },
                "400": {"$ref": "#/components/responses/EditError"},
                "401": {"$ref": "#/components/responses/Unauthorized"},
            },
        }

    def _emit_post_update(self, tree: str, url: str, mbean_name: str) -> None:
        sn = normalize_schema_name(mbean_name)
        self._ensure(url)["post"] = {
            "operationId": f"update{sn}__{_url_to_op_id(url)}",
            "tags": [_tag_for(tree, url)],
            "summary": f"Update {sn}",
            "description": f"Update an existing `{sn}` resource. Body may contain only the changed fields. Requires `X-Requested-By`.",
            "parameters": [{"$ref": self.version_param_ref}] + self._xrb(),
            "requestBody": {
                "required": True,
                "content": {"application/json": {"schema": self._ref_schema(mbean_name)}},
            },
            "responses": {
                "200": {
                    "description": f"`{sn}` updated.",
                    "content": {"application/json": {"schema": self._ref_schema(mbean_name)}},
                },
                "400": {"$ref": "#/components/responses/EditError"},
                "401": {"$ref": "#/components/responses/Unauthorized"},
                "404": {"$ref": "#/components/responses/NotFound"},
            },
        }

    def _emit_delete(self, tree: str, url: str, mbean_name: str) -> None:
        sn = normalize_schema_name(mbean_name)
        self._ensure(url)["delete"] = {
            "operationId": f"delete{sn}__{_url_to_op_id(url)}",
            "tags": [_tag_for(tree, url)],
            "summary": f"Delete {sn}",
            "description": f"Delete this `{sn}` resource. Requires `X-Requested-By`.",
            "parameters": [{"$ref": self.version_param_ref}] + self._xrb(),
            "responses": {
                "204": {"description": "Deleted."},
                "400": {"$ref": "#/components/responses/EditError"},
                "401": {"$ref": "#/components/responses/Unauthorized"},
                "404": {"$ref": "#/components/responses/NotFound"},
            },
        }

    # ----- recursion -----

    def _walk(
        self,
        tree: str,
        mbean_name: str,
        parent_url: str,
        visited: set[str],
        depth: int,
        used_param_names: set[str],
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
                continue
            child_simple = child_java_type.rsplit(".", 1)[-1]
            child_url_segment = _name_to_property(prop["name"])
            child_url = f"{parent_url}/{child_url_segment}"
            is_collection = bool(prop.get("array"))

            if is_collection:
                self._emit_get_collection(tree, child_url, child_simple)
                if cfg["writable"]:
                    self._emit_post_create(tree, child_url, child_simple)
                # Semantic param name for the item key.
                param_name = _derive_param_name(child_url_segment, used_param_names)
                self.param_name_choices.append((child_url_segment, param_name, child_url))
                item_url = f"{child_url}/{{{param_name}}}"
                self._emit_get_singleton(tree, item_url, child_simple)
                if cfg["writable"]:
                    self._emit_post_update(tree, item_url, child_simple)
                    self._emit_delete(tree, item_url, child_simple)
                self._walk(
                    tree,
                    child_simple,
                    item_url,
                    set(visited),
                    depth + 1,
                    used_param_names | {param_name},
                )
            else:
                self._emit_get_singleton(tree, child_url, child_simple)
                if cfg["writable"]:
                    self._emit_post_update(tree, child_url, child_simple)
                self._walk(
                    tree,
                    child_simple,
                    child_url,
                    set(visited),
                    depth + 1,
                    used_param_names,
                )

    # ----- top-level driver -----

    def build_all(self) -> None:
        for tree, cfg in TREE_CONFIG.items():
            url_root = cfg["url_root"]
            root_mbean = cfg["root_mbean"]
            self._emit_get_singleton(tree, url_root, root_mbean)
            self._walk(tree, root_mbean, url_root, set(), 0, set())

            for s_tree, s_parent, s_prop, s_child in SYNTHETIC_COLLECTIONS:
                if s_tree != tree:
                    continue
                coll_url = f"{url_root}{s_parent}/{s_prop}"
                self._emit_get_collection(tree, coll_url, s_child)
                param_name = _derive_param_name(s_prop, set())
                self.param_name_choices.append((s_prop, param_name, coll_url))
                item_url = f"{coll_url}/{{{param_name}}}"
                self._emit_get_singleton(tree, item_url, s_child)
                self._walk(
                    tree,
                    s_child,
                    item_url,
                    set(),
                    1,
                    {param_name},
                )

            tree_paths = [u for u in self.paths if u.startswith(url_root)]
            self.path_count_by_tree[tree] = len(tree_paths)


def _url_to_op_id(url: str) -> str:
    """Stable, bounded-length operationId fragment derived from a URL.

    Length-bounded because the Python client generator turns the
    operationId into snake_case test filenames; deeply-nested URLs
    produced > 255-byte filenames and broke client generation. Cap at ~80
    chars and append an 8-char hash of the full URL for uniqueness when
    truncating.
    """
    import hashlib

    parts = []
    for seg in url.strip("/").split("/"):
        if seg.startswith("{") and seg.endswith("}"):
            parts.append("by_" + seg[1:-1])
        else:
            parts.append(seg)
    full = "_".join(parts) or "root"
    if len(full) <= 80:
        return full
    h = hashlib.sha1(url.encode()).hexdigest()[:8]
    head = "_".join(parts[:2])
    tail = "_".join(parts[-2:])
    return f"{head}__{tail}_{h}"


if __name__ == "__main__":
    loader = HarvestedLoader("14.1.2.0.0")
    pb = PathBuilder(loader)
    pb.build_all()
    print(f"total paths: {len(pb.paths)}")
    for tree, n in pb.path_count_by_tree.items():
        print(f"  {tree}: {n}")
    # Sample some semantic params.
    print("\nSample param names chosen:")
    seen = set()
    for prop, param, url in pb.param_name_choices:
        if (prop, param) in seen:
            continue
        seen.add((prop, param))
        if len(seen) > 15:
            break
        print(f"  {prop:40s} -> {{{param}}}")
