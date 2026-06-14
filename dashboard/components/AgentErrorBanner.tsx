'use client';
import { useState } from 'react';
import { AlertTriangle, AlertCircle, WifiOff, RefreshCw, X } from 'lucide-react';

export type PerplexityErrorType =
  | 'MISSING_KEY'
  | 'INVALID_KEY'
  | 'QUOTA_EXCEEDED'
  | 'EMPTY_RESULT'
  | 'SERVICE_DOWN';

export interface UserAction {
  label: string;
  href: string;
}

export interface AgentError {
  error_type: PerplexityErrorType;
  message: string;
  retry_allowed: boolean;
  user_action: UserAction;
}

interface Props {
  error: AgentError;
  onDismiss?: () => void;
  onRetry?: () => void;
  onResume?: () => void;
}

// ── Per-error-type configuration ──────────────────────────────────────────

const ERROR_CONFIG: Record<
  PerplexityErrorType,
  {
    icon: React.ElementType;
    accentColor: string;
    bgColor: string;
    borderColor: string;
    iconColor: string;
  }
> = {
  MISSING_KEY: {
    icon: AlertCircle,
    accentColor: '#F59E0B',
    bgColor: 'rgba(245,158,11,0.08)',
    borderColor: 'rgba(245,158,11,0.3)',
    iconColor: '#F59E0B',
  },
  INVALID_KEY: {
    icon: AlertCircle,
    accentColor: '#EF4444',
    bgColor: 'rgba(239,68,68,0.08)',
    borderColor: 'rgba(239,68,68,0.3)',
    iconColor: '#EF4444',
  },
  QUOTA_EXCEEDED: {
    icon: AlertTriangle,
    accentColor: '#8B5CF6',
    bgColor: 'rgba(139,92,246,0.08)',
    borderColor: 'rgba(139,92,246,0.3)',
    iconColor: '#8B5CF6',
  },
  EMPTY_RESULT: {
    icon: AlertTriangle,
    accentColor: '#3B82F6',
    bgColor: 'rgba(59,130,246,0.08)',
    borderColor: 'rgba(59,130,246,0.3)',
    iconColor: '#3B82F6',
  },
  SERVICE_DOWN: {
    icon: WifiOff,
    accentColor: '#6B7280',
    bgColor: 'rgba(107,114,128,0.08)',
    borderColor: 'rgba(107,114,128,0.3)',
    iconColor: '#6B7280',
  },
};

// ── Component ─────────────────────────────────────────────────────────────

export default function AgentErrorBanner({ error, onDismiss, onRetry, onResume }: Props) {
  const [dismissed, setDismissed] = useState(false);

  if (dismissed) return null;

  const config = ERROR_CONFIG[error.error_type];
  const Icon = config.icon;

  function handleDismiss() {
    setDismissed(true);
    // Log dismissal for analytics
    try {
      fetch('/api/proxy/events', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          event: 'error_banner_dismissed',
          error_type: error.error_type,
          timestamp: new Date().toISOString(),
        }),
      }).catch(() => {}); // fire-and-forget
    } catch {}
    onDismiss?.();
  }

  return (
    <div
      role="alert"
      aria-live="polite"
      style={{
        display: 'flex',
        alignItems: 'flex-start',
        gap: 12,
        padding: '12px 16px',
        borderRadius: 'var(--radius-md, 8px)',
        border: `1px solid ${config.borderColor}`,
        background: config.bgColor,
        marginBottom: 12,
        position: 'relative',
      }}
    >
      {/* Icon */}
      <div style={{ flexShrink: 0, paddingTop: 1 }}>
        <Icon size={16} color={config.iconColor} />
      </div>

      {/* Content */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <p
          style={{
            margin: 0,
            fontSize: 13,
            fontWeight: 500,
            color: 'var(--text-primary)',
            lineHeight: 1.5,
          }}
        >
          {error.message}
        </p>

        {/* Action buttons */}
        <div style={{ display: 'flex', gap: 8, marginTop: 8, flexWrap: 'wrap' }}>
          {/* Primary CTA from error config */}
          {error.user_action.href && (
            <a
              href={error.user_action.href}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 4,
                padding: '4px 10px',
                borderRadius: 'var(--radius-sm, 4px)',
                background: config.accentColor,
                color: 'white',
                fontSize: 12,
                fontWeight: 500,
                textDecoration: 'none',
                lineHeight: 1.4,
              }}
            >
              {error.user_action.label}
            </a>
          )}

          {/* Retry button (EMPTY_RESULT) */}
          {error.error_type === 'EMPTY_RESULT' && onRetry && (
            <button
              onClick={onRetry}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 4,
                padding: '4px 10px',
                borderRadius: 'var(--radius-sm, 4px)',
                background: 'transparent',
                border: `1px solid ${config.borderColor}`,
                color: 'var(--text-primary)',
                fontSize: 12,
                fontWeight: 500,
                cursor: 'pointer',
              }}
            >
              <RefreshCw size={11} />
              Retry
            </button>
          )}

          {/* Resume button (SERVICE_DOWN) */}
          {error.error_type === 'SERVICE_DOWN' && onResume && (
            <button
              onClick={onResume}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 4,
                padding: '4px 10px',
                borderRadius: 'var(--radius-sm, 4px)',
                background: 'transparent',
                border: `1px solid ${config.borderColor}`,
                color: 'var(--text-primary)',
                fontSize: 12,
                fontWeight: 500,
                cursor: 'pointer',
              }}
            >
              Resume Run
            </button>
          )}
        </div>
      </div>

      {/* Dismiss button */}
      <button
        onClick={handleDismiss}
        aria-label="Dismiss error"
        style={{
          flexShrink: 0,
          background: 'transparent',
          border: 'none',
          padding: 2,
          cursor: 'pointer',
          color: 'var(--text-muted)',
          display: 'flex',
          alignItems: 'center',
        }}
      >
        <X size={14} />
      </button>
    </div>
  );
}
