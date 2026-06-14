'use client';
import { useEffect, useState } from 'react';
import { Bot, Search, Bug, Clock } from 'lucide-react';
import { notify } from '../../../lib/toast';

type ToolUsage  = { used: number; limit: number };
type VendorOR   = { used_tokens: number; credit_balance_usd: number; monthly_spend_usd: number; monthly_limit_usd: number; reset_at: string };
type VendorPX   = { requests_used: number; requests_limit: number; reset_at: string };
type VendorAP   = { compute_units_used: number; compute_units_limit: number; reset_at: string };

type UsageData = {
  reset_at: string;
  tier: string;
  tool_usage: Record<string, ToolUsage>;
  vendors: { openrouter: VendorOR; perplexity: VendorPX; apify: VendorAP };
};

const TOOL_LABELS: Record<string, string> = {
  research_trends: 'Research Trends', scrape_competitor: 'Scrape Competitor',
  generate_content: 'Generate Content', generate_visual: 'Generate Visual',
  queue_post: 'Queue Post', get_analytics: 'Get Analytics', update_strategy: 'Update Strategy',
};

function pct(used: number, limit: number) {
  if (!limit) return 0;
  return Math.min(100, Math.round((used / limit) * 100));
}

function fillColor(p: number) {
  if (p >= 95) return '#EF4444';
  if (p >= 70) return 'var(--warning)';
  return 'var(--success)';
}

function formatDate(iso: string) {
  try { return new Date(iso).toLocaleDateString('en-PK', { month: 'short', day: 'numeric' }); }
  catch { return '—'; }
}

function useCountdown(resetAt: string) {
  const [label, setLabel] = useState('');
  useEffect(() => {
    function update() {
      const diff = new Date(resetAt).getTime() - Date.now();
      if (diff <= 0) { setLabel('Resetting…'); return; }
      const h = Math.floor(diff / 3_600_000);
      const m = Math.floor((diff % 3_600_000) / 60_000);
      setLabel(`${h}h ${m}m`);
    }
    update();
    const id = setInterval(update, 60_000);
    return () => clearInterval(id);
  }, [resetAt]);
  return label;
}

