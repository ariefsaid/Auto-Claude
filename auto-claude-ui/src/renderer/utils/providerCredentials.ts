/**
 * Provider credential utilities for multi-provider support
 *
 * CRITICAL: normalizeProviderId() must produce identical output to Python
 * normalize_provider_id() function in auto-claude/core/providers/utils.py
 *
 * Test cases that must match:
 * - "OpenAI" → "openai"
 * - "Z.ai GLM 4.7" → "zai-glm-47"
 * - "Custom Provider" → "custom-provider"
 * - "  OpenAI  " → "openai" (whitespace trimming)
 * - "Custom---Provider" → "custom-provider" (dash deduplication)
 * - "Z.ai GLM 4.7!@#" → "zai-glm-47" (special char removal)
 */

import type {
  ProviderCredential,
  ProviderCredentialsStore,
  CredentialReference,
} from '@shared/types/provider';
import type { AppSettings } from '@shared/types/settings';

/**
 * Normalize a provider name to a consistent ID format.
 *
 * CRITICAL: This function must match Python normalize_provider_id() exactly:
 * ```python
 * def normalize_provider_id(name: str) -> str:
 *     normalized = name.lower().strip().replace(' ', '-')
 *     normalized = re.sub(r'[^a-z0-9-]', '', normalized)
 *     normalized = re.sub(r'-+', '-', normalized)
 *     return normalized.strip('-')
 * ```
 *
 * @param name - The provider name to normalize (e.g., "OpenAI", "Z.ai GLM 4.7")
 * @returns Normalized provider ID (e.g., "openai", "zai-glm-47")
 */
export function normalizeProviderId(name: string): string {
  // Step 1: Convert to lowercase, trim whitespace, replace spaces with dashes
  // CRITICAL: Must match Python exactly - only replace space character, not all whitespace
  let normalized = name.toLowerCase().trim().replace(/ /g, '-');

  // Step 2: Remove all characters except a-z, 0-9, and dash
  normalized = normalized.replace(/[^a-z0-9-]/g, '');

  // Step 3: Collapse multiple consecutive dashes into a single dash
  normalized = normalized.replace(/-+/g, '-');

  // Step 4: Remove leading and trailing dashes
  return normalized.replace(/^-+|-+$/g, '');
}

/**
 * Get a global credential from app settings by provider ID
 *
 * @param settings - App settings object (may be null/undefined)
 * @param providerId - Normalized provider ID to look up
 * @returns ProviderCredential if found, undefined otherwise
 */
export function getGlobalCredential(
  settings: AppSettings | null | undefined,
  providerId: string
): ProviderCredential | undefined {
  if (!settings) {
    return undefined;
  }

  // Check if providerCredentials exists in settings
  const providerCredentials = (settings as AppSettings & { providerCredentials?: Record<string, ProviderCredential> }).providerCredentials;

  if (!providerCredentials) {
    return undefined;
  }

  const normalizedId = normalizeProviderId(providerId);
  const credential = providerCredentials[normalizedId];

  if (!credential) {
    return undefined;
  }

  // Ensure isGlobal is set to true for global credentials
  return {
    ...credential,
    isGlobal: true,
  };
}

/**
 * Check if a global credential exists for a provider
 *
 * @param settings - App settings object (may be null/undefined)
 * @param providerId - Normalized provider ID to check
 * @returns true if the credential exists, false otherwise
 */
export function hasGlobalCredential(
  settings: AppSettings | null | undefined,
  providerId: string
): boolean {
  return getGlobalCredential(settings, providerId) !== undefined;
}

/**
 * Get a list of all configured provider IDs from global settings
 *
 * @param settings - App settings object (may be null/undefined)
 * @returns Array of normalized provider IDs that have credentials configured
 */
export function getConfiguredProviders(
  settings: AppSettings | null | undefined
): string[] {
  if (!settings) {
    return [];
  }

  const providerCredentials = (settings as AppSettings & { providerCredentials?: Record<string, ProviderCredential> }).providerCredentials;

  if (!providerCredentials) {
    return [];
  }

  // Return all provider IDs that have valid credentials (at minimum an apiKey)
  return Object.entries(providerCredentials)
    .filter(([, credential]) => credential && credential.apiKey)
    .map(([id]) => id);
}

/**
 * Get the display name for a provider.
 * Falls back to title-cased normalized ID if display name not found.
 *
 * @param settings - App settings object (may be null/undefined)
 * @param providerId - Normalized provider ID
 * @returns Display name string
 */
export function getProviderDisplayName(
  settings: AppSettings | null | undefined,
  providerId: string
): string {
  const credential = getGlobalCredential(settings, providerId);

  if (credential?.displayName) {
    return credential.displayName;
  }

  // Fallback: Convert normalized ID to title case
  // e.g., "openai" → "Openai", "zai-glm-47" → "Zai Glm 47"
  return toTitleCase(providerId);
}

