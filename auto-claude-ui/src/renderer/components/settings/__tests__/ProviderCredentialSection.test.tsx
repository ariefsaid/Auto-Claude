/**
 * Unit tests for ProviderCredentialSection component
 * Tests global/project toggle, credential source display, and input handling
 *
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ProviderCredentialSection } from '../ProviderCredentialSection';
import type { ProviderCredential, CredentialReference } from '@shared/types/provider';

// Mock global credential
const mockGlobalCredential: ProviderCredential = {
  provider: 'openai',
  displayName: 'OpenAI',
  apiKey: 'sk-global-test-key',
  isGlobal: true,
  defaultModel: 'gpt-4o',
  baseUrl: undefined,
};

// Mock credential reference for project
const mockCredentialRef: CredentialReference = {
  isGlobal: false,
  apiKey: 'sk-project-test-key',
  model: 'gpt-4-turbo',
  baseUrl: 'https://custom.api.com/v1',
};

describe('ProviderCredentialSection', () => {
  const defaultProps = {
    providerId: 'openai',
    providerDisplayName: 'OpenAI',
    isGlobal: true,
    onGlobalChange: vi.fn(),
    onCredentialChange: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Rendering', () => {
    it('should render the component', () => {
      render(<ProviderCredentialSection {...defaultProps} />);

      const section = screen.getByTestId('provider-credential-section');
      expect(section).toBeDefined();
    });

    it('should render with correct provider ID data attribute', () => {
      render(<ProviderCredentialSection {...defaultProps} />);

      const section = screen.getByTestId('provider-credential-section');
      expect(section.getAttribute('data-provider-id')).toBe('openai');
    });

    it('should render the credential source toggle', () => {
      render(<ProviderCredentialSection {...defaultProps} />);

      const toggle = screen.getByTestId('credential-source-toggle');
      expect(toggle).toBeDefined();
    });

    it('should render the credential source badge', () => {
      render(
        <ProviderCredentialSection
          {...defaultProps}
          globalCredential={mockGlobalCredential}
        />
      );

      const badge = screen.getByTestId('credential-source-badge');
      expect(badge).toBeDefined();
    });
  });

  describe('Global Credential Mode', () => {
    it('should show "Using Global" badge when using global credentials', () => {
      render(
        <ProviderCredentialSection
          {...defaultProps}
          isGlobal={true}
          globalCredential={mockGlobalCredential}
        />
      );

      const badge = screen.getByTestId('credential-source-badge');
      expect(badge.textContent).toContain('Using Global');
      expect(badge.getAttribute('data-source')).toBe('global');
    });

    it('should show checkmark in global badge', () => {
      render(
        <ProviderCredentialSection
          {...defaultProps}
          isGlobal={true}
          globalCredential={mockGlobalCredential}
        />
      );

      const badge = screen.getByTestId('credential-source-badge');
      expect(badge.textContent).toContain('\u2713');
    });

    it('should show global credential info when using global credentials', () => {
      render(
        <ProviderCredentialSection
          {...defaultProps}
          isGlobal={true}
          globalCredential={mockGlobalCredential}
        />
      );

      expect(
        screen.getByText(/Using credentials from App Settings/i)
      ).toBeDefined();
    });

    it('should show default model from global credential', () => {
      render(
        <ProviderCredentialSection
          {...defaultProps}
          isGlobal={true}
          globalCredential={mockGlobalCredential}
        />
      );

      expect(screen.getByText('gpt-4o')).toBeDefined();
    });

    it('should NOT show API key input when using global credentials', () => {
      render(
        <ProviderCredentialSection
          {...defaultProps}
          isGlobal={true}
          globalCredential={mockGlobalCredential}
        />
      );

      expect(screen.queryByTestId('api-key-section')).toBeNull();
    });

    it('should show warning when global credentials not available', () => {
      render(
        <ProviderCredentialSection
          {...defaultProps}
          isGlobal={true}
          globalCredential={null}
        />
      );

      const badge = screen.getByTestId('credential-source-badge');
      expect(badge.getAttribute('data-source')).toBe('missing');
      expect(screen.getByText(/No global credentials configured/i)).toBeDefined();
    });
  });

  describe('Project Credential Mode', () => {
    it('should show "Project Override" badge when using project credentials', () => {
      render(
        <ProviderCredentialSection
          {...defaultProps}
          isGlobal={false}
          credentialRef={mockCredentialRef}
        />
      );

      const badge = screen.getByTestId('credential-source-badge');
      expect(badge.textContent).toContain('Project Override');
      expect(badge.getAttribute('data-source')).toBe('project');
    });

    it('should show API key input when using project credentials', () => {
      render(
        <ProviderCredentialSection
          {...defaultProps}
          isGlobal={false}
          credentialRef={mockCredentialRef}
        />
      );

      const apiKeySection = screen.getByTestId('api-key-section');
      expect(apiKeySection).toBeDefined();

      const apiKeyInput = screen.getByTestId('api-key-input');
      expect(apiKeyInput).toBeDefined();
    });

    it('should display current API key value in input', () => {
      render(
        <ProviderCredentialSection
          {...defaultProps}
          isGlobal={false}
          credentialRef={mockCredentialRef}
        />
      );

      const apiKeyInput = screen.getByTestId('api-key-input') as HTMLInputElement;
      expect(apiKeyInput.value).toBe('sk-project-test-key');
    });

    it('should show project-specific info message', () => {
      render(
        <ProviderCredentialSection
          {...defaultProps}
          isGlobal={false}
          credentialRef={mockCredentialRef}
        />
      );

      expect(
        screen.getByText(/Using project-specific credentials/i)
      ).toBeDefined();
    });
  });

  describe('Toggle Interaction', () => {
    it('should call onGlobalChange when toggle is clicked', () => {
      const onGlobalChange = vi.fn();
      render(
        <ProviderCredentialSection
          {...defaultProps}
          isGlobal={false}
          globalCredential={mockGlobalCredential}
          onGlobalChange={onGlobalChange}
        />
      );

      const toggle = screen.getByTestId('credential-source-toggle');
      fireEvent.click(toggle);

      expect(onGlobalChange).toHaveBeenCalledWith(true);
    });

    it('should call onCredentialChange when toggle changes to global', () => {
      const onCredentialChange = vi.fn();
      render(
        <ProviderCredentialSection
          {...defaultProps}
          isGlobal={false}
          credentialRef={mockCredentialRef}
          globalCredential={mockGlobalCredential}
          onCredentialChange={onCredentialChange}
        />
      );

      const toggle = screen.getByTestId('credential-source-toggle');
      fireEvent.click(toggle);

      expect(onCredentialChange).toHaveBeenCalledWith(
        expect.objectContaining({
          isGlobal: true,
          apiKey: undefined, // API key should be cleared when switching to global
        })
      );
    });

    it('should disable toggle when no global credential available', () => {
      render(
        <ProviderCredentialSection
          {...defaultProps}
          isGlobal={false}
          globalCredential={null}
        />
      );

      const toggle = screen.getByTestId('credential-source-toggle');
      // Radix UI Switch uses 'disabled' attribute
      expect(toggle.hasAttribute('disabled') || toggle.getAttribute('data-disabled') === '' || toggle.getAttribute('aria-disabled') === 'true').toBe(true);
    });

    it('should disable toggle when component is disabled', () => {
      render(
        <ProviderCredentialSection
          {...defaultProps}
          globalCredential={mockGlobalCredential}
          disabled={true}
        />
      );

      const toggle = screen.getByTestId('credential-source-toggle');
      // Radix UI Switch uses 'disabled' attribute
      expect(toggle.hasAttribute('disabled') || toggle.getAttribute('data-disabled') === '' || toggle.getAttribute('aria-disabled') === 'true').toBe(true);
    });
  });

  describe('API Key Input Interaction', () => {
    it('should call onCredentialChange when API key changes', () => {
      const onCredentialChange = vi.fn();
      render(
        <ProviderCredentialSection
          {...defaultProps}
          isGlobal={false}
          onCredentialChange={onCredentialChange}
        />
      );

      const apiKeyInput = screen.getByTestId('api-key-input');
      fireEvent.change(apiKeyInput, { target: { value: 'sk-new-key' } });

      expect(onCredentialChange).toHaveBeenCalledWith(
        expect.objectContaining({
          isGlobal: false,
          apiKey: 'sk-new-key',
        })
      );
    });

    it('should clear API key when input is emptied', () => {
      const onCredentialChange = vi.fn();
      render(
        <ProviderCredentialSection
          {...defaultProps}
          isGlobal={false}
          credentialRef={mockCredentialRef}
          onCredentialChange={onCredentialChange}
        />
      );

      const apiKeyInput = screen.getByTestId('api-key-input');
      fireEvent.change(apiKeyInput, { target: { value: '' } });

      expect(onCredentialChange).toHaveBeenCalledWith(
        expect.objectContaining({
          apiKey: undefined,
        })
      );
    });
  });

  describe('Model Override Input', () => {
    it('should render model override section', () => {
      render(<ProviderCredentialSection {...defaultProps} />);

      const modelSection = screen.getByTestId('model-override-section');
      expect(modelSection).toBeDefined();
    });

    it('should display current model value', () => {
      render(
        <ProviderCredentialSection
          {...defaultProps}
          isGlobal={false}
          credentialRef={mockCredentialRef}
        />
      );

      const modelInput = screen.getByTestId('model-override-input') as HTMLInputElement;
      expect(modelInput.value).toBe('gpt-4-turbo');
    });

    it('should call onCredentialChange when model changes', () => {
      const onCredentialChange = vi.fn();
      render(
        <ProviderCredentialSection
          {...defaultProps}
          isGlobal={false}
          onCredentialChange={onCredentialChange}
        />
      );

      const modelInput = screen.getByTestId('model-override-input');
      fireEvent.change(modelInput, { target: { value: 'gpt-4o-mini' } });

      expect(onCredentialChange).toHaveBeenCalledWith(
        expect.objectContaining({
          model: 'gpt-4o-mini',
        })
      );
    });

    it('should show placeholder with global default model when using global', () => {
      render(
        <ProviderCredentialSection
          {...defaultProps}
          isGlobal={true}
          globalCredential={mockGlobalCredential}
        />
      );

      const modelInput = screen.getByTestId('model-override-input') as HTMLInputElement;
      expect(modelInput.placeholder).toContain('gpt-4o');
    });
  });

  describe('Base URL Input', () => {
    it('should render base URL section', () => {
      render(<ProviderCredentialSection {...defaultProps} />);

      const baseUrlSection = screen.getByTestId('base-url-section');
      expect(baseUrlSection).toBeDefined();
    });

    it('should display current base URL value', () => {
      render(
        <ProviderCredentialSection
          {...defaultProps}
          isGlobal={false}
          credentialRef={mockCredentialRef}
        />
      );

      const baseUrlInput = screen.getByTestId('base-url-input') as HTMLInputElement;
      expect(baseUrlInput.value).toBe('https://custom.api.com/v1');
    });

    it('should call onCredentialChange when base URL changes', () => {
      const onCredentialChange = vi.fn();
      render(
        <ProviderCredentialSection
          {...defaultProps}
          isGlobal={false}
          onCredentialChange={onCredentialChange}
        />
      );

      const baseUrlInput = screen.getByTestId('base-url-input');
      fireEvent.change(baseUrlInput, {
        target: { value: 'https://new-api.com/v1' },
      });

      expect(onCredentialChange).toHaveBeenCalledWith(
        expect.objectContaining({
          baseUrl: 'https://new-api.com/v1',
        })
      );
    });
  });

  describe('Disabled State', () => {
    it('should disable toggle when disabled prop is true', () => {
      render(
        <ProviderCredentialSection
          {...defaultProps}
          globalCredential={mockGlobalCredential}
          disabled={true}
        />
      );

      const toggle = screen.getByTestId('credential-source-toggle');
      // Radix UI Switch uses 'disabled' attribute
      expect(toggle.hasAttribute('disabled') || toggle.getAttribute('data-disabled') === '' || toggle.getAttribute('aria-disabled') === 'true').toBe(true);
    });

    it('should disable API key input when disabled', () => {
      render(
        <ProviderCredentialSection
          {...defaultProps}
          isGlobal={false}
          disabled={true}
        />
      );

      const apiKeyInput = screen.getByTestId('api-key-input');
      expect(apiKeyInput.getAttribute('disabled')).toBeDefined();
    });

    it('should disable model input when disabled', () => {
      render(
        <ProviderCredentialSection
          {...defaultProps}
          disabled={true}
        />
      );

      const modelInput = screen.getByTestId('model-override-input');
      expect(modelInput.getAttribute('disabled')).toBeDefined();
    });

    it('should disable base URL input when disabled', () => {
      render(
        <ProviderCredentialSection
          {...defaultProps}
          disabled={true}
        />
      );

      const baseUrlInput = screen.getByTestId('base-url-input');
      expect(baseUrlInput.getAttribute('disabled')).toBeDefined();
    });
  });

  describe('Custom Styling', () => {
    it('should accept custom className', () => {
      render(
        <ProviderCredentialSection
          {...defaultProps}
          className="my-custom-class"
        />
      );

      const section = screen.getByTestId('provider-credential-section');
      expect(section.className).toContain('my-custom-class');
    });

    it('should preserve default classes with custom className', () => {
      render(
        <ProviderCredentialSection
          {...defaultProps}
          className="extra-class"
        />
      );

      const section = screen.getByTestId('provider-credential-section');
      expect(section.className).toContain('space-y-4');
      expect(section.className).toContain('extra-class');
    });
  });

  describe('Edge Cases', () => {
    it('should handle undefined credentialRef', () => {
      render(
        <ProviderCredentialSection
          {...defaultProps}
          isGlobal={false}
          credentialRef={undefined}
        />
      );

      const apiKeyInput = screen.getByTestId('api-key-input') as HTMLInputElement;
      expect(apiKeyInput.value).toBe('');
    });

    it('should handle null globalCredential', () => {
      render(
        <ProviderCredentialSection
          {...defaultProps}
          isGlobal={true}
          globalCredential={null}
        />
      );

      const badge = screen.getByTestId('credential-source-badge');
      expect(badge.getAttribute('data-source')).toBe('missing');
    });

    it('should handle switching from project to global', () => {
      const onCredentialChange = vi.fn();
      const { rerender } = render(
        <ProviderCredentialSection
          {...defaultProps}
          isGlobal={false}
          credentialRef={mockCredentialRef}
          globalCredential={mockGlobalCredential}
          onCredentialChange={onCredentialChange}
        />
      );

      // Simulate toggle click
      const toggle = screen.getByTestId('credential-source-toggle');
      fireEvent.click(toggle);

      // Rerender with new isGlobal state
      rerender(
        <ProviderCredentialSection
          {...defaultProps}
          isGlobal={true}
          credentialRef={{ ...mockCredentialRef, isGlobal: true, apiKey: undefined }}
          globalCredential={mockGlobalCredential}
          onCredentialChange={onCredentialChange}
        />
      );

      // API key section should be hidden
      expect(screen.queryByTestId('api-key-section')).toBeNull();
    });

    it('should preserve model and baseUrl when switching credential source', () => {
      const onCredentialChange = vi.fn();
      render(
        <ProviderCredentialSection
          {...defaultProps}
          isGlobal={false}
          credentialRef={mockCredentialRef}
          globalCredential={mockGlobalCredential}
          onCredentialChange={onCredentialChange}
        />
      );

      const toggle = screen.getByTestId('credential-source-toggle');
      fireEvent.click(toggle);

      expect(onCredentialChange).toHaveBeenCalledWith(
        expect.objectContaining({
          model: 'gpt-4-turbo',
          baseUrl: 'https://custom.api.com/v1',
        })
      );
    });
  });

  describe('Accessibility', () => {
    it('should have data-testid for testing', () => {
      render(<ProviderCredentialSection {...defaultProps} />);

      expect(screen.getByTestId('provider-credential-section')).toBeDefined();
      expect(screen.getByTestId('credential-source-toggle')).toBeDefined();
      expect(screen.getByTestId('credential-source-badge')).toBeDefined();
    });

    it('should have aria-label on toggle', () => {
      render(
        <ProviderCredentialSection
          {...defaultProps}
          isGlobal={true}
          globalCredential={mockGlobalCredential}
        />
      );

      const toggle = screen.getByTestId('credential-source-toggle');
      expect(toggle.getAttribute('aria-label')).toBeDefined();
    });

    it('should have labels associated with inputs', () => {
      render(
        <ProviderCredentialSection
          {...defaultProps}
          isGlobal={false}
        />
      );

      // API key input should have associated label
      const apiKeyInput = screen.getByTestId('api-key-input');
      expect(apiKeyInput.getAttribute('id')).toBe('api-key-openai');
    });
  });

  describe('Provider Display Name', () => {
    it('should display provider name in info text', () => {
      render(
        <ProviderCredentialSection
          {...defaultProps}
          providerDisplayName="Z.ai GLM"
          isGlobal={true}
          globalCredential={mockGlobalCredential}
        />
      );

      expect(screen.getByText(/Z.ai GLM/)).toBeDefined();
    });

    it('should use provider name in placeholder text', () => {
      render(
        <ProviderCredentialSection
          {...defaultProps}
          providerDisplayName="Anthropic"
          isGlobal={false}
        />
      );

      const apiKeyInput = screen.getByTestId('api-key-input') as HTMLInputElement;
      expect(apiKeyInput.placeholder).toContain('Anthropic');
    });
  });
});
