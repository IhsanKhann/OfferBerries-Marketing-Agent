import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import AgentErrorBanner from '../../../components/AgentErrorBanner';
import type { AgentError } from '../../../components/AgentErrorBanner';

const MISSING_KEY_ERROR: AgentError = {
  error_type: 'MISSING_KEY',
  message: 'Perplexity API key is missing. Add PERPLEXITY_API_KEY to your environment.',
  retry_allowed: false,
  user_action: { label: 'Add API Key', href: '/settings' },
};

const QUOTA_ERROR: AgentError = {
  error_type: 'QUOTA_EXCEEDED',
  message: 'Perplexity quota exceeded for this month.',
  retry_allowed: false,
  user_action: { label: 'Upgrade Plan', href: 'https://perplexity.ai' },
};

const EMPTY_RESULT_ERROR: AgentError = {
  error_type: 'EMPTY_RESULT',
  message: 'Research returned no results for this topic.',
  retry_allowed: true,
  user_action: { label: 'Change Topic', href: '/queue' },
};

const SERVICE_DOWN_ERROR: AgentError = {
  error_type: 'SERVICE_DOWN',
  message: 'Perplexity service is temporarily unavailable.',
  retry_allowed: false,
  user_action: { label: 'Check Status', href: 'https://status.perplexity.ai' },
};

describe('AgentErrorBanner', () => {
  it('renders error message', () => {
    render(<AgentErrorBanner error={MISSING_KEY_ERROR} />);
    expect(screen.getByText(MISSING_KEY_ERROR.message)).toBeInTheDocument();
  });

  it('renders user_action link', () => {
    render(<AgentErrorBanner error={MISSING_KEY_ERROR} />);
    expect(screen.getByText('Add API Key')).toBeInTheDocument();
  });

  it('has role="alert" for accessibility', () => {
    render(<AgentErrorBanner error={MISSING_KEY_ERROR} />);
    expect(screen.getByRole('alert')).toBeInTheDocument();
  });

  it('dismisses on X button click', async () => {
    render(<AgentErrorBanner error={MISSING_KEY_ERROR} />);
    await userEvent.click(screen.getByLabelText('Dismiss error'));
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('calls onDismiss callback when dismissed', async () => {
    const onDismiss = vi.fn();
    render(<AgentErrorBanner error={MISSING_KEY_ERROR} onDismiss={onDismiss} />);
    await userEvent.click(screen.getByLabelText('Dismiss error'));
    expect(onDismiss).toHaveBeenCalled();
  });

  it('shows Retry button only for EMPTY_RESULT with onRetry prop', () => {
    const onRetry = vi.fn();
    render(<AgentErrorBanner error={EMPTY_RESULT_ERROR} onRetry={onRetry} />);
    expect(screen.getByText('Retry')).toBeInTheDocument();
  });

  it('does NOT show Retry button for MISSING_KEY', () => {
    render(<AgentErrorBanner error={MISSING_KEY_ERROR} onRetry={vi.fn()} />);
    expect(screen.queryByText('Retry')).not.toBeInTheDocument();
  });

  it('calls onRetry when Retry button clicked', async () => {
    const onRetry = vi.fn();
    render(<AgentErrorBanner error={EMPTY_RESULT_ERROR} onRetry={onRetry} />);
    await userEvent.click(screen.getByText('Retry'));
    expect(onRetry).toHaveBeenCalled();
  });

  it('shows Resume Run button only for SERVICE_DOWN with onResume prop', () => {
    const onResume = vi.fn();
    render(<AgentErrorBanner error={SERVICE_DOWN_ERROR} onResume={onResume} />);
    expect(screen.getByText('Resume Run')).toBeInTheDocument();
  });

  it('does NOT show Resume Run button for QUOTA_EXCEEDED', () => {
    render(<AgentErrorBanner error={QUOTA_ERROR} onResume={vi.fn()} />);
    expect(screen.queryByText('Resume Run')).not.toBeInTheDocument();
  });

  it('calls onResume when Resume Run clicked', async () => {
    const onResume = vi.fn();
    render(<AgentErrorBanner error={SERVICE_DOWN_ERROR} onResume={onResume} />);
    await userEvent.click(screen.getByText('Resume Run'));
    expect(onResume).toHaveBeenCalled();
  });

  it('renders QUOTA_EXCEEDED error message', () => {
    render(<AgentErrorBanner error={QUOTA_ERROR} />);
    expect(screen.getByText(QUOTA_ERROR.message)).toBeInTheDocument();
  });

  it('renders SERVICE_DOWN error with check status link', () => {
    render(<AgentErrorBanner error={SERVICE_DOWN_ERROR} />);
    expect(screen.getByText('Check Status')).toBeInTheDocument();
  });

  it('renders INVALID_KEY error type', () => {
    const error: AgentError = {
      error_type: 'INVALID_KEY',
      message: 'Invalid API key provided.',
      retry_allowed: false,
      user_action: { label: 'Fix Key', href: '/settings' },
    };
    render(<AgentErrorBanner error={error} />);
    expect(screen.getByText('Invalid API key provided.')).toBeInTheDocument();
  });
});
