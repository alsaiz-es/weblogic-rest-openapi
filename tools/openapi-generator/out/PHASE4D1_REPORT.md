# Phase 4d-1 — Quality of paths

WLS version: **14.1.2.0.0**  ·  spec: `tools/openapi-generator/out/spec-14.1.2.0.0.yaml`


## Spectral warnings — before / after

| Stage | errors | warnings |
|---|---:|---:|
| End of Phase 4c | 0 | 1989 |
| End of Phase 4d-1 | 0 | **0** |

Threshold per plan was **< 50** (target) / **< 100** (stop). Achieved **0**. Resolution per warning class:

| Warning class | 4c count | 4d-1 fix |
|---|---:|---|
| `operation-description` | 1983 | Added `description` per template (GET/POST/DELETE) on every emitted path; fallback to `summary` for any operation that still lacked one (covers virtual change-manager ops). |
| `operation-tag-defined` | 0 (4c had latent issue) | Aligned tag taxonomy: `domainRuntime`, `lifecycle`, `edit`, `change-manager`. The virtual overlay tag was renamed from `changeManager` to `change-manager` to match the doc-level `tags:` declaration. |
| `oas3-unused-component` | 4 | Removed `CollectionEnvelope` (path builder emits inline collection schemas). Retrofitted `ComponentRuntime` as a `oneOf` over its base + 4 subtypes (`WebApp`, `EJB`, `Connector`, `AppClient`) so the subtype schemas are referenced. Full discriminator/mapping setup deferred to 4d-3. |
| `info-contact` | 1 | Filled `info.contact` (name + GitHub URL). |
| `typed-enum` | 1 | The UI overlay encodes "use default; no override" as a `null`-valued legal value (e.g. `ServerTemplateMBean.StagingMode`). The schema builder now strips `None` from `legalValues`; if the resulting list is empty the enum is dropped entirely. |

## Operation coverage

- Total operations: **2018**
- With `summary`: 2018 (100%)
- With `description`: 2018 (100%)
- With at least one `tags` entry: 2018 (100%)

**Tag distribution:**

| Tag | Operations |
|---|---:|
| `edit` | 1521 |
| `domainRuntime` | 477 |
| `lifecycle` | 14 |
| `change-manager` | 6 |

## Validation results

| Validator | Phase 4c | Phase 4d-1 |
|---|---|---|
| `openapi-spec-validator` 3.0 strict | PASS | **PASS** |
| `openapi-generator-cli` Python client smoke test | PASS | **PASS** (5 API modules, 260 models) |
| `@stoplight/spectral-cli` (`spectral:oas` ruleset) | 0 errors / 1989 warnings | **0 / 0** |
| Swagger UI render via Docker | DEFERRED | DEFERRED — Docker not in environment |

## Path parameter naming — applied mapping

Names come from `PARAM_NAME_OVERRIDES` in `path_builder.py` for hand-picked cases, with a mechanical fallback `_strip_to_param_name` that strips `Runtimes` / `MBeans` / `s` from the property name and appends `Name`. Disambiguation is by numeric suffix when a parameter name would collide within a single URL (typical case: tasks containing tasks).

**Used overrides (sample, sorted alphabetically):**

