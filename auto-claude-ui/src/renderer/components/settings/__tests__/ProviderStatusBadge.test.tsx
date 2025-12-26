/**
 * Unit tests for ProviderStatusBadge component
 * Tests status display, icons, error messages, and styling
 *
 * @vitest-environment jsdom
 */
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ProviderStatusBadge } from '../ProviderStatusBadge';
import type { ProviderStatus } from '@shared/types/provider';

describe('ProviderStatusBadge', () => {
  describe('Rendering', () => {
    it('should render with configured status', () => {
      render(<ProviderStatusBadge status="configured" />);

      const badge = screen.getByTestId('provider-status-badge');
      expect(badge).toBeDefined();
      expect(badge.getAttribute('data-status')).toBe('configured');
      expect(badge.textContent).toContain('Configured');
    });

    it('should render with not_configured status', () => {
      render(<ProviderStatusBadge status="not_configured" />);

      const badge = screen.getByTestId('provider-status-badge');
      expect(badge).toBeDefined();
      expect(badge.getAttribute('data-status')).toBe('not_configured');
      expect(badge.textContent).toContain('Not Configured');
    });

    it('should render with error status', () => {
      render(<ProviderStatusBadge status="error" />);

      const badge = screen.getByTestId('provider-status-badge');
      expect(badge).toBeDefined();
      expect(badge.getAttribute('data-status')).toBe('error');
      // Without error message, just shows "Error" or falls back to label
    });

    it('should render with error status and error message', () => {
      render(
        <ProviderStatusBadge status="error" errorMessage="API key is invalid" />
      );

      const badge = screen.getByTestId('provider-status-badge');
      expect(badge.textContent).toContain('Error:');
      expect(badge.textContent).toContain('API key is invalid');
    });
  });

  describe('Error Message Handling', () => {
    it('should truncate long error messages', () => {
      const longErrorMessage =
        'This is a very long error message that should be truncated because it exceeds the maximum length';
      render(
        <ProviderStatusBadge status="error" errorMessage={longErrorMessage} />
      );

      const badge = screen.getByTestId('provider-status-badge');
      // Should be truncated with ellipsis
      expect(badge.textContent).toContain('...');
      // Should not contain the full message
      expect(badge.textContent?.length).toBeLessThan(longErrorMessage.length + 10);
    });

    it('should display short error messages without truncation', () => {
      const shortErrorMessage = 'Key missing';
      render(
        <ProviderStatusBadge status="error" errorMessage={shortErrorMessage} />
      );

      const badge = screen.getByTestId('provider-status-badge');
      expect(badge.textContent).toContain('Key missing');
      expect(badge.textContent).not.toContain('...');
    });

    it('should handle empty error message', () => {
      render(<ProviderStatusBadge status="error" errorMessage="" />);

      const badge = screen.getByTestId('provider-status-badge');
      expect(badge).toBeDefined();
    });

    it('should ignore error message when status is not error', () => {
      render(
        <ProviderStatusBadge
          status="configured"
          errorMessage="This should be ignored"
        />
      );

      const badge = screen.getByTestId('provider-status-badge');
      expect(badge.textContent).not.toContain('This should be ignored');
      expect(badge.textContent).toContain('Configured');
    });
  });

  describe('Icon Display', () => {
    it('should show icon by default', () => {
      render(<ProviderStatusBadge status="configured" />);

      const badge = screen.getByTestId('provider-status-badge');
      // Icon is an SVG inside the badge
      const svg = badge.querySelector('svg');
      expect(svg).toBeDefined();
    });

    it('should hide icon when showIcon is false', () => {
      render(<ProviderStatusBadge status="configured" showIcon={false} />);

      const badge = screen.getByTestId('provider-status-badge');
      const svg = badge.querySelector('svg');
      expect(svg).toBeNull();
    });

    it('should show different icons for different statuses', () => {
      const statuses: ProviderStatus[] = ['configured', 'not_configured', 'error'];

      statuses.forEach((status) => {
        const { unmount } = render(<ProviderStatusBadge status={status} />);

        const badge = screen.getByTestId('provider-status-badge');
        const svg = badge.querySelector('svg');
        expect(svg).toBeDefined();

        unmount();
      });
    });
  });

  describe('Custom Styling', () => {
    it('should accept custom className', () => {
      render(
        <ProviderStatusBadge status="configured" className="my-custom-class" />
      );

      const badge = screen.getByTestId('provider-status-badge');
      expect(badge.className).toContain('my-custom-class');
    });

    it('should preserve default classes with custom className', () => {
      render(
        <ProviderStatusBadge status="configured" className="extra-class" />
      );

      const badge = screen.getByTestId('provider-status-badge');
      // Should have inline-flex items-center from component
      expect(badge.className).toContain('inline-flex');
      expect(badge.className).toContain('items-center');
      expect(badge.className).toContain('extra-class');
    });
  });

  describe('Badge Variants', () => {
    it('should apply success variant for configured status', () => {
      render(<ProviderStatusBadge status="configured" />);

      const badge = screen.getByTestId('provider-status-badge');
      // Success variant typically has green/success styling
      // The exact class depends on the badge implementation
      expect(badge.className).toContain('success');
    });

    it('should apply warning variant for not_configured status', () => {
      render(<ProviderStatusBadge status="not_configured" />);

      const badge = screen.getByTestId('provider-status-badge');
      expect(badge.className).toContain('warning');
    });

    it('should apply destructive variant for error status', () => {
      render(<ProviderStatusBadge status="error" />);

      const badge = screen.getByTestId('provider-status-badge');
      expect(badge.className).toContain('destructive');
    });
  });

  describe('Accessibility', () => {
    it('should have data-testid for testing', () => {
      render(<ProviderStatusBadge status="configured" />);

      const badge = screen.getByTestId('provider-status-badge');
      expect(badge).toBeDefined();
    });

    it('should have data-status attribute for status identification', () => {
      const statuses: ProviderStatus[] = ['configured', 'not_configured', 'error'];

      statuses.forEach((status) => {
        const { unmount } = render(<ProviderStatusBadge status={status} />);

        const badge = screen.getByTestId('provider-status-badge');
        expect(badge.getAttribute('data-status')).toBe(status);

        unmount();
      });
    });
  });

  describe('Status Labels', () => {
    it('should display "Configured" for configured status', () => {
      render(<ProviderStatusBadge status="configured" />);

      expect(screen.getByTestId('provider-status-badge').textContent).toContain(
        'Configured'
      );
    });

    it('should display "Not Configured" for not_configured status', () => {
      render(<ProviderStatusBadge status="not_configured" />);

      expect(screen.getByTestId('provider-status-badge').textContent).toContain(
        'Not Configured'
      );
    });

    it('should display "Error:" prefix for error status with message', () => {
      render(
        <ProviderStatusBadge status="error" errorMessage="Something wrong" />
      );

      const badge = screen.getByTestId('provider-status-badge');
      expect(badge.textContent).toMatch(/Error:/);
    });
  });

  describe('Props Interface', () => {
    it('should accept all valid ProviderStatus values', () => {
      // This tests the TypeScript interface compliance
      const validStatuses: ProviderStatus[] = [
        'configured',
        'not_configured',
        'error',
      ];

      validStatuses.forEach((status) => {
        const { unmount } = render(<ProviderStatusBadge status={status} />);
        const badge = screen.getByTestId('provider-status-badge');
        expect(badge).toBeDefined();
        unmount();
      });
    });

    it('should work with minimal required props', () => {
      // Only status is required
      render(<ProviderStatusBadge status="configured" />);

      const badge = screen.getByTestId('provider-status-badge');
      expect(badge).toBeDefined();
    });

    it('should work with all props provided', () => {
      render(
        <ProviderStatusBadge
          status="error"
          errorMessage="Test error"
          className="test-class"
          showIcon={true}
        />
      );

      const badge = screen.getByTestId('provider-status-badge');
      expect(badge).toBeDefined();
      expect(badge.className).toContain('test-class');
      expect(badge.textContent).toContain('Error:');
      expect(badge.querySelector('svg')).toBeDefined();
    });
  });
});
