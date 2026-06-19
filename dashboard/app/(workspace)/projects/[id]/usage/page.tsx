'use client';
import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { Bot, Clock } from 'lucide-react';
import { notify } from '@/lib/toast';
import { ProjectFrame } from '../_components/ProjectFrame';

type ToolUsage = { used: number; limit: number };
type VendorOR  = { used_tokens: number; credit_balance_usd: number; monthly_spend_usd: number; monthly_limit_usd: number; reset_at: string };
type VendorPX  = { requests_used: number; requests_limit: number; reset_at: string };
type VendorAP  = { compute_units_used: number; compute_units_limit: number; reset_at: string };

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
  if (p >= 70) return '#F59E0B';
  return '#10B981';
}

function ProjectUsageContent() {
  const [data, setData] = useState<UsageData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/proxy/usage')
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d) setData(d); else notify.error('Failed to load usage'); })
      .finally(() => setLoading(false));
  }, []);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div className="topbar">
        <div>
          <div className="topbar-title">Usage</div>
          <div className="topbar-sub">Tool and vendor usage for your account</div>
        </div>
        {data && (
          <div className="topbar-actions">
            <span className="badge badge-muted" style={{ fontSize: 11 }}>{data.tier} tier</span>
            <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 12, color: 'var(--text-muted)' }}>
              <Clock size={12} /> Resets {new Date(data.reset_at).toLocaleDateString()}
            </span>
          </div>
        )}
      </div>

      <div className="page-container" style={{ flex: 1, overflowY: 'auto' }}>
        {loading ? (
          <div className="empty-state" style={{ padding: '48px 0' }}><span className="spinner spinner-dark" /></div>
        ) : !data ? null : (
          <>
            {/* Tool usage */}
            <div className="card" style={{ marginBottom: 24 }}>
              <h3 className="card-title" style={{ marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
                <Bot size={16} /> Daily Tool Usage
              </h3>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 16 }}>
                {Object.entries(data.tool_usage).map(([key, u]) => {
                  const p = pct(u.used, u.limit);
                  return (
                    <div key={key} style={{ padding: '12px 16px', borderRadius: 8, background: 'var(--bg-subtle)', border: '1px solid var(--border-subtle)' }}>
                      <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 8 }}>{TOOL_LABELS[key] ?? key}</div>
                      <div style={{ height: 4, borderRadius: 9999, background: 'var(--border-default)', marginBottom: 6, overflow: 'hidden' }}>
                        <div style={{ height: '100%', width: `${p}%`, background: fillColor(p), borderRadius: 9999 }} />
                      </div>
                      <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                        {u.used} / {u.limit === -1 ? '∞' : u.limit} used
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Vendor cards */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))', gap: 16 }}>
              {data.vendors.perplexity && (
                <div className="card">
                  <div className="card-title" style={{ marginBottom: 12 }}>Perplexity</div>
                  <div style={{ fontSize: 13 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                      <span style={{ color: 'var(--text-secondary)' }}>Requests</span>
                      <span style={{ fontWeight: 600 }}>{data.vendors.perplexity.requests_used} / {data.vendors.perplexity.requests_limit}</span>
                    </div>
                    <div style={{ height: 4, borderRadius: 9999, background: 'var(--border-default)', overflow: 'hidden' }}>
                      <div style={{ height: '100%', width: `${pct(data.vendors.perplexity.requests_used, data.vendors.perplexity.requests_limit)}%`, background: '#6366F1', borderRadius: 9999 }} />
                    </div>
                  </div>
                </div>
              )}
              {data.vendors.openrouter && (
                <div className="card">
                  <div className="card-title" style={{ marginBottom: 12 }}>OpenRouter</div>
                  <div style={{ fontSize: 13, color: 'var(--text-secondary)', display: 'flex', flexDirection: 'column', gap: 4 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}><span>Balance</span><span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>${data.vendors.openrouter.credit_balance_usd.toFixed(2)}</span></div>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}><span>Spent</span><span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>${data.vendors.openrouter.monthly_spend_usd.toFixed(2)}</span></div>
                  </div>
                </div>
              )}
              {data.vendors.apify && (
                <div className="card">
                  <div className="card-title" style={{ marginBottom: 12 }}>Apify</div>
                  <div style={{ fontSize: 13 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                      <span style={{ color: 'var(--text-secondary)' }}>Compute Units</span>
                      <span style={{ fontWeight: 600 }}>{data.vendors.apify.compute_units_used} / {data.vendors.apify.compute_units_limit}</span>
                    </div>
                    <div style={{ height: 4, borderRadius: 9999, background: 'var(--border-default)', overflow: 'hidden' }}>
                      <div style={{ height: '100%', width: `${pct(data.vendors.apify.compute_units_used, data.vendors.apify.compute_units_limit)}%`, background: '#F59E0B', borderRadius: 9999 }} />
                    </div>
                  </div>
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export default function ProjectUsagePage() {
  const { id: projectId } = useParams<{ id: string }>();
  return (
    <ProjectFrame projectId={projectId}>
      <ProjectUsageContent />
    </ProjectFrame>
  );
}
