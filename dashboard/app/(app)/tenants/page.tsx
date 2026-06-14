'use client';
import { useEffect, useState } from 'react';

type ApiKey = {
  key_prefix: string;
  tenant_id: string;
  tier: string;
  label: string;
  created_at: string;
  last_used_at?: string;
  revoked_at?: string;
};

type RunSummary = {
  run_id: string;
  status: string;
  completed_at: string;
};

const TIER_COLORS: Record<string, string> = {
  owner: '#7C3AED',
  pro: '#0A66C2',
  starter: '#10B981',
  demo: '#6B7280',
};

export default function TenantsPage() {
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [history, setHistory] = useState<RunSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [newTier, setNewTier] = useState('starter');
  const [newTenantId, setNewTenantId] = useState('');
  const [newLabel, setNewLabel] = useState('');
  const [newKey, setNewKey] = useState('');
  const [creating, setCreating] = useState(false);
  const [demoLink, setDemoLink] = useState('');

  useEffect(() => {
    Promise.all([
      fetch('/api/proxy/admin/api-keys').then(r => r.ok ? r.json() : []),
      fetch('/api/proxy/agent/history').then(r => r.ok ? r.json() : []),
    ]).then(([k, h]) => {
      setKeys(Array.isArray(k) ? k : []);
      setHistory(Array.isArray(h) ? h : []);
    }).finally(() => setLoading(false));
  }, []);

  async function createKey() {
    if (!newTenantId.trim() || !newLabel.trim()) return;
    setCreating(true);
    const res = await fetch('/api/proxy/admin/api-keys', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tenant_id: newTenantId, tier: newTier, label: newLabel }),
    });
    if (res.ok) {
      const data = await res.json();
      setNewKey(data.api_key);
      setNewTenantId('');
      setNewLabel('');
    }
    setCreating(false);
  }

  async function createDemo() {
    const res = await fetch('/api/proxy/admin/tenants/demo', { method: 'POST' });
    if (res.ok) {
      const data = await res.json();
      setDemoLink(`Key: ${data.api_key}\nExpires: ${data.expires_at}\nDemo URL: ${data.demo_url}`);
    }
  }

  if (loading) return <div style={{ color: 'var(--text-secondary)', padding: 40 }}>Loading...</div>;

  return (
    <div>
      <h1 style={{ fontSize: 28, fontWeight: 700, marginBottom: 8 }}>Tenant Management</h1>
      <p style={{ color: 'var(--text-secondary)', marginBottom: 32, fontSize: 14 }}>Manage API keys and agent run history.</p>

      {/* Create API Key */}
      <section style={{ background: 'white', border: '1px solid var(--border)', borderRadius: 12, padding: 24, marginBottom: 24 }}>
        <h2 style={{ fontSize: 16, fontWeight: 700, marginBottom: 16 }}>Create API Key</h2>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr auto', gap: 12, alignItems: 'end' }}>
          <div>
            <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 4 }}>Tenant ID</label>
            <input value={newTenantId} onChange={e => setNewTenantId(e.target.value)} placeholder="tenant-uuid" style={{ width: '100%', padding: '8px 12px', border: '1px solid var(--border)', borderRadius: 6, fontSize: 13, fontFamily: 'inherit', boxSizing: 'border-box' }} />
          </div>
          <div>
            <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 4 }}>Label</label>
            <input value={newLabel} onChange={e => setNewLabel(e.target.value)} placeholder="Acme Corp" style={{ width: '100%', padding: '8px 12px', border: '1px solid var(--border)', borderRadius: 6, fontSize: 13, fontFamily: 'inherit', boxSizing: 'border-box' }} />
          </div>
          <div>
            <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 4 }}>Tier</label>
            <select value={newTier} onChange={e => setNewTier(e.target.value)} style={{ width: '100%', padding: '8px 12px', border: '1px solid var(--border)', borderRadius: 6, fontSize: 13, fontFamily: 'inherit' }}>
              <option value="starter">Starter</option>
              <option value="pro">Pro</option>
              <option value="owner">Owner</option>
            </select>
          </div>
          <button onClick={createKey} disabled={creating || !newTenantId.trim() || !newLabel.trim()} style={{ padding: '8px 20px', background: 'var(--brand-primary)', color: 'white', border: 'none', borderRadius: 6, fontSize: 13, fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit', whiteSpace: 'nowrap' }}>
            {creating ? 'Creating...' : 'Create Key'}
          </button>
        </div>
        {newKey && (
          <div style={{ marginTop: 16, background: '#F0FDF4', border: '1px solid #86EFAC', borderRadius: 8, padding: 12 }}>
            <p style={{ fontSize: 12, fontWeight: 700, color: '#166534', marginBottom: 4 }}>New API Key (copy now — shown once):</p>
            <code style={{ fontSize: 13, color: '#166534', wordBreak: 'break-all' }}>{newKey}</code>
          </div>
        )}
      </section>

      {/* Create Demo Session */}
      <section style={{ background: 'white', border: '1px solid var(--border)', borderRadius: 12, padding: 24, marginBottom: 24 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <h2 style={{ fontSize: 16, fontWeight: 700, marginBottom: 4 }}>Demo Sessions</h2>
            <p style={{ fontSize: 13, color: 'var(--text-secondary)', margin: 0 }}>Create a 30-minute demo key to share with prospects.</p>
          </div>
          <button onClick={createDemo} style={{ padding: '8px 20px', background: 'var(--brand-primary)', color: 'white', border: 'none', borderRadius: 6, fontSize: 13, fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit' }}>
            New Demo
          </button>
        </div>
        {demoLink && (
          <pre style={{ marginTop: 16, background: '#F5F3FF', border: '1px solid #C4B5FD', borderRadius: 8, padding: 12, fontSize: 12, color: '#5B21B6', whiteSpace: 'pre-wrap', margin: '16px 0 0' }}>
            {demoLink}
          </pre>
        )}
      </section>

      {/* Active API Keys */}
      <section style={{ background: 'white', border: '1px solid var(--border)', borderRadius: 12, padding: 24, marginBottom: 24 }}>
        <h2 style={{ fontSize: 16, fontWeight: 700, marginBottom: 16 }}>Active API Keys</h2>
        {keys.length === 0 ? (
          <p style={{ fontSize: 14, color: 'var(--text-secondary)' }}>No API keys found.</p>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr>
                {['Tenant ID', 'Label', 'Tier', 'Prefix', 'Created', 'Last Used'].map(h => (
                  <th key={h} style={{ textAlign: 'left', padding: '8px 12px', fontSize: 11, fontWeight: 600, color: 'var(--text-secondary)', borderBottom: '1px solid var(--border)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {keys.map((k, i) => (
                <tr key={i} style={{ opacity: k.revoked_at ? 0.4 : 1 }}>
                  <td style={{ padding: '10px 12px', borderBottom: '1px solid var(--border)', fontFamily: 'monospace', fontSize: 11 }}>{k.tenant_id.substring(0, 20)}…</td>
                  <td style={{ padding: '10px 12px', borderBottom: '1px solid var(--border)' }}>{k.label}</td>
                  <td style={{ padding: '10px 12px', borderBottom: '1px solid var(--border)' }}>
                    <span style={{ background: TIER_COLORS[k.tier] || '#6B7280', color: 'white', fontSize: 11, fontWeight: 700, padding: '2px 8px', borderRadius: 10, textTransform: 'capitalize' }}>{k.tier}</span>
                  </td>
                  <td style={{ padding: '10px 12px', borderBottom: '1px solid var(--border)', fontFamily: 'monospace', fontSize: 11 }}>{k.key_prefix}</td>
                  <td style={{ padding: '10px 12px', borderBottom: '1px solid var(--border)', color: 'var(--text-secondary)' }}>{k.created_at ? new Date(k.created_at).toLocaleDateString('en-PK') : '—'}</td>
                  <td style={{ padding: '10px 12px', borderBottom: '1px solid var(--border)', color: 'var(--text-secondary)' }}>{k.last_used_at ? new Date(k.last_used_at).toLocaleDateString('en-PK') : 'Never'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      {/* Agent Run History */}
      <section style={{ background: 'white', border: '1px solid var(--border)', borderRadius: 12, padding: 24 }}>
        <h2 style={{ fontSize: 16, fontWeight: 700, marginBottom: 16 }}>Agent Run History</h2>
        {history.length === 0 ? (
          <p style={{ fontSize: 14, color: 'var(--text-secondary)' }}>No runs yet. Use the Queue page to start an agent run.</p>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr>
                {['Run ID', 'Status', 'Completed'].map(h => (
                  <th key={h} style={{ textAlign: 'left', padding: '8px 12px', fontSize: 11, fontWeight: 600, color: 'var(--text-secondary)', borderBottom: '1px solid var(--border)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {history.map(r => (
                <tr key={r.run_id}>
                  <td style={{ padding: '10px 12px', borderBottom: '1px solid var(--border)', fontFamily: 'monospace', fontSize: 11 }}>{r.run_id.substring(0, 16)}…</td>
                  <td style={{ padding: '10px 12px', borderBottom: '1px solid var(--border)' }}>
                    <span style={{
                      background: r.status === 'completed' ? '#D1FAE5' : r.status === 'failed' ? '#FEE2E2' : '#FEF3C7',
                      color: r.status === 'completed' ? '#065F46' : r.status === 'failed' ? '#991B1B' : '#92400E',
                      fontSize: 11, fontWeight: 700, padding: '2px 8px', borderRadius: 10, textTransform: 'capitalize',
                    }}>{r.status}</span>
                  </td>
                  <td style={{ padding: '10px 12px', borderBottom: '1px solid var(--border)', color: 'var(--text-secondary)' }}>
                    {r.completed_at ? new Date(r.completed_at).toLocaleString('en-PK', { timeZone: 'Asia/Karachi' }) : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
