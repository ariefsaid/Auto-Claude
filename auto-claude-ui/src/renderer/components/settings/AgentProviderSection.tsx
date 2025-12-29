/**
 * AgentProviderSection component
 * Main provider selection UI for project settings
 *
 * Features:
 * - Agent provider dropdown (Claude Code vs OpenCode)
 * - Provider status badge showing configuration status
 * - Global/project credential toggle
 * - Dynamic OpenCode provider/model selector (populated from `opencode models` CLI)
 * - No API key management needed - OpenCode handles credentials
 * - Inline help tooltips for all fields
 */

import * as React from 'react';
import { Bot, HelpCircle, AlertCircle, Settings2, RefreshCw, Loader2 } from 'lucide-react';
import { Label } from '../ui/label';
import { Input } from '../ui/input';
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
import { ProviderStatusBadge } from './ProviderStatusBadge';
import { ProviderCredentialSection } from './ProviderCredentialSection';
import { AddProviderDialog } from './AddProviderDialog';
import {
  getGlobalCredential,
  getConfiguredProviders,
  getProviderDisplayName,
  normalizeProviderId,
} from '../../utils/providerCredentials';
import {
  AGENT_PROVIDER_OPTIONS,
  DEFAULT_AGENT_PROVIDER,
} from '@shared/constants/providers';
import type {
  AgentProviderType,
  ProviderCredential,
  CredentialReference,
  ProviderCredentialsStore,
  ProviderStatus,
} from '@shared/types/provider';
import type { AppSettings } from '@shared/types/settings';
import { Button } from '../ui/button';

/** Model info from OpenCode CLI */
interface OpenCodeModel {
  provider: string;
  model: string;
  fullId: string;
}

export interface AgentProviderSectionProps {
  /** Current agent provider type (claude_code or opencode) */
  agentProvider: AgentProviderType;
  /** Callback when agent provider changes */
  onAgentProviderChange: (provider: AgentProviderType) => void;
  /** Whether using global credentials */
  isGlobal: boolean;
  /** Callback when global/project toggle changes */
  onGlobalChange: (isGlobal: boolean) => void;
  /** Current OpenCode provider ID (for opencode agent type) */
  opencodeProvider?: string;
  /** Callback when OpenCode provider changes */
  onOpencodeProviderChange: (providerId: string) => void;
  /** Current model override */
  opencodeModel?: string;
  /** Callback when model override changes */
  onOpencodeModelChange: (model: string) => void;
  /** Provider credentials store from project config */
  providerCredentials?: ProviderCredentialsStore;
  /** Callback when provider credentials change */
  onProviderCredentialsChange: (credentials: ProviderCredentialsStore) => void;
  /** Global app settings (for accessing global credentials) */
  appSettings?: AppSettings | null;
  /** Callback when a new provider is added to global settings */
  onAddGlobalProvider?: (credential: ProviderCredential) => void;
  /** Whether the section is disabled */
  disabled?: boolean;
  /** Additional CSS classes */
  className?: string;
}

/**
 * Determine provider status based on current configuration
 */
function getProviderStatus(
  agentProvider: AgentProviderType,
  isGlobal: boolean,
  opencodeProvider: string | undefined,
  providerCredentials: ProviderCredentialsStore | undefined,
  appSettings: AppSettings | null | undefined
): { status: ProviderStatus; errorMessage?: string } {
  // Claude Code is always configured (uses Claude CLI auth)
  if (agentProvider === 'claude_code') {
    return { status: 'configured' };
  }

  // OpenCode requires a provider to be selected
  if (!opencodeProvider) {
    return { status: 'not_configured', errorMessage: 'No provider selected' };
  }

  // Check if credentials are available
  if (isGlobal) {
    const globalCred = getGlobalCredential(appSettings, opencodeProvider);
    if (!globalCred) {
      return {
        status: 'error',
        errorMessage: `Global credential '${opencodeProvider}' not found`,
      };
    }
    return { status: 'configured' };
  }

  // Check project-specific credentials
  const credRef = providerCredentials?.[opencodeProvider];
  if (!credRef || (!credRef.isGlobal && !credRef.apiKey)) {
    return {
      status: 'not_configured',
      errorMessage: 'API key required',
    };
  }

  return { status: 'configured' };
}

