import type { Project, ProjectSettings as ProjectSettingsType, AutoBuildVersionInfo, ProjectEnvConfig, LinearSyncStatus, GitHubSyncStatus, AppSettings } from '../../../../shared/types';
import { SettingsSection } from '../SettingsSection';
import { GeneralSettings } from '../../project-settings/GeneralSettings';
import { EnvironmentSettings } from '../../project-settings/EnvironmentSettings';
import { SecuritySettings } from '../../project-settings/SecuritySettings';
import { LinearIntegration } from '../integrations/LinearIntegration';
import { GitHubIntegration } from '../integrations/GitHubIntegration';
import { InitializationGuard } from '../common/InitializationGuard';
import { AgentProviderSection } from '../AgentProviderSection';
import type { ProjectSettingsSection } from '../ProjectSettingsContent';

interface SectionRouterProps {
  activeSection: ProjectSettingsSection;
  project: Project;
  settings: ProjectSettingsType;
  setSettings: React.Dispatch<React.SetStateAction<ProjectSettingsType>>;
  versionInfo: AutoBuildVersionInfo | null;
  isCheckingVersion: boolean;
  isUpdating: boolean;
  envConfig: ProjectEnvConfig | null;
  isLoadingEnv: boolean;
  envError: string | null;
  updateEnvConfig: (updates: Partial<ProjectEnvConfig>) => void;
  showClaudeToken: boolean;
  setShowClaudeToken: React.Dispatch<React.SetStateAction<boolean>>;
  showLinearKey: boolean;
  setShowLinearKey: React.Dispatch<React.SetStateAction<boolean>>;
  showOpenAIKey: boolean;
  setShowOpenAIKey: React.Dispatch<React.SetStateAction<boolean>>;
  showGitHubToken: boolean;
  setShowGitHubToken: React.Dispatch<React.SetStateAction<boolean>>;
  gitHubConnectionStatus: GitHubSyncStatus | null;
  isCheckingGitHub: boolean;
  isCheckingClaudeAuth: boolean;
  claudeAuthStatus: 'checking' | 'authenticated' | 'not_authenticated' | 'error';
  linearConnectionStatus: LinearSyncStatus | null;
  isCheckingLinear: boolean;
  handleInitialize: () => Promise<void>;
  handleUpdate: () => Promise<void>;
  handleClaudeSetup: () => Promise<void>;
  onOpenLinearImport: () => void;
  appSettings?: AppSettings | null;
  onAddGlobalProvider?: (credential: import('@shared/types/provider').ProviderCredential) => void;
}

/**
 * Routes to the appropriate settings section based on activeSection.
 * Handles initialization guards and section-specific configurations.
 */
