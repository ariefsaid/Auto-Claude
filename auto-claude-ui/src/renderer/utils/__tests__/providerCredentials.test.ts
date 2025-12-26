/**
 * Unit tests for provider credential utilities
 *
 * CRITICAL: normalizeProviderId tests verify parity with Python normalize_provider_id()
 * These test cases MUST match the Python implementation exactly.
 */
import { describe, it, expect } from 'vitest';
import {
  normalizeProviderId,
  getGlobalCredential,
  hasGlobalCredential,
  getConfiguredProviders,
  getProviderDisplayName,
  toTitleCase,
  resolveCredentials,
  validateApiKeyFormat,
  createCredentialReference,
  serializeCredentials,
  parseCredentials,
} from '../providerCredentials';
import type { AppSettings } from '@shared/types/settings';
import type { ProviderCredential, ProviderCredentialsStore } from '@shared/types/provider';

// Extended AppSettings type with providerCredentials
type ExtendedAppSettings = AppSettings & {
  providerCredentials?: Record<string, ProviderCredential>;
};

// Mock settings factory
function createMockSettings(
  credentials?: Record<string, ProviderCredential>
): ExtendedAppSettings {
  return {
    theme: 'dark',
    defaultModel: 'sonnet',
    agentFramework: 'claude',
    autoUpdateAutoBuild: false,
    autoNameTerminals: true,
    notifications: {
      onTaskComplete: true,
      onTaskFailed: true,
      onReviewNeeded: false,
      sound: false,
    },
    providerCredentials: credentials,
  };
}

describe('normalizeProviderId', () => {
  describe('basic normalization', () => {
    it('should lowercase simple provider names', () => {
      expect(normalizeProviderId('OpenAI')).toBe('openai');
      expect(normalizeProviderId('OPENAI')).toBe('openai');
      expect(normalizeProviderId('Anthropic')).toBe('anthropic');
    });

    it('should handle spaces by replacing with dashes', () => {
      expect(normalizeProviderId('Custom Provider')).toBe('custom-provider');
      expect(normalizeProviderId('My Custom Provider')).toBe('my-custom-provider');
    });

    it('should trim leading and trailing whitespace', () => {
      expect(normalizeProviderId('  OpenAI  ')).toBe('openai');
      expect(normalizeProviderId('\tOpenAI\n')).toBe('openai');
      expect(normalizeProviderId('   Custom Provider   ')).toBe('custom-provider');
    });
  });

  describe('special character handling', () => {
    it('should handle dots and special characters - Z.ai GLM case', () => {
      // CRITICAL: This must match Python exactly
      expect(normalizeProviderId('Z.ai GLM 4.7')).toBe('zai-glm-47');
    });

    it('should remove special characters completely', () => {
      expect(normalizeProviderId('Z.ai GLM 4.7!@#')).toBe('zai-glm-47');
      expect(normalizeProviderId('Provider@#$%^&*()')).toBe('provider');
      expect(normalizeProviderId('Test!Provider')).toBe('testprovider');
    });

    it('should handle underscores and other separators', () => {
      expect(normalizeProviderId('my_provider')).toBe('myprovider');
      expect(normalizeProviderId('my.provider')).toBe('myprovider');
    });
  });

  describe('dash handling', () => {
    it('should collapse multiple dashes into single dash', () => {
      expect(normalizeProviderId('Custom---Provider')).toBe('custom-provider');
      expect(normalizeProviderId('a--b---c----d')).toBe('a-b-c-d');
    });

    it('should remove leading dashes', () => {
      expect(normalizeProviderId('---provider')).toBe('provider');
      expect(normalizeProviderId('-openai')).toBe('openai');
    });

    it('should remove trailing dashes', () => {
      expect(normalizeProviderId('provider---')).toBe('provider');
      expect(normalizeProviderId('openai-')).toBe('openai');
    });

    it('should handle dashes at both ends', () => {
      expect(normalizeProviderId('---provider---')).toBe('provider');
      expect(normalizeProviderId('--custom--provider--')).toBe('custom-provider');
    });
  });

  describe('edge cases', () => {
    it('should handle empty string', () => {
      expect(normalizeProviderId('')).toBe('');
    });

    it('should handle string with only special characters', () => {
      expect(normalizeProviderId('!@#$%')).toBe('');
    });

    it('should handle string with only spaces', () => {
      expect(normalizeProviderId('   ')).toBe('');
    });

    it('should handle numbers', () => {
      expect(normalizeProviderId('gpt4')).toBe('gpt4');
      expect(normalizeProviderId('Claude 3.5')).toBe('claude-35');
    });

    it('should preserve existing lowercase', () => {
      expect(normalizeProviderId('openai')).toBe('openai');
    });

    it('should handle mixed case with numbers', () => {
      expect(normalizeProviderId('GPT-4o')).toBe('gpt-4o');
    });
  });

  describe('Python parity test cases', () => {
    // These are the exact test cases from the spec that must match Python
    it('should match Python: "OpenAI" → "openai"', () => {
      expect(normalizeProviderId('OpenAI')).toBe('openai');
    });

    it('should match Python: "Z.ai GLM 4.7" → "zai-glm-47"', () => {
      expect(normalizeProviderId('Z.ai GLM 4.7')).toBe('zai-glm-47');
    });

    it('should match Python: "Custom Provider" → "custom-provider"', () => {
      expect(normalizeProviderId('Custom Provider')).toBe('custom-provider');
    });

    it('should match Python: "  Custom---Provider!  " → "custom-provider"', () => {
      expect(normalizeProviderId('  Custom---Provider!  ')).toBe('custom-provider');
    });
  });
});

