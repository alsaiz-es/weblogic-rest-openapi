# WebLogic REST Management API — Cross-Version Deltas (bulk coverage)

Diffs between adjacent supported WLS versions, regenerated against **bulk-coverage** specs (every harvested MBean processed, not just the 22 curated). Diffs now reflect every MBean change Oracle ships, including subsystems that were stubs in earlier sub-phases (JTA, WLDF, work managers, JMS detail, deployments, security).

Counts are computed against the generated specs. Stub schemas — polymorphic subtypes declared in the Remote Console UI overlay but without harvested YAML bodies (12 such subtypes per version) — are excluded from the *property-level* diff (no body to compare). Their presence/absence is reflected in the path counts and total schema counts.

## 12.2.1.3.0 → 12.2.1.4.0

- Schemas total: 974 → 978.
- Real (non-stub) schemas added/removed: +4 / -0.
- Properties on shared real schemas: +61 added, -14 removed, 0 type-signature changes.
- Paths: +12 added, -0 removed.

**Schemas added** (4):

- `AllowList`
- `AllowListViolationAction`
- `ProducerLoadBalancingPolicy`
- `WebServiceResiliency`

**Property additions** (top schemas):

- `SingleSignOnServices` (+13): `allowedTargetHosts`, `assertionEncryptionDecryptionKeyAlias`, `assertionEncryptionDecryptionKeyPassPhrase`, `assertionEncryptionDecryptionKeyPassPhraseEncrypted`, `assertionEncryptionEnabled`, `assertionSubjectSessionTimeoutCheckEnabled`, … +7
- `Server` (+7): `RMIDeserializationMaxTimeLimit`, `cleanupOrphanedSessionsEnabled`, `sessionReplicationOnShutdownEnabled`, `transactionPrimaryChannelName`, `transactionPublicChannelName`, `transactionPublicSecureChannelName`, … +1
- `ServerDebug` (+7): `debugAllowList`, `debugEjbMdbListener`, `debugJMSClient`, `debugJMSClientStackTrace`, `debugMessagingKernelVerbose`, `debugRJVMRequestResponse`, … +1
- `ServerTemplate` (+7): `RMIDeserializationMaxTimeLimit`, `cleanupOrphanedSessionsEnabled`, `sessionReplicationOnShutdownEnabled`, `transactionPrimaryChannelName`, `transactionPublicChannelName`, `transactionPublicSecureChannelName`, … +1
- `Domain` (+2): `allowList`, `pathServices`
- `JTA` (+2): `useNonSecureAddressesForDomains`, `usePublicAddressesForRemoteDomains`
- `JTACluster` (+2): `useNonSecureAddressesForDomains`, `usePublicAddressesForRemoteDomains`
- `KernelDebug` (+2): `debugRJVMRequestResponse`, `defaultRJVMDiagMessages`
- `WebAppContainer` (+2): `rejectMaliciousPathParameters`, `restrictUserManagementAccessPatterns`
- `Cluster` (+1): `maxSecondarySelectionAttempts`
- `CoherenceCacheConfig` (+1): `runtimeCacheConfigurationUri`
- `CoherenceLoggingParamsBean` (+1): `severityLevel`

**Property removals** (top schemas):

- `KeyStore` (-7): `privateKeyStoreLocation`, `privateKeyStorePassPhrase`, `privateKeyStorePassPhraseEncrypted`, `rootCAKeyStoreLocation`, `rootCAKeyStorePassPhrase`, `rootCAKeyStorePassPhraseEncrypted`, … +1
- `SNMPAgent` (-2): `communityBasedAccessEnabled`, `communityPrefix`
- `SNMPAgentDeployment` (-2): `communityBasedAccessEnabled`, `communityPrefix`
- `JDBCStore` (-1): `oraclePiggybackCommitEnabled`
- `SNMPTrapDestination` (-1): `community`
- `TransactionLogJDBCStore` (-1): `oraclePiggybackCommitEnabled`

**Path additions** (12 total). Sample:

