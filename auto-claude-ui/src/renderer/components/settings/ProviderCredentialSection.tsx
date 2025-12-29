/**
 * ProviderCredentialSection component
 * Handles global/project credential toggle and credential source badge display
 *
 * Features:
 * - Toggle between global and project-specific credentials
 * - Source badge showing "Using Global" vs "Project Override"
 * - API key input shown only when using project-specific credentials
 * - Model override option for both global and project credentials
 * - Base URL override for custom/self-hosted providers
 */

import * as React from 'react';
import { Globe, FileText, Key, Settings2 } from 'lucide-react';
import { Switch } from '../ui/switch';
import { Label } from '../ui/label';
import { Badge } from '../ui/badge';
import { Input } from '../ui/input';
import { cn } from '../../lib/utils';
import type { CredentialReference, ProviderCredential } from '@shared/types/provider';
import {
  CREDENTIAL_SOURCE_LABELS,
  CREDENTIAL_SOURCE_VARIANTS,
} from '@shared/constants/providers';

export type CredentialSource = 'global' | 'project' | 'missing';

export interface ProviderCredentialSectionProps {
  /** Normalized provider ID (e.g., 'openai', 'zai-glm') */
  providerId: string;
  /** Display name of the provider (e.g., 'OpenAI', 'Z.ai GLM') */
  providerDisplayName: string;
  /** Whether using global credentials (true) or project-specific (false) */
  isGlobal: boolean;
  /** Callback when global/project toggle changes */
  onGlobalChange: (isGlobal: boolean) => void;
  /** The global credential for this provider (if available) */
  globalCredential?: ProviderCredential | null;
  /** The current credential reference from project config */
  credentialRef?: CredentialReference | null;
  /** Callback when credential reference changes */
  onCredentialChange: (ref: CredentialReference) => void;
  /** Whether the section is disabled */
  disabled?: boolean;
  /** Additional CSS classes */
  className?: string;
}

/**
 * Get the credential source based on configuration
 */
function getCredentialSource(
  isGlobal: boolean,
  globalCredential?: ProviderCredential | null
): CredentialSource {
  if (isGlobal) {
    return globalCredential ? 'global' : 'missing';
  }
  return 'project';
}

/**
 * ProviderCredentialSection - Manages credential source selection and input
 *
 * @example
 * // Using global credentials
 * <ProviderCredentialSection
 *   providerId="openai"
 *   providerDisplayName="OpenAI"
 *   isGlobal={true}
 *   onGlobalChange={setIsGlobal}
 *   globalCredential={globalOpenAiCredential}
 *   credentialRef={projectCredentialRef}
 *   onCredentialChange={handleCredentialChange}
 * />
 *
 * @example
 * // Using project-specific credentials
 * <ProviderCredentialSection
 *   providerId="openai"
 *   providerDisplayName="OpenAI"
 *   isGlobal={false}
 *   onGlobalChange={setIsGlobal}
 *   credentialRef={{ isGlobal: false, apiKey: 'sk-...', model: 'gpt-4o' }}
 *   onCredentialChange={handleCredentialChange}
 * />
 */