describe('getGlobalCredential', () => {
  it('should return undefined for null settings', () => {
    expect(getGlobalCredential(null, 'openai')).toBeUndefined();
  });

  it('should return undefined for undefined settings', () => {
    expect(getGlobalCredential(undefined, 'openai')).toBeUndefined();
  });

  it('should return undefined when providerCredentials is missing', () => {
    const settings = createMockSettings();
    delete settings.providerCredentials;
    expect(getGlobalCredential(settings, 'openai')).toBeUndefined();
  });

  it('should return undefined for non-existent provider', () => {
    const settings = createMockSettings({
      openai: {
        provider: 'openai',
        displayName: 'OpenAI',
        apiKey: 'sk-test',
        isGlobal: true,
      },
    });
    expect(getGlobalCredential(settings, 'anthropic')).toBeUndefined();
  });

  it('should return credential for existing provider', () => {
    const settings = createMockSettings({
      openai: {
        provider: 'openai',
        displayName: 'OpenAI',
        apiKey: 'sk-test123',
        isGlobal: true,
      },
    });
    const credential = getGlobalCredential(settings, 'openai');
    expect(credential).toBeDefined();
    expect(credential?.apiKey).toBe('sk-test123');
    expect(credential?.isGlobal).toBe(true);
  });

  it('should normalize provider ID before lookup', () => {
    const settings = createMockSettings({
      openai: {
        provider: 'openai',
        displayName: 'OpenAI',
        apiKey: 'sk-test',
        isGlobal: true,
      },
    });
    expect(getGlobalCredential(settings, 'OpenAI')).toBeDefined();
    expect(getGlobalCredential(settings, 'OPENAI')).toBeDefined();
  });
});

describe('hasGlobalCredential', () => {
  it('should return false for null settings', () => {
    expect(hasGlobalCredential(null, 'openai')).toBe(false);
  });

  it('should return false for missing credential', () => {
    const settings = createMockSettings({});
    expect(hasGlobalCredential(settings, 'openai')).toBe(false);
  });

  it('should return true for existing credential', () => {
    const settings = createMockSettings({
      openai: {
        provider: 'openai',
        displayName: 'OpenAI',
        apiKey: 'sk-test',
        isGlobal: true,
      },
    });
    expect(hasGlobalCredential(settings, 'openai')).toBe(true);
  });
});