| Containment property | Parameter name |
|---|---|
| `DBClientDataDeploymentRuntimes` | `{deploymentName}` |
| `JDBCDataSourceRuntimeMBeans` | `{dataSourceName}` |
| `JDBCStores` | `{storeName}` |
| `JDBCSystemResources` | `{systemResourceName}` |
| `JMSServers` | `{JMSServerName}` |
| `JMSSystemResources` | `{systemResourceName}` |
| `WLDFSystemResources` | `{systemResourceName}` |
| `allWorkflows` | `{workflowName}` |
| `appDeploymentRuntimes` | `{deploymentName}` |
| `appDeployments` | `{deploymentName}` |
| `applicationRuntimes` | `{applicationName}` |
| `callouts` | `{calloutName}` |
| `clusters` | `{clusterName}` |
| `coherenceClusterSystemResources` | `{systemResourceName}` |
| `componentRuntimes` | `{componentName}` |
| `customResources` | `{resourceName}` |
| `deploymentProgressObjects` | `{deploymentProgressId}` |
| `fairShareRequestClasses` | `{requestClassName}` |
| `fileStores` | `{storeName}` |
| `foreignJNDIProviders` | `{providerName}` |
| `inactiveWorkflows` | `{workflowName}` |
| `libDeploymentRuntimes` | `{deploymentName}` |
| `libraryRuntimes` | `{libraryName}` |
| `logFilters` | `{filterName}` |
| `machines` | `{machineName}` |
| `managedExecutorServiceTemplates` | `{templateName}` |
| `managedScheduledExecutorServiceTemplates` | `{templateName}` |
| `managedThreadFactoryTemplates` | `{templateName}` |
| `messagingBridges` | `{bridgeName}` |
| `migratableTargets` | `{targetName}` |
| `migrationDataRuntimes` | `{migrationName}` |
| `migrationTaskRuntimes` | `{taskName}` |
| `networkAccessPoints` | `{channelName}` |
| `nodeManagerRuntimes` | `{nodeManagerName}` |
| `pathServices` | `{pathServiceName}` |
| `responseTimeRequestClasses` | `{requestClassName}` |
| `scalingTasks` | `{taskName}` |
| `serverChannelRuntimes` | `{channelName}` |
| `serverLifeCycleRuntimes` | `{serverName}` |
| `serverRuntimes` | `{serverName}` |
| `serverTemplates` | `{templateName}` |
| `servers` | `{serverName}` |
| `serviceMigrationDataRuntimes` | `{migrationName}` |
| `shutdownClasses` | `{className}` |
| `singletonServices` | `{serviceName}` |
| `startupClasses` | `{className}` |
| `stoppedWorkflows` | `{workflowName}` |
| `subDeployments` | `{subDeploymentName}` |
| `subTasks` | `{taskName}` |
| `systemComponentLifeCycleRuntimes` | `{componentName}` |
| `tasks` | `{taskName}` |
| `virtualHosts` | `{hostName}` |
| `workManagers` | `{workManagerName}` |

**Disambiguated params (suffix > 1) — where the algorithm fell back:**

| Property | Param | Example URL |
|---|---|---|
| `subTasks` | `{taskName2}` | `/domainRuntime/elasticServiceManagerRuntime/scalingTasks/{taskName}/subTasks` |
| `subTasks` | `{taskName3}` | `/domainRuntime/elasticServiceManagerRuntime/scalingTasks/{taskName}/subTasks/{taskName2…` |
| `wseeV2Runtimes` | `{wseeV2Name}` | `/domainRuntime/serverRuntimes/{serverName}/applicationRuntimes/{applicationName}/wseeV2…` |
| `subDeployments` | `{subDeploymentName2}` | `/edit/appDeployments/{deploymentName}/subDeployments/{subDeploymentName}/subDeployments` |

These are intentionally numbered: the same containment type genuinely appears more than once on the same path (e.g. tasks containing subtasks containing further subtasks; or sub-deployments inside sub-deployments). The numeric suffix preserves uniqueness at the cost of a slightly less human-friendly name. Alternative would be hand-rolled overrides per depth level — not warranted for ≤ 3 occurrences.

## Sample of cleaned paths

Each block below is a copy of one path-item from the generated spec. These are representative rather than exhaustive.

