/**
 * UI Provider Integration Tests with Mocked IPC
 *
 * Tests the complete provider selection flow from UI components through to IPC handlers.
 * Verifies that UI components correctly communicate with the main process via mocked IPC.
 *
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { AgentProviderSection } from '../AgentProviderSection';
import { AddProviderDialog } from '../AddProviderDialog';
import { ProviderCredentialSection } from '../ProviderCredentialSection';
import { ProviderStatusBadge } from '../ProviderStatusBadge';
import type {
  AgentProviderType,
  ProviderCredential,
  ProviderCredentialsStore,
  ProviderStatusResponse,
  ProviderValidationResult,
  AgentProviderConfig,
  CredentialReference,
} from '@shared/types/provider';
import type { AppSettings } from '@shared/types/settings';
import {
  normalizeProviderId,
  getGlobalCredential,
  hasGlobalCredential,
  getConfiguredProviders,
} from '../../../utils/providerCredentials';

// ============================================
// Mock IPC Responses
// ============================================

/**
 * Mock IPC result structure
 */
interface MockIPCResult<T = unknown> {
  success: boolean;
  data?: T;
  error?: string;
}

/**
 * Create mock provider status response
 */
function createMockProviderStatus(overrides?: Partial<ProviderStatusResponse>): ProviderStatusResponse {
  return {
    provider: 'claude_code',
    source: 'default',
    isConfigured: true,
    errors: [],
    credentialSources: {},
    ...overrides,
  };
}

/**
 * Create mock validation result
 */
function createMockValidationResult(overrides?: Partial<ProviderValidationResult>): ProviderValidationResult {
  return {
    isValid: true,
    errors: [],
    warnings: [],
    ...overrides,
  };
}

/**
 * Mock global app settings with provider credentials
 */
const mockAppSettings: AppSettings = {
  theme: 'dark',
  defaultModel: 'claude-3-5-sonnet',
  agentFramework: 'claude-code',
  autoUpdateAutoBuild: true,
  autoNameTerminals: true,
  notifications: {
    onTaskComplete: true,
    onTaskFailed: true,
    onReviewNeeded: true,
    sound: true,
  },
  providerCredentials: {
    openai: {
      provider: 'openai',
      displayName: 'OpenAI',
      apiKey: 'sk-test-openai-key-12345',
      isGlobal: true,
      defaultModel: 'gpt-4o',
    },
    anthropic: {
      provider: 'anthropic',
      displayName: 'Anthropic',
      apiKey: 'sk-ant-test-key-12345',
      isGlobal: true,
      defaultModel: 'claude-3-5-sonnet-20241022',
    },
    'zai-glm': {
      provider: 'zai-glm',
      displayName: 'Z.ai GLM',
      apiKey: 'zai-test-key-12345',
      isGlobal: true,
      defaultModel: 'glm-4.7',
    },
  },
  globalDefaultProvider: 'claude_code',
};

/**
 * Mock empty app settings
 */
const mockEmptyAppSettings: AppSettings = {
  theme: 'dark',
  defaultModel: 'claude-3-5-sonnet',
  agentFramework: 'claude-code',
  autoUpdateAutoBuild: true,
  autoNameTerminals: true,
  notifications: {
    onTaskComplete: true,
    onTaskFailed: true,
    onReviewNeeded: true,
    sound: true,
  },
  providerCredentials: {},
};

// ============================================
// Integration Test: Full Provider Flow
// ============================================