describe('getConfiguredProviders', () => {
  it('should return empty array for null settings', () => {
    expect(getConfiguredProviders(null)).toEqual([]);
  });

  it('should return empty array for undefined settings', () => {
    expect(getConfiguredProviders(undefined)).toEqual([]);
  });

  it('should return empty array when no credentials configured', () => {
    const settings = createMockSettings({});
    expect(getConfiguredProviders(settings)).toEqual([]);
  });

  it('should return provider IDs with valid credentials', () => {
    const settings = createMockSettings({
      openai: {
        provider: 'openai',
        displayName: 'OpenAI',
        apiKey: 'sk-test',
        isGlobal: true,
      },
      anthropic: {
        provider: 'anthropic',
        displayName: 'Anthropic',
        apiKey: 'sk-ant-test',
        isGlobal: true,
      },
    });
    const providers = getConfiguredProviders(settings);
    expect(providers).toContain('openai');
    expect(providers).toContain('anthropic');
    expect(providers).toHaveLength(2);
  });

  it('should exclude providers without apiKey', () => {
    const settings = createMockSettings({
      openai: {
        provider: 'openai',
        displayName: 'OpenAI',
        apiKey: 'sk-test',
        isGlobal: true,
      },
      anthropic: {
        provider: 'anthropic',
        displayName: 'Anthropic',
        apiKey: '', // Empty API key
        isGlobal: true,
      },
    });
    const providers = getConfiguredProviders(settings);
    expect(providers).toContain('openai');
    expect(providers).not.toContain('anthropic');
  });
});

describe('getProviderDisplayName', () => {
  it('should return display name from credential', () => {
    const settings = createMockSettings({
      openai: {
        provider: 'openai',
        displayName: 'OpenAI',
        apiKey: 'sk-test',
        isGlobal: true,
      },
    });
    expect(getProviderDisplayName(settings, 'openai')).toBe('OpenAI');
  });

  it('should fallback to title case for unknown provider', () => {
    const settings = createMockSettings({});
    expect(getProviderDisplayName(settings, 'openai')).toBe('Openai');
    expect(getProviderDisplayName(settings, 'custom-provider')).toBe('Custom Provider');
  });

  it('should fallback to title case when displayName is missing', () => {
    const settings = createMockSettings({
      openai: {
        provider: 'openai',
        displayName: '', // Empty display name
        apiKey: 'sk-test',
        isGlobal: true,
      },
    });
    expect(getProviderDisplayName(settings, 'openai')).toBe('Openai');
  });

  it('should handle null settings', () => {
    expect(getProviderDisplayName(null, 'openai')).toBe('Openai');
  });
});

describe('toTitleCase', () => {
  it('should convert simple words to title case', () => {
    expect(toTitleCase('openai')).toBe('Openai');
    expect(toTitleCase('anthropic')).toBe('Anthropic');
  });

  it('should handle hyphenated words', () => {
    expect(toTitleCase('custom-provider')).toBe('Custom Provider');
    expect(toTitleCase('zai-glm-47')).toBe('Zai Glm 47');
  });

  it('should handle single character segments', () => {
    expect(toTitleCase('a-b-c')).toBe('A B C');
  });

  it('should handle empty string', () => {
    expect(toTitleCase('')).toBe('');
  });
});

describe('resolveCredentials', () => {
  it('should return empty object for null project credentials', () => {
    const settings = createMockSettings({});
    expect(resolveCredentials(null, settings)).toEqual({});
  });

  it('should resolve global credentials', () => {
    const projectCredentials: ProviderCredentialsStore = {
      openai: { isGlobal: true },
    };
    const settings = createMockSettings({
      openai: {
        provider: 'openai',
        displayName: 'OpenAI',
        apiKey: 'sk-global-test',
        isGlobal: true,
      },
    });
    const resolved = resolveCredentials(projectCredentials, settings);
    expect(resolved.openai).toBeDefined();
    expect(resolved.openai.apiKey).toBe('sk-global-test');
    expect(resolved.openai.isGlobal).toBe(true);
  });

  it('should use project-specific credentials when isGlobal is false', () => {
    const projectCredentials: ProviderCredentialsStore = {
      openai: { isGlobal: false, apiKey: 'sk-project-test' },
    };
    const settings = createMockSettings({
      openai: {
        provider: 'openai',
        displayName: 'OpenAI',
        apiKey: 'sk-global-test',
        isGlobal: true,
      },
    });
    const resolved = resolveCredentials(projectCredentials, settings);
    expect(resolved.openai).toBeDefined();
    expect(resolved.openai.apiKey).toBe('sk-project-test');
    expect(resolved.openai.isGlobal).toBe(false);
  });

  it('should apply model override from project', () => {
    const projectCredentials: ProviderCredentialsStore = {
      openai: { isGlobal: true, model: 'gpt-4o' },
    };
    const settings = createMockSettings({
      openai: {
        provider: 'openai',
        displayName: 'OpenAI',
        apiKey: 'sk-test',
        isGlobal: true,
        defaultModel: 'gpt-3.5-turbo',
      },
    });
    const resolved = resolveCredentials(projectCredentials, settings);
    expect(resolved.openai.defaultModel).toBe('gpt-4o');
  });
});

