'use client';
import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { TrendingUp, MousePointer, Eye, Calendar, Layers } from 'lucide-react';
import { notify } from '@/lib/toast';
import { ProjectFrame } from '../_components/ProjectFrame';

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

function ProjectAnalyticsContent({ projectId }: { projectId: string }) {
  const [report, setReport] = useState<AnalyticsReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState(7);

  useEffect(() => { fetchReport(); }, [days, projectId]);

  async function fetchReport() {
    setLoading(true);
    try {
      const res = await fetch(`/api/proxy/analytics?days=${days}&project_id=${projectId}`);
      if (res.ok) setReport(await res.json());
      else notify.error('Failed to load analytics');
    } finally {
      setLoading(false);
    }
  }

  const kpis = report ? [
    { label: 'Total Impressions', value: report.total_impressions.toLocaleString(), icon: Eye,          color: '#3B82F6' },
    { label: 'Total Clicks',      value: report.total_clicks.toLocaleString(),       icon: MousePointer, color: '#8B5CF6' },
    { label: 'Best Day',          value: report.best_performing_day || '—',          icon: Calendar,     color: '#F59E0B' },
    { label: 'Best Template',     value: report.best_performing_template || '—',     icon: Layers,       color: '#10B981' },
  ] : [];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div className="topbar">
        <div>
          <div className="topbar-title">Analytics</div>
          <div className="topbar-sub">Performance insights for this project</div>
        </div>
        <div className="topbar-actions">
          {[7, 14, 30].map(d => (
            <button key={d} onClick={() => setDays(d)} className={`chip${days === d ? ' active' : ''}`}>{d}d</button>
          ))}
          {report && (
            <span className={`badge ${TREND_BADGE[report.trend] ?? 'badge-muted'}`} style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
              <TrendingUp size={11} /> {report.trend}
            </span>
          )}
        </div>
      </div>

      <div className="page-container" style={{ flex: 1, overflowY: 'auto' }}>
        {loading ? (
          <div className="empty-state" style={{ padding: '48px 0' }}><span className="spinner spinner-dark" /></div>
        ) : !report ? (
          <div className="empty-state" style={{ padding: '48px 0' }}>
            <div className="empty-title">No analytics data</div>
            <div className="empty-sub">Generate and publish content to see analytics.</div>
          </div>
        ) : (
          <>
            {/* KPI cards */}
            <div className="kpi-grid" style={{ marginBottom: 24 }}>
              {kpis.map(k => (
                <div key={k.label} className="card kpi-card">
                  <div className="kpi-icon" style={{ background: k.color + '18', color: k.color }}>
                    <k.icon size={18} />
                  </div>
                  <div className="kpi-value">{k.value}</div>
                  <div className="kpi-label">{k.label}</div>
                </div>
              ))}
            </div>

            {/* Platform breakdown */}
            {Object.keys(report.platform_breakdown).length > 0 && (
              <div className="card" style={{ marginBottom: 24 }}>
                <h3 className="card-title" style={{ marginBottom: 16 }}>Platform Breakdown</h3>
                <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                  <thead>
                    <tr>
                      {['Platform', 'Impressions', 'Clicks', 'Engagement'].map(h => (
                        <th key={h} style={{ padding: '8px 12px', textAlign: 'left', fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', borderBottom: '1px solid var(--border-subtle)' }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(report.platform_breakdown).map(([platform, data]) => (
                      <tr key={platform} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                        <td style={{ padding: '10px 12px', fontWeight: 600, textTransform: 'capitalize', fontSize: 13 }}>{platform}</td>
                        <td style={{ padding: '10px 12px', fontSize: 13 }}>{data.impressions.toLocaleString()}</td>
                        <td style={{ padding: '10px 12px', fontSize: 13 }}>{data.clicks.toLocaleString()}</td>
                        <td style={{ padding: '10px 12px' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            <div style={{ flex: 1, height: 6, background: 'var(--border-subtle)', borderRadius: 9999, overflow: 'hidden' }}>
                              <div style={{ height: '100%', width: `${Math.min(100, data.engagement_rate)}%`, background: 'var(--brand-primary)', borderRadius: 9999 }} />
                            </div>
                            <span style={{ fontSize: 12, color: 'var(--text-secondary)', minWidth: 36 }}>{data.engagement_rate.toFixed(1)}%</span>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* Recommendations */}
            {report.recommendations?.length > 0 && (
              <div className="card">
                <h3 className="card-title" style={{ marginBottom: 12 }}>Recommendations</h3>
                <ul style={{ margin: 0, padding: '0 0 0 16px', display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {report.recommendations.map((rec, i) => (
                    <li key={i} style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.5 }}>{rec}</li>
                  ))}
                </ul>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

export default function ProjectAnalyticsPage() {
  const { id: projectId } = useParams<{ id: string }>();
  return (
    <ProjectFrame projectId={projectId}>
      <ProjectAnalyticsContent projectId={projectId} />
    </ProjectFrame>
  );
}
