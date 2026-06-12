'use client';
import { useEffect, useState } from 'react';

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

export default function AnalyticsPage() {
  const [report, setReport] = useState<AnalyticsReport | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/proxy/analytics')
      .then(r => r.ok ? r.json() : null)
      .then(data => { if (data) setReport(data); })
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div style={{ color: 'var(--text-secondary)', padding: 40 }}>Loading analytics...</div>;

  return (
    <div>
      <h1 style={{ fontSize: 28, fontWeight: 700, marginBottom: 8 }}>Analytics</h1>
      <p style={{ color: 'var(--text-secondary)', marginBottom: 32, fontSize: 14 }}>
        Last {report?.period_days || 7} days · Trend: <strong>{report?.trend || 'flat'}</strong>
      </p>

      {/* Metric cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 32 }}>
        {[
          { label: 'Total Impressions', value: (report?.total_impressions || 0).toLocaleString() },
          { label: 'Total Clicks', value: (report?.total_clicks || 0).toLocaleString() },
          { label: 'Best Day', value: report?.best_performing_day || '—' },
          { label: 'Best Template', value: report?.best_performing_template || '—' },
        ].map(({ label, value }) => (
          <div key={label} style={{ background: 'white', border: '1px solid var(--border)', borderRadius: 12, padding: 24 }}>
            <div style={{ fontSize: 12, color: 'var(--text-secondary)', fontWeight: 600, letterSpacing: '0.05em', textTransform: 'uppercase', marginBottom: 8 }}>{label}</div>
            <div style={{ fontSize: 28, fontWeight: 700, color: 'var(--brand-primary)' }}>{value}</div>
          </div>
        ))}
      </div>

      {/* Platform breakdown */}
      {report?.platform_breakdown && Object.keys(report.platform_breakdown).length > 0 && (
        <div style={{ background: 'white', border: '1px solid var(--border)', borderRadius: 12, padding: 24, marginBottom: 24 }}>
          <h2 style={{ fontSize: 16, fontWeight: 700, marginBottom: 20 }}>Platform Breakdown</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {['Platform', 'Impressions', 'Clicks', 'Engagement Rate'].map(h => (
                  <th key={h} style={{ textAlign: 'left', padding: '8px 12px', fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', borderBottom: '1px solid var(--border)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {Object.entries(report.platform_breakdown).map(([platform, stats]) => (
                <tr key={platform}>
                  <td style={{ padding: '12px 12px', fontSize: 14, fontWeight: 600, textTransform: 'capitalize', borderBottom: '1px solid var(--border)' }}>{platform}</td>
                  <td style={{ padding: '12px 12px', fontSize: 14, color: 'var(--text-secondary)', borderBottom: '1px solid var(--border)' }}>{stats.impressions.toLocaleString()}</td>
                  <td style={{ padding: '12px 12px', fontSize: 14, color: 'var(--text-secondary)', borderBottom: '1px solid var(--border)' }}>{stats.clicks.toLocaleString()}</td>
                  <td style={{ padding: '12px 12px', fontSize: 14, color: 'var(--text-secondary)', borderBottom: '1px solid var(--border)' }}>{(stats.engagement_rate * 100).toFixed(1)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Recommendations */}
      {report?.recommendations && report.recommendations.length > 0 && (
        <div style={{ background: 'white', border: '1px solid var(--border)', borderRadius: 12, padding: 24 }}>
          <h2 style={{ fontSize: 16, fontWeight: 700, marginBottom: 16 }}>Recommendations</h2>
          <ul style={{ margin: 0, paddingLeft: 20 }}>
            {report.recommendations.map((rec, i) => (
              <li key={i} style={{ fontSize: 14, color: 'var(--text-primary)', marginBottom: 8, lineHeight: 1.5 }}>{rec}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