- `/edit/allowList`
- `/edit/partitions/{partitionName}/resourceGroups/{groupName}/pathServices`
- `/edit/partitions/{partitionName}/resourceGroups/{groupName}/pathServices/{pathServiceName}`
- `/edit/partitions/{partitionName}/webService/webServiceResiliency`
- `/edit/pathServices`
- `/edit/pathServices/{pathServiceName}`
- `/edit/resourceGroupTemplates/{templateName}/pathServices`
- `/edit/resourceGroupTemplates/{templateName}/pathServices/{pathServiceName}`
- `/edit/resourceGroups/{groupName}/pathServices`
- `/edit/resourceGroups/{groupName}/pathServices/{pathServiceName}`
- … +2 more

## 12.2.1.4.0 → 14.1.1

- Schemas total: 978 → 974.
- Real (non-stub) schemas added/removed: +3 / -6.
- Properties on shared real schemas: +16 added, -82 removed, 0 type-signature changes.
- Paths: +5 added, -1276 removed.

**Schemas added** (3):

- `Callout`
- `Http2Config`
- `WLDFBuiltinWatchConfiguration`

**Schemas removed** (6):

- `FairShareConstraintRuntime`
- `JMSInteropModule`
- `KeyStore`
- `ResourceManagerRuntime`
- `ResourceRuntime`
- `TriggerRuntime`

**Property additions** (top schemas):

- `Realm` (+3): `identityAssertionCacheEnabled`, `identityAssertionCacheTTL`, `identityAssertionDoNotCacheContextElements`
- `Cluster` (+2): `autoMigrationTableCreationDDLFile`, `autoMigrationTableCreationPolicy`
- `Domain` (+2): `callouts`, `installedSoftwareVersion`
- `JTARuntime` (+2): `DBPassiveModeState`, `transactionServiceState`
- `CoherenceClusterParamsBean` (+1): `globalSocketProvider`
- `DynamicServers` (+1): `serverNameStartingIndex`
- `JDBCConnectionPoolParamsBean` (+1): `invokeBeginEndRequest`
- `NetworkAccessPoint` (+1): `excludedCiphersuites`
- `SSL` (+1): `excludedCiphersuites`
- `WLDFServerDiagnostic` (+1): `WLDFBuiltinWatchConfiguration`
- `WebAppContainer` (+1): `http2Config`

**Property removals** (top schemas):

- `Partition` (-16): `JDBCSystemResourceOverrides`, `JTAPartition`, `adminVirtualTarget`, `coherencePartitionCacheConfigs`, `dataSourcePartition`, `foreignJNDIProviderOverrides`, … +10
- `PartitionTemplate` (-16): `JDBCSystemResourceOverrides`, `JTAPartition`, `adminVirtualTarget`, `coherencePartitionCacheConfigs`, `dataSourcePartition`, `foreignJNDIProviderOverrides`, … +10
- `Domain` (-8): `JMSInteropModules`, `partitionUriSpace`, `partitionWorkManagers`, `partitions`, `resourceGroupTemplates`, `resourceGroups`, … +2
- `PartitionRuntime` (-7): `JDBCPartitionRuntime`, `JTAPartitionRuntime`, `WLDFPartitionRuntime`, `batchJobRepositoryRuntime`, `partitionResourceMetricsRuntime`, `partitionWorkManagerRuntime`, … +1
- `DomainPartitionRuntime` (-3): `partitionID`, `partitionLifeCycleRuntime`, `partitionUserFileSystemManager`
- `DomainRuntime` (-3): `currentDomainPartitionRuntime`, `domainPartitionRuntimes`, `resourceGroupLifeCycleRuntimes`
- `ServerDebug` (-3): `debugPartitionResourceMetricsRuntime`, `diagnosticContextDebugMode`, `partitionDebugLoggingEnabled`
- `PartitionLifeCycleRuntime` (-2): `resourceGroupLifeCycleRuntimes`, `tasks`

**Path additions** (5 total). Sample:

- `/edit/callouts`
- `/edit/callouts/{calloutName}`
- `/edit/serverTemplates/{templateName}/serverDiagnosticConfig/WLDFBuiltinWatchConfiguration`
- `/edit/servers/{serverName}/serverDiagnosticConfig/WLDFBuiltinWatchConfiguration`
- `/edit/webAppContainer/http2Config`

**Path removals** (1276 total). Sample:

- `/domainRuntime/domainPartitionRuntimes`
- `/domainRuntime/domainPartitionRuntimes/{domainPartitionName}`
- `/domainRuntime/domainPartitionRuntimes/{domainPartitionName}/appRuntimeStateRuntime`
- `/domainRuntime/domainPartitionRuntimes/{domainPartitionName}/deploymentManager`
- `/domainRuntime/domainPartitionRuntimes/{domainPartitionName}/deploymentManager/appDeploymentRuntimes`
- `/domainRuntime/domainPartitionRuntimes/{domainPartitionName}/deploymentManager/appDeploymentRuntimes/{deploymentName}`
- `/domainRuntime/domainPartitionRuntimes/{domainPartitionName}/deploymentManager/appDeploymentRuntimes/{deploymentName}/createPlan`
- `/domainRuntime/domainPartitionRuntimes/{domainPartitionName}/deploymentManager/appDeploymentRuntimes/{deploymentName}/redeploy`
- `/domainRuntime/domainPartitionRuntimes/{domainPartitionName}/deploymentManager/appDeploymentRuntimes/{deploymentName}/start`
- `/domainRuntime/domainPartitionRuntimes/{domainPartitionName}/deploymentManager/appDeploymentRuntimes/{deploymentName}/stop`
- … +1266 more

## 14.1.1 → 14.1.2

- Schemas total: 974 → 946.
- Real (non-stub) schemas added/removed: +9 / -40.
- Properties on shared real schemas: +222 added, -12 removed, 8 type-signature changes.
- Paths: +36 added, -0 removed.

**Schemas added** (9):

- `DBClientDataDeploymentRuntime`
- `DBClientDataDirectory`
- `HealthScore`
- `JMSMessageManagementTaskRuntime`
- `JTARemoteDomain`
- `OIDCIdentityAsserter`
- `RemoteConsoleHelper`
- `UserDescriptionAttribute`
- `VirtualThreadEnableOption`

**Schemas removed** (40):

- `AcknowledgePolicy`
- `DefaultDeliveryMode`
- `DeliveryModeOverride`
- `Direction`
- `ExpirationPolicy`
- `ForeignJMSConnectionFactory`
- `ForeignJMSDestination`
- `ForeignJMSServer`
- `IPlanetAuthenticator`
- `JDBCPartitionRuntime`
- `JDBCPropertyOverride`
- `JDBCProxyDataSourceRuntime`
- `JDBCSystemResourceOverride`
- `JMSConnectionFactory`
- `JMSDestCommon`
- `JMSDestination`
- `JMSDestinationKey`
- `JMSDistributedDestination`
- `JMSDistributedDestinationMember`
- `JMSDistributedQueue`
- … +20 more

**Property additions** (top schemas):

