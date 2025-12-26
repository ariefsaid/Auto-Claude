/**
 * Unit tests for AddProviderDialog component
 * Tests dialog behavior, form validation, template selection, and provider creation
 *
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { AddProviderDialog } from '../AddProviderDialog';
import type { ProviderCredential } from '@shared/types/provider';

describe('AddProviderDialog', () => {
  const mockOnAddProvider = vi.fn();

  beforeEach(() => {
    mockOnAddProvider.mockClear();
  });

  describe('Rendering', () => {
    it('should render default trigger button', () => {
      render(<AddProviderDialog onAddProvider={mockOnAddProvider} />);

      const trigger = screen.getByTestId('add-provider-trigger');
      expect(trigger).toBeDefined();
      expect(trigger.textContent).toContain('Add Provider');
    });

    it('should render custom trigger when provided', () => {
      render(
        <AddProviderDialog
          onAddProvider={mockOnAddProvider}
          trigger={<button data-testid="custom-trigger">Custom</button>}
        />
      );

      const trigger = screen.getByTestId('custom-trigger');
      expect(trigger).toBeDefined();
      expect(trigger.textContent).toBe('Custom');
    });

    it('should open dialog when trigger is clicked', async () => {
      render(<AddProviderDialog onAddProvider={mockOnAddProvider} />);

      const trigger = screen.getByTestId('add-provider-trigger');
      fireEvent.click(trigger);

      await waitFor(() => {
        const dialog = screen.getByTestId('add-provider-dialog');
        expect(dialog).toBeDefined();
      });
    });

    it('should render all form fields when dialog is open', () => {
      render(
        <AddProviderDialog onAddProvider={mockOnAddProvider} open={true} />
      );

      expect(screen.getByTestId('template-select-trigger')).toBeDefined();
      expect(screen.getByTestId('display-name-input')).toBeDefined();
      expect(screen.getByTestId('api-key-input')).toBeDefined();
      expect(screen.getByTestId('default-model-input')).toBeDefined();
      expect(screen.getByTestId('base-url-input')).toBeDefined();
      expect(screen.getByTestId('cancel-button')).toBeDefined();
      expect(screen.getByTestId('save-button')).toBeDefined();
    });

    it('should render dialog header correctly', () => {
      render(
        <AddProviderDialog onAddProvider={mockOnAddProvider} open={true} />
      );

      // Find the dialog title by role
      const title = screen.getByRole('heading', { name: 'Add Provider' });
      expect(title).toBeDefined();
      expect(
        screen.getByText(/Add a new LLM provider to your global settings/)
      ).toBeDefined();
    });
  });

  describe('Controlled Mode', () => {
    it('should be controlled when open prop is provided', () => {
      const onOpenChange = vi.fn();

      const { rerender } = render(
        <AddProviderDialog
          onAddProvider={mockOnAddProvider}
          open={false}
          onOpenChange={onOpenChange}
        />
      );

      // Dialog should not be visible
      expect(screen.queryByTestId('add-provider-dialog')).toBeNull();

      // Rerender with open=true
      rerender(
        <AddProviderDialog
          onAddProvider={mockOnAddProvider}
          open={true}
          onOpenChange={onOpenChange}
        />
      );

      // Dialog should now be visible
      expect(screen.getByTestId('add-provider-dialog')).toBeDefined();
    });

    it('should call onOpenChange when dialog is closed', () => {
      const onOpenChange = vi.fn();

      render(
        <AddProviderDialog
          onAddProvider={mockOnAddProvider}
          open={true}
          onOpenChange={onOpenChange}
        />
      );

      const cancelButton = screen.getByTestId('cancel-button');
      fireEvent.click(cancelButton);

      expect(onOpenChange).toHaveBeenCalledWith(false);
    });
  });

  describe('Template Selection', () => {
    it('should display template selector', () => {
      render(
        <AddProviderDialog onAddProvider={mockOnAddProvider} open={true} />
      );

      const templateTrigger = screen.getByTestId('template-select-trigger');
      expect(templateTrigger).toBeDefined();
    });

    // Note: Radix UI Select component has issues with scrollIntoView in jsdom
    // We test form auto-fill behavior through integration tests instead
    // The template selection functionality is tested through E2E tests
  });

  describe('Normalized ID Preview', () => {
    it('should show normalized ID as user types display name', async () => {
      render(
        <AddProviderDialog onAddProvider={mockOnAddProvider} open={true} />
      );

      const displayNameInput = screen.getByTestId('display-name-input');
      fireEvent.change(displayNameInput, { target: { value: 'OpenAI' } });

      await waitFor(() => {
        const normalizedPreview = screen.getByTestId('normalized-id-preview');
        expect(normalizedPreview.textContent).toContain('openai');
      });
    });

    it('should normalize complex names correctly', async () => {
      render(
        <AddProviderDialog onAddProvider={mockOnAddProvider} open={true} />
      );

      const displayNameInput = screen.getByTestId('display-name-input');
      fireEvent.change(displayNameInput, { target: { value: 'Z.ai GLM 4.7' } });

      await waitFor(() => {
        const normalizedPreview = screen.getByTestId('normalized-id-preview');
        expect(normalizedPreview.textContent).toContain('zai-glm-47');
      });
    });

    it('should not show normalized ID preview when display name is empty', () => {
      render(
        <AddProviderDialog onAddProvider={mockOnAddProvider} open={true} />
      );

      const normalizedPreview = screen.queryByTestId('normalized-id-preview');
      expect(normalizedPreview).toBeNull();
    });

    it('should handle whitespace in display name', async () => {
      render(
        <AddProviderDialog onAddProvider={mockOnAddProvider} open={true} />
      );

      const displayNameInput = screen.getByTestId('display-name-input');
      fireEvent.change(displayNameInput, { target: { value: '  Custom Provider  ' } });

      await waitFor(() => {
        const normalizedPreview = screen.getByTestId('normalized-id-preview');
        expect(normalizedPreview.textContent).toContain('custom-provider');
      });
    });
  });

  describe('Form Validation', () => {
    it('should disable save button when form is invalid', () => {
      render(
        <AddProviderDialog onAddProvider={mockOnAddProvider} open={true} />
      );

      const saveButton = screen.getByTestId('save-button') as HTMLButtonElement;
      expect(saveButton.disabled).toBe(true);
    });

    it('should enable save button when required fields are filled', async () => {
      render(
        <AddProviderDialog onAddProvider={mockOnAddProvider} open={true} />
      );

      const displayNameInput = screen.getByTestId('display-name-input');
      const apiKeyInput = screen.getByTestId('api-key-input');

      fireEvent.change(displayNameInput, { target: { value: 'Test Provider' } });
      fireEvent.change(apiKeyInput, { target: { value: 'test-api-key-12345' } });

      await waitFor(() => {
        const saveButton = screen.getByTestId('save-button') as HTMLButtonElement;
        expect(saveButton.disabled).toBe(false);
      });
    });

    it('should disable save button when only display name is filled', () => {
      render(
        <AddProviderDialog onAddProvider={mockOnAddProvider} open={true} />
      );

      const displayNameInput = screen.getByTestId('display-name-input');
      fireEvent.change(displayNameInput, { target: { value: 'Test Provider' } });

      const saveButton = screen.getByTestId('save-button') as HTMLButtonElement;
      expect(saveButton.disabled).toBe(true);
    });

    it('should disable save button when only API key is filled', () => {
      render(
        <AddProviderDialog onAddProvider={mockOnAddProvider} open={true} />
      );

      const apiKeyInput = screen.getByTestId('api-key-input');
      fireEvent.change(apiKeyInput, { target: { value: 'test-api-key' } });

      const saveButton = screen.getByTestId('save-button') as HTMLButtonElement;
      expect(saveButton.disabled).toBe(true);
    });

    it('should show API key format error for OpenAI', async () => {
      render(
        <AddProviderDialog onAddProvider={mockOnAddProvider} open={true} />
      );

      const displayNameInput = screen.getByTestId('display-name-input');
      const apiKeyInput = screen.getByTestId('api-key-input');

      fireEvent.change(displayNameInput, { target: { value: 'OpenAI' } });
      fireEvent.change(apiKeyInput, { target: { value: 'invalid-key' } });

      await waitFor(() => {
        const error = screen.getByTestId('api-key-error');
        expect(error.textContent).toContain('sk-');
      });
    });

    it('should accept valid OpenAI API key format', () => {
      render(
        <AddProviderDialog onAddProvider={mockOnAddProvider} open={true} />
      );

      const displayNameInput = screen.getByTestId('display-name-input');
      const apiKeyInput = screen.getByTestId('api-key-input');

      fireEvent.change(displayNameInput, { target: { value: 'OpenAI' } });
      fireEvent.change(apiKeyInput, { target: { value: 'sk-valid-key-12345' } });

      const error = screen.queryByTestId('api-key-error');
      expect(error).toBeNull();
    });

    it('should disable save button when API key has format error', () => {
      render(
        <AddProviderDialog onAddProvider={mockOnAddProvider} open={true} />
      );

      const displayNameInput = screen.getByTestId('display-name-input');
      const apiKeyInput = screen.getByTestId('api-key-input');

      fireEvent.change(displayNameInput, { target: { value: 'OpenAI' } });
      fireEvent.change(apiKeyInput, { target: { value: 'invalid-key' } });

      const saveButton = screen.getByTestId('save-button') as HTMLButtonElement;
      expect(saveButton.disabled).toBe(true);
    });
  });

  describe('Form Submission', () => {
    it('should call onAddProvider with correct data on submit', () => {
      render(
        <AddProviderDialog onAddProvider={mockOnAddProvider} open={true} />
      );

      const displayNameInput = screen.getByTestId('display-name-input');
      const apiKeyInput = screen.getByTestId('api-key-input');
      const modelInput = screen.getByTestId('default-model-input');
      const baseUrlInput = screen.getByTestId('base-url-input');

      fireEvent.change(displayNameInput, { target: { value: 'Test Provider' } });
      fireEvent.change(apiKeyInput, { target: { value: 'test-api-key-12345' } });
      fireEvent.change(modelInput, { target: { value: 'test-model' } });
      fireEvent.change(baseUrlInput, { target: { value: 'https://api.test.com/v1' } });

      const saveButton = screen.getByTestId('save-button');
      fireEvent.click(saveButton);

      expect(mockOnAddProvider).toHaveBeenCalledTimes(1);
      const credential = mockOnAddProvider.mock.calls[0][0] as ProviderCredential;

      expect(credential.provider).toBe('test-provider');
      expect(credential.displayName).toBe('Test Provider');
      expect(credential.apiKey).toBe('test-api-key-12345');
      expect(credential.defaultModel).toBe('test-model');
      expect(credential.baseUrl).toBe('https://api.test.com/v1');
      expect(credential.isGlobal).toBe(true);
    });

    it('should only include optional fields when filled', () => {
      render(
        <AddProviderDialog onAddProvider={mockOnAddProvider} open={true} />
      );

      const displayNameInput = screen.getByTestId('display-name-input');
      const apiKeyInput = screen.getByTestId('api-key-input');

      fireEvent.change(displayNameInput, { target: { value: 'Simple Provider' } });
      fireEvent.change(apiKeyInput, { target: { value: 'simple-key' } });

      const saveButton = screen.getByTestId('save-button');
      fireEvent.click(saveButton);

      const credential = mockOnAddProvider.mock.calls[0][0] as ProviderCredential;

      expect(credential.provider).toBe('simple-provider');
      expect(credential.displayName).toBe('Simple Provider');
      expect(credential.apiKey).toBe('simple-key');
      expect(credential.isGlobal).toBe(true);
      expect(credential.defaultModel).toBeUndefined();
      expect(credential.baseUrl).toBeUndefined();
    });

    it('should close dialog after successful submission', () => {
      const onOpenChange = vi.fn();

      render(
        <AddProviderDialog
          onAddProvider={mockOnAddProvider}
          open={true}
          onOpenChange={onOpenChange}
        />
      );

      const displayNameInput = screen.getByTestId('display-name-input');
      const apiKeyInput = screen.getByTestId('api-key-input');

      fireEvent.change(displayNameInput, { target: { value: 'Test' } });
      fireEvent.change(apiKeyInput, { target: { value: 'key' } });

      const saveButton = screen.getByTestId('save-button');
      fireEvent.click(saveButton);

      expect(onOpenChange).toHaveBeenCalledWith(false);
    });

    it('should trim whitespace from all fields before submission', () => {
      render(
        <AddProviderDialog onAddProvider={mockOnAddProvider} open={true} />
      );

      const displayNameInput = screen.getByTestId('display-name-input');
      const apiKeyInput = screen.getByTestId('api-key-input');
      const modelInput = screen.getByTestId('default-model-input');

      fireEvent.change(displayNameInput, { target: { value: '  Trimmed Provider  ' } });
      fireEvent.change(apiKeyInput, { target: { value: '  trimmed-key  ' } });
      fireEvent.change(modelInput, { target: { value: '  trimmed-model  ' } });

      const saveButton = screen.getByTestId('save-button');
      fireEvent.click(saveButton);

      const credential = mockOnAddProvider.mock.calls[0][0] as ProviderCredential;

      expect(credential.displayName).toBe('Trimmed Provider');
      expect(credential.apiKey).toBe('trimmed-key');
      expect(credential.defaultModel).toBe('trimmed-model');
    });
  });

  describe('Cancel Behavior', () => {
    it('should close dialog when cancel is clicked', () => {
      const onOpenChange = vi.fn();

      render(
        <AddProviderDialog
          onAddProvider={mockOnAddProvider}
          open={true}
          onOpenChange={onOpenChange}
        />
      );

      const cancelButton = screen.getByTestId('cancel-button');
      fireEvent.click(cancelButton);

      expect(onOpenChange).toHaveBeenCalledWith(false);
    });

    it('should not call onAddProvider when cancel is clicked', () => {
      render(
        <AddProviderDialog onAddProvider={mockOnAddProvider} open={true} />
      );

      const displayNameInput = screen.getByTestId('display-name-input');
      const apiKeyInput = screen.getByTestId('api-key-input');

      fireEvent.change(displayNameInput, { target: { value: 'Test' } });
      fireEvent.change(apiKeyInput, { target: { value: 'key' } });

      const cancelButton = screen.getByTestId('cancel-button');
      fireEvent.click(cancelButton);

      expect(mockOnAddProvider).not.toHaveBeenCalled();
    });
  });

  describe('Form Reset', () => {
    it('should reset form when cancel is clicked and dialog reopens', () => {
      const onOpenChange = vi.fn();

      const { rerender } = render(
        <AddProviderDialog
          onAddProvider={mockOnAddProvider}
          open={true}
          onOpenChange={onOpenChange}
        />
      );

      const displayNameInput = screen.getByTestId('display-name-input') as HTMLInputElement;
      fireEvent.change(displayNameInput, { target: { value: 'Test Provider' } });
      expect(displayNameInput.value).toBe('Test Provider');

      // Click cancel to close dialog (which triggers reset)
      const cancelButton = screen.getByTestId('cancel-button');
      fireEvent.click(cancelButton);

      expect(onOpenChange).toHaveBeenCalledWith(false);

      // Unmount and remount to simulate fresh dialog
      rerender(
        <AddProviderDialog
          onAddProvider={mockOnAddProvider}
          open={false}
          onOpenChange={onOpenChange}
        />
      );

      rerender(
        <AddProviderDialog
          onAddProvider={mockOnAddProvider}
          open={true}
          onOpenChange={onOpenChange}
        />
      );

      // Form should be reset
      const newDisplayNameInput = screen.getByTestId('display-name-input') as HTMLInputElement;
      expect(newDisplayNameInput.value).toBe('');
    });
  });

  describe('Disabled State', () => {
    it('should disable trigger button when disabled prop is true', () => {
      render(
        <AddProviderDialog onAddProvider={mockOnAddProvider} disabled={true} />
      );

      const trigger = screen.getByTestId('add-provider-trigger') as HTMLButtonElement;
      expect(trigger.disabled).toBe(true);
    });
  });

  describe('Accessibility', () => {
    it('should have proper labels for all form fields', () => {
      render(
        <AddProviderDialog onAddProvider={mockOnAddProvider} open={true} />
      );

      expect(screen.getByLabelText(/display name/i)).toBeDefined();
      expect(screen.getByLabelText(/api key/i)).toBeDefined();
      expect(screen.getByLabelText(/default model/i)).toBeDefined();
      expect(screen.getByLabelText(/base url/i)).toBeDefined();
    });

    it('should have data-testid on all interactive elements', () => {
      render(
        <AddProviderDialog onAddProvider={mockOnAddProvider} open={true} />
      );

      expect(screen.getByTestId('add-provider-dialog')).toBeDefined();
      expect(screen.getByTestId('template-select-trigger')).toBeDefined();
      expect(screen.getByTestId('display-name-input')).toBeDefined();
      expect(screen.getByTestId('api-key-input')).toBeDefined();
      expect(screen.getByTestId('default-model-input')).toBeDefined();
      expect(screen.getByTestId('base-url-input')).toBeDefined();
      expect(screen.getByTestId('cancel-button')).toBeDefined();
      expect(screen.getByTestId('save-button')).toBeDefined();
    });
  });

  describe('Custom className', () => {
    it('should accept custom className', () => {
      render(
        <AddProviderDialog
          onAddProvider={mockOnAddProvider}
          open={true}
          className="custom-dialog-class"
        />
      );

      const dialog = screen.getByTestId('add-provider-dialog');
      expect(dialog.className).toContain('custom-dialog-class');
    });
  });

  describe('Normalization Edge Cases', () => {
    it('should handle special characters', async () => {
      render(
        <AddProviderDialog onAddProvider={mockOnAddProvider} open={true} />
      );

      const displayNameInput = screen.getByTestId('display-name-input');
      fireEvent.change(displayNameInput, { target: { value: 'Z.ai GLM 4.7!@#' } });

      await waitFor(() => {
        const normalizedPreview = screen.getByTestId('normalized-id-preview');
        expect(normalizedPreview.textContent).toContain('zai-glm-47');
      });
    });

    it('should handle multiple dashes', async () => {
      render(
        <AddProviderDialog onAddProvider={mockOnAddProvider} open={true} />
      );

      const displayNameInput = screen.getByTestId('display-name-input');
      fireEvent.change(displayNameInput, { target: { value: 'Custom---Provider' } });

      await waitFor(() => {
        const normalizedPreview = screen.getByTestId('normalized-id-preview');
        expect(normalizedPreview.textContent).toContain('custom-provider');
      });
    });

    it('should handle leading/trailing spaces', async () => {
      render(
        <AddProviderDialog onAddProvider={mockOnAddProvider} open={true} />
      );

      const displayNameInput = screen.getByTestId('display-name-input');
      fireEvent.change(displayNameInput, { target: { value: '  OpenAI  ' } });

      await waitFor(() => {
        const normalizedPreview = screen.getByTestId('normalized-id-preview');
        expect(normalizedPreview.textContent).toContain('openai');
      });
    });
  });

  describe('API Key Validation for Different Providers', () => {
    it('should validate Anthropic API key format', async () => {
      render(
        <AddProviderDialog onAddProvider={mockOnAddProvider} open={true} />
      );

      const displayNameInput = screen.getByTestId('display-name-input');
      const apiKeyInput = screen.getByTestId('api-key-input');

      fireEvent.change(displayNameInput, { target: { value: 'Anthropic' } });
      fireEvent.change(apiKeyInput, { target: { value: 'invalid-key' } });

      await waitFor(() => {
        const error = screen.getByTestId('api-key-error');
        expect(error.textContent).toContain('sk-ant-');
      });
    });

    it('should accept any key format for unknown providers', () => {
      render(
        <AddProviderDialog onAddProvider={mockOnAddProvider} open={true} />
      );

      const displayNameInput = screen.getByTestId('display-name-input');
      const apiKeyInput = screen.getByTestId('api-key-input');

      fireEvent.change(displayNameInput, { target: { value: 'Custom Provider' } });
      fireEvent.change(apiKeyInput, { target: { value: 'any-format-key' } });

      const error = screen.queryByTestId('api-key-error');
      expect(error).toBeNull();
    });
  });
});