describe('validateApiKeyFormat', () => {
  it('should return error for empty API key', () => {
    expect(validateApiKeyFormat('openai', '')).toBe('API key is required');
    expect(validateApiKeyFormat('openai', '   ')).toBe('API key is required');
  });

  it('should validate OpenAI key format', () => {
    expect(validateApiKeyFormat('openai', 'sk-test123')).toBeNull();
    expect(validateApiKeyFormat('openai', 'invalid-key')).toBe(
      'OpenAI API keys should start with "sk-"'
    );
  });

  it('should validate Anthropic key format', () => {
    expect(validateApiKeyFormat('anthropic', 'sk-ant-test123')).toBeNull();
    expect(validateApiKeyFormat('anthropic', 'sk-test123')).toBe(
      'Anthropic API keys should start with "sk-ant-"'
    );
  });

  it('should accept any format for unknown providers', () => {
    expect(validateApiKeyFormat('custom-provider', 'any-key-format')).toBeNull();
    expect(validateApiKeyFormat('gemini', 'AIza...')).toBeNull();
  });
});

describe('createCredentialReference', () => {
  it('should create global credential reference', () => {
    const ref = createCredentialReference(true);
    expect(ref.isGlobal).toBe(true);
    expect(ref.apiKey).toBeUndefined();
  });

  it('should create project-specific credential reference', () => {
    const ref = createCredentialReference(false, 'sk-test');
    expect(ref.isGlobal).toBe(false);
    expect(ref.apiKey).toBe('sk-test');
  });

  it('should include optional model and baseUrl', () => {
    const ref = createCredentialReference(true, undefined, 'gpt-4o', 'https://api.example.com');
    expect(ref.model).toBe('gpt-4o');
    expect(ref.baseUrl).toBe('https://api.example.com');
  });
});

describe('serializeCredentials', () => {
  it('should serialize credentials to JSON', () => {
    const credentials: ProviderCredentialsStore = {
      openai: { isGlobal: true },
    };
    const json = serializeCredentials(credentials);
    expect(json).toBe('{"openai":{"isGlobal":true}}');
  });

  it('should handle complex credentials', () => {
    const credentials: ProviderCredentialsStore = {
      openai: { isGlobal: true, model: 'gpt-4o' },
      anthropic: { isGlobal: false, apiKey: 'sk-ant-test' },
    };
    const json = serializeCredentials(credentials);
    const parsed = JSON.parse(json);
    expect(parsed.openai.isGlobal).toBe(true);
    expect(parsed.anthropic.apiKey).toBe('sk-ant-test');
  });
});

describe('parseCredentials', () => {
  it('should parse valid JSON', () => {
    const json = '{"openai":{"isGlobal":true}}';
    const parsed = parseCredentials(json);
    expect(parsed.openai).toBeDefined();
    expect(parsed.openai.isGlobal).toBe(true);
  });

  it('should return empty object for null', () => {
    expect(parseCredentials(null)).toEqual({});
  });

  it('should return empty object for undefined', () => {
    expect(parseCredentials(undefined)).toEqual({});
  });

  it('should return empty object for empty string', () => {
    expect(parseCredentials('')).toEqual({});
    expect(parseCredentials('   ')).toEqual({});
  });

  it('should return empty object for invalid JSON', () => {
    expect(parseCredentials('not json')).toEqual({});
    expect(parseCredentials('{broken')).toEqual({});
  });

  it('should return empty object for non-object JSON', () => {
    expect(parseCredentials('"string"')).toEqual({});
    expect(parseCredentials('null')).toEqual({});
    expect(parseCredentials('123')).toEqual({});
  });
});