- `ServerDebug` (+128): `OSGiForApps`, `debugAbbrevs`, `debugAppAnnoLookup`, `debugAppAnnoQuery`, `debugAppAnnoQueryVerbose`, `debugAppAnnoScanData`, … +122
- `Domain` (+7): `DBClientDataDirectories`, `SSLEnabled`, `healthScore`, `listenPortEnabled`, `remoteConsoleHelper`, `remoteConsoleHelperEnabled`, … +1
- `Server` (+6): `healthScore`, `logCriticalRemoteExceptionsEnabled`, `selfTuningThreadPoolSizeMax`, `selfTuningThreadPoolSizeMin`, `synchronizedSessionTimeoutEnabled`, `virtualThreadEnableOption`
- `ServerTemplate` (+6): `healthScore`, `logCriticalRemoteExceptionsEnabled`, `selfTuningThreadPoolSizeMax`, `selfTuningThreadPoolSizeMin`, `synchronizedSessionTimeoutEnabled`, `virtualThreadEnableOption`
- `MigrationTaskRuntime` (+5): `JTA`, `running`, `statusCode`, `terminal`, `waitingForUser`
- `WebAppContainer` (+5): `formAuthXFrameOptionsHeaderValue`, `sameSiteFilterCookieSettings`, `sameSiteFilterSecureChannelRequired`, `sameSiteFilterUserAgentRegEx`, `synchronizedSessionTimeoutEnabled`
- `JTA` (+4): `JTARemoteDomains`, `localDomainSecurityCacheEnabled`, `localDomainSecurityCacheTTL`, `localDomainSecurityEnabled`
- `JTACluster` (+4): `JTARemoteDomains`, `localDomainSecurityCacheEnabled`, `localDomainSecurityCacheTTL`, `localDomainSecurityEnabled`
- `Kernel` (+4): `logCriticalRemoteExceptionsEnabled`, `selfTuningThreadPoolSizeMax`, `selfTuningThreadPoolSizeMin`, `virtualThreadEnableOption`
- `SecurityConfiguration` (+4): `connectionFilterIgnoreRuleErrorsEnabled`, `crossDomainSecurityCacheEnabled`, `crossDomainSecurityCacheTTL`, `twoWayTLSRequiredForAdminClients`
- `CoherenceClusterParamsBean` (+3): `ignoreHostnameVerification`, `securedProduction`, `useVirtualThreads`
- `DefaultAuditor` (+3): `numberOfFilesLimit`, `rotationSize`, `rotationType`

**Property removals** (top schemas):

- `Server` (-3): `buzzAddress`, `buzzEnabled`, `buzzPort`
- `ServerDebug` (-3): `debugBuzzProtocol`, `debugBuzzProtocolDetails`, `debugBuzzProtocolHttp`
- `ServerTemplate` (-3): `buzzAddress`, `buzzEnabled`, `buzzPort`
- `AppDeploymentRuntime` (-1): `partitionName`
- `ApplicationRuntime` (-1): `partitionName`
- `EJBComponentRuntime` (-1): `kodoPersistenceUnitRuntimes`

**Type-signature changes on shared properties**:

- `ClientParamsBean.acknowledgePolicy`: `$ref:AcknowledgePolicy` → `string`
- `ClientParamsBean.multicastOverrunPolicy`: `$ref:OverrunPolicy` → `string`
- `CoherenceClusterParamsBean.globalSocketProvider`: `boolean` → `string`
- `DefaultDeliveryParamsBean.defaultDeliveryMode`: `$ref:DefaultDeliveryMode` → `string`
- `DeliveryFailureParamsBean.expirationPolicy`: `$ref:ExpirationPolicy` → `string`
- `DeliveryParamsOverridesBean.deliveryMode`: `$ref:DeliveryModeOverride` → `string`
- `DestinationKeyBean.keyType`: `$ref:KeyType` → `string`
- `DestinationKeyBean.sortOrder`: `$ref:Direction` → `string`

**Path additions** (36 total). Sample:

- `/domainRuntime/deploymentManager/DBClientDataDeploymentRuntimes`
- `/domainRuntime/deploymentManager/DBClientDataDeploymentRuntimes/{deploymentName}`
- `/domainRuntime/deploymentManager/DBClientDataDeploymentRuntimes/{deploymentName}/redeploy`
- `/domainRuntime/deploymentManager/DBClientDataDeploymentRuntimes/{deploymentName}/uploadAndRedeploy`
- `/domainRuntime/migratableServiceCoordinatorRuntime/migrationTaskRuntimes`
- `/domainRuntime/migratableServiceCoordinatorRuntime/migrationTaskRuntimes/{taskName}`
- `/domainRuntime/migratableServiceCoordinatorRuntime/migrationTaskRuntimes/{taskName}/subTasks`
- `/domainRuntime/migratableServiceCoordinatorRuntime/migrationTaskRuntimes/{taskName}/subTasks/{taskName2}`
- `/domainRuntime/migratableServiceCoordinatorRuntime/migrationTaskRuntimes/{taskName}/subTasks/{taskName2}/subTasks`
- `/domainRuntime/migratableServiceCoordinatorRuntime/migrationTaskRuntimes/{taskName}/subTasks/{taskName2}/subTasks/{taskName3}`
- … +26 more

