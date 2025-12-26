/**
 * AddProviderDialog component
 * Dialog for adding new provider credentials to global settings
 *
 * Features:
 * - Display name input with real-time normalized ID preview
 * - API key input with format validation
 * - Optional model and base URL override inputs
 * - Quick setup with suggested provider templates
 * - Saves provider credentials to global settings
 */

import * as React from 'react';
import { Plus, Sparkles, Key, Settings2, Globe, HelpCircle } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '../ui/dialog';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Badge } from '../ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../ui/select';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '../ui/tooltip';
import { cn } from '../../lib/utils';
import { normalizeProviderId, validateApiKeyFormat } from '../../utils/providerCredentials';
import { SUGGESTED_PROVIDER_TEMPLATES } from '@shared/constants/providers';
import type { ProviderCredential, SuggestedProviderTemplate } from '@shared/types/provider';

export interface AddProviderDialogProps {
  /** Callback when a new provider is added */
  onAddProvider: (credential: ProviderCredential) => void;
  /** Whether the dialog is open (controlled mode) */
  open?: boolean;
  /** Callback when dialog open state changes (controlled mode) */
  onOpenChange?: (open: boolean) => void;
  /** Trigger element (if not controlled) */
  trigger?: React.ReactNode;
  /** Whether the dialog is disabled */
  disabled?: boolean;
  /** Additional CSS classes */
  className?: string;
}

interface FormState {
  displayName: string;
  apiKey: string;
  defaultModel: string;
  baseUrl: string;
}

const CUSTOM_PROVIDER_VALUE = '__custom__';

/**
 * AddProviderDialog - Modal dialog for adding new provider credentials
 *
 * @example
 * // Uncontrolled mode with default trigger
 * <AddProviderDialog
 *   onAddProvider={(credential) => saveToSettings(credential)}
 * />
 *
 * @example
 * // Controlled mode with custom trigger
 * <AddProviderDialog
 *   open={isOpen}
 *   onOpenChange={setIsOpen}
 *   onAddProvider={(credential) => saveToSettings(credential)}
 *   trigger={<Button variant="outline">Add New Provider</Button>}
 * />
 */
