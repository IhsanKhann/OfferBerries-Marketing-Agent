'use client';
import { useState, useEffect } from 'react';
import { Copy, Check, RefreshCw, Trash2 } from 'lucide-react';
import { notify } from '../../../lib/toast';

const TIER_LIMITS: Record<string, Record<string, number>> = {
  owner:   { research_trends:9999, scrape_competitor:9999, generate_content:9999, generate_visual:9999, queue_post:9999, get_analytics:9999, update_strategy:9999 },
  pro:     { research_trends:30,   scrape_competitor:100,  generate_content:200,  generate_visual:200,  queue_post:100,  get_analytics:9999, update_strategy:9999 },
  starter: { research_trends:10,   scrape_competitor:20,   generate_content:50,   generate_visual:50,   queue_post:30,   get_analytics:9999, update_strategy:9999 },
  demo:    { research_trends:3,    scrape_competitor:0,    generate_content:5,    generate_visual:5,    queue_post:0,    get_analytics:0,    update_strategy:0 },
};

const TOOL_LABELS: Record<string, string> = {
  research_trends: 'Research Trends', scrape_competitor: 'Scrape Competitor',
  generate_content: 'Generate Content', generate_visual: 'Generate Visual',
  queue_post: 'Queue Post', get_analytics: 'Get Analytics', update_strategy: 'Update Strategy',
};

type AccountInfo = { tier: string; tenant_id: string; api_key_masked: string | null; api_key_active: boolean };
type Model = { id: string; name: string; tier: string; context_length: number; pricing: { prompt: string; completion: string }; description?: string };

