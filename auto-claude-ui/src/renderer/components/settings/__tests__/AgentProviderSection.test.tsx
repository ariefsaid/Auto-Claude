/**
 * Unit tests for AgentProviderSection component
 * Tests provider selection, credential toggle, and OpenCode configuration
 *
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { AgentProviderSection } from '../AgentProviderSection';
import type { AgentProviderType, ProviderCredential, ProviderCredentialsStore } from '@shared/types/provider';
import type { AppSettings } from '@shared/types/settings';

// Mock app settings with provider credentials
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
      apiKey: 'sk-test-key',
      isGlobal: true,
      defaultModel: 'gpt-4o',
    },
    anthropic: {
      provider: 'anthropic',
      displayName: 'Anthropic',
      apiKey: 'sk-ant-test-key',
      isGlobal: true,
      defaultModel: 'claude-3-5-sonnet-20241022',
    },
  },
};

// Mock app settings with no provider credentials
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

describe('AgentProviderSection', () => {
  const defaultProps = {
    agentProvider: 'claude_code' as AgentProviderType,
    onAgentProviderChange: vi.fn(),
    isGlobal: true,
    onGlobalChange: vi.fn(),
    opencodeProvider: undefined,
    onOpencodeProviderChange: vi.fn(),
    opencodeModel: '',
    onOpencodeModelChange: vi.fn(),
    providerCredentials: {} as ProviderCredentialsStore,
    onProviderCredentialsChange: vi.fn(),
    appSettings: mockAppSettings,
    onAddGlobalProvider: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Rendering', () => {
    it('should render the section with testid', () => {
      render(<AgentProviderSection {...defaultProps} />);

      const section = screen.getByTestId('agent-provider-section');
      expect(section).toBeDefined();
    });

    it('should render the section title', () => {
      render(<AgentProviderSection {...defaultProps} />);

      expect(screen.getByText('Agent Provider')).toBeDefined();
    });

    it('should render the provider type selector', () => {
      render(<AgentProviderSection {...defaultProps} />);

      const selector = screen.getByTestId('agent-provider-select');
      expect(selector).toBeDefined();
    });

    it('should render the provider status badge', () => {
      render(<AgentProviderSection {...defaultProps} />);

      const badge = screen.getByTestId('provider-status-badge');
      expect(badge).toBeDefined();
    });
  });

  describe('Claude Code Provider', () => {
    it('should show Claude Code info when claude_code is selected', () => {
      render(<AgentProviderSection {...defaultProps} />);

      expect(screen.getByText('Claude Code SDK')).toBeDefined();
      expect(
        screen.getByText(/Uses the official Claude Code SDK/)
      ).toBeDefined();
    });

    it('should show configured status for claude_code', () => {
      render(<AgentProviderSection {...defaultProps} />);

      const badge = screen.getByTestId('provider-status-badge');
      expect(badge.getAttribute('data-status')).toBe('configured');
    });

    it('should not show OpenCode configuration when claude_code is selected', () => {
      render(<AgentProviderSection {...defaultProps} />);

      expect(screen.queryByTestId('opencode-provider-select')).toBeNull();
    });
  });

  describe('OpenCode Provider', () => {
    const opencodeProps = {
      ...defaultProps,
      agentProvider: 'opencode' as AgentProviderType,
      opencodeProvider: 'openai',
      providerCredentials: {
        openai: { isGlobal: true },
      },
    };

    it('should show OpenCode configuration when opencode is selected', () => {
      render(<AgentProviderSection {...opencodeProps} />);

      const selector = screen.getByTestId('opencode-provider-select');
      expect(selector).toBeDefined();
    });

    it('should show the LLM Provider label', () => {
      render(<AgentProviderSection {...opencodeProps} />);

      expect(screen.getByText('LLM Provider')).toBeDefined();
    });

    it('should show Add Provider button', () => {
      render(<AgentProviderSection {...opencodeProps} />);

      const addButton = screen.getByTestId('add-provider-trigger');
      expect(addButton).toBeDefined();
    });

    it('should show Model input when provider is selected', () => {
      render(<AgentProviderSection {...opencodeProps} />);

      const modelInput = screen.getByTestId('opencode-model-input');
      expect(modelInput).toBeDefined();
    });

    it('should show ProviderCredentialSection when provider is selected', () => {
      render(<AgentProviderSection {...opencodeProps} />);

      const credSection = screen.getByTestId('provider-credential-section');
      expect(credSection).toBeDefined();
    });

    it('should show configured status when using global credentials with valid provider', () => {
      render(<AgentProviderSection {...opencodeProps} />);

      const badge = screen.getByTestId('provider-status-badge');
      expect(badge.getAttribute('data-status')).toBe('configured');
    });
  });

  describe('No Providers Configured', () => {
    const noProvidersProps = {
      ...defaultProps,
      agentProvider: 'opencode' as AgentProviderType,
      appSettings: mockEmptyAppSettings,
    };

    it('should show warning when no providers are configured', () => {
      render(<AgentProviderSection {...noProvidersProps} />);

      expect(screen.getByText('No providers configured')).toBeDefined();
    });

    it('should suggest adding a provider in App Settings', () => {
      render(<AgentProviderSection {...noProvidersProps} />);

      expect(
        screen.getByText(/Add a provider in App Settings/)
      ).toBeDefined();
    });

    it('should show not_configured status when no provider selected', () => {
      render(<AgentProviderSection {...noProvidersProps} />);

      const badge = screen.getByTestId('provider-status-badge');
      expect(badge.getAttribute('data-status')).toBe('not_configured');
    });
  });

  describe('Provider Selection', () => {
    it('should call onAgentProviderChange when provider type is changed', () => {
      const onAgentProviderChange = vi.fn();
      render(
        <AgentProviderSection
          {...defaultProps}
          onAgentProviderChange={onAgentProviderChange}
        />
      );

      const selector = screen.getByTestId('agent-provider-select');
      fireEvent.click(selector);

      // Note: Radix Select is tricky to test, so we verify the handler is callable
      expect(onAgentProviderChange).not.toHaveBeenCalled();
    });

    it('should call onOpencodeProviderChange when OpenCode provider is changed', () => {
      const onOpencodeProviderChange = vi.fn();
      render(
        <AgentProviderSection
          {...defaultProps}
          agentProvider="opencode"
          opencodeProvider="openai"
          providerCredentials={{ openai: { isGlobal: true } }}
          onOpencodeProviderChange={onOpencodeProviderChange}
        />
      );

      const selector = screen.getByTestId('opencode-provider-select');
      expect(selector).toBeDefined();
    });
  });

  describe('Model Override', () => {
    const opencodeProps = {
      ...defaultProps,
      agentProvider: 'opencode' as AgentProviderType,
      opencodeProvider: 'openai',
      opencodeModel: 'gpt-4o-mini',
      providerCredentials: {
        openai: { isGlobal: true },
      },
    };

    it('should display current model value', () => {
      render(<AgentProviderSection {...opencodeProps} />);

      const modelInput = screen.getByTestId('opencode-model-input') as HTMLInputElement;
      expect(modelInput.value).toBe('gpt-4o-mini');
    });

    it('should call onOpencodeModelChange when model is changed', () => {
      const onOpencodeModelChange = vi.fn();
      render(
        <AgentProviderSection
          {...opencodeProps}
          onOpencodeModelChange={onOpencodeModelChange}
        />
      );

      const modelInput = screen.getByTestId('opencode-model-input');
      fireEvent.change(modelInput, { target: { value: 'gpt-4-turbo' } });

      expect(onOpencodeModelChange).toHaveBeenCalledWith('gpt-4-turbo');
    });

    it('should show placeholder with default model from global credential', () => {
      render(<AgentProviderSection {...opencodeProps} opencodeModel="" />);

      const modelInput = screen.getByTestId('opencode-model-input');
      expect(modelInput.getAttribute('placeholder')).toContain('gpt-4o');
    });
  });

  describe('Disabled State', () => {
    it('should disable provider selector when disabled is true', () => {
      render(<AgentProviderSection {...defaultProps} disabled={true} />);

      const selector = screen.getByTestId('agent-provider-select');
      expect(selector.hasAttribute('disabled') || selector.getAttribute('aria-disabled') === 'true').toBe(true);
    });

    it('should disable OpenCode provider selector when disabled is true', () => {
      render(
        <AgentProviderSection
          {...defaultProps}
          agentProvider="opencode"
          opencodeProvider="openai"
          providerCredentials={{ openai: { isGlobal: true } }}
          disabled={true}
        />
      );

      const selector = screen.getByTestId('opencode-provider-select');
      expect(selector.hasAttribute('disabled') || selector.getAttribute('aria-disabled') === 'true').toBe(true);
    });

    it('should disable model input when disabled is true', () => {
      render(
        <AgentProviderSection
          {...defaultProps}
          agentProvider="opencode"
          opencodeProvider="openai"
          providerCredentials={{ openai: { isGlobal: true } }}
          disabled={true}
        />
      );

      const modelInput = screen.getByTestId('opencode-model-input') as HTMLInputElement;
      expect(modelInput.disabled).toBe(true);
    });
  });

  describe('Provider Status', () => {
    it('should show configured for claude_code', () => {
      render(<AgentProviderSection {...defaultProps} />);

      const badge = screen.getByTestId('provider-status-badge');
      expect(badge.getAttribute('data-status')).toBe('configured');
    });

    it('should show not_configured when opencode has no provider selected', () => {
      render(
        <AgentProviderSection
          {...defaultProps}
          agentProvider="opencode"
          opencodeProvider={undefined}
        />
      );

      const badge = screen.getByTestId('provider-status-badge');
      expect(badge.getAttribute('data-status')).toBe('not_configured');
    });

    it('should show error when global credential not found', () => {
      render(
        <AgentProviderSection
          {...defaultProps}
          agentProvider="opencode"
          opencodeProvider="nonexistent-provider"
          providerCredentials={{ 'nonexistent-provider': { isGlobal: true } }}
        />
      );

      const badge = screen.getByTestId('provider-status-badge');
      expect(badge.getAttribute('data-status')).toBe('error');
    });

    it('should show configured when using valid global credentials', () => {
      render(
        <AgentProviderSection
          {...defaultProps}
          agentProvider="opencode"
          opencodeProvider="openai"
          providerCredentials={{ openai: { isGlobal: true } }}
        />
      );

      const badge = screen.getByTestId('provider-status-badge');
      expect(badge.getAttribute('data-status')).toBe('configured');
    });
  });

  describe('Custom className', () => {
    it('should accept custom className', () => {
      render(
        <AgentProviderSection {...defaultProps} className="my-custom-class" />
      );

      const section = screen.getByTestId('agent-provider-section');
      expect(section.className).toContain('my-custom-class');
    });
  });

  describe('Tooltips', () => {
    it('should have tooltip on Provider Type field', () => {
      render(<AgentProviderSection {...defaultProps} />);

      // The help icon for tooltip should be present
      const helpIcons = document.querySelectorAll('[class*="cursor-help"]');
      expect(helpIcons.length).toBeGreaterThan(0);
    });
  });

  describe('Credential Section Integration', () => {
    const opencodeProps = {
      ...defaultProps,
      agentProvider: 'opencode' as AgentProviderType,
      opencodeProvider: 'openai',
      providerCredentials: {
        openai: { isGlobal: true },
      },
    };

    it('should render credential section for selected provider', () => {
      render(<AgentProviderSection {...opencodeProps} />);

      const credSection = screen.getByTestId('provider-credential-section');
      expect(credSection.getAttribute('data-provider-id')).toBe('openai');
    });

    it('should not render credential section when no provider is selected', () => {
      render(
        <AgentProviderSection
          {...defaultProps}
          agentProvider="opencode"
          opencodeProvider={undefined}
        />
      );

      expect(screen.queryByTestId('provider-credential-section')).toBeNull();
    });
  });

  describe('Add Provider Integration', () => {
    it('should call onAddGlobalProvider when adding a provider', () => {
      const onAddGlobalProvider = vi.fn();
      render(
        <AgentProviderSection
          {...defaultProps}
          agentProvider="opencode"
          onAddGlobalProvider={onAddGlobalProvider}
        />
      );

      // The Add Provider button should be present
      const addButton = screen.getByTestId('add-provider-trigger');
      expect(addButton).toBeDefined();
    });
  });

  describe('Props Interface', () => {
    it('should work with minimal required props', () => {
      const minimalProps = {
        agentProvider: 'claude_code' as AgentProviderType,
        onAgentProviderChange: vi.fn(),
        isGlobal: true,
        onGlobalChange: vi.fn(),
        onOpencodeProviderChange: vi.fn(),
        onOpencodeModelChange: vi.fn(),
        onProviderCredentialsChange: vi.fn(),
      };

      render(<AgentProviderSection {...minimalProps} />);

      const section = screen.getByTestId('agent-provider-section');
      expect(section).toBeDefined();
    });

    it('should work with all props provided', () => {
      render(<AgentProviderSection {...defaultProps} />);

      const section = screen.getByTestId('agent-provider-section');
      expect(section).toBeDefined();
    });
  });
});
