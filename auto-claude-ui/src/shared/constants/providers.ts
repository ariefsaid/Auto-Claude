/**
 * Provider constants for multi-provider support
 * Agent types, suggested templates, and provider configuration constants
 */

import type {
  AgentProviderType,
  AgentProviderOption,
  SuggestedProviderTemplate,
  ProviderInfo,
} from '../types/provider';

// ============================================
// Agent Provider Constants
// ============================================

/**
 * Available agent provider types
 * - claude_code: Official Claude Code SDK (default)
 * - opencode: Multi-provider CLI supporting 20+ LLM providers
 */
export const AGENT_PROVIDER_TYPES = {
  CLAUDE_CODE: 'claude_code' as AgentProviderType,
  OPENCODE: 'opencode' as AgentProviderType,
} as const;

/**
 * Default agent provider when not configured
 */
export const DEFAULT_AGENT_PROVIDER: AgentProviderType = 'claude_code';

/**
 * Agent provider options for UI dropdown selection
 */
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
] as const;

// ============================================
// Suggested Provider Templates
// ============================================

/**
 * Pre-configured templates for common LLM providers
 * Used in AddProviderDialog for quick setup
 */
export const SUGGESTED_PROVIDER_TEMPLATES: SuggestedProviderTemplate[] = [
  {
    displayName: 'OpenAI',
    normalizedId: 'openai',
    defaultModel: 'gpt-4o',
    apiKeyPattern: 'sk-*',
    apiKeyPlaceholder: 'sk-...',
  },
  {
    displayName: 'Anthropic',
    normalizedId: 'anthropic',
    defaultModel: 'claude-3-5-sonnet-20241022',
    apiKeyPattern: 'sk-ant-*',
    apiKeyPlaceholder: 'sk-ant-...',
  },
  {
    displayName: 'Z.ai GLM',
    normalizedId: 'zai-glm',
    defaultModel: 'glm-4',
    apiKeyPattern: 'zai-*',
    apiKeyPlaceholder: 'zai-...',
  },
  {
    displayName: 'OpenRouter',
    normalizedId: 'openrouter',
    defaultModel: 'anthropic/claude-3.5-sonnet',
    apiKeyPattern: 'sk-or-*',
    apiKeyPlaceholder: 'sk-or-...',
    baseUrl: 'https://openrouter.ai/api/v1',
  },
  {
    displayName: 'Google Gemini',
    normalizedId: 'google-gemini',
    defaultModel: 'gemini-1.5-pro',
    apiKeyPattern: 'AIza*',
    apiKeyPlaceholder: 'AIza...',
  },
  {
    displayName: 'Groq',
    normalizedId: 'groq',
    defaultModel: 'llama-3.1-70b-versatile',
    apiKeyPattern: 'gsk_*',
    apiKeyPlaceholder: 'gsk_...',
    baseUrl: 'https://api.groq.com/openai/v1',
  },
  {
    displayName: 'Together AI',
    normalizedId: 'together-ai',
    defaultModel: 'meta-llama/Llama-3.1-70B-Instruct-Turbo',
    apiKeyPattern: '*',
    apiKeyPlaceholder: 'Enter API key...',
    baseUrl: 'https://api.together.xyz/v1',
  },
  {
    displayName: 'Mistral AI',
    normalizedId: 'mistral-ai',
    defaultModel: 'mistral-large-latest',
    apiKeyPattern: '*',
    apiKeyPlaceholder: 'Enter API key...',
  },
  {
    displayName: 'Fireworks AI',
    normalizedId: 'fireworks-ai',
    defaultModel: 'accounts/fireworks/models/llama-v3p1-70b-instruct',
    apiKeyPattern: '*',
    apiKeyPlaceholder: 'Enter API key...',
    baseUrl: 'https://api.fireworks.ai/inference/v1',
  },
  {
    displayName: 'Ollama (Local)',
    normalizedId: 'ollama',
    defaultModel: 'llama3.1',
    apiKeyPattern: '*',
    apiKeyPlaceholder: 'ollama (or leave empty)',
    baseUrl: 'http://localhost:11434/v1',
  },
] as const;

// ============================================
// Provider Information
// ============================================

/**
 * Detailed provider information for UI display and validation
 */
