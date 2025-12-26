import { ipcMain, app } from 'electron';
import type { BrowserWindow } from 'electron';
import { existsSync, readFileSync, writeFileSync } from 'fs';
import path from 'path';
import { IPC_CHANNELS, DEFAULT_APP_SETTINGS } from '../../shared/constants';
import type {
  IPCResult,
  AppSettings,
  ProviderCredential,
  ProviderStatusResponse,
  ProviderValidationResult,
  AgentProviderConfig,
} from '../../shared/types';
import { projectStore } from '../project-store';
import { parseEnvFile } from './utils';

/**
 * Normalize a provider name to a consistent ID format.
 * Must match Python normalize_provider_id() exactly.
 *
 * @param name - The provider name to normalize
 * @returns Normalized provider ID
 */
function normalizeProviderId(name: string): string {
  // Step 1: Convert to lowercase, trim whitespace, replace spaces with dashes
  let normalized = name.toLowerCase().trim().replace(/ /g, '-');

  // Step 2: Remove all characters except a-z, 0-9, and dash
  normalized = normalized.replace(/[^a-z0-9-]/g, '');

  // Step 3: Collapse multiple consecutive dashes into a single dash
  normalized = normalized.replace(/-+/g, '-');

  // Step 4: Remove leading and trailing dashes
  return normalized.replace(/^-+|-+$/g, '');
}

/**
 * Register all provider-related IPC handlers
 */
