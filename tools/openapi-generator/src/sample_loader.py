"""Map live JSON samples in `samples/<version>/` onto generated operations.

Each sample file is mapped to a `(path_template, method, role, status)`
tuple. Roles:

- `canonical`: the single most representative sample for the operation.
  Emitted as a native OpenAPI `examples` block on the response keyed
  by status.
- `overflow`: additional samples for the same operation. Emitted as
  paths in `x-weblogic-sample-paths` on the operation.
- `error`: an error-response sample (4xx / 5xx). Emitted as native
  `examples` under that status when the operation has the response;
  falls back to `x-weblogic-sample-paths` otherwise.

Path templates here are unprefixed (no `/management/weblogic/{version}`)
and use the placeholders the generator emits (e.g. `{serverName}`,
`{name}`).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]
SAMPLES_ROOT = REPO_ROOT / "samples"

# WLS spec versions → on-disk directory under samples/.
SAMPLE_DIRS = {
    "12.2.1.4.0": "12.2.1.4",
    "14.1.2.0.0": "14.1.2",
}


# Per-version explicit map. Each entry: relative path under samples/<dir>/
# → (path_template, method, role, status, summary).
#
# The mapping is deliberately exhaustive rather than heuristic: with
# ~60 files per version a hand-curated table is more reliable than a
# pattern matcher and the report can document each decision.

_SAMPLES_14_1_2: list[tuple[str, str, str, str, str, str]] = [
    # Domain root
    ("domainRuntime_root.json",
     "/domainRuntime", "get", "canonical", "200",
     "Root of the domainRuntime bean tree (links to every child)."),

    # Server runtimes
    ("serverRuntimes_collection.json",
     "/domainRuntime/serverRuntimes", "get", "canonical", "200",
     "Collection on a domain with managed servers running."),
    ("serverRuntimes_collection_with_server1_400.json",
     "/domainRuntime/serverRuntimes", "get", "error", "400",
     "400 returned when X-Requested-By is missing and a managed server runs."),
    ("serverRuntime_AdminServer.json",
     "/domainRuntime/serverRuntimes/{serverName}", "get", "canonical", "200",
     "AdminServer runtime (verbatim WLS 14.1.2)."),

    # Threads & JVM
    ("threadPoolRuntime_AdminServer.json",
     "/domainRuntime/serverRuntimes/{serverName}/threadPoolRuntime", "get", "canonical", "200",
     "Self-tuning thread pool on AdminServer."),
    ("jvmRuntime_AdminServer.json",
     "/domainRuntime/serverRuntimes/{serverName}/JVMRuntime", "get", "canonical", "200",
     "JVM runtime on AdminServer (HotSpot 21)."),

    # Channels
    ("serverChannelRuntimes_collection_AdminServer.json",
     "/domainRuntime/serverRuntimes/{serverName}/serverChannelRuntimes", "get", "canonical", "200",
     "Network channel collection on AdminServer."),
    ("serverChannelRuntimes_collection_server1.json",
     "/domainRuntime/serverRuntimes/{serverName}/serverChannelRuntimes", "get", "overflow", "200",
     "Same collection on a managed server."),
    ("serverChannelRuntime_individual_AdminServer_t3.json",
     "/domainRuntime/serverRuntimes/{serverName}/serverChannelRuntimes/{channelName}", "get", "canonical", "200",
     "Default[t3] channel on AdminServer."),

    # Applications
    ("applicationRuntimes_collection_AdminServer.json",
     "/domainRuntime/serverRuntimes/{serverName}/applicationRuntimes", "get", "canonical", "200",
     "Application runtime collection on AdminServer."),
    ("applicationRuntimes_collection_server1.json",
     "/domainRuntime/serverRuntimes/{serverName}/applicationRuntimes", "get", "overflow", "200",
     "Application runtime collection on a managed server."),
    ("applicationRuntimes_summary.json",
     "/domainRuntime/serverRuntimes/{serverName}/applicationRuntimes", "get", "overflow", "200",
     "Trimmed-fields summary view for inventory."),
    ("applicationRuntime_individual_AdminServer_bea_wls_internal.json",
     "/domainRuntime/serverRuntimes/{serverName}/applicationRuntimes/{applicationName}", "get", "canonical", "200",
     "Framework-internal application (`bea_wls_internal`)."),
    ("applicationRuntime_individual_AdminServer_jamagent.json",
     "/domainRuntime/serverRuntimes/{serverName}/applicationRuntimes/{applicationName}", "get", "overflow", "200",
     "Java Mission Agent application instance."),

    # Components
    ("componentRuntimes_collection_wls-management-services.json",
     "/domainRuntime/serverRuntimes/{serverName}/applicationRuntimes/{applicationName}/componentRuntimes",
     "get", "canonical", "200",
     "Components of `wls-management-services` (web modules)."),
    ("componentRuntimes_collection_jms-internal-xa-adp.json",
     "/domainRuntime/serverRuntimes/{serverName}/applicationRuntimes/{applicationName}/componentRuntimes",
     "get", "overflow", "200",
     "Components of the JMS internal XA connector application."),
    ("componentRuntime_individual_wls-management-services_webapp.json",
     "/domainRuntime/serverRuntimes/{serverName}/applicationRuntimes/{applicationName}/componentRuntimes/{componentName}",
     "get", "canonical", "200",
     "Web module of `wls-management-services` (`WebAppComponentRuntime`)."),
    ("componentRuntime_individual_jmsadp_connector.json",
     "/domainRuntime/serverRuntimes/{serverName}/applicationRuntimes/{applicationName}/componentRuntimes/{componentName}",
     "get", "overflow", "200",
     "JCA resource adapter component (`ConnectorComponentRuntime`)."),

    # JDBC service & datasources
    ("jdbcServiceRuntime_AdminServer.json",
     "/domainRuntime/serverRuntimes/{serverName}/JDBCServiceRuntime", "get", "canonical", "200",
     "JDBC service runtime container on AdminServer."),
    ("jdbc_datasources_collection.json",
     "/domainRuntime/serverRuntimes/{serverName}/JDBCServiceRuntime/JDBCDataSourceRuntimeMBeans",
     "get", "canonical", "200",
     "Datasource runtime collection."),
    ("jdbc_datasource_TestDS.json",
     "/domainRuntime/serverRuntimes/{serverName}/JDBCServiceRuntime/JDBCDataSourceRuntimeMBeans/{dataSourceName}",
     "get", "canonical", "200",
     "TestDS datasource runtime."),

    # JMS
    ("jmsRuntime_AdminServer.json",
     "/domainRuntime/serverRuntimes/{serverName}/JMSRuntime", "get", "canonical", "200",
     "JMS runtime container on AdminServer (no JMS servers targeted)."),
    ("jmsRuntime_server1.json",
     "/domainRuntime/serverRuntimes/{serverName}/JMSRuntime", "get", "overflow", "200",
     "JMS runtime on a managed server."),
    ("jmsRuntime_server1_with_jmsserver.json",
     "/domainRuntime/serverRuntimes/{serverName}/JMSRuntime", "get", "overflow", "200",
     "JMS runtime on a managed server with one JMS server targeted."),
    ("jmsServers_collection_AdminServer.json",
     "/domainRuntime/serverRuntimes/{serverName}/JMSRuntime/JMSServers", "get", "canonical", "200",
     "Empty JMS server collection on AdminServer."),
    ("jmsServers_collection_server1.json",
     "/domainRuntime/serverRuntimes/{serverName}/JMSRuntime/JMSServers", "get", "overflow", "200",
     "JMS server collection on a managed server."),
    ("jmsServers_collection_server1_with_jmsserver.json",
     "/domainRuntime/serverRuntimes/{serverName}/JMSRuntime/JMSServers", "get", "overflow", "200",
     "JMS server collection with one targeted server."),
    ("jmsServer_individual_server1_myJMSServer.json",
     "/domainRuntime/serverRuntimes/{serverName}/JMSRuntime/JMSServers/{JMSServerName}", "get", "canonical", "200",
     "JMSServer runtime detail on managed server."),

    # Lifecycle
    ("lifecycle/serverLifeCycleRuntime_server1.json",
     "/domainRuntime/serverLifeCycleRuntimes/{serverName}", "get", "canonical", "200",
     "Lifecycle runtime for a managed server."),
    ("lifecycle/serverLifeCycleRuntime_server1_with_links.json",
     "/domainRuntime/serverLifeCycleRuntimes/{serverName}", "get", "overflow", "200",
     "Same with links expanded (action rels visible)."),
    ("lifecycle/tasks_collection.json",
     "/domainRuntime/serverLifeCycleRuntimes/{serverName}/tasks", "get", "canonical", "200",
     "Task history on a managed server lifecycle runtime."),

    # Search
    ("search_empty.json",
     "/domainRuntime/search", "post", "canonical", "200",
     "Bulk search with empty body — returns the full domainRuntime root."),
    ("search_post_minimal.json",
     "/domainRuntime/search", "post", "overflow", "200",
     "Minimal POST body."),
    ("search_servers_basic.json",
     "/domainRuntime/search", "post", "overflow", "200",
     "Names and states of every running server."),
    ("search_servers_filtered.json",
     "/domainRuntime/search", "post", "overflow", "200",
     "Activation time of a single named server."),
    ("search_servers_threadpool.json",
     "/domainRuntime/search", "post", "overflow", "200",
     "Server state plus thread-pool counters in one call."),
    ("search_workaround_for_400_collection.json",
     "/domainRuntime/search", "post", "overflow", "200",
     "Workaround for the GET-collection 400 by going through search."),

    # Edit — change manager
    ("edit-tree/changeManager_idle.json",
     "/edit/changeManager", "get", "canonical", "200",
     "Edit session idle (no lock held)."),
    ("edit-tree/changeManager_idle_after_cancel.json",
     "/edit/changeManager", "get", "overflow", "200",
     "Idle state after a cancelEdit."),
    ("edit-tree/changeManager_active.json",
     "/edit/changeManager", "get", "overflow", "200",
     "Lock held with no pending changes."),
    ("edit-tree/changeManager_startEdit.json",
     "/edit/changeManager/startEdit", "post", "canonical", "200",
     "POST startEdit — empty body acknowledgment."),
    ("edit-tree/changeManager_cancel.json",
     "/edit/changeManager/cancelEdit", "post", "canonical", "200",
     "POST cancelEdit — empty body acknowledgment."),
    ("edit-tree/changeManager_safeResolve_idle_400.json",
     "/edit/changeManager/safeResolve", "post", "error", "400",
     "400 when calling safeResolve without holding the lock."),
    ("edit-tree/changeManager_forceResolve_idle_400.json",
     "/edit/changeManager/forceResolve", "post", "error", "400",
     "400 when calling forceResolve without holding the lock."),

    # Edit — servers
    ("edit-tree/edit_servers_collection.json",
     "/edit/servers", "get", "canonical", "200",
     "Configured server collection in the edit tree."),
    ("edit-tree/edit_server_AdminServer.json",
     "/edit/servers/{serverName}", "get", "canonical", "200",
     "AdminServer config (full ~136-property projection)."),
    ("edit-tree/edit_server_OpenAPISpecTestServer1_after_create.json",
     "/edit/servers/{serverName}", "get", "overflow", "200",
     "Newly-created managed server after activation."),

    # Edit — clusters
    ("edit-tree/edit_clusters_collection.json",
     "/edit/clusters", "get", "canonical", "200",
     "Configured cluster collection."),
    ("edit-tree/edit_cluster_cluster1.json",
     "/edit/clusters/{clusterName}", "get", "canonical", "200",
     "Cluster `cluster1` configuration."),
    ("edit-tree/edit_cluster_OpenAPISpecTestCluster_after_create.json",
     "/edit/clusters/{clusterName}", "get", "overflow", "200",
     "Newly-created cluster after activation."),

    # Edit — JDBCSystemResources tree
    ("edit-tree/edit_jdbcsysres_shell_after_create.json",
     "/edit/JDBCSystemResources/{systemResourceName}", "get", "canonical", "200",
     "Datasource shell after the partial-create POST registers the parent."),
    ("edit-tree/edit_jdbcsysres_OpenAPISpecTestDS_full.json",
     "/edit/JDBCSystemResources/{systemResourceName}", "get", "overflow", "200",
     "Datasource shell after staged-create completes."),
    ("edit-tree/edit_jdbcsysres_OpenAPISpecTestDS_after_update.json",
     "/edit/JDBCSystemResources/{systemResourceName}", "get", "overflow", "200",
     "Datasource shell after a subsequent update."),
    ("edit-tree/edit_jdbcsysres_minimal_post_400.json",
     "/edit/JDBCSystemResources", "post", "error", "400",
     "Partial-create 400 on POST — parent shell still registered."),
    ("edit-tree/edit_jdbcsysres_JDBCResource_full.json",
     "/edit/JDBCSystemResources/{systemResourceName}/JDBCResource", "get", "canonical", "200",
     "JDBCResource node populated."),
    ("edit-tree/edit_jdbcsysres_jdbcresource_default.json",
     "/edit/JDBCSystemResources/{systemResourceName}/JDBCResource", "get", "overflow", "200",
     "JDBCResource node in default state."),
    ("edit-tree/edit_jdbcsysres_JDBCDataSourceParams_full.json",
     "/edit/JDBCSystemResources/{systemResourceName}/JDBCResource/JDBCDataSourceParams", "get", "canonical", "200",
     "JDBCDataSourceParams populated (JNDI + transaction protocol)."),
    ("edit-tree/edit_jdbcsysres_JDBCDataSourceParams_after_update.json",
     "/edit/JDBCSystemResources/{systemResourceName}/JDBCResource/JDBCDataSourceParams", "get", "overflow", "200",
     "JDBCDataSourceParams after an update."),
    ("edit-tree/edit_jdbcsysres_JDBCResource_JDBCDataSourceParams_default.json",
     "/edit/JDBCSystemResources/{systemResourceName}/JDBCResource/JDBCDataSourceParams", "get", "overflow", "200",
     "JDBCDataSourceParams default state."),
    ("edit-tree/edit_jdbcsysres_JDBCDriverParams_full.json",
     "/edit/JDBCSystemResources/{systemResourceName}/JDBCResource/JDBCDriverParams", "get", "canonical", "200",
     "JDBCDriverParams populated (driver, URL, props)."),
    ("edit-tree/edit_jdbcsysres_JDBCDriverParams_after_update.json",
     "/edit/JDBCSystemResources/{systemResourceName}/JDBCResource/JDBCDriverParams", "get", "overflow", "200",
     "JDBCDriverParams after an update."),
    ("edit-tree/edit_jdbcsysres_JDBCResource_JDBCDriverParams_default.json",
     "/edit/JDBCSystemResources/{systemResourceName}/JDBCResource/JDBCDriverParams", "get", "overflow", "200",
     "JDBCDriverParams default state."),
    ("edit-tree/edit_jdbcsysres_JDBCConnectionPoolParams_full.json",
     "/edit/JDBCSystemResources/{systemResourceName}/JDBCResource/JDBCConnectionPoolParams", "get", "canonical", "200",
     "JDBCConnectionPoolParams populated (pool sizing + probing)."),
    ("edit-tree/edit_jdbcsysres_JDBCConnectionPoolParams_after_update.json",
     "/edit/JDBCSystemResources/{systemResourceName}/JDBCResource/JDBCConnectionPoolParams", "get", "overflow", "200",
     "JDBCConnectionPoolParams after an update."),
    ("edit-tree/edit_jdbcsysres_JDBCResource_JDBCConnectionPoolParams_default.json",
     "/edit/JDBCSystemResources/{systemResourceName}/JDBCResource/JDBCConnectionPoolParams", "get", "overflow", "200",
     "JDBCConnectionPoolParams default state."),
]

# 12.2.1.4 set: largely the same operations with different live data.
_SAMPLES_12_2_1_4: list[tuple[str, str, str, str, str, str]] = [
    ("domainRuntime_root.json",
     "/domainRuntime", "get", "canonical", "200",
     "Root of the domainRuntime bean tree (12.2.1.4 OSB domain)."),

    ("serverRuntimes_collection.json",
     "/domainRuntime/serverRuntimes", "get", "canonical", "200",
     "Collection on a 12.2.1.4 OSB domain (AdminServer + managed)."),
    ("serverRuntimes_collection_with_csrf_header.json",
     "/domainRuntime/serverRuntimes", "get", "overflow", "200",
     "Same collection request with X-Requested-By header set."),
    ("serverRuntimes_collection_with_managed_400.json",
     "/domainRuntime/serverRuntimes", "get", "error", "400",
     "400 when the managed server is up and the header is missing."),
    ("serverRuntime_AdminServer.json",
     "/domainRuntime/serverRuntimes/{serverName}", "get", "canonical", "200",
     "AdminServer runtime (verbatim WLS 12.2.1.4)."),
    ("serverRuntime_osb_server1.json",
     "/domainRuntime/serverRuntimes/{serverName}", "get", "overflow", "200",
     "OSB managed server (osb_server1) runtime."),
    ("serverRuntime_direct_osb_server1.json",
     "/domainRuntime/serverRuntimes/{serverName}", "get", "overflow", "200",
     "OSB managed server fetched directly."),

    ("threadPoolRuntime_osb_server1.json",
     "/domainRuntime/serverRuntimes/{serverName}/threadPoolRuntime", "get", "canonical", "200",
     "Thread pool runtime on a 12.2.1.4 OSB managed server."),
    ("jvmRuntime_osb_server1.json",
     "/domainRuntime/serverRuntimes/{serverName}/JVMRuntime", "get", "canonical", "200",
     "JVM runtime on a 12.2.1.4 OSB managed server (HotSpot 8)."),

    ("serverChannelRuntimes_collection_osb_server1.json",
     "/domainRuntime/serverRuntimes/{serverName}/serverChannelRuntimes", "get", "canonical", "200",
     "Network channel collection on osb_server1."),
    ("serverChannelRuntime_individual_osb_server1_t3.json",
     "/domainRuntime/serverRuntimes/{serverName}/serverChannelRuntimes/{channelName}", "get", "canonical", "200",
     "Default[t3] channel on osb_server1."),

    ("applicationRuntimes_collection_osb_server1.json",
     "/domainRuntime/serverRuntimes/{serverName}/applicationRuntimes", "get", "canonical", "200",
     "Applications targeted at osb_server1 (76-app FMW domain)."),
    ("applicationRuntimes_summary.json",
     "/domainRuntime/serverRuntimes/{serverName}/applicationRuntimes", "get", "overflow", "200",
     "Trimmed-fields summary."),
    ("applicationRuntime_individual_osb_server1_DbAdapter.json",
     "/domainRuntime/serverRuntimes/{serverName}/applicationRuntimes/{applicationName}", "get", "canonical", "200",
     "Single application runtime (DbAdapter)."),

    ("componentRuntimes_collection_wsm-pm.json",
     "/domainRuntime/serverRuntimes/{serverName}/applicationRuntimes/{applicationName}/componentRuntimes",
     "get", "canonical", "200",
     "Components of `wsm-pm` (mixed web + EJB)."),
    ("componentRuntimes_collection_service-bus-routing.json",
     "/domainRuntime/serverRuntimes/{serverName}/applicationRuntimes/{applicationName}/componentRuntimes",
     "get", "overflow", "200",
     "Components of `service-bus-routing` (web + appclient)."),
    ("componentRuntime_individual_wsm-pm_webapp.json",
     "/domainRuntime/serverRuntimes/{serverName}/applicationRuntimes/{applicationName}/componentRuntimes/{componentName}",
     "get", "canonical", "200",
     "Web module component (`WebAppComponentRuntime`)."),
    ("componentRuntime_individual_wsm-pm_ejb.json",
     "/domainRuntime/serverRuntimes/{serverName}/applicationRuntimes/{applicationName}/componentRuntimes/{componentName}",
     "get", "overflow", "200",
     "EJB jar component (`EJBComponentRuntime`)."),
    ("componentRuntime_individual_service-bus-routing_appclient.json",
     "/domainRuntime/serverRuntimes/{serverName}/applicationRuntimes/{applicationName}/componentRuntimes/{componentName}",
     "get", "overflow", "200",
     "AppClient jar component (`AppClientComponentRuntime`)."),
    ("componentRuntime_individual_jmsadp_connector.json",
     "/domainRuntime/serverRuntimes/{serverName}/applicationRuntimes/{applicationName}/componentRuntimes/{componentName}",
     "get", "overflow", "200",
     "JCA resource adapter component (`ConnectorComponentRuntime`)."),

    ("jdbcServiceRuntime_osb_server1.json",
     "/domainRuntime/serverRuntimes/{serverName}/JDBCServiceRuntime", "get", "canonical", "200",
     "JDBC service runtime on osb_server1."),
    ("jdbc_datasources_collection.json",
     "/domainRuntime/serverRuntimes/{serverName}/JDBCServiceRuntime/JDBCDataSourceRuntimeMBeans",
     "get", "canonical", "200",
     "Datasource runtime collection (FMW internal datasources)."),
    ("jdbc_datasource_wlsbjmsrpDataSource.json",
     "/domainRuntime/serverRuntimes/{serverName}/JDBCServiceRuntime/JDBCDataSourceRuntimeMBeans/{dataSourceName}",
     "get", "canonical", "200",
     "wlsbjmsrpDataSource — XA, Oracle 19c."),

    ("jmsRuntime_osb_server1.json",
     "/domainRuntime/serverRuntimes/{serverName}/JMSRuntime", "get", "canonical", "200",
     "JMS runtime on osb_server1 (no JMS servers initially)."),
    ("jmsRuntime_osb_server1_after_myJMSServer.json",
     "/domainRuntime/serverRuntimes/{serverName}/JMSRuntime", "get", "overflow", "200",
     "JMS runtime after targeting myJMSServer."),
    ("jmsServers_collection_osb_server1.json",
     "/domainRuntime/serverRuntimes/{serverName}/JMSRuntime/JMSServers", "get", "canonical", "200",
     "JMS server collection on osb_server1."),
    ("jmsServer_individual_osb_server1_myJMSServer.json",
     "/domainRuntime/serverRuntimes/{serverName}/JMSRuntime/JMSServers/{JMSServerName}", "get", "canonical", "200",
     "myJMSServer instance with active counters."),
    ("jmsServer_individual_osb_server1_wlsbJMSServer_auto_2.json",
     "/domainRuntime/serverRuntimes/{serverName}/JMSRuntime/JMSServers/{JMSServerName}", "get", "overflow", "200",
     "wlsbJMSServer_auto_2 instance (JMS auto-targeted server)."),

    ("lifecycle/serverLifeCycleRuntime_osb_server1.json",
     "/domainRuntime/serverLifeCycleRuntimes/{serverName}", "get", "canonical", "200",
     "Lifecycle runtime on osb_server1."),

    ("search_servers_basic.json",
     "/domainRuntime/search", "post", "canonical", "200",
     "Basic POST /search returning server names + states."),
    ("search_servers_threadpool.json",
     "/domainRuntime/search", "post", "overflow", "200",
     "Server states plus thread-pool counters in one call."),

    # Edit — change manager
    ("edit-tree/changeManager_idle.json",
     "/edit/changeManager", "get", "canonical", "200",
     "Edit session idle (12.2.1.4)."),
    ("edit-tree/changeManager_idle_after_cancel.json",
     "/edit/changeManager", "get", "overflow", "200",
     "Idle state after cancelEdit."),
    ("edit-tree/changeManager_active.json",
     "/edit/changeManager", "get", "overflow", "200",
     "Lock held."),
    ("edit-tree/changeManager_startEdit.json",
     "/edit/changeManager/startEdit", "post", "canonical", "200",
     "POST startEdit acknowledgment."),
    ("edit-tree/changeManager_cancel.json",
     "/edit/changeManager/cancelEdit", "post", "canonical", "200",
     "POST cancelEdit acknowledgment."),
    ("edit-tree/changeManager_safeResolve_idle_400.json",
     "/edit/changeManager/safeResolve", "post", "error", "400",
     "400 when calling safeResolve without holding the lock."),
    ("edit-tree/changeManager_forceResolve_idle_400.json",
     "/edit/changeManager/forceResolve", "post", "error", "400",
     "400 when calling forceResolve without holding the lock."),

    # Edit — clusters
    ("edit-tree/edit_clusters_collection.json",
     "/edit/clusters", "get", "canonical", "200",
     "Configured cluster collection."),
    ("edit-tree/edit_cluster_cluster1.json",
     "/edit/clusters/{clusterName}", "get", "canonical", "200",
     "Cluster `cluster1` configuration."),
    ("edit-tree/edit_cluster_OpenAPISpecTestCluster_after_create.json",
     "/edit/clusters/{clusterName}", "get", "overflow", "200",
     "Newly-created cluster after activation."),

    # Edit — servers (12.2.1.4 has no `edit_servers_collection`/`edit_server_AdminServer`).
    ("edit-tree/edit_server_OpenAPISpecTestServer1_after_create.json",
     "/edit/servers/{serverName}", "get", "canonical", "200",
     "Newly-created managed server after activation."),

    # Edit — JDBCSystemResources
    ("edit-tree/edit_jdbcsysres_OpenAPISpecTestDS_after_create.json",
     "/edit/JDBCSystemResources/{systemResourceName}", "get", "canonical", "200",
     "Datasource shell after staged-create completes."),
    ("edit-tree/edit_jdbcsysres_full_tree_post_400.json",
     "/edit/JDBCSystemResources", "post", "error", "400",
     "POST root with full nested tree returns 400; partial parent stays."),
    ("edit-tree/edit_jdbcsysres_JDBCResource_full.json",
     "/edit/JDBCSystemResources/{systemResourceName}/JDBCResource", "get", "canonical", "200",
     "JDBCResource node populated."),
    ("edit-tree/edit_jdbcsysres_JDBCResource_default.json",
     "/edit/JDBCSystemResources/{systemResourceName}/JDBCResource", "get", "overflow", "200",
     "JDBCResource node default state."),
    ("edit-tree/edit_jdbcsysres_JDBCDataSourceParams_full.json",
     "/edit/JDBCSystemResources/{systemResourceName}/JDBCResource/JDBCDataSourceParams", "get", "canonical", "200",
     "JDBCDataSourceParams populated."),
    ("edit-tree/edit_jdbcsysres_JDBCResource_JDBCDataSourceParams_default.json",
     "/edit/JDBCSystemResources/{systemResourceName}/JDBCResource/JDBCDataSourceParams", "get", "overflow", "200",
     "JDBCDataSourceParams default state."),
    ("edit-tree/edit_jdbcsysres_JDBCDriverParams_full.json",
     "/edit/JDBCSystemResources/{systemResourceName}/JDBCResource/JDBCDriverParams", "get", "canonical", "200",
     "JDBCDriverParams populated."),
    ("edit-tree/edit_jdbcsysres_JDBCResource_JDBCDriverParams_default.json",
     "/edit/JDBCSystemResources/{systemResourceName}/JDBCResource/JDBCDriverParams", "get", "overflow", "200",
     "JDBCDriverParams default state."),
    ("edit-tree/edit_jdbcsysres_JDBCConnectionPoolParams_full.json",
     "/edit/JDBCSystemResources/{systemResourceName}/JDBCResource/JDBCConnectionPoolParams", "get", "canonical", "200",
     "JDBCConnectionPoolParams populated."),
    ("edit-tree/edit_jdbcsysres_JDBCResource_JDBCConnectionPoolParams_default.json",
     "/edit/JDBCSystemResources/{systemResourceName}/JDBCResource/JDBCConnectionPoolParams", "get", "overflow", "200",
     "JDBCConnectionPoolParams default state."),
]


# Files in samples/<dir>/ that are intentionally not mapped (e.g.
# generic error captures, csrf-test text artefacts). Reported in stats
# as "skipped".
_SKIPPED = {
    "12.2.1.4.0": [
        "error_400_sample.json",
        "error_404_sample.json",
        "error_401_sample.html",  # not JSON, harmless
        # csrf-test/* are .txt raw HTTP captures, not directly attachable
    ],
    "14.1.2.0.0": [
        "error_404_sample.json",
        "error_401_sample.html",
    ],
}


def _entries_for(version: str) -> list[tuple[str, str, str, str, str, str]]:
    return {
        "12.2.1.4.0": _SAMPLES_12_2_1_4,
        "14.1.2.0.0": _SAMPLES_14_1_2,
    }.get(version, [])


def load_inventory(version: str) -> dict[tuple[str, str], dict[str, Any]]:
    """Build a `(path_template, method) -> {canonical, overflow[], errors{}}` map."""
    sample_dir = SAMPLES_ROOT / SAMPLE_DIRS.get(version, "")
    entries = _entries_for(version)
    if not entries or not sample_dir.is_dir():
        return {}

    out: dict[tuple[str, str], dict[str, Any]] = {}
    for rel, path_tmpl, method, role, status, summary in entries:
        sample_path = sample_dir / rel
        if not sample_path.is_file():
            continue
        try:
            content = json.loads(sample_path.read_text())
        except Exception:
            continue
        repo_rel = f"samples/{SAMPLE_DIRS[version]}/{rel}"
        record = {
            "rel": rel,
            "repo_rel": repo_rel,
            "summary": summary,
            "content": content,
            "status": status,
        }
        bucket = out.setdefault((path_tmpl, method), {
            "canonical": None,
            "overflow": [],
            "errors": {},
        })
        if role == "canonical":
            if bucket["canonical"] is None:
                bucket["canonical"] = record
            else:
                # Two canonicals declared — keep the first, bump the
                # second to overflow. Should not happen in a valid map.
                bucket["overflow"].append(record)
        elif role == "overflow":
            bucket["overflow"].append(record)
        elif role == "error":
            bucket["errors"].setdefault(status, []).append(record)
    return out


def apply_samples(doc: dict[str, Any], version: str) -> dict[str, Any]:
    """Inject samples into the document. Returns stats."""
    inventory = load_inventory(version)
    if not inventory:
        return {
            "version": version,
            "operations_with_samples": 0,
            "canonical_injected": 0,
            "overflow_paths_injected": 0,
            "error_examples_injected": 0,
            "operations_unmatched": [],
        }

    paths = doc.get("paths", {})
    prefix = "/management/weblogic/{version}"

    canonical_injected = 0
    overflow_paths_injected = 0
    error_examples_injected = 0
    error_paths_injected = 0
    extension_only_injected = 0
    ops_with_any: set[tuple[str, str]] = set()
    unmatched: list[tuple[str, str]] = []

    # Operations whose response schemas trip spectral's recursion limit
    # (the Server edit schema is the only one observed). For these we
    # skip the native examples block and ship the sample only as an
    # x-weblogic-sample-paths entry.
    extension_only_ops: set[tuple[str, str]] = {
        # Spectral hits "Maximum call stack size exceeded" on the
        # 136-property edit-tree Server schema.
        ("/edit/servers", "get"),
        ("/edit/servers/{serverName}", "get"),
        # JDBCResource.datasourceType is an enum that does not include
        # `null` — but the live default sample returns null. Setting
        # `nullable: true` is insufficient under OAS 3.0 because the
        # enum check runs independently. Route through extension only.
        ("/edit/JDBCSystemResources/{systemResourceName}/JDBCResource", "get"),
        # Cluster has shape mismatches between harvested (`migratableTargets`
        # typed as array-of-array references) and live REST projection
        # (`array-of-{identity}` wrappers). Real schema correction is
        # heavier than a nullability flag; route through extension.
        ("/edit/clusters/{clusterName}", "get"),
    }

    for (path_tmpl, method), bucket in inventory.items():
        full_path = f"{prefix}{path_tmpl}"
        item = paths.get(full_path)
        if not item:
            unmatched.append((path_tmpl, method))
            continue
        op = item.get(method)
        if not isinstance(op, dict):
            unmatched.append((path_tmpl, method))
            continue
        ops_with_any.add((path_tmpl, method))
        force_ext = (path_tmpl, method) in extension_only_ops

        responses = op.setdefault("responses", {})
        sample_paths_extension: list[dict[str, Any]] = []

        canon = bucket["canonical"]
        if canon is not None:
            if force_ext or _response_is_ref(responses.get(canon["status"])):
                sample_paths_extension.append({
                    "path": canon["repo_rel"],
                    "summary": f"{canon['status']}: {canon['summary']}",
                })
                extension_only_injected += 1
            else:
                _inject_example(responses, canon["status"], "canonical", canon)
                canonical_injected += 1

        for record in bucket["overflow"]:
            sample_paths_extension.append({
                "path": record["repo_rel"],
                "summary": record["summary"],
            })
            overflow_paths_injected += 1

        for status, records in bucket["errors"].items():
            response = responses.get(status)
            if response is None or _response_is_ref(response) or force_ext:
                for record in records:
                    sample_paths_extension.append({
                        "path": record["repo_rel"],
                        "summary": f"{status}: {record['summary']}",
                    })
                    error_paths_injected += 1
                continue
            for i, record in enumerate(records):
                key = "canonical" if i == 0 else f"overflow{i}"
                _inject_example(responses, status, key, record)
                error_examples_injected += 1

        if sample_paths_extension:
            existing = op.get("x-weblogic-sample-paths") or []
            existing.extend(sample_paths_extension)
            op["x-weblogic-sample-paths"] = existing

    return {
        "version": version,
        "operations_with_samples": len(ops_with_any),
        "canonical_injected": canonical_injected,
        "overflow_paths_injected": overflow_paths_injected,
        "error_examples_injected": error_examples_injected,
        "error_paths_injected": error_paths_injected,
        "extension_only_injected": extension_only_injected,
        "operations_unmatched": unmatched,
    }


def _response_is_ref(response: Any) -> bool:
    """A response is `$ref`-only when its sole keys make it a pure $ref.

    Adding `content` / `description` next to a `$ref` is forbidden in
    OAS 3.0 (`no-$ref-siblings`). For these cases we route the sample
    through the `x-weblogic-sample-paths` extension instead.
    """
    if not isinstance(response, dict):
        return False
    return "$ref" in response


def _inject_example(
    responses: dict[str, Any], status: str, key: str, record: dict[str, Any]
) -> None:
    response = responses.setdefault(status, {})
    content = response.setdefault("content", {})
    media = content.setdefault("application/json", {})
    examples = media.setdefault("examples", {})
    examples[key] = {
        "summary": record["summary"],
        "value": record["content"],
        "x-weblogic-sample-source": record["repo_rel"],
    }
    # Make sure the response carries a description if it doesn't yet
    # (responses without descriptions trip spectral). Fall back to the
    # sample summary.
    if not response.get("description"):
        response["description"] = record["summary"]
