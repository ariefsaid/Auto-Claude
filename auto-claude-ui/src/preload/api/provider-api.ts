import { ipcRenderer } from 'electron';
import { IPC_CHANNELS } from '../../shared/constants';
import type {
  IPCResult,
  ProviderStatusResponse,
  ProviderValidationResult,
  ProviderCredential,
  AgentProviderConfig
} from '../../shared/types';

/**
 * Provider API for multi-provider support
 * Handles provider status, validation, and credential management
 */
export interface ProviderAPI {
  /**
   * Get the current provider configuration status for a project
   * @param projectId - The project ID to check provider status for
   * @returns Provider status including configuration source and validation state
   */
  getProviderStatus: (projectId: string) => Promise<IPCResult<ProviderStatusResponse>>;

  /**
   * Validate a provider configuration before saving
   * @param config - The provider configuration to validate
   * @returns Validation result with errors and warnings
   */
  validateProviderConfig: (config: Partial<AgentProviderConfig>) => Promise<IPCResult<ProviderValidationResult>>;

  /**
   * Add provider credentials to global settings
   * @param credential - The provider credential to save globally
   * @returns Success or failure result
   */
  addProviderToGlobal: (credential: Omit<ProviderCredential, 'isGlobal'>) => Promise<IPCResult>;

  /**
   * Get list of configured providers from global settings
   * @returns Array of configured provider credentials
   */
  getConfiguredProviders: () => Promise<IPCResult<ProviderCredential[]>>;

  /**
   * Remove a provider from global settings
   * @param providerId - The normalized provider ID to remove
   * @returns Success or failure result
   */
  removeProviderFromGlobal: (providerId: string) => Promise<IPCResult>;
}

/**
 * Create the provider API for preload context
 * Maps API methods to IPC channel invocations
 */
export const createProviderAPI = (): ProviderAPI => ({
  getProviderStatus: (projectId: string): Promise<IPCResult<ProviderStatusResponse>> =>
    ipcRenderer.invoke(IPC_CHANNELS.PROVIDER_GET_STATUS, projectId),

  validateProviderConfig: (config: Partial<AgentProviderConfig>): Promise<IPCResult<ProviderValidationResult>> =>
    ipcRenderer.invoke(IPC_CHANNELS.PROVIDER_VALIDATE, config),

  addProviderToGlobal: (credential: Omit<ProviderCredential, 'isGlobal'>): Promise<IPCResult> =>
    ipcRenderer.invoke(IPC_CHANNELS.PROVIDER_ADD_TO_GLOBAL, credential),

  getConfiguredProviders: (): Promise<IPCResult<ProviderCredential[]>> =>
    ipcRenderer.invoke(IPC_CHANNELS.PROVIDER_GET_CONFIGURED),

  removeProviderFromGlobal: (providerId: string): Promise<IPCResult> =>
    ipcRenderer.invoke(IPC_CHANNELS.PROVIDER_REMOVE_GLOBAL, providerId)
});