export function registerProviderHandlers(
  _getMainWindow: () => BrowserWindow | null
): void {
  // ============================================
  // Provider Configuration Operations
  // ============================================

  // Get settings file path
  const settingsPath = path.join(app.getPath('userData'), 'settings.json');

  /**
   * Load global settings
   */
  const loadGlobalSettings = (): AppSettings => {
    let settings: AppSettings = { ...DEFAULT_APP_SETTINGS };
    if (existsSync(settingsPath)) {
      try {
        const content = readFileSync(settingsPath, 'utf-8');
        settings = { ...settings, ...JSON.parse(content) };
      } catch {
        // Use defaults
      }
    }
    return settings;
  };

  /**
   * Save global settings
   */
  const saveGlobalSettings = (settings: AppSettings): void => {
    writeFileSync(settingsPath, JSON.stringify(settings, null, 2));
  };

  /**
   * Get provider status for a project
   *
   * Returns the current provider configuration status including:
   * - provider: Current provider type (claude_code or opencode)
   * - source: Where the configuration came from
   * - isConfigured: Whether the provider is properly configured
   * - errors: List of configuration errors
   * - credentialSources: Map of provider IDs to their credential source
   */
  ipcMain.handle(
    IPC_CHANNELS.PROVIDER_GET_STATUS,
    async (_, projectId: string): Promise<IPCResult<ProviderStatusResponse>> => {
      try {
        const project = projectStore.getProject(projectId);
        if (!project) {
          return { success: false, error: 'Project not found' };
        }

        const globalSettings = loadGlobalSettings();
        const errors: string[] = [];
        const credentialSources: Record<string, 'global' | 'project' | 'missing'> = {};

        // Load project environment
        let projectEnv: Record<string, string> = {};
        if (project.autoBuildPath) {
          const envPath = path.join(project.path, project.autoBuildPath, '.env');
          if (existsSync(envPath)) {
            try {
              const content = readFileSync(envPath, 'utf-8');
              projectEnv = parseEnvFile(content);
            } catch {
              // Continue with empty env
            }
          }
        }

        // Determine provider and source (priority: project_env > global_settings > default)
        let agentProvider: 'claude_code' | 'opencode' = 'claude_code';
        let source: 'cli_flag' | 'project_env' | 'global_settings' | 'default' = 'default';

        const envProvider = projectEnv['AGENT_PROVIDER']?.trim().toLowerCase();
        if (envProvider === 'claude_code' || envProvider === 'opencode') {
          agentProvider = envProvider;
          source = 'project_env';
        } else if (globalSettings.globalDefaultProvider) {
          const globalProvider = globalSettings.globalDefaultProvider;
          if (globalProvider === 'claude_code' || globalProvider === 'opencode') {
            agentProvider = globalProvider;
            source = 'global_settings';
          }
        }

        // Validate configuration
        let isConfigured = true;

        if (agentProvider === 'opencode') {
          // OpenCode requires provider selection and credentials
          const opencodeProvider = projectEnv['OPENCODE_PROVIDER'] || globalSettings.globalOpencodeProvider || '';

          if (!opencodeProvider) {
            isConfigured = false;
            errors.push('OpenCode provider not selected');
          } else {
            const normalizedProvider = normalizeProviderId(opencodeProvider);

            // Parse provider credentials from project env
            let providerCredentials: Record<string, { isGlobal?: boolean; apiKey?: string }> = {};
            try {
              const credJson = projectEnv['PROVIDER_CREDENTIALS'];
              if (credJson) {
                providerCredentials = JSON.parse(credJson);
              }
            } catch {
              // Continue with empty credentials
            }

            const credRef = providerCredentials[normalizedProvider] || {};

            if (credRef.isGlobal) {
              // Using global credential
              const globalCred = globalSettings.providerCredentials?.[normalizedProvider];
              if (globalCred?.apiKey) {
                credentialSources[normalizedProvider] = 'global';
              } else {
                credentialSources[normalizedProvider] = 'missing';
                isConfigured = false;
                errors.push(`Global credential '${normalizedProvider}' not found`);
              }
            } else if (credRef.apiKey) {
              // Project-specific credential
              credentialSources[normalizedProvider] = 'project';
            } else {
              // No credential configured
              credentialSources[normalizedProvider] = 'missing';
              isConfigured = false;
              errors.push(`No credential configured for provider '${normalizedProvider}'`);
            }
          }
        } else if (agentProvider === 'claude_code') {
          // Claude Code requires OAuth token
          const oauthToken = projectEnv['CLAUDE_CODE_OAUTH_TOKEN'];
          const isGlobal = projectEnv['CLAUDE_TOKEN_IS_GLOBAL']?.toLowerCase() === 'true';

          if (!oauthToken) {
            if (isGlobal && globalSettings.globalClaudeOAuthToken) {
              credentialSources['claude_code'] = 'global';
            } else if (isGlobal) {
              credentialSources['claude_code'] = 'missing';
              isConfigured = false;
              errors.push('Global Claude OAuth token not found');
            } else {
              credentialSources['claude_code'] = 'missing';
              isConfigured = false;
              errors.push("Claude OAuth token not configured. Run 'claude setup-token' to authenticate.");
            }
          } else {
            credentialSources['claude_code'] = isGlobal ? 'global' : 'project';
          }
        }

        return {
          success: true,
          data: {
            provider: agentProvider,
            source,
            isConfigured,
            errors,
            credentialSources,
          },
        };
      } catch (error) {
        return {
          success: false,
          error: error instanceof Error ? error.message : 'Failed to get provider status',
        };
      }
    }
  );

  /**
   * Validate a provider configuration before saving
   *
   * Checks that the configuration is complete and valid:
   * - Agent provider type is valid
   * - OpenCode provider is specified when using opencode
   * - Credentials are available (global or project-specific)
   */
  ipcMain.handle(
    IPC_CHANNELS.PROVIDER_VALIDATE,
    async (_, config: AgentProviderConfig): Promise<IPCResult<ProviderValidationResult>> => {
      try {
        const errors: string[] = [];
        const warnings: string[] = [];
        const globalSettings = loadGlobalSettings();

        // Validate agent provider type
        const agentProvider = config.agentProvider;
        if (agentProvider !== 'claude_code' && agentProvider !== 'opencode') {
          errors.push(`Invalid agent provider: '${agentProvider}'. Must be 'claude_code' or 'opencode'`);
          return {
            success: true,
            data: { isValid: false, errors, warnings },
          };
        }

        if (agentProvider === 'opencode') {
          // Validate OpenCode configuration
          const opencodeProvider = config.opencodeProvider;
          if (!opencodeProvider) {
            errors.push("OpenCode provider is required when using 'opencode' agent");
          } else {
            const normalized = normalizeProviderId(opencodeProvider);
            if (!normalized) {
              errors.push(`Invalid OpenCode provider ID: '${opencodeProvider}'`);
            } else {
              // Check credentials
              const credRef = config.providerCredentials?.[normalized];

              if (config.agentProviderIsGlobal || credRef?.isGlobal) {
                // Will use global credential
                const globalCred = globalSettings.providerCredentials?.[normalized];
                if (!globalCred?.apiKey) {
                  errors.push(`Global credential for '${normalized}' not found`);
                }
              } else {
                // Project-specific credential required
                if (!credRef?.apiKey) {
                  errors.push(`API key required for provider '${normalized}'`);
                } else {
                  // Validate API key format for known providers
                  const keyError = validateApiKeyFormat(normalized, credRef.apiKey);
                  if (keyError) {
                    warnings.push(keyError);
                  }
                }
              }
            }
          }

          // Validate OpenCode model (optional but warn if unusual)
          const opencodeModel = config.opencodeModel;
          if (opencodeModel && !/^[a-zA-Z0-9._/-]+$/.test(opencodeModel)) {
            warnings.push(`Unusual model name format: '${opencodeModel}'`);
          }
        }

        // Check for conflicting configurations
        if (agentProvider === 'opencode' && config.providerCredentials) {
          for (const [providerId, credRef] of Object.entries(config.providerCredentials)) {
            if (credRef.isGlobal && credRef.apiKey) {
              warnings.push(
                `Provider '${providerId}' has both isGlobal=true and an apiKey. ` +
                'The apiKey will be ignored in favor of the global credential.'
              );
            }
          }
        }

        return {
          success: true,
          data: {
            isValid: errors.length === 0,
            errors,
            warnings,
          },
        };
      } catch (error) {
        return {
          success: false,
          error: error instanceof Error ? error.message : 'Failed to validate provider config',
        };
      }
    }
  );

  /**
   * Add a provider credential to global settings
   *
   * Saves the credential to ~/.config/auto-claude-ui/settings.json
   * so it can be used across all projects
   */
  ipcMain.handle(
    IPC_CHANNELS.PROVIDER_ADD_TO_GLOBAL,
    async (_, credential: ProviderCredential): Promise<IPCResult> => {
      try {
        // Validate the credential
        if (!credential.provider) {
          return { success: false, error: 'Provider ID is required' };
        }

        const normalizedId = normalizeProviderId(credential.provider);
        if (!normalizedId) {
          return { success: false, error: 'Invalid provider ID' };
        }

        if (!credential.apiKey && normalizedId !== 'ollama') {
          return { success: false, error: 'API key is required' };
        }

        // Load current settings
        const settings = loadGlobalSettings();

        // Initialize providerCredentials if it doesn't exist
        if (!settings.providerCredentials) {
          settings.providerCredentials = {};
        }

        // Add or update the credential
        settings.providerCredentials[normalizedId] = {
          provider: normalizedId,
          displayName: credential.displayName || toTitleCase(normalizedId),
          apiKey: credential.apiKey,
          isGlobal: true,
          ...(credential.baseUrl && { baseUrl: credential.baseUrl }),
          ...(credential.defaultModel && { defaultModel: credential.defaultModel }),
          ...(credential.metadata && { metadata: credential.metadata }),
        };

        // Save settings
        saveGlobalSettings(settings);

        return { success: true };
      } catch (error) {
        return {
          success: false,
          error: error instanceof Error ? error.message : 'Failed to add provider to global settings',
        };
      }
    }
  );

  /**
   * Get list of configured providers from global settings
   */
  ipcMain.handle(
    IPC_CHANNELS.PROVIDER_GET_CONFIGURED,
    async (): Promise<IPCResult<ProviderCredential[]>> => {
      try {
        const settings = loadGlobalSettings();
        const providerCredentials = settings.providerCredentials || {};

        const providers: ProviderCredential[] = Object.entries(providerCredentials)
          .filter(([, cred]) => cred && cred.apiKey)
          .map(([id, cred]) => ({
            provider: id,
            displayName: cred.displayName || toTitleCase(id),
            apiKey: cred.apiKey,
            isGlobal: true,
            ...(cred.baseUrl && { baseUrl: cred.baseUrl }),
            ...(cred.defaultModel && { defaultModel: cred.defaultModel }),
            ...(cred.metadata && { metadata: cred.metadata }),
          }));

        return { success: true, data: providers };
      } catch (error) {
        return {
          success: false,
          error: error instanceof Error ? error.message : 'Failed to get configured providers',
        };
      }
    }
  );

  /**
   * Remove a provider from global settings
   */
  ipcMain.handle(
    IPC_CHANNELS.PROVIDER_REMOVE_GLOBAL,
    async (_, providerId: string): Promise<IPCResult> => {
      try {
        const normalizedId = normalizeProviderId(providerId);
        if (!normalizedId) {
          return { success: false, error: 'Invalid provider ID' };
        }

        // Load current settings
        const settings = loadGlobalSettings();

        if (!settings.providerCredentials?.[normalizedId]) {
          return { success: false, error: `Provider '${normalizedId}' not found in global settings` };
        }

        // Remove the credential
        delete settings.providerCredentials[normalizedId];

        // Save settings
        saveGlobalSettings(settings);

        return { success: true };
      } catch (error) {
        return {
          success: false,
          error: error instanceof Error ? error.message : 'Failed to remove provider from global settings',
        };
      }
    }
  );
}