```yaml
/management/weblogic/{version}/domainRuntime/serverRuntimes/{serverName}:
  get:
    operationId: getServerRuntime__domainRuntime_serverRuntimes_by_serverName
    tags:
    - domainRuntime
    summary: Get ServerRuntime
    description: Retrieve the `ServerRuntime` resource at this path.
    parameters:
    - $ref: '#/components/parameters/VersionPathParam'
    - $ref: '#/components/parameters/FieldsParam'
    - $ref: '#/components/parameters/ExcludeFieldsParam'
    - $ref: '#/components/parameters/LinksParam'
    - $ref: '#/components/parameters/ExcludeLinksParam'
    responses:
      '200':
        description: '`ServerRuntime` bean.'
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/ServerRuntime'
      '401':
        $ref: '#/components/responses/Unauthorized'
      '404':
        $ref: '#/components/responses/NotFound'
  parameters:
  - name: serverName
    in: path
    required: true
    description: Identifier of the parent collection item (`serverName`).
    schema:
      type: string
```

```yaml
/management/weblogic/{version}/domainRuntime/serverRuntimes/{serverName}/applicationRuntimes/{applicationName}:
  get:
    operationId: getApplicationRuntime__domainRuntime_serverRuntimes__applicationRuntimes_by_applicationName_9491e364
    tags:
    - domainRuntime
    summary: Get ApplicationRuntime
    description: Retrieve the `ApplicationRuntime` resource at this path.
    parameters:
    - $ref: '#/components/parameters/VersionPathParam'
    - $ref: '#/components/parameters/FieldsParam'
    - $ref: '#/components/parameters/ExcludeFieldsParam'
    - $ref: '#/components/parameters/LinksParam'
    - $ref: '#/components/parameters/ExcludeLinksParam'
    responses:
      '200':
        description: '`ApplicationRuntime` bean.'
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/ApplicationRuntime'
      '401':
        $ref: '#/components/responses/Unauthorized'
      '404':
        $ref: '#/components/responses/NotFound'
  parameters:
  - name: serverName
    in: path
    required: true
    description: Identifier of the parent collection item (`serverName`).
    schema:
      type: string
  - name: applicationName
    in: path
    required: true
    description: Identifier of the parent collection item (`applicationName`).
    schema:
      type: string
```

```yaml
? /management/weblogic/{version}/domainRuntime/serverRuntimes/{serverName}/JDBCServiceRuntime/JDBCDataSourceRuntimeMBeans/{dataSourceName}
: get:
    operationId: getJDBCDataSourceRuntime__domainRuntime_serverRuntimes__JDBCDataSourceRuntimeMBeans_by_dataSourceName_0be2730a
    tags:
    - domainRuntime
    summary: Get JDBCDataSourceRuntime
    description: Retrieve the `JDBCDataSourceRuntime` resource at this path.
    parameters:
    - $ref: '#/components/parameters/VersionPathParam'
    - $ref: '#/components/parameters/FieldsParam'
    - $ref: '#/components/parameters/ExcludeFieldsParam'
    - $ref: '#/components/parameters/LinksParam'
    - $ref: '#/components/parameters/ExcludeLinksParam'
    responses:
      '200':
        description: '`JDBCDataSourceRuntime` bean.'
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/JDBCDataSourceRuntime'
      '401':
        $ref: '#/components/responses/Unauthorized'
      '404':
        $ref: '#/components/responses/NotFound'
  parameters:
  - name: serverName
    in: path
    required: true
    description: Identifier of the parent collection item (`serverName`).
    schema:
      type: string
  - name: dataSourceName
    in: path
    required: true
    description: Identifier of the parent collection item (`dataSourceName`).
    schema:
      type: string
```

```yaml
/management/weblogic/{version}/domainRuntime/serverLifeCycleRuntimes/{serverName}/start:
  post:
    operationId: start__domainRuntime_serverLifeCycleRuntimes_by_serverName_start
    tags:
    - lifecycle
    summary: start on ServerLifeCycleRuntime
    description: Invoke the `start` operation on `ServerLifeCycleRuntime`. Requires `X-Requested-By`.
    parameters:
    - $ref: '#/components/parameters/VersionPathParam'
    - $ref: '#/components/parameters/XRequestedByHeader'
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
          example: {}
    responses:
      '200':
        description: Action result.
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/ServerLifeCycleTaskRuntime'
      '400':
        $ref: '#/components/responses/EditError'
      '401':
        $ref: '#/components/responses/Unauthorized'
      '404':
        $ref: '#/components/responses/NotFound'
  parameters:
  - name: serverName
    in: path
    required: true
    description: Identifier of the parent collection item (`serverName`).
    schema:
      type: string
```