> **Editorial note** — the property additions in this transition (~220) reach across many subsystems that bulk coverage now exposes: WLDF additions, work-manager tuning, virtual-thread / self-tuning kernel options, JTA accounting fields. Bulk coverage exposes these for the first time; in 4d-5 the same comparison was constrained to the 22 curated schemas and saw only 9 additions.

## 14.1.2 → 15.1.1

- Schemas total: 946 → 960.
- Real (non-stub) schemas added/removed: +14 / -0.
- Properties on shared real schemas: +29 added, -2 removed, 0 type-signature changes.
- Paths: +49 added, -2 removed.

**Schemas added** (14):

- `CertificateIssuerPlugin`
- `CertificateManagement`
- `CertificateManagementDomainRuntime`
- `CertificateManagementServerRuntime`
- `CredentialSet`
- `DomainKeystoresDomainRuntime`
- `DomainKeystoresServerRuntime`
- `EncryptedProperty`
- `PluginConfiguration`
- `PluginDeployment`
- `PluginDeploymentRuntime`
- `PluginRuntime`
- `RMIForwarding`
- `WeblogicPluginRouting`

**Property additions** (top schemas):

- `JDBCConnectionPoolParamsBean` (+6): `hangDetectionMaxTestWaitSeconds`, `refreshAvailableAfterTestFailure`, `shrinkFactorPercent`, `shrinkHistorySeconds`, `shrinkSpareCapacityPercent`, `testTimeoutSeconds`
- `Domain` (+3): `RMIForwardings`, `pluginDeployments`, `serverKeyStores`
- `ServerRuntime` (+3): `certificateManagementRuntime`, `domainKeystoresRuntime`, `pluginRuntimes`
- `Cluster` (+2): `secureClusterBroadcastEnabled`, `weblogicPluginRouting`
- `DomainRuntime` (+2): `certificateManagementRuntime`, `domainKeystoresRuntime`
- `NetworkAccessPoint` (+2): `domainKeystoresClientCertAlias`, `domainKeystoresServerCertAlias`
- `SSL` (+2): `domainKeystoresClientCertAlias`, `domainKeystoresServerCertAlias`
- `SecurityConfiguration` (+2): `certificateManagement`, `credentialSets`
- `CoherenceClusterParamsBean` (+1): `discoveryAddress`
- `CoherenceKeystoreParamsBean` (+1): `coherenceKeyRefreshPeriod`
- `DeploymentManager` (+1): `pluginDeploymentRuntimes`
- `OracleIdentityCloudIntegrator` (+1): `altClientIDTokenClaim`

**Property removals** (top schemas):

- `Server` (-1): `federationServices`
- `ServerTemplate` (-1): `federationServices`

**Path additions** (49 total). Sample:

- `/domainRuntime/certificateManagementRuntime`
- `/domainRuntime/certificateManagementRuntime/refreshMachineCertificatesAllMachines`
- `/domainRuntime/certificateManagementRuntime/refreshMachineTrustAllMachines`
- `/domainRuntime/certificateManagementRuntime/refreshServerCertificateAllServers`
- `/domainRuntime/certificateManagementRuntime/refreshServerTrustAllServers`
- `/domainRuntime/certificateManagementRuntime/rollDomainCertificateAuthority`
- `/domainRuntime/deploymentManager/pluginDeploymentRuntimes`
- `/domainRuntime/deploymentManager/pluginDeploymentRuntimes/{pluginDeploymentName}`
- `/domainRuntime/domainKeystoresRuntime`
- `/domainRuntime/domainKeystoresRuntime/addProvisionedIdentityCertificate`
- … +39 more

**Path removals** (2 total). Sample:

- `/edit/serverTemplates/{templateName}/federationServices`
- `/edit/servers/{serverName}/federationServices`
