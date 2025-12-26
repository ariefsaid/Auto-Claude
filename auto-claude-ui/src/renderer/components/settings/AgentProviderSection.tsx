/**
 * AgentProviderSection component
 * Main provider selection UI for project settings
 *
 * Features:
 * - Agent provider dropdown (Claude Code vs OpenCode)
 * - Provider status badge showing configuration status
 * - Global/project credential toggle
 * - Dynamic OpenCode provider selector (populated from global credentials)
 * - Model override field
 * - "Add Provider" button for adding new providers to global settings
 * - Inline help tooltips for all fields
 */

import * as React from 'react';
import { Bot, HelpCircle, AlertCircle, Settings2 } from 'lucide-react';
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
  // Get configured providers from global settings
  const configuredProviders = React.useMemo(() => {
    return getConfiguredProviders(appSettings);
  }, [appSettings]);

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

    // If switching to OpenCode and no provider selected, select first configured
    if (newProvider === 'opencode' && !opencodeProvider && configuredProviders.length > 0) {
      onOpencodeProviderChange(configuredProviders[0]);
    }
  };

  // Handle OpenCode provider selection
  const handleOpencodeProviderChange = (providerId: string) => {
    onOpencodeProviderChange(providerId);

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

  // Handle model override change
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
  const hasConfiguredProviders = configuredProviders.length > 0;

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
          {/* No providers warning */}
          {!hasConfiguredProviders && (
            <div className="rounded-lg bg-warning/10 border border-warning/30 p-3">
              <div className="flex items-start gap-2">
                <AlertCircle className="h-4 w-4 text-warning mt-0.5 shrink-0" />
                <div className="flex-1">
                  <p className="text-sm font-medium text-foreground">
                    No providers configured
                  </p>
                  <p className="text-xs text-muted-foreground mt-1">
                    Add a provider in App Settings to use OpenCode.
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* OpenCode Provider Selector */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Label htmlFor="opencode-provider" className="text-sm font-medium">
                  LLM Provider
                </Label>
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <HelpCircle className="h-3.5 w-3.5 text-muted-foreground cursor-help" />
                    </TooltipTrigger>
                    <TooltipContent>
                      <p className="max-w-xs">
                        Select the LLM provider to use with OpenCode. Providers
                        must be configured in App Settings first.
                      </p>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              </div>
              <AddProviderDialog
                onAddProvider={handleAddProvider}
                disabled={disabled}
              />
            </div>
            <Select
              value={opencodeProvider || ''}
              onValueChange={handleOpencodeProviderChange}
              disabled={disabled || !hasConfiguredProviders}
            >
              <SelectTrigger
                id="opencode-provider"
                data-testid="opencode-provider-select"
              >
                <SelectValue placeholder="Select provider..." />
              </SelectTrigger>
              <SelectContent>
                {configuredProviders.map((providerId) => (
                  <SelectItem key={providerId} value={providerId}>
                    {getProviderDisplayName(appSettings, providerId)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

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

          {/* Model Override */}
          {opencodeProvider && (
            <div className="space-y-2" data-testid="model-section">
              <div className="flex items-center gap-2">
                <Settings2 className="h-4 w-4 text-muted-foreground" />
                <Label htmlFor="opencode-model" className="text-sm font-medium">
                  Model
                </Label>
                <span className="text-xs text-muted-foreground">(optional)</span>
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <HelpCircle className="h-3.5 w-3.5 text-muted-foreground cursor-help" />
                    </TooltipTrigger>
                    <TooltipContent>
                      <p className="max-w-xs">
                        Override the default model for this provider. Leave
                        empty to use the provider&apos;s default model.
                      </p>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              </div>
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