export function SectionRouter({
  activeSection,
  project,
  settings,
  setSettings,
  versionInfo,
  isCheckingVersion,
  isUpdating,
  envConfig,
  isLoadingEnv,
  envError,
  updateEnvConfig,
  showClaudeToken,
  setShowClaudeToken,
  showLinearKey,
  setShowLinearKey,
  showOpenAIKey,
  setShowOpenAIKey,
  showGitHubToken,
  setShowGitHubToken,
  gitHubConnectionStatus,
  isCheckingGitHub,
  isCheckingClaudeAuth,
  claudeAuthStatus,
  linearConnectionStatus,
  isCheckingLinear,
  handleInitialize,
  handleUpdate,
  handleClaudeSetup,
  onOpenLinearImport,
  appSettings,
  onAddGlobalProvider
}: SectionRouterProps) {
  switch (activeSection) {
    case 'general':
      return (
        <SettingsSection
          title="General"
          description={`Configure Auto-Build, agent model, and notifications for ${project.name}`}
        >
          <GeneralSettings
            project={project}
            settings={settings}
            setSettings={setSettings}
            versionInfo={versionInfo}
            isCheckingVersion={isCheckingVersion}
            isUpdating={isUpdating}
            handleInitialize={handleInitialize}
            handleUpdate={handleUpdate}
          />
        </SettingsSection>
      );

    case 'claude':
      return (
        <SettingsSection
          title="Claude Authentication"
          description="Configure Claude CLI authentication for this project"
        >
          <InitializationGuard
            initialized={!!project.autoBuildPath}
            title="Claude Authentication"
            description="Configure Claude CLI authentication"
          >
            <EnvironmentSettings
              envConfig={envConfig}
              isLoadingEnv={isLoadingEnv}
              envError={envError}
              updateEnvConfig={updateEnvConfig}
              isCheckingClaudeAuth={isCheckingClaudeAuth}
              claudeAuthStatus={claudeAuthStatus}
              handleClaudeSetup={handleClaudeSetup}
              showClaudeToken={showClaudeToken}
              setShowClaudeToken={setShowClaudeToken}
              expanded={true}
              onToggle={() => {}}
            />
          </InitializationGuard>
        </SettingsSection>
      );

    case 'provider':
      return (
        <SettingsSection
          title="Agent Provider"
          description="Configure which AI provider to use for coding tasks"
        >
          <InitializationGuard
            initialized={!!project.autoBuildPath}
            title="Agent Provider"
            description="Select and configure your AI provider"
          >
            <AgentProviderSection
              agentProvider={envConfig?.agentProvider || 'claude_code'}
              onAgentProviderChange={(provider) =>
                updateEnvConfig({ agentProvider: provider })
              }
              isGlobal={envConfig?.agentProviderIsGlobal ?? false}
              onGlobalChange={(isGlobal) =>
                updateEnvConfig({ agentProviderIsGlobal: isGlobal })
              }
              opencodeProvider={envConfig?.opencodeProvider}
              onOpencodeProviderChange={(provider) =>
                updateEnvConfig({ opencodeProvider: provider })
              }
              opencodeModel={envConfig?.opencodeModel}
              onOpencodeModelChange={(model) =>
                updateEnvConfig({ opencodeModel: model })
              }
              providerCredentials={envConfig?.providerCredentials}
              onProviderCredentialsChange={(credentials) =>
                updateEnvConfig({ providerCredentials: credentials })
              }
              appSettings={appSettings}
              onAddGlobalProvider={onAddGlobalProvider}
            />
          </InitializationGuard>
        </SettingsSection>
      );

    case 'linear':
      return (
        <SettingsSection
          title="Linear Integration"
          description="Connect to Linear for issue tracking and task import"
        >
          <InitializationGuard
            initialized={!!project.autoBuildPath}
            title="Linear Integration"
            description="Sync with Linear for issue tracking"
          >
            <LinearIntegration
              envConfig={envConfig}
              updateEnvConfig={updateEnvConfig}
              showLinearKey={showLinearKey}
              setShowLinearKey={setShowLinearKey}
              linearConnectionStatus={linearConnectionStatus}
              isCheckingLinear={isCheckingLinear}
              onOpenLinearImport={onOpenLinearImport}
            />
          </InitializationGuard>
        </SettingsSection>
      );

    case 'github':
      return (
        <SettingsSection
          title="GitHub Integration"
          description="Connect to GitHub for issue tracking"
        >
          <InitializationGuard
            initialized={!!project.autoBuildPath}
            title="GitHub Integration"
            description="Sync with GitHub Issues"
          >
            <GitHubIntegration
              envConfig={envConfig}
              updateEnvConfig={updateEnvConfig}
              showGitHubToken={showGitHubToken}
              setShowGitHubToken={setShowGitHubToken}
              gitHubConnectionStatus={gitHubConnectionStatus}
              isCheckingGitHub={isCheckingGitHub}
              projectPath={project.path}
            />
          </InitializationGuard>
        </SettingsSection>
      );

    case 'memory':
      return (
        <SettingsSection
          title="Memory"
          description="Configure persistent cross-session memory for agents"
        >
          <InitializationGuard
            initialized={!!project.autoBuildPath}
            title="Memory"
            description="Configure persistent memory"
          >
            <SecuritySettings
              envConfig={envConfig}
              settings={settings}
              setSettings={setSettings}
              updateEnvConfig={updateEnvConfig}
              showOpenAIKey={showOpenAIKey}
              setShowOpenAIKey={setShowOpenAIKey}
              expanded={true}
              onToggle={() => {}}
            />
          </InitializationGuard>
        </SettingsSection>
      );

    default:
      return null;
  }
}