export function AddProviderDialog({
  onAddProvider,
  open,
  onOpenChange,
  trigger,
  disabled = false,
  className,
}: AddProviderDialogProps) {
  // Internal open state for uncontrolled mode
  const [internalOpen, setInternalOpen] = React.useState(false);
  const isControlled = open !== undefined;
  const isOpen = isControlled ? open : internalOpen;

  const handleOpenChange = (newOpen: boolean) => {
    if (isControlled) {
      onOpenChange?.(newOpen);
    } else {
      setInternalOpen(newOpen);
    }

    // Reset form when dialog closes
    if (!newOpen) {
      resetForm();
    }
  };

  // Form state
  const [formState, setFormState] = React.useState<FormState>({
    displayName: '',
    apiKey: '',
    defaultModel: '',
    baseUrl: '',
  });

  // Selected template for quick setup
  const [selectedTemplate, setSelectedTemplate] = React.useState<string>('');

  // Validation state
  const [apiKeyError, setApiKeyError] = React.useState<string | null>(null);

  // Computed normalized ID
  const normalizedId = React.useMemo(() => {
    if (!formState.displayName.trim()) {
      return '';
    }
    return normalizeProviderId(formState.displayName);
  }, [formState.displayName]);

  // Reset form to initial state
  const resetForm = () => {
    setFormState({
      displayName: '',
      apiKey: '',
      defaultModel: '',
      baseUrl: '',
    });
    setSelectedTemplate('');
    setApiKeyError(null);
  };

  // Handle template selection
  const handleTemplateChange = (value: string) => {
    setSelectedTemplate(value);

    if (value === CUSTOM_PROVIDER_VALUE) {
      // Reset to empty for custom provider
      setFormState({
        displayName: '',
        apiKey: '',
        defaultModel: '',
        baseUrl: '',
      });
      setApiKeyError(null);
      return;
    }

    // Find the selected template
    const template = SUGGESTED_PROVIDER_TEMPLATES.find(
      (t) => t.normalizedId === value
    );

    if (template) {
      setFormState({
        displayName: template.displayName,
        apiKey: '',
        defaultModel: template.defaultModel,
        baseUrl: template.baseUrl || '',
      });
      setApiKeyError(null);
    }
  };

  // Handle display name change
  const handleDisplayNameChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newName = e.target.value;
    setFormState((prev) => ({ ...prev, displayName: newName }));

    // Clear template selection if user modifies the name
    if (selectedTemplate && selectedTemplate !== CUSTOM_PROVIDER_VALUE) {
      const template = SUGGESTED_PROVIDER_TEMPLATES.find(
        (t) => t.normalizedId === selectedTemplate
      );
      if (template && template.displayName !== newName) {
        setSelectedTemplate(CUSTOM_PROVIDER_VALUE);
      }
    }
  };

  // Handle API key change with validation
  const handleApiKeyChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newApiKey = e.target.value;
    setFormState((prev) => ({ ...prev, apiKey: newApiKey }));

    // Validate API key format if we have a normalized ID
    if (normalizedId && newApiKey) {
      const error = validateApiKeyFormat(normalizedId, newApiKey);
      setApiKeyError(error);
    } else {
      setApiKeyError(null);
    }
  };

  // Handle model change
  const handleModelChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormState((prev) => ({ ...prev, defaultModel: e.target.value }));
  };

  // Handle base URL change
  const handleBaseUrlChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormState((prev) => ({ ...prev, baseUrl: e.target.value }));
  };

  // Check if form is valid for submission
  const isFormValid = React.useMemo(() => {
    if (!formState.displayName.trim()) return false;
    if (!formState.apiKey.trim()) return false;
    if (apiKeyError) return false;
    return true;
  }, [formState.displayName, formState.apiKey, apiKeyError]);

  // Handle form submission
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    if (!isFormValid) return;

    const credential: ProviderCredential = {
      provider: normalizedId,
      displayName: formState.displayName.trim(),
      apiKey: formState.apiKey.trim(),
      isGlobal: true,
      ...(formState.defaultModel.trim() && {
        defaultModel: formState.defaultModel.trim(),
      }),
      ...(formState.baseUrl.trim() && {
        baseUrl: formState.baseUrl.trim(),
      }),
    };

    onAddProvider(credential);
    handleOpenChange(false);
  };

  // Default trigger button
  const defaultTrigger = (
    <Button
      variant="outline"
      size="sm"
      disabled={disabled}
      data-testid="add-provider-trigger"
    >
      <Plus className="h-4 w-4 mr-2" />
      Add Provider
    </Button>
  );

  return (
    <Dialog open={isOpen} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>{trigger || defaultTrigger}</DialogTrigger>
      <DialogContent
        className={cn('max-w-md', className)}
        data-testid="add-provider-dialog"
      >
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Plus className="h-5 w-5" />
              Add Provider
            </DialogTitle>
            <DialogDescription>
              Add a new LLM provider to your global settings. These credentials
              can be shared across all projects.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            {/* Template Selector */}
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-muted-foreground" />
                <Label htmlFor="template-select" className="text-sm font-medium">
                  Quick Setup
                </Label>
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <HelpCircle className="h-3.5 w-3.5 text-muted-foreground cursor-help" />
                    </TooltipTrigger>
                    <TooltipContent>
                      <p className="max-w-xs">
                        Select a provider template to auto-fill configuration,
                        or choose Custom to add any provider.
                      </p>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              </div>
              <Select
                value={selectedTemplate}
                onValueChange={handleTemplateChange}
                data-testid="template-select"
              >
                <SelectTrigger id="template-select" data-testid="template-select-trigger">
                  <SelectValue placeholder="Select a provider or start fresh..." />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={CUSTOM_PROVIDER_VALUE}>
                    Custom Provider
                  </SelectItem>
                  {SUGGESTED_PROVIDER_TEMPLATES.map((template) => (
                    <SelectItem
                      key={template.normalizedId}
                      value={template.normalizedId}
                    >
                      {template.displayName}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Display Name */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label htmlFor="display-name" className="text-sm font-medium">
                  Display Name
                </Label>
                {normalizedId && (
                  <Badge
                    variant="secondary"
                    className="text-xs font-mono"
                    data-testid="normalized-id-preview"
                  >
                    ID: {normalizedId}
                  </Badge>
                )}
              </div>
              <Input
                id="display-name"
                placeholder="e.g., OpenAI, Z.ai GLM, Custom Provider"
                value={formState.displayName}
                onChange={handleDisplayNameChange}
                data-testid="display-name-input"
              />
              <p className="text-xs text-muted-foreground">
                The name shown in the UI. A normalized ID will be generated
                automatically.
              </p>
            </div>

            {/* API Key */}
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <Key className="h-4 w-4 text-muted-foreground" />
                <Label htmlFor="api-key" className="text-sm font-medium">
                  API Key
                </Label>
              </div>
              <Input
                id="api-key"
                type="password"
                placeholder={
                  selectedTemplate && selectedTemplate !== CUSTOM_PROVIDER_VALUE
                    ? SUGGESTED_PROVIDER_TEMPLATES.find(
                        (t) => t.normalizedId === selectedTemplate
                      )?.apiKeyPlaceholder || 'Enter API key...'
                    : 'Enter API key...'
                }
                value={formState.apiKey}
                onChange={handleApiKeyChange}
                className={cn(apiKeyError && 'border-destructive')}
                data-testid="api-key-input"
              />
              {apiKeyError ? (
                <p className="text-xs text-destructive" data-testid="api-key-error">
                  {apiKeyError}
                </p>
              ) : (
                <p className="text-xs text-muted-foreground">
                  Your API key is stored securely in global settings.
                </p>
              )}
            </div>

            {/* Default Model */}
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <Settings2 className="h-4 w-4 text-muted-foreground" />
                <Label htmlFor="default-model" className="text-sm font-medium">
                  Default Model
                </Label>
                <span className="text-xs text-muted-foreground">(optional)</span>
              </div>
              <Input
                id="default-model"
                placeholder="e.g., gpt-4o, claude-3-sonnet, llama-3.1-70b"
                value={formState.defaultModel}
                onChange={handleModelChange}
                data-testid="default-model-input"
              />
            </div>

            {/* Base URL */}
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <Globe className="h-4 w-4 text-muted-foreground" />
                <Label htmlFor="base-url" className="text-sm font-medium">
                  Base URL
                </Label>
                <span className="text-xs text-muted-foreground">(optional)</span>
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <HelpCircle className="h-3.5 w-3.5 text-muted-foreground cursor-help" />
                    </TooltipTrigger>
                    <TooltipContent>
                      <p className="max-w-xs">
                        Override the default API endpoint for self-hosted
                        providers or API proxies.
                      </p>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              </div>
              <Input
                id="base-url"
                type="url"
                placeholder="https://api.example.com/v1"
                value={formState.baseUrl}
                onChange={handleBaseUrlChange}
                data-testid="base-url-input"
              />
            </div>
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => handleOpenChange(false)}
              data-testid="cancel-button"
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={!isFormValid}
              data-testid="save-button"
            >
              <Plus className="h-4 w-4 mr-2" />
              Add Provider
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export default AddProviderDialog;
