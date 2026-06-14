'use client';
import { useEffect, useState } from 'react';
import { TrendingUp, MousePointer, Eye, Calendar, Layers } from 'lucide-react';
import { notify } from '../../../lib/toast';

type AnalyticsReport = {
  period_days: number;
  total_impressions: number;
  total_clicks: number;
  top_posts: { postiz_id: string; platform: string; impressions: number; clicks: number }[];
  platform_breakdown: Record<string, { impressions: number; clicks: number; engagement_rate: number }>;
  trend: string;
  recommendations: string[];
  best_performing_template: string;
  best_performing_day: string;
};

const TREND_BADGE: Record<string, string> = {
  growing: 'badge-success',
  flat: 'badge-muted',
  declining: 'badge-danger',
};

export default function AnalyticsPage() {
  const [report, setReport]   = useState<AnalyticsReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [days, setDays]       = useState(7);

  useEffect(() => { fetchReport(); }, [days]);

  async function fetchReport() {
    setLoading(true);
    try {
      const res = await fetch(`/api/proxy/analytics?days=${days}`);
      if (res.ok) setReport(await res.json());
      else notify.error('Failed to load analytics', 'Check your connection');
    } finally {
      setLoading(false);
    }
  }

  const kpis = report ? [
    { label: 'Total Impressions', value: report.total_impressions.toLocaleString(), icon: Eye,           color: 'var(--hr-accent)' },
    { label: 'Total Clicks',      value: report.total_clicks.toLocaleString(),       icon: MousePointer,  color: 'var(--fin-accent)' },
    { label: 'Best Day',          value: report.best_performing_day || '—',          icon: Calendar,      color: 'var(--ops-accent)' },
    { label: 'Best Template',     value: report.best_performing_template || '—',     icon: Layers,        color: 'var(--success)' },
  ] : [];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
      <div className="topbar">
        <div>
          <div className="topbar-title">Analytics</div>
          <div className="topbar-sub">Performance insights from your queue</div>
        </div>
        <div className="topbar-actions">
          {[7, 14, 30].map(d => (
            <button key={d} onClick={() => setDays(d)} className={`chip${days === d ? ' active' : ''}`}>{d}d</button>
          ))}
          {report && (
            <span className={`badge ${TREND_BADGE[report.trend] || 'badge-muted'}`}>
              <TrendingUp size={10} /> {report.trend}
            </span>
          )}
          <div className="avatar-chip">I</div>
        </div>
      </div>

      <div className="content-area">
        {loading ? (
          <div className="grid-4 mb-4">
            {[1,2,3,4].map(i => <div key={i} className="skeleton-pulse" style={{ height: 100 }} />)}
          </div>
        ) : (
          <>
            {/* KPI cards */}
            <div className="grid-4 mb-4">
              {kpis.map(({ label, value, icon: Icon, color }) => (
                <div key={label} className="card">
                  <div className="flex-between mb-4" style={{ alignItems: 'flex-start' }}>
                    <span className="stat-label">{label}</span>
                    <div style={{ width: 32, height: 32, borderRadius: 'var(--radius-md)', background: color + '18', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                      <Icon size={14} style={{ color }} />
                    </div>
                  </div>
                  <div className="stat-number" style={{ color }}>{value}</div>
                </div>
              ))}
            </div>

            {/* Platform breakdown */}
            {report?.platform_breakdown && Object.keys(report.platform_breakdown).length > 0 && (
              <div className="card mb-4">
                <div className="card-title mb-4">Platform Breakdown</div>
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Platform</th>
                        <th>Impressions</th>
                        <th>Clicks</th>
                        <th>Engagement Rate</th>
                        <th>Trend</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(report.platform_breakdown).map(([platform, stats]) => {
                        const pct = Math.round(stats.engagement_rate * 100);
                        return (
                          <tr key={platform}>
                            <td>
                              <span style={{ fontWeight: 600, textTransform: 'capitalize' }}>{platform}</span>
                            </td>
                            <td style={{ color: 'var(--text-secondary)' }}>{stats.impressions.toLocaleString()}</td>
                            <td style={{ color: 'var(--text-secondary)' }}>{stats.clicks.toLocaleString()}</td>
                            <td>
                              <div className="flex-row gap-2">
                                <div className="progress-track" style={{ width: 80 }}>
                                  <div className="progress-fill" style={{ width: `${Math.min(100, pct)}%` }} />
                                </div>
                                <span style={{ fontSize: 12, color: 'var(--text-secondary)', minWidth: 32 }}>{pct}%</span>
                              </div>
                            </td>
                            <td>
                              <span className={`badge ${pct > 5 ? 'badge-success' : pct > 2 ? 'badge-warning' : 'badge-muted'}`}>
                                {pct > 5 ? 'High' : pct > 2 ? 'Medium' : 'Low'}
                              </span>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Recommendations */}
            {report?.recommendations && report.recommendations.length > 0 && (
              <div className="card">
                <div className="card-title mb-4">Recommendations</div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                  {report.recommendations.map((rec, i) => (
                    <div key={i} style={{ display: 'flex', gap: 10, padding: '10px 14px', background: 'var(--bg-subtle)', borderRadius: 'var(--radius-md)' }}>
                      <span style={{ color: 'var(--brand-primary)', flexShrink: 0, marginTop: 1 }}>→</span>
                      <span style={{ fontSize: 13, color: 'var(--text-primary)', lineHeight: 1.5 }}>{rec}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {!report?.platform_breakdown || Object.keys(report.platform_breakdown).length === 0 ? (
              <div className="empty-state">
                <div className="empty-icon">📊</div>
                <div className="empty-title">No analytics yet</div>
                <div className="empty-sub">Generate and publish posts to see performance data here.</div>
              </div>
            ) : null}
          </>
        )}
      </div>
    </div>
  );
}