```yaml
/management/weblogic/{version}/edit/changeManager:
  get:
    operationId: getChangeManagerState
    tags:
    - change-manager
    summary: Read current edit-session state.
    parameters:
    - $ref: '#/components/parameters/VersionPathParam'
    responses:
      '200':
        description: Session state envelope.
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/ChangeManagerState'
      '401':
        $ref: '#/components/responses/Unauthorized'
    description: Read current edit-session state.
```

```yaml
/management/weblogic/{version}/edit/clusters/{clusterName}:
  get:
    operationId: getCluster__edit_clusters_by_clusterName
    tags:
    - edit
    summary: Get Cluster
    description: Retrieve the `Cluster` resource at this path.
    parameters:
    - $ref: '#/components/parameters/VersionPathParam'
    - $ref: '#/components/parameters/FieldsParam'
    - $ref: '#/components/parameters/ExcludeFieldsParam'
    - $ref: '#/components/parameters/LinksParam'
    - $ref: '#/components/parameters/ExcludeLinksParam'
    responses:
      '200':
        description: '`Cluster` bean.'
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/Cluster'
      '401':
        $ref: '#/components/responses/Unauthorized'
      '404':
        $ref: '#/components/responses/NotFound'
  post:
    operationId: updateCluster__edit_clusters_by_clusterName
    tags:
    - edit
    summary: Update Cluster
    description: Update an existing `Cluster` resource. Body may contain only the changed fields. Requires `X-Requested-By`.
    parameters:
    - $ref: '#/components/parameters/VersionPathParam'
    - $ref: '#/components/parameters/XRequestedByHeader'
    requestBody:
      required: true
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/Cluster'
    responses:
      '200':
        description: '`Cluster` updated.'
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/Cluster'
      '400':
        $ref: '#/components/responses/EditError'
      '401':
        $ref: '#/components/responses/Unauthorized'
      '404':
        $ref: '#/components/responses/NotFound'
  delete:
    operationId: deleteCluster__edit_clusters_by_clusterName
    tags:
    - edit
    summary: Delete Cluster
    description: Delete this `Cluster` resource. Requires `X-Requested-By`.
    parameters:
    - $ref: '#/components/parameters/VersionPathParam'
    - $ref: '#/components/parameters/XRequestedByHeader'
    responses:
      '204':
        description: Deleted.
      '400':
        $ref: '#/components/responses/EditError'
      '401':
        $ref: '#/components/responses/Unauthorized'
      '404':
        $ref: '#/components/responses/NotFound'
  parameters:
  - name: clusterName
    in: path
    required: true
    description: Identifier of the parent collection item (`clusterName`).
    schema:
      type: string
```