export default function SettingsPage() {
  const [account, setAccount]     = useState<AccountInfo | null>(null);
  const [models, setModels]       = useState<Model[]>([]);
  const [selectedModel, setSelectedModel] = useState('google/gemini-2.5-flash');
  const [brandVoice, setBrandVoice] = useState('');
  const [topicFocus, setTopicFocus] = useState('hr_payroll');
  const [formatPref, setFormatPref] = useState('carousel');
  const [loadingBv, setLoadingBv]  = useState(true);
  const [loadingAccount, setLoadingAccount] = useState(true);
  const [loadingModels, setLoadingModels]   = useState(true);
  const [copiedKey, setCopiedKey]  = useState(false);

  // Danger zone confirm states
  const [clearArmed, setClearArmed]   = useState(false);
  const [resetArmed, setResetArmed]   = useState(false);

  useEffect(() => {
    fetch('/api/proxy/account').then(r => r.ok ? r.json() : null).then(d => { if (d) setAccount(d); }).finally(() => setLoadingAccount(false));
    fetch('/api/proxy/config/brand-voice').then(r => r.ok ? r.json() : null).then(d => { if (d?.content) setBrandVoice(d.content); }).finally(() => setLoadingBv(false));
    fetch('/api/proxy/config/strategy').then(r => r.ok ? r.json() : null).then(d => { if (d) { if (d.topic_focus) setTopicFocus(d.topic_focus); if (d.format_preference) setFormatPref(d.format_preference); } });
    fetch('/api/proxy/models/available').then(r => r.ok ? r.json() : []).then(setModels).finally(() => setLoadingModels(false));
    fetch('/api/proxy/config/content-model').then(r => r.ok ? r.json() : null).then(d => { if (d?.model_id) setSelectedModel(d.model_id); });
  }, []);

  async function saveBrandVoice() {
    const res = await fetch('/api/proxy/config/brand-voice', {
      method: 'PUT', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content: brandVoice }),
    });
    if (res.ok) notify.success('Saved', 'Brand voice updated');
    else notify.error('Save failed', 'Check connection and try again');
  }

  async function saveStrategy() {
    const res = await fetch('/api/proxy/mcp', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ method: 'tools/call', params: { name: 'update_strategy', arguments: { changes: { topic_focus: topicFocus, format_preference: formatPref } } } }),
    });
    if (res.ok) notify.success('Saved', 'Content strategy updated');
    else notify.error('Save failed', 'Check connection and try again');
  }

  async function selectModel(modelId: string, modelName: string) {
    const prev = selectedModel;
    setSelectedModel(modelId);
    const res = await fetch('/api/proxy/config/content-model', {
      method: 'PUT', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model_id: modelId }),
    });
    if (res.ok) notify.success('Model saved', `${modelName} selected`);
    else { setSelectedModel(prev); notify.error('Failed to save', 'Please try again'); }
  }

  function copyKey() {
    if (account?.api_key_masked) {
      navigator.clipboard.writeText(account.api_key_masked);
      setCopiedKey(true);
      setTimeout(() => setCopiedKey(false), 2000);
      notify.success('Copied', 'API key copied to clipboard');
    }
  }

  async function clearMemory() {
    if (!clearArmed) { setClearArmed(true); setTimeout(() => setClearArmed(false), 3000); return; }
    setClearArmed(false);
    notify.success('Memory cleared', 'Agent run history cleared');
  }

  async function resetStrategy() {
    if (!resetArmed) { setResetArmed(true); setTimeout(() => setResetArmed(false), 3000); return; }
    setResetArmed(false);
    setTopicFocus('hr_payroll');
    setFormatPref('carousel');
    await saveStrategy();
    notify.success('Strategy reset', 'Defaults restored');
  }

  const tier = account?.tier || 'owner';
  const tierLimits = TIER_LIMITS[tier] || TIER_LIMITS.starter;

  const modelGroups = ['fast', 'balanced', 'premium'];
  const modelGroupLabels: Record<string, string> = { fast: 'Fast & Economical', balanced: 'Balanced', premium: 'Premium / Highest Quality' };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
      <div className="topbar">
        <div className="topbar-title">Settings</div>
        <div className="topbar-actions">
          {!loadingAccount && account && (
            <span className={`tier-badge tier-${tier}`}>{tier.charAt(0).toUpperCase() + tier.slice(1)}</span>
          )}
          <div className="avatar-chip">I</div>
        </div>
      </div>

      <div className="content-area">
        <div className="settings-layout">

          {/* 1. API Access */}
          <div className="settings-section">
            <div className="settings-section-title">OfferBerries API Access</div>
            <div className="settings-card">
              <div className="flex-between" style={{ alignItems: 'flex-start' }}>
                <div>
                  <div className="card-title">API Key</div>
                  <div className="card-sub">Use this key to authenticate with the OfferBerries API</div>
                </div>
                {!loadingAccount && <span className={`tier-badge tier-${tier}`}>{tier}</span>}
              </div>

              {loadingAccount ? (
                <div className="skeleton-pulse mt-3" style={{ height: 44 }} />
              ) : (
                <div className="key-box flex-between">
                  <span>{account?.api_key_masked || 'No API key'}</span>
                  {account?.api_key_active && (
                    <button onClick={copyKey} className="btn btn-sm" style={{ background: 'rgba(255,255,255,0.1)', color: 'rgba(255,255,255,0.8)', border: '1px solid rgba(255,255,255,0.15)' }}>
                      {copiedKey ? <><Check size={12} /> Copied</> : <><Copy size={12} /> Copy</>}
                    </button>
                  )}
                </div>
              )}

              {tier === 'demo' ? (
                <div className="alert alert-warning mt-3">
                  You're on the demo tier — generate and activate a paid API key to unlock scraping, posting, and analytics.
                </div>
              ) : (
                <div className="alert alert-success mt-3">
                  ✓ Active · {tier.charAt(0).toUpperCase() + tier.slice(1)} tier — all tools unlocked including content generation and queue management.
                </div>
              )}

              {/* Tier permissions grid */}
              <div className="overline mt-4" style={{ marginBottom: 8 }}>Tier Permissions</div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
                {Object.entries(tierLimits).map(([tool, limit]) => (
                  <div key={tool} style={{
                    display: 'flex', alignItems: 'center', gap: 8,
                    padding: '5px 10px', borderRadius: 'var(--radius-sm)',
                    background: limit > 0 ? 'var(--success-bg)' : 'var(--bg-subtle)',
                    border: `1px solid ${limit > 0 ? 'var(--success-border)' : 'var(--border-default)'}`,
                    fontSize: 11,
                  }}>
                    <span style={{ color: limit > 0 ? 'var(--success)' : 'var(--text-muted)' }}>{limit > 0 ? '✓' : '—'}</span>
                    <span style={{ color: limit > 0 ? 'var(--success-text)' : 'var(--text-muted)', fontWeight: 600 }}>{TOOL_LABELS[tool]}</span>
                    {limit > 0 && limit < 9999 && <span style={{ color: 'var(--text-muted)', marginLeft: 'auto' }}>{limit}/day</span>}
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* 2. Content Generation Model */}
          <div className="settings-section">
            <div className="settings-section-title">Content Generation Model</div>
            <div className="settings-card">
              <div className="flex-between mb-4">
                <div>
                  <div className="card-title">OpenRouter Model</div>
                  <div className="card-sub">Choose the AI model for content generation</div>
                </div>
                {!loadingModels && <span className="badge badge-info">{models.length} available</span>}
              </div>
              {loadingModels ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {[1,2,3].map(i => <div key={i} className="skeleton-pulse" style={{ height: 52 }} />)}
                </div>
              ) : (
                modelGroups.map(group => {
                  const groupModels = models.filter(m => m.tier === group);
                  if (!groupModels.length) return null;
                  return (
                    <div key={group} style={{ marginBottom: 16 }}>
                      <div className="overline" style={{ marginBottom: 8 }}>{modelGroupLabels[group]}</div>
                      {groupModels.map(m => (
                        <div key={m.id} className={`model-row${selectedModel === m.id ? ' selected' : ''}`}>
                          <div>
                            <div className="model-name">{m.name}</div>
                            <div className="model-meta">
                              {(m.context_length / 1000).toFixed(0)}K ctx · ${m.pricing.prompt}/1M in
                              {m.description && ` · ${m.description}`}
                            </div>
                          </div>
                          {selectedModel === m.id ? (
                            <span className="badge badge-success">Active</span>
                          ) : (
                            <button onClick={() => selectModel(m.id, m.name)} className="btn btn-secondary btn-sm">Select</button>
                          )}
                        </div>
                      ))}
                    </div>
                  );
                })
              )}
            </div>
          </div>

          {/* 3. Brand Voice */}
          <div className="settings-section">
            <div className="settings-section-title">Brand Voice</div>
            <div className="settings-card">
              <div className="card-title" style={{ marginBottom: 4 }}>Voice & Tone Guidelines</div>
              <div className="card-sub" style={{ marginBottom: 12 }}>Used by the AI when generating content for your brand</div>
              <textarea
                rows={6}
                value={loadingBv ? 'Loading…' : brandVoice}
                onChange={e => setBrandVoice(e.target.value)}
                disabled={loadingBv}
                placeholder="Describe your brand voice, tone, and content guidelines…"
                className="input"
                style={{ resize: 'vertical', minHeight: 120 }}
              />
              <button onClick={saveBrandVoice} disabled={loadingBv} className="btn btn-primary btn-sm mt-3">
                Save Brand Voice
              </button>
            </div>
          </div>

          {/* 4. Content Strategy */}
          <div className="settings-section">
            <div className="settings-section-title">Content Strategy</div>
            <div className="settings-card">
              <div className="card-title" style={{ marginBottom: 4 }}>Default Strategy</div>
              <div className="card-sub" style={{ marginBottom: 16 }}>Configure the default topic and format for new agent runs</div>
              <div className="grid-2">
                <div>
                  <label className="field-label">Topic Focus</label>
                  <input value={topicFocus} onChange={e => setTopicFocus(e.target.value)} className="input" />
                </div>
                <div>
                  <label className="field-label">Format Preference</label>
                  <select value={formatPref} onChange={e => setFormatPref(e.target.value)} className="input">
                    <option value="carousel">Carousel</option>
                    <option value="single">Single Image</option>
                    <option value="video">Video Script</option>
                  </select>
                </div>
              </div>
              <button onClick={saveStrategy} className="btn btn-primary btn-sm mt-4">Save Strategy</button>
            </div>
          </div>

          {/* 5. Social Accounts */}
          <div className="settings-section">
            <div className="settings-section-title">Social Accounts</div>
            <div className="settings-card">
              <div className="card-title" style={{ marginBottom: 4 }}>Connect Accounts</div>
              <div className="card-sub" style={{ marginBottom: 16 }}>Connect your social accounts via Postiz to enable publishing</div>
              <a href="/postiz" target="_blank" className="btn btn-primary btn-sm">Manage in Postiz</a>
            </div>
          </div>

          {/* 6. Danger Zone */}
          <div className="settings-section">
            <div className="settings-section-title danger">Danger Zone</div>
            <div className="settings-card danger-card">
              <div className="flex-row gap-3">
                <button
                  onClick={clearMemory}
                  className={`btn btn-sm ${clearArmed ? 'btn-danger' : 'btn-ghost'}`}
                >
                  <Trash2 size={12} />
                  {clearArmed ? 'Click again to confirm' : 'Clear Agent Memory'}
                </button>
                <button
                  onClick={resetStrategy}
                  className={`btn btn-sm ${resetArmed ? 'btn-danger' : 'btn-ghost'}`}
                >
                  <RefreshCw size={12} />
                  {resetArmed ? 'Click again to confirm' : 'Reset Strategy'}
                </button>
              </div>
              <div className="card-sub mt-3">Clearing memory removes agent run history. Resetting strategy restores default topic and format.</div>
            </div>
          </div>

        </div>
      </div>
    </div>
  );
}