/**
 * Convert a normalized provider ID to title case for display
 *
 * @param normalizedId - Normalized provider ID (e.g., "openai", "zai-glm-47")
 * @returns Title-cased string (e.g., "Openai", "Zai Glm 47")
 */
function toTitleCase(normalizedId: string): string {
  return normalizedId
    .split('-')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

/**
 * Validate an API key format for known providers.
 * Returns null if valid, or an error message if invalid.
 *
 * @param providerId - Normalized provider ID
 * @param apiKey - API key to validate
 * @returns Error message if invalid, null if valid
 */
function validateApiKeyFormat(providerId: string, apiKey: string): string | null {
  if (!apiKey || apiKey.trim() === '') {
    return 'API key is required';
  }

  // Known API key patterns
  const patterns: Record<string, { pattern: RegExp; message: string }> = {
    openai: {
      pattern: /^sk-/,
      message: 'OpenAI API keys should start with "sk-"',
    },
    anthropic: {
      pattern: /^sk-ant-/,
      message: 'Anthropic API keys should start with "sk-ant-"',
    },
    'zai-glm': {
      pattern: /^zai-/,
      message: 'Z.ai API keys should start with "zai-"',
    },
  };

  // Check if we have a pattern for this provider
  for (const [prefix, { pattern, message }] of Object.entries(patterns)) {
    if (providerId.startsWith(prefix) || providerId === prefix) {
      if (!pattern.test(apiKey)) {
        return message;
      }
    }
  }

  // No specific pattern known - accept any non-empty string
  return null;
}
