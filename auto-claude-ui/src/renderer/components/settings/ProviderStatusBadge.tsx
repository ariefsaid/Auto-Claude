/**
 * ProviderStatusBadge component
 * Displays the configuration status of a provider with visual indicators
 *
 * Status states:
 * - "Configured ✓" (green/success) - Provider is properly configured
 * - "Not Configured" (yellow/warning) - Provider needs configuration
 * - "Error: ..." (red/destructive) - Configuration has errors
 */

import * as React from 'react';
import { CheckCircle2, AlertCircle, XCircle } from 'lucide-react';
import { Badge } from '../ui/badge';
import { cn } from '../../lib/utils';
import type { ProviderStatus } from '@shared/types/provider';
import {
  PROVIDER_STATUS_LABELS,
  PROVIDER_STATUS_VARIANTS,
} from '@shared/constants/providers';

export interface ProviderStatusBadgeProps {
  /** The current provider status */
  status: ProviderStatus;
  /** Error message to display when status is 'error' */
  errorMessage?: string;
  /** Additional CSS classes */
  className?: string;
  /** Whether to show the status icon */
  showIcon?: boolean;
}

/**
 * Get the appropriate icon for the provider status
 */
function getStatusIcon(status: ProviderStatus): React.ReactNode {
  switch (status) {
    case 'configured':
      return <CheckCircle2 className="h-3 w-3 mr-1" />;
    case 'not_configured':
      return <AlertCircle className="h-3 w-3 mr-1" />;
    case 'error':
      return <XCircle className="h-3 w-3 mr-1" />;
    default:
      return null;
  }
}

/**
 * Get the label text for the provider status
 */
function getStatusLabel(status: ProviderStatus, errorMessage?: string): string {
  if (status === 'error' && errorMessage) {
    // Truncate long error messages
    const maxLength = 30;
    const truncatedMessage =
      errorMessage.length > maxLength
        ? `${errorMessage.slice(0, maxLength)}...`
        : errorMessage;
    return `Error: ${truncatedMessage}`;
  }

  return PROVIDER_STATUS_LABELS[status] || 'Unknown';
}

/**
 * ProviderStatusBadge - Visual indicator for provider configuration status
 *
 * @example
 * // Configured state
 * <ProviderStatusBadge status="configured" />
 *
 * @example
 * // Not configured state
 * <ProviderStatusBadge status="not_configured" />
 *
 * @example
 * // Error state with message
 * <ProviderStatusBadge status="error" errorMessage="API key is invalid" />
 */
export function ProviderStatusBadge({
  status,
  errorMessage,
  className,
  showIcon = true,
}: ProviderStatusBadgeProps) {
  const variant = PROVIDER_STATUS_VARIANTS[status] || 'default';
  const label = getStatusLabel(status, errorMessage);
  const icon = showIcon ? getStatusIcon(status) : null;

  return (
    <Badge
      variant={variant}
      className={cn('inline-flex items-center', className)}
      data-testid="provider-status-badge"
      data-status={status}
    >
      {icon}
      <span>{label}</span>
    </Badge>
  );
}

export default ProviderStatusBadge;