```yaml
/management/weblogic/{version}/edit/JDBCSystemResources/{systemResourceName}/JDBCResource/JDBCDriverParams:
  get:
    operationId: getJDBCDriverParamsBean__edit_JDBCSystemResources_by_systemResourceName_JDBCResource_JDBCDriverParams
    tags:
    - edit
    summary: Get JDBCDriverParamsBean
    description: Retrieve the `JDBCDriverParamsBean` resource at this path.
    parameters:
    - $ref: '#/components/parameters/VersionPathParam'
    - $ref: '#/components/parameters/FieldsParam'
    - $ref: '#/components/parameters/ExcludeFieldsParam'
    - $ref: '#/components/parameters/LinksParam'
    - $ref: '#/components/parameters/ExcludeLinksParam'
    responses:
      '200':
        description: '`JDBCDriverParamsBean` bean.'
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/JDBCDriverParamsBean'
      '401':
        $ref: '#/components/responses/Unauthorized'
      '404':
        $ref: '#/components/responses/NotFound'
  post:
    operationId: updateJDBCDriverParamsBean__edit_JDBCSystemResources_by_systemResourceName_JDBCResource_JDBCDriverParams
    tags:
    - edit
    summary: Update JDBCDriverParamsBean
    description: Update an existing `JDBCDriverParamsBean` resource. Body may contain only the changed fields. Requires `X-Requested-By`.
    parameters:
    - $ref: '#/components/parameters/VersionPathParam'
    - $ref: '#/components/parameters/XRequestedByHeader'
    requestBody:
      required: true
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/JDBCDriverParamsBean'
    responses:
      '200':
        description: '`JDBCDriverParamsBean` updated.'
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/JDBCDriverParamsBean'
      '400':
        $ref: '#/components/responses/EditError'
      '401':
        $ref: '#/components/responses/Unauthorized'
      '404':
        $ref: '#/components/responses/NotFound'
  parameters:
  - name: systemResourceName
    in: path
    required: true
    description: Identifier of the parent collection item (`systemResourceName`).
    schema:
      type: string
```

## Edge cases discovered in 4d-1

- **OperationId length blew the Python client smoke test.** Deeply-nested URLs produced operationIds like `listCoherenceClusterWellKnownAddressBean__edit_coherenceClusterSystemResources_by_systemResourceName_coherenceClusterResource_coherenceClusterParams_coherenceClusterWellKnownAddresses_coherenceClusterWellKnownAddresses` (~165 chars). The generator turned that into snake-case `test_*_200_response.py` paths well past the 255-byte filename limit on macOS / Linux. Fix: cap `_url_to_op_id` output at 80 chars; when over, splice an 8-char SHA-1 hash of the URL between the head and tail segments. operationIds remain unique and the smoke test passes.
- **`null` legal values.** The UI overlay sometimes encodes "no override; use default" as `legalValues: [{value: null, label: default}]` (e.g. `ServerTemplateMBean.StagingMode`). OAS rejects `null` in a `string`-typed enum. Fix: filter `None` out of the resolved enum list; drop the `enum` constraint entirely if the list becomes empty.
- **Tag-name mismatch between overlay and doc.** The 4c virtual overlay used `changeManager`; the doc declared `change-manager`. Spectral correctly flagged 6 operations with an undeclared tag. Aligned to `change-manager`.
- **`{name2}` legitimately persists for nested same-type collections.** Tasks-of-tasks, sub-deployments-of-sub-deployments. Documented above; not a defect.
- **`ComponentRuntime` polymorphism.** Subtype schemas existed but nothing referenced them, generating `oas3-unused-component` warnings. Retrofitted `ComponentRuntime` as a `oneOf` over `[ComponentRuntimeBase, WebAppComponentRuntime, EJBComponentRuntime, ConnectorComponentRuntime, AppClientComponentRuntime]`. Discriminator/mapping setup deferred to 4d-3.

## Out of scope, deferred

- Quirks migration → 4d-2.
- Java-scraped operations (`startInAdmin`, `startInStandby`, `/domainRuntime/search`) → 4d-2.
- Enum extraction to shared schemas → 4d-3.
- Sub-type discriminator + mapping for `ComponentRuntime` (and any other polymorphic bean) → 4d-3.
- Server (165 props) / Cluster (77 props) surface curation → 4d-4.
- Multi-version generation (12.2.1.x, 14.1.1, 15.1.1) → 4d-5.
- Description merge policy (harvested + curated operational notes) → 4d-5.
- Live samples linking → 4d-5.

## Verdict

Spec went from 1989 spectral warnings to 0, every operation has summary + description + tag, path parameters read naturally (`{serverName}`, `{applicationName}`, `{dataSourceName}`, …) with `{name2}` only on the rare cases where it semantically fits. End-to-end validators all pass. Ready for review and 4d-2.