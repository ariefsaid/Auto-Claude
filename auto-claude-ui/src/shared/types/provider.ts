/**
 * Provider-related types for multi-provider support
 *
 * These types match the Python backend models for provider credentials,
 * agent provider configuration, and settings. The normalization logic
 * is implemented in providerCredentials.ts utility.
 */

// ============================================
// Agent Provider Types
// ============================================

/**
 * Agent provider type - the main types of agent execution backends
 * - claude_code: Official Claude Code SDK (default)
 * - opencode: Multi-provider CLI supporting 20+ LLM providers
 */
export type AgentProviderType = 'claude_code' | 'opencode';

/**
 * Provider credential configuration
 * Stores API key and configuration for a specific LLM provider (e.g., OpenAI, Anthropic)
 */
export interface ProviderCredential {
  /** Normalized provider ID (e.g., 'openai', 'zai-glm-47') */
  provider: string;
  /** Human-readable display name (e.g., 'OpenAI', 'Z.ai GLM 4.7') */
  displayName: string;
  /** API key for the provider */
  apiKey: string;
  /** Whether this credential is stored globally or per-project */
  isGlobal: boolean;
  /** Optional base URL for self-hosted or proxy endpoints */
  baseUrl?: string;
  /** Optional default model to use with this provider */
  defaultModel?: string;
  /** Optional additional metadata for provider-specific configuration */
  metadata?: Record<string, unknown>;
}

/**
 * Credential reference for project .env storage
 * When isGlobal is true, the apiKey is loaded from global settings
 */
export interface CredentialReference {
  /** Whether to use the global credential */
  isGlobal: boolean;
  /** API key (only set when isGlobal is false) */
  apiKey?: string;
  /** Optional model override */
  model?: string;
  /** Optional base URL override */
  baseUrl?: string;
}

/**
 * Provider credentials store - maps normalized provider IDs to credential references
 * Serialized as JSON in PROVIDER_CREDENTIALS environment variable
 */
export type ProviderCredentialsStore = Record<string, CredentialReference>;

// ============================================
// Agent Provider Configuration
// ============================================

/**
 * Full agent provider configuration
 * Used in ProjectEnvConfig and passed to the agent CLI
 */
export interface AgentProviderConfig {
  /** The agent provider type to use */
  agentProvider: AgentProviderType;
  /** Whether using global credentials for the selected provider */
  agentProviderIsGlobal: boolean;
  /** Provider credentials store (JSON serializable) */
  providerCredentials?: ProviderCredentialsStore;

  // OpenCode-specific fields (only used when agentProvider is 'opencode')
  /** Normalized LLM provider ID for OpenCode (e.g., 'openai', 'zai-glm') */
  opencodeProvider?: string;
  /** Model override for OpenCode (e.g., 'gpt-4o', 'glm-4.7') */
  opencodeModel?: string;
}

// ============================================
// Provider Status Types
// ============================================

/**
 * Provider configuration status
 * Used by UI to display provider health and configuration state
 */
export type ProviderStatus = 'configured' | 'not_configured' | 'error';

/**
 * Provider status response from IPC handler
 */
export interface ProviderStatusResponse {
  /** Current provider type */
  provider: AgentProviderType;
  /** Source of the configuration */
  source: 'cli_flag' | 'project_env' | 'global_settings' | 'default';
  /** Whether the provider is properly configured */
  isConfigured: boolean;
  /** Configuration errors if any */
  errors: string[];
  /** Credential sources for transparency */
  credentialSources: Record<string, 'global' | 'project' | 'missing'>;
}

/**
 * Provider validation result
 */
export interface ProviderValidationResult {
  /** Whether the configuration is valid */
  isValid: boolean;
  /** Validation errors */
  errors: string[];
  /** Validation warnings (non-blocking) */
  warnings: string[];
}

// ============================================
// Provider Info Types (for UI display)
// ============================================

/**
 * Provider information for UI dropdown and display
 */
export interface ProviderInfo {
  /** Normalized provider ID */
  id: string;
  /** Human-readable display name */
  displayName: string;
  /** Description of the provider */
  description: string;
  /** Whether this provider requires an API key */
  requiresApiKey: boolean;
  /** Default model for this provider */
  defaultModel: string;
  /** List of supported models */
  supportedModels: string[];
  /** Optional base URL hint (for self-hosted providers) */
  baseUrlHint?: string;
  /** API key format pattern for validation (e.g., 'sk-*' for OpenAI) */
  apiKeyPattern?: string;
}

/**
 * Agent provider option for dropdown selection
 */
export interface AgentProviderOption {
  /** Provider type value */
  value: AgentProviderType;
  /** Display label */
  label: string;
  /** Description of capabilities */
  description: string;
}

// ============================================
// Suggested Provider Templates
// ============================================

/**
 * Suggested provider template for quick setup
 * Pre-configured settings for common providers
 */
export interface SuggestedProviderTemplate {
  /** Display name (e.g., 'OpenAI') */
  displayName: string;
  /** Normalized ID preview */
  normalizedId: string;
  /** Default model */
  defaultModel: string;
  /** API key format pattern */
  apiKeyPattern: string;
  /** API key placeholder text */
  apiKeyPlaceholder: string;
  /** Optional base URL for the provider */
  baseUrl?: string;
}

// ============================================
// Default Values
// ============================================

/** Default agent provider when not configured */
export const DEFAULT_AGENT_PROVIDER: AgentProviderType = 'claude_code';

/** Agent provider options for UI dropdown */
export const AGENT_PROVIDER_OPTIONS: AgentProviderOption[] = [
  {
    value: 'claude_code',
    label: 'Claude Code',
    description: 'Official Claude Code SDK - recommended for most use cases',
  },
  {
    value: 'opencode',
    label: 'OpenCode',
    description: 'Multi-provider CLI supporting 20+ LLM providers (OpenAI, Gemini, etc.)',
  },
];