/**
 * AgentProviderSection - Main provider selection UI
 *
 * @example
 * <AgentProviderSection
 *   agentProvider="claude_code"
 *   onAgentProviderChange={setAgentProvider}
 *   isGlobal={true}
 *   onGlobalChange={setIsGlobal}
 *   opencodeProvider="openai"
 *   onOpencodeProviderChange={setOpencodeProvider}
 *   opencodeModel=""
 *   onOpencodeModelChange={setOpencodeModel}
 *   providerCredentials={credentials}
 *   onProviderCredentialsChange={setCredentials}
 *   appSettings={appSettings}
 *   onAddGlobalProvider={handleAddProvider}
 * />
 */
export function AgentProviderSection({
  agentProvider,
  onAgentProviderChange,
  isGlobal,
  onGlobalChange,
  opencodeProvider,
  onOpencodeProviderChange,
  opencodeModel,
  onOpencodeModelChange,
  providerCredentials,
  onProviderCredentialsChange,
  appSettings,
  onAddGlobalProvider,
  disabled = false,
  className,
}: AgentProviderSectionProps) {
  // State for dynamic OpenCode models from CLI
  const [openCodeModels, setOpenCodeModels] = React.useState<OpenCodeModel[]>([]);
  const [openCodeProviders, setOpenCodeProviders] = React.useState<string[]>([]);
  const [isLoadingModels, setIsLoadingModels] = React.useState(false);
  const [modelsError, setModelsError] = React.useState<string | null>(null);

  // Fetch OpenCode models from CLI when component mounts or when switching to OpenCode
  const fetchOpenCodeModels = React.useCallback(async () => {
    if (!window.electronAPI?.getOpenCodeModels) {
      // Fallback to legacy configured providers
      return;
    }

    setIsLoadingModels(true);
    setModelsError(null);

    try {
      const result = await window.electronAPI.getOpenCodeModels();
      if (result.success && result.data) {
        setOpenCodeModels(result.data.models || []);
        setOpenCodeProviders(result.data.providers || []);
      } else {
        setModelsError(result.error || 'Failed to fetch models');
      }
    } catch (error) {
      setModelsError(error instanceof Error ? error.message : 'Unknown error');
    } finally {
      setIsLoadingModels(false);
    }
  }, []);

  // Note: Models are only fetched when user clicks the Refresh button
  // No auto-fetch on mount to avoid unnecessary API calls

  // Get configured providers from global settings (legacy fallback)
  const configuredProviders = React.useMemo(() => {
    return getConfiguredProviders(appSettings);
  }, [appSettings]);

  // Use dynamic providers if available, otherwise fall back to configured
  const availableProviders = openCodeProviders.length > 0 ? openCodeProviders : configuredProviders;

  // Get models for currently selected provider
  const modelsForProvider = React.useMemo(() => {
    if (!opencodeProvider) return [];
    return openCodeModels.filter(m => m.provider === opencodeProvider);
  }, [openCodeModels, opencodeProvider]);

  // Get current provider status
  const { status: providerStatus, errorMessage } = React.useMemo(() => {
    return getProviderStatus(
      agentProvider,
      isGlobal,
      opencodeProvider,
      providerCredentials,
      appSettings
    );
  }, [agentProvider, isGlobal, opencodeProvider, providerCredentials, appSettings]);

  // Handle agent provider type change
  const handleAgentProviderChange = (value: string) => {
    const newProvider = value as AgentProviderType;
    onAgentProviderChange(newProvider);

    // If switching to OpenCode and no provider selected, select first available
    if (newProvider === 'opencode' && !opencodeProvider && availableProviders.length > 0) {
      onOpencodeProviderChange(availableProviders[0]);
    }
  };

  // Handle OpenCode provider selection (from dynamic list)
  const handleOpencodeProviderChange = (providerId: string) => {
    // providerId is the exact provider ID from `opencode models` (e.g., "zai-coding-plan")
    onOpencodeProviderChange(providerId);

    // Clear model selection when provider changes
    onOpencodeModelChange('');

    // Update provider credentials store with the new selection
    const normalizedId = normalizeProviderId(providerId);
    const currentRef = providerCredentials?.[normalizedId];

    // If switching providers, create a new credential reference
    if (!currentRef) {
      onProviderCredentialsChange({
        ...providerCredentials,
        [normalizedId]: {
          isGlobal: isGlobal,
        },
      });
    }
  };

  // Handle model selection (from dynamic list or manual input)
  const handleModelSelect = (modelId: string) => {
    onOpencodeModelChange(modelId);
  };

  // Handle manual model input
  const handleModelChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onOpencodeModelChange(e.target.value || '');
  };

  // Handle credential reference change from ProviderCredentialSection
  const handleCredentialChange = (ref: CredentialReference) => {
    if (!opencodeProvider) return;

    const normalizedId = normalizeProviderId(opencodeProvider);
    onProviderCredentialsChange({
      ...providerCredentials,
      [normalizedId]: ref,
    });
  };

  // Handle adding a new provider to global settings
  const handleAddProvider = (credential: ProviderCredential) => {
    onAddGlobalProvider?.(credential);

    // If this is the first provider and OpenCode is selected, auto-select it
    if (
      agentProvider === 'opencode' &&
      !opencodeProvider &&
      configuredProviders.length === 0
    ) {
      onOpencodeProviderChange(credential.provider);
    }
  };

  // Get the current credential reference for the selected OpenCode provider
  const currentCredentialRef = opencodeProvider
    ? providerCredentials?.[normalizeProviderId(opencodeProvider)]
    : undefined;

  // Get the global credential for the selected OpenCode provider
  const globalCredential = opencodeProvider
    ? getGlobalCredential(appSettings, opencodeProvider)
    : undefined;

  // Get display name for the selected provider
  const selectedProviderDisplayName = opencodeProvider
    ? getProviderDisplayName(appSettings, opencodeProvider)
    : '';

  const isOpenCode = agentProvider === 'opencode';
  const hasAvailableProviders = availableProviders.length > 0;
  const hasDynamicModels = openCodeModels.length > 0;

  return (
    <section
      className={cn('space-y-4', className)}
      data-testid="agent-provider-section"
    >
      {/* Section Header */}
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-foreground flex items-center gap-2">
          <Bot className="h-4 w-4 text-muted-foreground" />
          Agent Provider
        </h3>
        <ProviderStatusBadge
          status={providerStatus}
          errorMessage={errorMessage}
          data-testid="provider-status"
        />
      </div>

      {/* Agent Provider Type Selector */}
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <Label htmlFor="agent-provider" className="text-sm font-medium">
            Provider Type
          </Label>
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <HelpCircle className="h-3.5 w-3.5 text-muted-foreground cursor-help" />
              </TooltipTrigger>
              <TooltipContent>
                <p className="max-w-xs">
                  Choose between Claude Code (official SDK) or OpenCode
                  (multi-provider CLI supporting 20+ LLM providers).
                </p>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>
        <Select
          value={agentProvider || DEFAULT_AGENT_PROVIDER}
          onValueChange={handleAgentProviderChange}
          disabled={disabled}
        >
          <SelectTrigger id="agent-provider" data-testid="agent-provider-select">
            <SelectValue placeholder="Select provider..." />
          </SelectTrigger>
          <SelectContent>
            {AGENT_PROVIDER_OPTIONS.map((option) => (
              <SelectItem key={option.value} value={option.value}>
                <div className="flex flex-col">
                  <span>{option.label}</span>
                  <span className="text-xs text-muted-foreground">
                    {option.description}
                  </span>
                </div>
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* OpenCode-specific configuration */}
      {isOpenCode && (
        <div className="rounded-lg border border-border bg-muted/30 p-4 space-y-4">
          {/* Loading state */}
          {isLoadingModels && (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading available models from OpenCode...
            </div>
          )}

          {/* Error state */}
          {modelsError && !isLoadingModels && (
            <div className="rounded-lg bg-destructive/10 border border-destructive/30 p-3">
              <div className="flex items-start gap-2">
                <AlertCircle className="h-4 w-4 text-destructive mt-0.5 shrink-0" />
                <div className="flex-1">
                  <p className="text-sm font-medium text-foreground">
                    Failed to fetch OpenCode models
                  </p>
                  <p className="text-xs text-muted-foreground mt-1">
                    {modelsError}
                  </p>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="mt-2 h-7 text-xs"
                    onClick={fetchOpenCodeModels}
                  >
                    <RefreshCw className="h-3 w-3 mr-1" />
                    Retry
                  </Button>
                </div>
              </div>
            </div>
          )}

          {/* No providers warning (only if no dynamic models and not loading) */}
          {!hasAvailableProviders && !isLoadingModels && !modelsError && (
            <div className="rounded-lg bg-warning/10 border border-warning/30 p-3">
              <div className="flex items-start gap-2">
                <AlertCircle className="h-4 w-4 text-warning mt-0.5 shrink-0" />
                <div className="flex-1">
                  <p className="text-sm font-medium text-foreground">
                    No providers available
                  </p>
                  <p className="text-xs text-muted-foreground mt-1">
                    OpenCode CLI not found or no models configured.
                    Make sure OpenCode is installed and configured.
                  </p>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="mt-2 h-7 text-xs"
                    onClick={fetchOpenCodeModels}
                  >
                    <RefreshCw className="h-3 w-3 mr-1" />
                    Refresh
                  </Button>
                </div>
              </div>
            </div>
          )}

          {/* OpenCode Provider Selector */}
          {hasAvailableProviders && !isLoadingModels && (
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Label htmlFor="opencode-provider" className="text-sm font-medium">
                    Provider
                  </Label>
                  <TooltipProvider>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <HelpCircle className="h-3.5 w-3.5 text-muted-foreground cursor-help" />
                      </TooltipTrigger>
                      <TooltipContent>
                        <p className="max-w-xs">
                          Select the LLM provider from OpenCode. These are fetched
                          dynamically from your OpenCode installation.
                        </p>
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-7 text-xs"
                  onClick={fetchOpenCodeModels}
                  disabled={isLoadingModels}
                >
                  <RefreshCw className={cn("h-3 w-3 mr-1", isLoadingModels && "animate-spin")} />
                  Refresh
                </Button>
              </div>
              <Select
                value={opencodeProvider || ''}
                onValueChange={handleOpencodeProviderChange}
                disabled={disabled}
              >
                <SelectTrigger
                  id="opencode-provider"
                  data-testid="opencode-provider-select"
                >
                  <SelectValue placeholder="Select provider..." />
                </SelectTrigger>
                <SelectContent>
                  {availableProviders.map((providerId) => (
                    <SelectItem key={providerId} value={providerId}>
                      {providerId}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}

          {/* Credential Section - Only show when provider is selected */}
          {opencodeProvider && (
            <ProviderCredentialSection
              providerId={opencodeProvider}
              providerDisplayName={selectedProviderDisplayName}
              isGlobal={currentCredentialRef?.isGlobal ?? isGlobal}
              onGlobalChange={(newIsGlobal) => {
                onGlobalChange(newIsGlobal);
                handleCredentialChange({
                  ...currentCredentialRef,
                  isGlobal: newIsGlobal,
                });
              }}
              globalCredential={globalCredential}
              credentialRef={currentCredentialRef}
              onCredentialChange={handleCredentialChange}
              disabled={disabled}
            />
          )}

          {/* Model Selection */}
          {opencodeProvider && !isLoadingModels && (
            <div className="space-y-2" data-testid="model-section">
              <div className="flex items-center gap-2">
                <Settings2 className="h-4 w-4 text-muted-foreground" />
                <Label htmlFor="opencode-model" className="text-sm font-medium">
                  Model
                </Label>
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <HelpCircle className="h-3.5 w-3.5 text-muted-foreground cursor-help" />
                    </TooltipTrigger>
                    <TooltipContent>
                      <p className="max-w-xs">
                        Select a model from the available options, or enter a
                        custom model name.
                      </p>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              </div>

              {/* Show dropdown if we have dynamic models for this provider */}
              {modelsForProvider.length > 0 ? (
                <Select
                  value={opencodeModel || ''}
                  onValueChange={handleModelSelect}
                  disabled={disabled}
                >
                  <SelectTrigger
                    id="opencode-model"
                    data-testid="opencode-model-select"
                  >
                    <SelectValue placeholder="Select model..." />
                  </SelectTrigger>
                  <SelectContent>
                    {modelsForProvider.map((m) => (
                      <SelectItem key={m.fullId} value={m.model}>
                        {m.model}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              ) : (
                /* Fallback to text input if no dynamic models */
                <Input
                  id="opencode-model"
                  type="text"
                  placeholder={
                    globalCredential?.defaultModel
                      ? `Default: ${globalCredential.defaultModel}`
                      : 'e.g., gpt-4o, claude-3-sonnet'
                  }
                  value={opencodeModel || ''}
                  onChange={handleModelChange}
                  disabled={disabled}
                  data-testid="opencode-model-input"
                />
              )}

              {/* Show selected full ID for clarity */}
              {opencodeProvider && opencodeModel && (
                <p className="text-xs text-muted-foreground">
                  Full model ID: <code className="bg-muted px-1 rounded">{opencodeProvider}/{opencodeModel}</code>
                </p>
              )}
            </div>
          )}
        </div>
      )}

      {/* Claude Code info */}
      {!isOpenCode && (
        <div className="rounded-lg border border-border bg-muted/30 p-4">
          <div className="flex items-start gap-3">
            <Bot className="h-5 w-5 text-primary mt-0.5 shrink-0" />
            <div>
              <p className="text-sm font-medium text-foreground">
                Claude Code SDK
              </p>
              <p className="text-xs text-muted-foreground mt-1">
                Uses the official Claude Code SDK with your Claude CLI
                authentication. Configure your Claude credentials in the
                Environment section below.
              </p>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}

export default AgentProviderSection;