export function ProviderCredentialSection({
  providerId,
  providerDisplayName,
  isGlobal,
  onGlobalChange,
  globalCredential,
  credentialRef,
  onCredentialChange,
  disabled = false,
  className,
}: ProviderCredentialSectionProps) {
  const credentialSource = getCredentialSource(isGlobal, globalCredential);
  const sourceLabel = CREDENTIAL_SOURCE_LABELS[credentialSource];
  const sourceVariant = CREDENTIAL_SOURCE_VARIANTS[credentialSource];

  // Handle toggle change
  const handleGlobalToggle = (checked: boolean) => {
    onGlobalChange(checked);

    // Update credential reference to match the new global state
    onCredentialChange({
      isGlobal: checked,
      // Clear API key when switching to global
      apiKey: checked ? undefined : credentialRef?.apiKey,
      model: credentialRef?.model,
      baseUrl: credentialRef?.baseUrl,
    });
  };

  // Handle API key change
  const handleApiKeyChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onCredentialChange({
      ...credentialRef,
      isGlobal: false,
      apiKey: e.target.value || undefined,
    });
  };

  // Handle model override change
  const handleModelChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onCredentialChange({
      ...credentialRef,
      isGlobal,
      model: e.target.value || undefined,
    });
  };

  // Handle base URL override change
  const handleBaseUrlChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onCredentialChange({
      ...credentialRef,
      isGlobal,
      baseUrl: e.target.value || undefined,
    });
  };

  const hasGlobalCredential = !!globalCredential;

  return (
    <div
      className={cn('space-y-4', className)}
      data-testid="provider-credential-section"
      data-provider-id={providerId}
    >
      {/* Global/Project Toggle */}
      <div className="rounded-lg border border-border bg-muted/30 p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              {isGlobal ? (
                <Globe className="h-4 w-4 text-muted-foreground" />
              ) : (
                <FileText className="h-4 w-4 text-muted-foreground" />
              )}
              <Label className="text-sm font-medium text-foreground">
                Credential Source
              </Label>
            </div>
            <Badge
              variant={sourceVariant}
              className="text-xs"
              data-testid="credential-source-badge"
              data-source={credentialSource}
            >
              {sourceLabel}
              {credentialSource === 'global' && ' \u2713'}
            </Badge>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground">
              {isGlobal ? 'Global' : 'Project'}
            </span>
            <Switch
              checked={isGlobal}
              onCheckedChange={handleGlobalToggle}
              disabled={disabled || !hasGlobalCredential}
              data-testid="credential-source-toggle"
              aria-label={`Use ${isGlobal ? 'project-specific' : 'global'} credentials`}
            />
          </div>
        </div>

        {/* Global credential info */}
        {isGlobal && hasGlobalCredential && (
          <div className="mt-3 text-xs text-muted-foreground">
            <span className="flex items-center gap-1">
              <Globe className="h-3 w-3" />
              Using credentials from App Settings for {providerDisplayName}
            </span>
            {globalCredential.defaultModel && (
              <span className="mt-1 block">
                Default model: <code className="px-1 bg-muted rounded">{globalCredential.defaultModel}</code>
              </span>
            )}
          </div>
        )}

        {/* Warning when global not available */}
        {isGlobal && !hasGlobalCredential && (
          <div className="mt-3 text-xs text-warning">
            No global credentials configured for {providerDisplayName}.
            Please add credentials in App Settings or use project-specific credentials.
          </div>
        )}

        {/* Info when using project-specific */}
        {!isGlobal && (
          <div className="mt-3 text-xs text-muted-foreground">
            <span className="flex items-center gap-1">
              <FileText className="h-3 w-3" />
              Using project-specific credentials (stored in .env file)
            </span>
          </div>
        )}
      </div>

      {/* API Key Input - Only show for project-specific */}
      {!isGlobal && (
        <div className="space-y-2" data-testid="api-key-section">
          <div className="flex items-center gap-2">
            <Key className="h-4 w-4 text-muted-foreground" />
            <Label htmlFor={`api-key-${providerId}`} className="text-sm font-medium">
              API Key
            </Label>
          </div>
          <Input
            id={`api-key-${providerId}`}
            type="password"
            placeholder={`Enter ${providerDisplayName} API key...`}
            value={credentialRef?.apiKey || ''}
            onChange={handleApiKeyChange}
            disabled={disabled}
            className="font-mono text-sm"
            data-testid="api-key-input"
          />
          <p className="text-xs text-muted-foreground">
            Your API key will be stored securely in the project&apos;s .env file
          </p>
        </div>
      )}

      {/* Model Override */}
      <div className="space-y-2" data-testid="model-override-section">
        <div className="flex items-center gap-2">
          <Settings2 className="h-4 w-4 text-muted-foreground" />
          <Label htmlFor={`model-${providerId}`} className="text-sm font-medium">
            Model Override
          </Label>
          <span className="text-xs text-muted-foreground">(optional)</span>
        </div>
        <Input
          id={`model-${providerId}`}
          type="text"
          placeholder={
            isGlobal && globalCredential?.defaultModel
              ? `Using: ${globalCredential.defaultModel}`
              : 'Enter model name (e.g., gpt-4o, claude-3-sonnet)...'
          }
          value={credentialRef?.model || ''}
          onChange={handleModelChange}
          disabled={disabled}
          data-testid="model-override-input"
        />
      </div>

      {/* Base URL Override */}
      <div className="space-y-2" data-testid="base-url-section">
        <div className="flex items-center gap-2">
          <Globe className="h-4 w-4 text-muted-foreground" />
          <Label htmlFor={`base-url-${providerId}`} className="text-sm font-medium">
            Base URL Override
          </Label>
          <span className="text-xs text-muted-foreground">(optional)</span>
        </div>
        <Input
          id={`base-url-${providerId}`}
          type="url"
          placeholder={
            isGlobal && globalCredential?.baseUrl
              ? `Using: ${globalCredential.baseUrl}`
              : 'https://api.example.com/v1'
          }
          value={credentialRef?.baseUrl || ''}
          onChange={handleBaseUrlChange}
          disabled={disabled}
          data-testid="base-url-input"
        />
        <p className="text-xs text-muted-foreground">
          For custom endpoints or API proxies
        </p>
      </div>
    </div>
  );
}

export default ProviderCredentialSection;