export const PROVIDER_INFO: Record<string, ProviderInfo> = {
  openai: {
    id: 'openai',
    displayName: 'OpenAI',
    description: 'GPT-4, GPT-4o, and other OpenAI models',
    requiresApiKey: true,
    defaultModel: 'gpt-4o',
    supportedModels: ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'o1', 'o1-mini'],
    apiKeyPattern: '^sk-[A-Za-z0-9]+$',
  },
  anthropic: {
    id: 'anthropic',
    displayName: 'Anthropic',
    description: 'Claude 3.5, Claude 3 Opus, Sonnet, and Haiku models',
    requiresApiKey: true,
    defaultModel: 'claude-3-5-sonnet-20241022',
    supportedModels: [
      'claude-3-5-sonnet-20241022',
      'claude-3-opus-20240229',
      'claude-3-sonnet-20240229',
      'claude-3-haiku-20240307',
    ],
    apiKeyPattern: '^sk-ant-[A-Za-z0-9]+$',
  },
  'zai-glm': {
    id: 'zai-glm',
    displayName: 'Z.ai GLM',
    description: 'Z.ai GLM models for coding and analysis',
    requiresApiKey: true,
    defaultModel: 'glm-4',
    supportedModels: ['glm-4', 'glm-4-flash', 'glm-4.7'],
    apiKeyPattern: '^zai-[A-Za-z0-9]+$',
  },
  openrouter: {
    id: 'openrouter',
    displayName: 'OpenRouter',
    description: 'Access 100+ models through OpenRouter API',
    requiresApiKey: true,
    defaultModel: 'anthropic/claude-3.5-sonnet',
    supportedModels: [
      'anthropic/claude-3.5-sonnet',
      'openai/gpt-4o',
      'google/gemini-pro-1.5',
      'meta-llama/llama-3.1-70b-instruct',
    ],
    baseUrlHint: 'https://openrouter.ai/api/v1',
    apiKeyPattern: '^sk-or-[A-Za-z0-9]+$',
  },
  'google-gemini': {
    id: 'google-gemini',
    displayName: 'Google Gemini',
    description: 'Google Gemini Pro and Flash models',
    requiresApiKey: true,
    defaultModel: 'gemini-1.5-pro',
    supportedModels: ['gemini-1.5-pro', 'gemini-1.5-flash', 'gemini-2.0-flash-exp'],
    apiKeyPattern: '^AIza[A-Za-z0-9-_]+$',
  },
  groq: {
    id: 'groq',
    displayName: 'Groq',
    description: 'Fast inference with Llama and Mixtral models',
    requiresApiKey: true,
    defaultModel: 'llama-3.1-70b-versatile',
    supportedModels: [
      'llama-3.1-70b-versatile',
      'llama-3.1-8b-instant',
      'mixtral-8x7b-32768',
      'gemma2-9b-it',
    ],
    baseUrlHint: 'https://api.groq.com/openai/v1',
    apiKeyPattern: '^gsk_[A-Za-z0-9]+$',
  },
  'together-ai': {
    id: 'together-ai',
    displayName: 'Together AI',
    description: 'Open-source models with fast inference',
    requiresApiKey: true,
    defaultModel: 'meta-llama/Llama-3.1-70B-Instruct-Turbo',
    supportedModels: [
      'meta-llama/Llama-3.1-70B-Instruct-Turbo',
      'meta-llama/Llama-3.1-8B-Instruct-Turbo',
      'mistralai/Mixtral-8x7B-Instruct-v0.1',
    ],
    baseUrlHint: 'https://api.together.xyz/v1',
  },
  'mistral-ai': {
    id: 'mistral-ai',
    displayName: 'Mistral AI',
    description: 'Mistral Large and Mistral models',
    requiresApiKey: true,
    defaultModel: 'mistral-large-latest',
    supportedModels: ['mistral-large-latest', 'mistral-medium-latest', 'mistral-small-latest'],
  },
  'fireworks-ai': {
    id: 'fireworks-ai',
    displayName: 'Fireworks AI',
    description: 'Fast inference for open-source models',
    requiresApiKey: true,
    defaultModel: 'accounts/fireworks/models/llama-v3p1-70b-instruct',
    supportedModels: [
      'accounts/fireworks/models/llama-v3p1-70b-instruct',
      'accounts/fireworks/models/llama-v3p1-8b-instruct',
      'accounts/fireworks/models/mixtral-8x7b-instruct',
    ],
    baseUrlHint: 'https://api.fireworks.ai/inference/v1',
  },
  ollama: {
    id: 'ollama',
    displayName: 'Ollama (Local)',
    description: 'Run models locally with Ollama',
    requiresApiKey: false,
    defaultModel: 'llama3.1',
    supportedModels: ['llama3.1', 'llama3.1:70b', 'codellama', 'mistral', 'mixtral'],
    baseUrlHint: 'http://localhost:11434/v1',
  },
} as const;

// ============================================
// Credential Source Labels
// ============================================

/**
 * Labels for credential source display in UI
 */
export const CREDENTIAL_SOURCE_LABELS = {
  global: 'Using Global',
  project: 'Project Override',
  missing: 'Not Configured',
} as const;

/**
 * Badge variants for credential source display
 */
export const CREDENTIAL_SOURCE_VARIANTS = {
  global: 'success' as const,
  project: 'default' as const,
  missing: 'warning' as const,
} as const;

// ============================================
// Provider Status Labels
// ============================================

/**
 * Labels for provider status display in UI
 */
export const PROVIDER_STATUS_LABELS = {
  configured: 'Configured',
  not_configured: 'Not Configured',
  error: 'Error',
} as const;

/**
 * Badge variants for provider status display
 */
export const PROVIDER_STATUS_VARIANTS = {
  configured: 'success' as const,
  not_configured: 'warning' as const,
  error: 'destructive' as const,
} as const;

// ============================================
// Environment Variable Names
// ============================================

/**
 * Environment variable names for provider configuration
 * Used in .env file generation and parsing
 */
export const PROVIDER_ENV_VARS = {
  /** Agent provider type (claude_code | opencode) */
  AGENT_PROVIDER: 'AGENT_PROVIDER',
  /** Whether using global credentials */
  AGENT_PROVIDER_IS_GLOBAL: 'AGENT_PROVIDER_IS_GLOBAL',
  /** JSON-serialized provider credentials */
  PROVIDER_CREDENTIALS: 'PROVIDER_CREDENTIALS',
  /** OpenCode LLM provider ID */
  OPENCODE_PROVIDER: 'OPENCODE_PROVIDER',
  /** OpenCode model override */
  OPENCODE_MODEL: 'OPENCODE_MODEL',

  // Legacy fields (backward compatibility)
  /** Legacy Claude OAuth token */
  CLAUDE_CODE_OAUTH_TOKEN: 'CLAUDE_CODE_OAUTH_TOKEN',
  /** Legacy global token flag */
  CLAUDE_TOKEN_IS_GLOBAL: 'CLAUDE_TOKEN_IS_GLOBAL',
} as const;