/**
 * Convert a normalized provider ID to title case for display
 *
 * @param normalizedId - Normalized provider ID (e.g., "openai", "zai-glm-47")
 * @returns Title-cased string (e.g., "Openai", "Zai Glm 47")
 */
export function toTitleCase(normalizedId: string): string {
  return normalizedId
    .split('-')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

/**
 * Merge project credentials with global credentials.
 * Project credentials take precedence when isGlobal is false.
 *
 * @param projectCredentials - Credential references from project .env
 * @param settings - App settings containing global credentials
 * @returns Resolved credentials store with full ProviderCredential objects
 */
export function resolveCredentials(
  projectCredentials: ProviderCredentialsStore | null | undefined,
  settings: AppSettings | null | undefined
): Record<string, ProviderCredential> {
  const resolved: Record<string, ProviderCredential> = {};

  if (!projectCredentials) {
    return resolved;
  }

  for (const [providerId, ref] of Object.entries(projectCredentials)) {
    if (ref.isGlobal) {
      // Use global credential
      const globalCred = getGlobalCredential(settings, providerId);
      if (globalCred) {
        resolved[providerId] = {
          ...globalCred,
          // Apply project-level overrides
          ...(ref.model && { defaultModel: ref.model }),
          ...(ref.baseUrl && { baseUrl: ref.baseUrl }),
        };
      }
    } else {
      // Use project-specific credential
      if (ref.apiKey) {
        resolved[providerId] = {
          provider: providerId,
          displayName: getProviderDisplayName(settings, providerId),
          apiKey: ref.apiKey,
          isGlobal: false,
          ...(ref.model && { defaultModel: ref.model }),
          ...(ref.baseUrl && { baseUrl: ref.baseUrl }),
        };
      }
    }
  }

  return resolved;
}

/**
 * Validate an API key format for known providers.
 * Returns null if valid, or an error message if invalid.
 *
 * @param providerId - Normalized provider ID
 * @param apiKey - API key to validate
 * @returns Error message if invalid, null if valid
 */
export function validateApiKeyFormat(
  providerId: string,
  apiKey: string
): string | null {
  if (!apiKey || apiKey.trim() === '') {
    return 'API key is required';
  }

  const normalizedId = normalizeProviderId(providerId);

  // Known API key patterns
  // Note: Only validate patterns for providers with well-known, documented key formats
  // Z.ai GLM and other providers may use various key formats
  const patterns: Record<string, { pattern: RegExp; message: string }> = {
    openai: {
      pattern: /^sk-/,
      message: 'OpenAI API keys should start with "sk-"',
    },
    anthropic: {
      pattern: /^sk-ant-/,
      message: 'Anthropic API keys should start with "sk-ant-"',
    },
  };

  // Check if we have a pattern for this provider
  for (const [prefix, { pattern, message }] of Object.entries(patterns)) {
    if (normalizedId.startsWith(prefix) || normalizedId === prefix) {
      if (!pattern.test(apiKey)) {
        return message;
      }
    }
  }

  // No specific pattern known - accept any non-empty string
  return null;
}

/**
 * Create a credential reference for project .env storage
 *
 * @param isGlobal - Whether to use global credential
 * @param apiKey - API key (only when isGlobal is false)
 * @param model - Optional model override
 * @param baseUrl - Optional base URL override
 * @returns CredentialReference object
 */
export function createCredentialReference(
  isGlobal: boolean,
  apiKey?: string,
  model?: string,
  baseUrl?: string
): CredentialReference {
  if (isGlobal) {
    return {
      isGlobal: true,
      ...(model && { model }),
      ...(baseUrl && { baseUrl }),
    };
  }

  return {
    isGlobal: false,
    apiKey,
    ...(model && { model }),
    ...(baseUrl && { baseUrl }),
  };
}

/**
 * Serialize provider credentials to JSON for .env file
 *
 * @param credentials - Provider credentials store
 * @returns JSON string
 */
export function serializeCredentials(
  credentials: ProviderCredentialsStore
): string {
  return JSON.stringify(credentials);
}

/**
 * Parse provider credentials from JSON string
 *
 * @param json - JSON string from .env file
 * @returns Parsed credentials store or empty object on error
 */
export function parseCredentials(json: string | null | undefined): ProviderCredentialsStore {
  if (!json || json.trim() === '') {
    return {};
  }

  try {
    const parsed = JSON.parse(json);
    if (typeof parsed !== 'object' || parsed === null) {
      return {};
    }
    return parsed as ProviderCredentialsStore;
  } catch {
    return {};
  }
}