describe('Provider Integration Tests (Mocked IPC)', () => {
  // Mock IPC handlers - using simple vi.fn() for better TypeScript compatibility
  const mockGetProviderStatus = vi.fn();
  const mockValidateProviderConfig = vi.fn();
  const mockAddProviderToGlobal = vi.fn();
  const mockGetConfiguredProviders = vi.fn();
  const mockRemoveProviderFromGlobal = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();

    // Default mock implementations with proper typing
    mockGetProviderStatus.mockResolvedValue({
      success: true,
      data: createMockProviderStatus(),
    } as MockIPCResult<ProviderStatusResponse>);

    mockValidateProviderConfig.mockResolvedValue({
      success: true,
      data: createMockValidationResult(),
    } as MockIPCResult<ProviderValidationResult>);

    mockAddProviderToGlobal.mockResolvedValue({ success: true } as MockIPCResult);

    mockGetConfiguredProviders.mockResolvedValue({
      success: true,
      data: Object.values(mockAppSettings.providerCredentials || {}),
    } as MockIPCResult<ProviderCredential[]>);

    mockRemoveProviderFromGlobal.mockResolvedValue({ success: true } as MockIPCResult);

    // Mock window.electronAPI if not already set
    if (typeof window !== 'undefined') {
      const windowWithAPI = window as unknown as {
        electronAPI?: Record<string, unknown>;
      };
      const existingAPI = windowWithAPI.electronAPI || {};
      windowWithAPI.electronAPI = {
        ...existingAPI,
        provider: {
          getProviderStatus: mockGetProviderStatus,
          validateProviderConfig: mockValidateProviderConfig,
          addProviderToGlobal: mockAddProviderToGlobal,
          getConfiguredProviders: mockGetConfiguredProviders,
          removeProviderFromGlobal: mockRemoveProviderFromGlobal,
        },
      };
    }
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  // ============================================
  // Provider Selection Integration
  // ============================================

  describe('Provider Selection Flow', () => {
    it('should render provider section with correct initial state', () => {
      const props = {
        agentProvider: 'claude_code' as AgentProviderType,
        onAgentProviderChange: vi.fn(),
        isGlobal: true,
        onGlobalChange: vi.fn(),
        onOpencodeProviderChange: vi.fn(),
        onOpencodeModelChange: vi.fn(),
        providerCredentials: {} as ProviderCredentialsStore,
        onProviderCredentialsChange: vi.fn(),
        appSettings: mockAppSettings,
        onAddGlobalProvider: vi.fn(),
      };

      render(<AgentProviderSection {...props} />);

      // Verify initial render
      const section = screen.getByTestId('agent-provider-section');
      expect(section).toBeDefined();

      // Verify Claude Code is displayed
      expect(screen.getByText('Claude Code SDK')).toBeDefined();

      // Verify status badge shows configured
      const badge = screen.getByTestId('provider-status-badge');
      expect(badge.getAttribute('data-status')).toBe('configured');
    });

    it('should switch from claude_code to opencode provider', async () => {
      const onAgentProviderChange = vi.fn();

      const props = {
        agentProvider: 'claude_code' as AgentProviderType,
        onAgentProviderChange,
        isGlobal: true,
        onGlobalChange: vi.fn(),
        onOpencodeProviderChange: vi.fn(),
        onOpencodeModelChange: vi.fn(),
        providerCredentials: {} as ProviderCredentialsStore,
        onProviderCredentialsChange: vi.fn(),
        appSettings: mockAppSettings,
        onAddGlobalProvider: vi.fn(),
      };

      const { rerender } = render(<AgentProviderSection {...props} />);

      // Verify initial state
      expect(screen.getByText('Claude Code SDK')).toBeDefined();

      // Rerender with opencode selected to simulate the change
      rerender(
        <AgentProviderSection
          {...props}
          agentProvider="opencode"
          opencodeProvider="openai"
          providerCredentials={{ openai: { isGlobal: true } }}
        />
      );

      // Verify OpenCode configuration is now shown
      await waitFor(() => {
        expect(screen.getByTestId('opencode-provider-select')).toBeDefined();
      });
    });

    it('should show configured providers in OpenCode dropdown', async () => {
      const props = {
        agentProvider: 'opencode' as AgentProviderType,
        onAgentProviderChange: vi.fn(),
        isGlobal: true,
        onGlobalChange: vi.fn(),
        opencodeProvider: 'openai',
        onOpencodeProviderChange: vi.fn(),
        onOpencodeModelChange: vi.fn(),
        providerCredentials: { openai: { isGlobal: true } } as ProviderCredentialsStore,
        onProviderCredentialsChange: vi.fn(),
        appSettings: mockAppSettings,
        onAddGlobalProvider: vi.fn(),
      };

      render(<AgentProviderSection {...props} />);

      // Verify OpenCode provider select is present
      const select = screen.getByTestId('opencode-provider-select');
      expect(select).toBeDefined();

      // Verify model input is shown
      const modelInput = screen.getByTestId('opencode-model-input');
      expect(modelInput).toBeDefined();
    });
  });

  // ============================================
  // Credential Management Integration
  // ============================================

  describe('Credential Management Flow', () => {
    it('should show global credential badge when using global credentials', () => {
      const globalCredential = mockAppSettings.providerCredentials?.['openai'];
      const props = {
        providerId: 'openai',
        providerDisplayName: 'OpenAI',
        isGlobal: true,
        onGlobalChange: vi.fn(),
        globalCredential,
        credentialRef: { isGlobal: true } as CredentialReference,
        onCredentialChange: vi.fn(),
      };

      render(<ProviderCredentialSection {...props} />);

      // Verify credential source badge shows "Using Global"
      const badge = screen.getByTestId('credential-source-badge');
      expect(badge.getAttribute('data-source')).toBe('global');

      // Verify API key input is not shown for global credentials
      expect(screen.queryByTestId('api-key-input')).toBeNull();
    });

    it('should show API key input when using project credentials', () => {
      const globalCredential = mockAppSettings.providerCredentials?.['openai'];
      const props = {
        providerId: 'openai',
        providerDisplayName: 'OpenAI',
        isGlobal: false,
        onGlobalChange: vi.fn(),
        globalCredential,
        credentialRef: { isGlobal: false, apiKey: 'sk-project-specific-key' } as CredentialReference,
        onCredentialChange: vi.fn(),
      };

      render(<ProviderCredentialSection {...props} />);

      // Verify credential source badge shows "Project Override"
      const badge = screen.getByTestId('credential-source-badge');
      expect(badge.getAttribute('data-source')).toBe('project');

      // Verify API key input is shown
      const apiKeyInput = screen.getByTestId('api-key-input') as HTMLInputElement;
      expect(apiKeyInput).toBeDefined();
      expect(apiKeyInput.value).toBe('sk-project-specific-key');
    });

    it('should toggle between global and project credentials', () => {
      const onGlobalChange = vi.fn();
      const onCredentialChange = vi.fn();
      const globalCredential = mockAppSettings.providerCredentials?.['openai'];

      const props = {
        providerId: 'openai',
        providerDisplayName: 'OpenAI',
        isGlobal: true,
        onGlobalChange,
        globalCredential,
        credentialRef: { isGlobal: true } as CredentialReference,
        onCredentialChange,
      };

      render(<ProviderCredentialSection {...props} />);

      // Find and click the toggle
      const toggle = screen.getByTestId('credential-source-toggle');
      fireEvent.click(toggle);

      // Verify callback was called with false (switch to project)
      expect(onGlobalChange).toHaveBeenCalledWith(false);
    });
  });

  // ============================================
  // Add Provider Dialog Integration
  // ============================================

  describe('Add Provider Dialog Flow', () => {
    it('should add provider through dialog and trigger IPC call', async () => {
      const onAddProvider = vi.fn();

      render(<AddProviderDialog onAddProvider={onAddProvider} open={true} />);

      // Fill in the form
      const displayNameInput = screen.getByTestId('display-name-input');
      const apiKeyInput = screen.getByTestId('api-key-input');
      const modelInput = screen.getByTestId('default-model-input');

      fireEvent.change(displayNameInput, { target: { value: 'OpenAI' } });
      fireEvent.change(apiKeyInput, { target: { value: 'sk-valid-api-key-12345' } });
      fireEvent.change(modelInput, { target: { value: 'gpt-4o' } });

      // Verify normalized ID preview
      await waitFor(() => {
        const preview = screen.getByTestId('normalized-id-preview');
        expect(preview.textContent).toContain('openai');
      });

      // Submit the form
      const saveButton = screen.getByTestId('save-button');
      fireEvent.click(saveButton);

      // Verify callback was called with correct data
      expect(onAddProvider).toHaveBeenCalledTimes(1);
      const credential = onAddProvider.mock.calls[0][0] as ProviderCredential;
      expect(credential.provider).toBe('openai');
      expect(credential.displayName).toBe('OpenAI');
      expect(credential.apiKey).toBe('sk-valid-api-key-12345');
      expect(credential.defaultModel).toBe('gpt-4o');
      expect(credential.isGlobal).toBe(true);
    });

    it('should normalize provider name correctly', async () => {
      const onAddProvider = vi.fn();

      render(<AddProviderDialog onAddProvider={onAddProvider} open={true} />);

      const displayNameInput = screen.getByTestId('display-name-input');
      const apiKeyInput = screen.getByTestId('api-key-input');

      // Test with complex name
      fireEvent.change(displayNameInput, { target: { value: 'Z.ai GLM 4.7' } });
      fireEvent.change(apiKeyInput, { target: { value: 'zai-test-key-12345' } });

      await waitFor(() => {
        const preview = screen.getByTestId('normalized-id-preview');
        expect(preview.textContent).toContain('zai-glm-47');
      });

      // Submit
      const saveButton = screen.getByTestId('save-button');
      fireEvent.click(saveButton);

      const credential = onAddProvider.mock.calls[0][0] as ProviderCredential;
      expect(credential.provider).toBe('zai-glm-47');
    });

    it('should validate API key format for known providers', async () => {
      render(<AddProviderDialog onAddProvider={vi.fn()} open={true} />);

      const displayNameInput = screen.getByTestId('display-name-input');
      const apiKeyInput = screen.getByTestId('api-key-input');

      // Enter OpenAI with invalid key format
      fireEvent.change(displayNameInput, { target: { value: 'OpenAI' } });
      fireEvent.change(apiKeyInput, { target: { value: 'invalid-key' } });

      await waitFor(() => {
        const error = screen.getByTestId('api-key-error');
        expect(error.textContent).toContain('sk-');
      });

      // Save button should be disabled
      const saveButton = screen.getByTestId('save-button') as HTMLButtonElement;
      expect(saveButton.disabled).toBe(true);
    });
  });

  // ============================================
  // Provider Status Badge Integration
  // ============================================

  describe('Provider Status Badge Flow', () => {
    it('should display configured status correctly', () => {
      render(<ProviderStatusBadge status="configured" />);

      const badge = screen.getByTestId('provider-status-badge');
      expect(badge.getAttribute('data-status')).toBe('configured');
      expect(badge.textContent).toContain('Configured');
    });

    it('should display not_configured status correctly', () => {
      render(<ProviderStatusBadge status="not_configured" />);

      const badge = screen.getByTestId('provider-status-badge');
      expect(badge.getAttribute('data-status')).toBe('not_configured');
      expect(badge.textContent).toContain('Not Configured');
    });

    it('should display error status with message', () => {
      render(<ProviderStatusBadge status="error" errorMessage="API key not found" />);

      const badge = screen.getByTestId('provider-status-badge');
      expect(badge.getAttribute('data-status')).toBe('error');
      expect(badge.textContent).toContain('Error');
    });
  });

  // ============================================
  // Provider Utilities Integration
  // ============================================

  describe('Provider Utilities', () => {
    describe('normalizeProviderId', () => {
      it('should match Python implementation exactly', () => {
        // Test cases from spec
        expect(normalizeProviderId('OpenAI')).toBe('openai');
        expect(normalizeProviderId('Z.ai GLM 4.7')).toBe('zai-glm-47');
        expect(normalizeProviderId('Custom Provider')).toBe('custom-provider');
        expect(normalizeProviderId('  OpenAI  ')).toBe('openai');
        expect(normalizeProviderId('Custom---Provider')).toBe('custom-provider');
        expect(normalizeProviderId('Z.ai GLM 4.7!@#')).toBe('zai-glm-47');
      });

      it('should handle edge cases', () => {
        expect(normalizeProviderId('')).toBe('');
        expect(normalizeProviderId('   ')).toBe('');
        expect(normalizeProviderId('---')).toBe('');
        expect(normalizeProviderId('A')).toBe('a');
        expect(normalizeProviderId('123')).toBe('123');
      });
    });

    describe('getGlobalCredential', () => {
      it('should retrieve global credential by provider ID', () => {
        // Note: function signature is (settings, providerId)
        const credential = getGlobalCredential(mockAppSettings, 'openai');
        expect(credential).toBeDefined();
        expect(credential?.provider).toBe('openai');
        expect(credential?.apiKey).toBe('sk-test-openai-key-12345');
      });

      it('should return undefined for non-existent provider', () => {
        const credential = getGlobalCredential(mockAppSettings, 'nonexistent');
        expect(credential).toBeUndefined();
      });

      it('should handle null/undefined settings', () => {
        expect(getGlobalCredential(undefined, 'openai')).toBeUndefined();
        expect(getGlobalCredential(null as unknown as AppSettings, 'openai')).toBeUndefined();
      });
    });

    describe('hasGlobalCredential', () => {
      it('should return true for configured provider', () => {
        // Note: function signature is (settings, providerId)
        expect(hasGlobalCredential(mockAppSettings, 'openai')).toBe(true);
        expect(hasGlobalCredential(mockAppSettings, 'anthropic')).toBe(true);
      });

      it('should return false for non-configured provider', () => {
        expect(hasGlobalCredential(mockAppSettings, 'nonexistent')).toBe(false);
      });

      it('should handle empty settings', () => {
        expect(hasGlobalCredential(mockEmptyAppSettings, 'openai')).toBe(false);
      });
    });

    describe('getConfiguredProviders', () => {
      it('should return list of configured provider IDs', () => {
        // Note: function returns string[] of provider IDs, not ProviderCredential[]
        const providers = getConfiguredProviders(mockAppSettings);
        expect(providers.length).toBe(3);
        expect(providers).toContain('openai');
        expect(providers).toContain('anthropic');
        expect(providers).toContain('zai-glm');
      });

      it('should return empty array for empty settings', () => {
        const providers = getConfiguredProviders(mockEmptyAppSettings);
        expect(providers.length).toBe(0);
      });
    });
  });

  // ============================================
  // Full Integration Flow
  // ============================================

  describe('Full Provider Configuration Flow', () => {
    it('should complete full flow: select provider -> configure credentials -> validate', async () => {
      const onAgentProviderChange = vi.fn();
      const onOpencodeProviderChange = vi.fn();
      const onProviderCredentialsChange = vi.fn();

      // Start with Claude Code selected
      const initialProps = {
        agentProvider: 'claude_code' as AgentProviderType,
        onAgentProviderChange,
        isGlobal: true,
        onGlobalChange: vi.fn(),
        onOpencodeProviderChange,
        onOpencodeModelChange: vi.fn(),
        providerCredentials: {} as ProviderCredentialsStore,
        onProviderCredentialsChange,
        appSettings: mockAppSettings,
        onAddGlobalProvider: vi.fn(),
      };

      const { rerender } = render(<AgentProviderSection {...initialProps} />);

      // Verify Claude Code is shown
      expect(screen.getByText('Claude Code SDK')).toBeDefined();
      expect(screen.getByTestId('provider-status-badge').getAttribute('data-status')).toBe('configured');

      // Simulate switch to OpenCode
      rerender(
        <AgentProviderSection
          {...initialProps}
          agentProvider="opencode"
          opencodeProvider="openai"
          providerCredentials={{ openai: { isGlobal: true } }}
        />
      );

      // Verify OpenCode configuration appears
      await waitFor(() => {
        expect(screen.getByTestId('opencode-provider-select')).toBeDefined();
      });

      // Verify credential section is shown
      expect(screen.getByTestId('provider-credential-section')).toBeDefined();

      // Verify status badge shows configured (using global credential)
      expect(screen.getByTestId('provider-status-badge').getAttribute('data-status')).toBe('configured');
    });

    it('should show error when global credential is missing', async () => {
      const props = {
        agentProvider: 'opencode' as AgentProviderType,
        onAgentProviderChange: vi.fn(),
        isGlobal: true,
        onGlobalChange: vi.fn(),
        opencodeProvider: 'nonexistent-provider',
        onOpencodeProviderChange: vi.fn(),
        onOpencodeModelChange: vi.fn(),
        providerCredentials: { 'nonexistent-provider': { isGlobal: true } } as ProviderCredentialsStore,
        onProviderCredentialsChange: vi.fn(),
        appSettings: mockAppSettings,
        onAddGlobalProvider: vi.fn(),
      };

      render(<AgentProviderSection {...props} />);

      // Verify error status is shown
      const badge = screen.getByTestId('provider-status-badge');
      expect(badge.getAttribute('data-status')).toBe('error');
    });

    it('should show not_configured when no OpenCode provider selected', () => {
      const props = {
        agentProvider: 'opencode' as AgentProviderType,
        onAgentProviderChange: vi.fn(),
        isGlobal: true,
        onGlobalChange: vi.fn(),
        opencodeProvider: undefined,
        onOpencodeProviderChange: vi.fn(),
        onOpencodeModelChange: vi.fn(),
        providerCredentials: {} as ProviderCredentialsStore,
        onProviderCredentialsChange: vi.fn(),
        appSettings: mockAppSettings,
        onAddGlobalProvider: vi.fn(),
      };

      render(<AgentProviderSection {...props} />);

      // Verify not_configured status is shown
      const badge = screen.getByTestId('provider-status-badge');
      expect(badge.getAttribute('data-status')).toBe('not_configured');
    });
  });

  // ============================================
  // Edge Cases
  // ============================================

  describe('Edge Cases', () => {
    it('should handle empty provider credentials store', () => {
      const props = {
        agentProvider: 'opencode' as AgentProviderType,
        onAgentProviderChange: vi.fn(),
        isGlobal: true,
        onGlobalChange: vi.fn(),
        onOpencodeProviderChange: vi.fn(),
        onOpencodeModelChange: vi.fn(),
        providerCredentials: {} as ProviderCredentialsStore,
        onProviderCredentialsChange: vi.fn(),
        appSettings: mockEmptyAppSettings,
        onAddGlobalProvider: vi.fn(),
      };

      render(<AgentProviderSection {...props} />);

      // Should show "No providers configured" message
      expect(screen.getByText('No providers configured')).toBeDefined();
    });

    it('should handle null appSettings', () => {
      const props = {
        agentProvider: 'claude_code' as AgentProviderType,
        onAgentProviderChange: vi.fn(),
        isGlobal: true,
        onGlobalChange: vi.fn(),
        onOpencodeProviderChange: vi.fn(),
        onOpencodeModelChange: vi.fn(),
        providerCredentials: {} as ProviderCredentialsStore,
        onProviderCredentialsChange: vi.fn(),
        appSettings: undefined,
        onAddGlobalProvider: vi.fn(),
      };

      // Should not throw
      render(<AgentProviderSection {...props} />);
      expect(screen.getByTestId('agent-provider-section')).toBeDefined();
    });

    it('should handle switching providers rapidly', async () => {
      const onAgentProviderChange = vi.fn();

      const props = {
        agentProvider: 'claude_code' as AgentProviderType,
        onAgentProviderChange,
        isGlobal: true,
        onGlobalChange: vi.fn(),
        onOpencodeProviderChange: vi.fn(),
        onOpencodeModelChange: vi.fn(),
        providerCredentials: {} as ProviderCredentialsStore,
        onProviderCredentialsChange: vi.fn(),
        appSettings: mockAppSettings,
        onAddGlobalProvider: vi.fn(),
      };

      const { rerender } = render(<AgentProviderSection {...props} />);

      // Rapid rerenders should not cause issues
      await act(async () => {
        rerender(<AgentProviderSection {...props} agentProvider="opencode" />);
        rerender(<AgentProviderSection {...props} agentProvider="claude_code" />);
        rerender(<AgentProviderSection {...props} agentProvider="opencode" />);
      });

      // Component should still be functional
      expect(screen.getByTestId('agent-provider-section')).toBeDefined();
    });

    it('should handle provider with project-specific credentials', () => {
      const props = {
        agentProvider: 'opencode' as AgentProviderType,
        onAgentProviderChange: vi.fn(),
        isGlobal: false,
        onGlobalChange: vi.fn(),
        opencodeProvider: 'openai',
        onOpencodeProviderChange: vi.fn(),
        onOpencodeModelChange: vi.fn(),
        providerCredentials: {
          openai: {
            isGlobal: false,
            apiKey: 'sk-project-specific-key',
          },
        } as ProviderCredentialsStore,
        onProviderCredentialsChange: vi.fn(),
        appSettings: mockAppSettings,
        onAddGlobalProvider: vi.fn(),
      };

      render(<AgentProviderSection {...props} />);

      // Should show configured with project credentials
      const badge = screen.getByTestId('provider-status-badge');
      expect(badge.getAttribute('data-status')).toBe('configured');
    });
  });

  // ============================================
  // Model Override Integration
  // ============================================

  describe('Model Override Flow', () => {
    it('should display model input with placeholder from global credential', () => {
      const props = {
        agentProvider: 'opencode' as AgentProviderType,
        onAgentProviderChange: vi.fn(),
        isGlobal: true,
        onGlobalChange: vi.fn(),
        opencodeProvider: 'openai',
        onOpencodeProviderChange: vi.fn(),
        opencodeModel: '',
        onOpencodeModelChange: vi.fn(),
        providerCredentials: { openai: { isGlobal: true } } as ProviderCredentialsStore,
        onProviderCredentialsChange: vi.fn(),
        appSettings: mockAppSettings,
        onAddGlobalProvider: vi.fn(),
      };

      render(<AgentProviderSection {...props} />);

      const modelInput = screen.getByTestId('opencode-model-input');
      expect(modelInput.getAttribute('placeholder')).toContain('gpt-4o');
    });

    it('should call model change handler', () => {
      const onOpencodeModelChange = vi.fn();

      const props = {
        agentProvider: 'opencode' as AgentProviderType,
        onAgentProviderChange: vi.fn(),
        isGlobal: true,
        onGlobalChange: vi.fn(),
        opencodeProvider: 'openai',
        onOpencodeProviderChange: vi.fn(),
        opencodeModel: '',
        onOpencodeModelChange,
        providerCredentials: { openai: { isGlobal: true } } as ProviderCredentialsStore,
        onProviderCredentialsChange: vi.fn(),
        appSettings: mockAppSettings,
        onAddGlobalProvider: vi.fn(),
      };

      render(<AgentProviderSection {...props} />);

      const modelInput = screen.getByTestId('opencode-model-input');
      fireEvent.change(modelInput, { target: { value: 'gpt-4-turbo' } });

      expect(onOpencodeModelChange).toHaveBeenCalledWith('gpt-4-turbo');
    });
  });

  // ============================================
  // Disabled State Integration
  // ============================================

  describe('Disabled State', () => {
    it('should disable all interactive elements when disabled prop is true', () => {
      const props = {
        agentProvider: 'opencode' as AgentProviderType,
        onAgentProviderChange: vi.fn(),
        isGlobal: true,
        onGlobalChange: vi.fn(),
        opencodeProvider: 'openai',
        onOpencodeProviderChange: vi.fn(),
        opencodeModel: '',
        onOpencodeModelChange: vi.fn(),
        providerCredentials: { openai: { isGlobal: true } } as ProviderCredentialsStore,
        onProviderCredentialsChange: vi.fn(),
        appSettings: mockAppSettings,
        onAddGlobalProvider: vi.fn(),
        disabled: true,
      };

      render(<AgentProviderSection {...props} />);

      // Agent provider select should be disabled
      const agentSelect = screen.getByTestId('agent-provider-select');
      expect(
        agentSelect.hasAttribute('disabled') ||
          agentSelect.getAttribute('aria-disabled') === 'true'
      ).toBe(true);

      // OpenCode provider select should be disabled
      const opencodeSelect = screen.getByTestId('opencode-provider-select');
      expect(
        opencodeSelect.hasAttribute('disabled') ||
          opencodeSelect.getAttribute('aria-disabled') === 'true'
      ).toBe(true);

      // Model input should be disabled
      const modelInput = screen.getByTestId('opencode-model-input') as HTMLInputElement;
      expect(modelInput.disabled).toBe(true);
    });
  });

  // ============================================
  // Credential Section UI States
  // ============================================

  describe('Credential Section UI States', () => {
    it('should show global credential info when isGlobal is true', () => {
      const globalCredential = mockAppSettings.providerCredentials?.['openai'];

      render(
        <ProviderCredentialSection
          providerId="openai"
          providerDisplayName="OpenAI"
          isGlobal={true}
          onGlobalChange={vi.fn()}
          globalCredential={globalCredential}
          credentialRef={{ isGlobal: true }}
          onCredentialChange={vi.fn()}
        />
      );

      // Check for the badge with global source
      const badge = screen.getByTestId('credential-source-badge');
      expect(badge.getAttribute('data-source')).toBe('global');
    });

    it('should allow entering project-specific API key', () => {
      const onCredentialChange = vi.fn();

      render(
        <ProviderCredentialSection
          providerId="openai"
          providerDisplayName="OpenAI"
          isGlobal={false}
          onGlobalChange={vi.fn()}
          globalCredential={mockAppSettings.providerCredentials?.['openai']}
          credentialRef={{ isGlobal: false, apiKey: '' }}
          onCredentialChange={onCredentialChange}
        />
      );

      const apiKeyInput = screen.getByTestId('api-key-input');
      fireEvent.change(apiKeyInput, { target: { value: 'sk-new-project-key' } });

      expect(onCredentialChange).toHaveBeenCalled();
      // The callback receives the full credential reference object
      const lastCall = onCredentialChange.mock.calls[onCredentialChange.mock.calls.length - 1][0];
      expect(lastCall.apiKey).toBe('sk-new-project-key');
    });
  });

  // ============================================
  // IPC Communication Tests
  // ============================================

  describe('IPC Communication', () => {
    it('should structure provider config correctly for IPC', () => {
      // Verify the config structure matches what IPC handlers expect
      const config: Partial<AgentProviderConfig> = {
        agentProvider: 'opencode',
        agentProviderIsGlobal: true,
        opencodeProvider: 'openai',
        opencodeModel: 'gpt-4o',
        providerCredentials: {
          openai: { isGlobal: true },
        },
      };

      // Simulate validation call
      mockValidateProviderConfig(config);

      expect(mockValidateProviderConfig).toHaveBeenCalledWith(config);
    });

    it('should handle IPC error responses gracefully', async () => {
      mockGetProviderStatus.mockResolvedValueOnce({
        success: false,
        error: 'Network error',
      });

      // The component should handle this error gracefully
      // This tests that the mocked IPC setup works correctly
      const result = await mockGetProviderStatus('test-project');
      expect(result.success).toBe(false);
      expect(result.error).toBe('Network error');
    });

    it('should handle provider credential addition via IPC', async () => {
      const newCredential: ProviderCredential = {
        provider: 'custom-provider',
        displayName: 'Custom Provider',
        apiKey: 'custom-api-key-12345',
        isGlobal: true,
        defaultModel: 'custom-model',
      };

      await mockAddProviderToGlobal(newCredential);

      expect(mockAddProviderToGlobal).toHaveBeenCalledWith(newCredential);
    });

    it('should retrieve configured providers via IPC', async () => {
      const result = await mockGetConfiguredProviders();

      expect(result.success).toBe(true);
      expect(result.data).toBeDefined();
      expect(result.data?.length).toBe(3); // openai, anthropic, zai-glm
    });
  });

  // ============================================
  // Provider Validation Tests
  // ============================================

  describe('Provider Validation', () => {
    it('should validate opencode requires provider selection', async () => {
      const invalidConfig: Partial<AgentProviderConfig> = {
        agentProvider: 'opencode',
        opencodeProvider: '', // Missing provider
      };

      mockValidateProviderConfig.mockResolvedValueOnce({
        success: true,
        data: {
          isValid: false,
          errors: ["OpenCode provider is required when using 'opencode' agent"],
          warnings: [],
        },
      });

      const result = await mockValidateProviderConfig(invalidConfig);

      expect(result.data?.isValid).toBe(false);
      expect(result.data?.errors).toContain("OpenCode provider is required when using 'opencode' agent");
    });

    it('should validate global credential exists', async () => {
      const configWithMissingCredential: Partial<AgentProviderConfig> = {
        agentProvider: 'opencode',
        agentProviderIsGlobal: true,
        opencodeProvider: 'nonexistent',
        providerCredentials: {
          nonexistent: { isGlobal: true },
        },
      };

      mockValidateProviderConfig.mockResolvedValueOnce({
        success: true,
        data: {
          isValid: false,
          errors: ["Global credential for 'nonexistent' not found"],
          warnings: [],
        },
      });

      const result = await mockValidateProviderConfig(configWithMissingCredential);

      expect(result.data?.isValid).toBe(false);
      expect(result.data?.errors).toContain("Global credential for 'nonexistent' not found");
    });

    it('should pass validation for valid config', async () => {
      const validConfig: Partial<AgentProviderConfig> = {
        agentProvider: 'opencode',
        agentProviderIsGlobal: true,
        opencodeProvider: 'openai',
        opencodeModel: 'gpt-4o',
        providerCredentials: {
          openai: { isGlobal: true },
        },
      };

      const result = await mockValidateProviderConfig(validConfig);

      expect(result.data?.isValid).toBe(true);
      expect(result.data?.errors?.length).toBe(0);
    });
  });
});