export default function UsagePage() {
  const [data, setData]     = useState<UsageData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]   = useState(false);
  const countdown = useCountdown(data?.reset_at || new Date(Date.now() + 86_400_000).toISOString());

  async function load() {
    setLoading(true); setError(false);
    try {
      const res = await fetch('/api/proxy/usage');
      if (res.ok) setData(await res.json());
      else { setError(true); notify.error('Failed to load usage data', 'Please try again'); }
    } catch { setError(true); notify.error('Network error', 'Check your connection'); }
    finally { setLoading(false); }
  }

  useEffect(() => { load(); }, []);

  const tier = data?.tier || '';

  if (loading) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
        <div className="topbar"><div className="topbar-title">Usage &amp; Limits</div></div>
        <div className="content-area">
          <div className="usage-tool-grid mb-6">
            {Array.from({ length: 7 }).map((_, i) => <div key={i} className="skeleton-pulse" style={{ height: 110 }} />)}
          </div>
          <div className="vendor-cards">
            {[1,2,3].map(i => <div key={i} className="skeleton-pulse" style={{ height: 160 }} />)}
          </div>
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
        <div className="topbar"><div className="topbar-title">Usage &amp; Limits</div></div>
        <div className="content-area">
          <div className="empty-state">
            <div className="empty-icon">⚠️</div>
            <div className="empty-title">Failed to load usage data</div>
            <div className="empty-sub">Check your connection and try again.</div>
            <button onClick={load} className="btn btn-primary mt-4">Retry</button>
          </div>
        </div>
      </div>
    );
  }

  const or = data.vendors.openrouter;
  const px = data.vendors.perplexity;
  const ap = data.vendors.apify;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
      <div className="topbar">
        <div>
          <div className="topbar-title">Usage &amp; Limits</div>
          <div className="topbar-sub">Resets daily at midnight UTC</div>
        </div>
        <div className="topbar-actions">
          {data.reset_at && (
            <span className="countdown-badge">
              <Clock size={12} /> Resets in {countdown}
            </span>
          )}
          <span className={`badge badge-${tier === 'owner' ? 'hr' : tier === 'pro' ? 'fin' : 'success'}`}>
            {tier.charAt(0).toUpperCase() + tier.slice(1)} tier
          </span>
          <div className="avatar-chip">I</div>
        </div>
      </div>

      <div className="content-area">
        {/* Tool usage */}
        <div className="flex-between mb-4">
          <div className="section-title">Daily Tool Usage</div>
        </div>
        <div className="usage-tool-grid mb-6">
          {Object.entries(data.tool_usage).map(([tool, { used, limit }]) => {
            const p = pct(used, limit);
            const disabled = limit === 0;
            return (
              <div key={tool} className={`usage-tool-card${disabled ? ' disabled' : ''}`}>
                <div className="overline">{TOOL_LABELS[tool] || tool}</div>
                {disabled ? (
                  <div className="usage-limit mt-3" style={{ color: 'var(--text-muted)' }}>
                    Not available on {tier} tier
                    <div><a href="/settings" className="mt-3" style={{ fontSize: 12, color: 'var(--text-link)' }}>Upgrade in Settings →</a></div>
                  </div>
                ) : (
                  <>
                    <div className="usage-count">
                      {used} <span style={{ fontSize: 14, fontWeight: 500, color: 'var(--text-muted)' }}>/ {limit >= 9999 ? '∞' : limit}</span>
                    </div>
                    <div className="progress-track mb-4">
                      <div className="progress-fill" style={{ width: `${limit >= 9999 ? 10 : p}%`, background: fillColor(p) }} />
                    </div>
                    <div className="usage-limit" style={{
                      color: p >= 95 ? 'var(--danger-text)' : p >= 70 ? 'var(--warning-text)' : 'var(--text-muted)',
                      fontWeight: p >= 95 ? 700 : undefined,
                    }}>
                      {limit >= 9999 ? 'Unlimited' : `${p}% used today${p >= 95 ? ' — almost exhausted!' : p >= 70 ? ' — nearing limit' : ''}`}
                    </div>
                  </>
                )}
              </div>
            );
          })}
        </div>

        {/* Vendor usage */}
        <div className="section-title mt-6 mb-4">Third-Party Vendors</div>
        <div className="vendor-cards">
          {/* OpenRouter */}
          <div className="vendor-card">
            <div className="vendor-icon" style={{ background: 'var(--hr-bg)' }}>
              <Bot size={20} style={{ color: 'var(--hr-accent)' }} />
            </div>
            <div className="vendor-label" style={{ color: 'var(--hr-accent)' }}>OPENROUTER</div>
            <div className="vendor-credit" style={{ color: 'var(--hr-text)' }}>${or.credit_balance_usd.toFixed(2)}</div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 10 }}>credit balance</div>
            <div className="progress-track mb-4">
              <div className="progress-fill" style={{ width: `${pct(or.monthly_spend_usd, or.monthly_limit_usd)}%`, background: 'var(--hr-gradient)' }} />
            </div>
            <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 4 }}>${or.monthly_spend_usd.toFixed(2)} / ${or.monthly_limit_usd.toFixed(2)} monthly</div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>↺ Resets {formatDate(or.reset_at)}</div>
          </div>

          {/* Perplexity */}
          <div className="vendor-card">
            <div className="vendor-icon" style={{ background: 'var(--fin-bg)' }}>
              <Search size={20} style={{ color: 'var(--fin-accent)' }} />
            </div>
            <div className="vendor-label" style={{ color: 'var(--fin-accent)' }}>PERPLEXITY</div>
            <div className="vendor-credit" style={{ color: 'var(--fin-text)' }}>{px.requests_used.toLocaleString()}</div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 10 }}>requests used today</div>
            <div className="progress-track mb-4">
              <div className="progress-fill" style={{ width: `${pct(px.requests_used, px.requests_limit)}%`, background: 'var(--fin-gradient)' }} />
            </div>
            <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 4 }}>{px.requests_used} / {px.requests_limit} daily</div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>↺ Resets midnight UTC</div>
          </div>

          {/* Apify */}
          <div className="vendor-card">
            <div className="vendor-icon" style={{ background: 'var(--ops-bg)' }}>
              <Bug size={20} style={{ color: 'var(--ops-accent)' }} />
            </div>
            <div className="vendor-label" style={{ color: 'var(--ops-accent)' }}>APIFY</div>
            <div className="vendor-credit" style={{ color: 'var(--ops-text)' }}>{ap.compute_units_used.toLocaleString()}</div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 10 }}>compute units used</div>
            <div className="progress-track mb-4">
              <div className="progress-fill" style={{ width: `${pct(ap.compute_units_used, ap.compute_units_limit)}%`, background: 'var(--ops-gradient)' }} />
            </div>
            <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 4 }}>{ap.compute_units_used.toLocaleString()} / {ap.compute_units_limit.toLocaleString()} monthly</div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>↺ Resets {formatDate(ap.reset_at)}</div>
          </div>
        </div>
      </div>
    </div>
  );
}
