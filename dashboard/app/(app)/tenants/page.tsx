'use client';
import { useEffect, useState } from 'react';
import { Copy, Check, Plus } from 'lucide-react';
import { notify } from '../../../lib/toast';

type ApiKey = { key_prefix: string; tenant_id: string; tier: string; label: string; created_at: string; last_used_at?: string; revoked_at?: string };
type RunSummary = { run_id: string; status: string; completed_at: string };

const TIER_BADGE: Record<string, string> = { owner: 'badge-hr', pro: 'badge-fin', starter: 'badge-success', demo: 'badge-muted' };
const STATUS_BADGE: Record<string, string> = { completed: 'badge-success', failed: 'badge-danger', running: 'badge-warning' };

export default function TenantsPage() {
  const [keys, setKeys]         = useState<ApiKey[]>([]);
  const [history, setHistory]   = useState<RunSummary[]>([]);
  const [loading, setLoading]   = useState(true);
  const [newTier, setNewTier]   = useState('starter');
  const [newTenantId, setNewTenantId] = useState('');
  const [newLabel, setNewLabel] = useState('');
  const [newKey, setNewKey]     = useState('');
  const [creating, setCreating] = useState(false);
  const [demoLink, setDemoLink] = useState('');
  const [copied, setCopied]     = useState(false);

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
      notify.success('API key created', 'Copy it now — shown once');
    } else {
      notify.error('Failed to create key', 'Check permissions');
    }
    setCreating(false);
  }

  async function createDemo() {
    const res = await fetch('/api/proxy/admin/tenants/demo', { method: 'POST' });
    if (res.ok) {
      const data = await res.json();
      setDemoLink(`Key: ${data.api_key}\nExpires: ${data.expires_at}\nDemo URL: ${data.demo_url}`);
      notify.success('Demo session created', '30-minute key generated');
    }
  }

  function copyKey() {
    navigator.clipboard.writeText(newKey);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
    notify.success('Copied', 'API key copied to clipboard');
  }

  if (loading) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
        <div className="topbar"><div className="topbar-title">Tenant Management</div></div>
        <div className="content-area">
          {[1,2,3].map(i => <div key={i} className="skeleton-pulse mb-4" style={{ height: 80 }} />)}
        </div>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
      <div className="topbar">
        <div>
          <div className="topbar-title">Tenant Management</div>
          <div className="topbar-sub">Manage API keys and agent run history</div>
        </div>
        <div className="topbar-actions"><div className="avatar-chip">I</div></div>
      </div>

      <div className="content-area">
        {/* Create API Key */}
        <div className="card mb-4">
          <div className="card-title" style={{ marginBottom: 16 }}>Create API Key</div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 160px auto', gap: 12, alignItems: 'end' }}>
            <div>
              <label className="field-label">Tenant ID</label>
              <input value={newTenantId} onChange={e => setNewTenantId(e.target.value)} placeholder="tenant-uuid" className="input" />
            </div>
            <div>
              <label className="field-label">Label</label>
              <input value={newLabel} onChange={e => setNewLabel(e.target.value)} placeholder="Acme Corp" className="input" />
            </div>
            <div>
              <label className="field-label">Tier</label>
              <select value={newTier} onChange={e => setNewTier(e.target.value)} className="input">
                <option value="starter">Starter</option>
                <option value="pro">Pro</option>
                <option value="owner">Owner</option>
              </select>
            </div>
            <button
              onClick={createKey}
              disabled={creating || !newTenantId.trim() || !newLabel.trim()}
              className="btn btn-primary"
              style={{ alignSelf: 'end' }}
            >
              <Plus size={14} />
              {creating ? 'Creating…' : 'Create Key'}
            </button>
          </div>
          {newKey && (
            <div className="alert alert-success mt-4">
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                <strong>New API Key — copy now, shown once:</strong>
                <button onClick={copyKey} className="btn btn-sm" style={{ background: 'var(--success-bg)', color: 'var(--success-text)', border: '1px solid var(--success-border)' }}>
                  {copied ? <><Check size={12} /> Copied</> : <><Copy size={12} /> Copy</>}
                </button>
              </div>
              <code style={{ fontFamily: 'var(--font-mono)', fontSize: 12, wordBreak: 'break-all' }}>{newKey}</code>
            </div>
          )}
        </div>

        {/* Demo Sessions */}
        <div className="card mb-4">
          <div className="flex-between">
            <div>
              <div className="card-title">Demo Sessions</div>
              <div className="card-sub mt-3">Create a 30-minute demo key to share with prospects</div>
            </div>
            <button onClick={createDemo} className="btn btn-primary btn-sm">New Demo</button>
          </div>
          {demoLink && (
            <pre style={{ marginTop: 16, background: 'var(--hr-bg)', border: '1px solid var(--hr-border)', borderRadius: 'var(--radius-md)', padding: 12, fontSize: 12, color: 'var(--hr-text)', whiteSpace: 'pre-wrap', margin: '16px 0 0' }}>
              {demoLink}
            </pre>
          )}
        </div>

        {/* Active API Keys */}
        <div className="card mb-4">
          <div className="card-title" style={{ marginBottom: 16 }}>Active API Keys</div>
          {keys.length === 0 ? (
            <div className="empty-state" style={{ padding: '32px 0' }}>
              <div className="empty-sub">No API keys found.</div>
            </div>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    {['Tenant ID', 'Label', 'Tier', 'Prefix', 'Created', 'Last Used'].map(h => (
                      <th key={h}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {keys.map((k, i) => (
                    <tr key={i} style={{ opacity: k.revoked_at ? 0.4 : 1 }}>
                      <td><code style={{ fontFamily: 'var(--font-mono)', fontSize: 11 }}>{k.tenant_id.substring(0, 20)}…</code></td>
                      <td style={{ fontWeight: 600 }}>{k.label}</td>
                      <td><span className={`badge ${TIER_BADGE[k.tier] || 'badge-muted'}`}>{k.tier}</span></td>
                      <td><code style={{ fontFamily: 'var(--font-mono)', fontSize: 11 }}>{k.key_prefix}</code></td>
                      <td style={{ color: 'var(--text-muted)' }}>{k.created_at ? new Date(k.created_at).toLocaleDateString('en-PK') : '—'}</td>
                      <td style={{ color: 'var(--text-muted)' }}>{k.last_used_at ? new Date(k.last_used_at).toLocaleDateString('en-PK') : 'Never'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Agent Run History */}
        <div className="card">
          <div className="card-title" style={{ marginBottom: 16 }}>Agent Run History</div>
          {history.length === 0 ? (
            <div className="empty-state" style={{ padding: '32px 0' }}>
              <div className="empty-sub">No runs yet. Use the Queue page to start an agent run.</div>
            </div>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>{['Run ID', 'Status', 'Completed'].map(h => <th key={h}>{h}</th>)}</tr>
                </thead>
                <tbody>
                  {history.map(r => (
                    <tr key={r.run_id}>
                      <td><code style={{ fontFamily: 'var(--font-mono)', fontSize: 11 }}>{r.run_id.substring(0, 16)}…</code></td>
                      <td><span className={`badge ${STATUS_BADGE[r.status] || 'badge-muted'}`}>{r.status}</span></td>
                      <td style={{ color: 'var(--text-muted)' }}>{r.completed_at ? new Date(r.completed_at).toLocaleString('en-PK', { timeZone: 'Asia/Karachi' }) : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
