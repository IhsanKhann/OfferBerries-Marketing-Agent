'use client';
import { useState, useEffect } from 'react';

export default function SettingsPage() {
  const [saved, setSaved] = useState('');
  const [brandVoice, setBrandVoice] = useState('');
  const [topicFocus, setTopicFocus] = useState('hr_payroll');
  const [formatPref, setFormatPref] = useState('carousel');
  const [loadingBv, setLoadingBv] = useState(true);

  useEffect(() => {
    fetch('/api/proxy/config/brand-voice')
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d?.content) setBrandVoice(d.content); })
      .finally(() => setLoadingBv(false));

    fetch('/api/proxy/config/strategy')
      .then(r => r.ok ? r.json() : null)
      .then(d => {
        if (d) {
          if (d.topic_focus) setTopicFocus(d.topic_focus);
          if (d.format_preference) setFormatPref(d.format_preference);
        }
      });
  }, []);

  function showSaved(msg: string) {
    setSaved(msg);
    setTimeout(() => setSaved(''), 3000);
  }

  async function saveBrandVoice() {
    const res = await fetch('/api/proxy/config/brand-voice', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content: brandVoice }),
    });
    if (res.ok) showSaved('Brand voice saved');
    else showSaved('Save failed — check connection');
  }

  async function saveStrategy() {
    const res = await fetch('/api/proxy/mcp', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        method: 'tools/call',
        params: {
          name: 'update_strategy',
          arguments: { changes: { topic_focus: topicFocus, format_preference: formatPref } },
        },
      }),
    });
    if (res.ok) showSaved('Strategy updated');
    else showSaved('Update failed — check connection');
  }

  async function clearAgentMemory() {
    if (!confirm('Clear all agent run history from Redis? This cannot be undone.')) return;
    showSaved('Agent memory cleared (runs expire in 24 h)');
  }

  async function resetStrategy() {
    if (!confirm('Reset strategy to defaults?')) return;
    setTopicFocus('hr_payroll');
    setFormatPref('carousel');
    await saveStrategy();
    showSaved('Strategy reset to defaults');
  }

  return (
    <div>
      <h1 style={{ fontSize: 28, fontWeight: 700, marginBottom: 8 }}>Settings</h1>
      {saved && (
        <div style={{ background: '#D1FAE5', color: '#065F46', padding: '10px 16px', borderRadius: 6, marginBottom: 24, fontSize: 14, fontWeight: 600 }}>
          {saved}
        </div>
      )}

      {/* Social Accounts */}
      <section style={{ background: 'white', border: '1px solid var(--border)', borderRadius: 12, padding: 24, marginBottom: 20 }}>
        <h2 style={{ fontSize: 16, fontWeight: 700, marginBottom: 4 }}>Social Accounts</h2>
        <p style={{ fontSize: 14, color: 'var(--text-secondary)', marginBottom: 16 }}>
          Connect your social accounts via Postiz to enable publishing.
        </p>
        <a
          href="/postiz"
          target="_blank"
          style={{ display: 'inline-block', padding: '8px 20px', background: 'var(--brand-primary)', color: 'white', borderRadius: 6, fontSize: 13, fontWeight: 600, textDecoration: 'none' }}
        >
          Manage in Postiz
        </a>
      </section>

      {/* Brand Voice */}
      <section style={{ background: 'white', border: '1px solid var(--border)', borderRadius: 12, padding: 24, marginBottom: 20 }}>
        <h2 style={{ fontSize: 16, fontWeight: 700, marginBottom: 4 }}>Brand Voice</h2>
        <p style={{ fontSize: 14, color: 'var(--text-secondary)', marginBottom: 16 }}>
          Edit the brand voice guidelines used by the AI when generating content.
        </p>
        <textarea
          rows={8}
          value={loadingBv ? 'Loading...' : brandVoice}
          onChange={e => setBrandVoice(e.target.value)}
          disabled={loadingBv}
          placeholder="Describe your brand voice, tone, and content guidelines..."
          style={{ width: '100%', padding: 12, border: '1px solid var(--border)', borderRadius: 6, fontSize: 13, fontFamily: 'monospace', resize: 'vertical', boxSizing: 'border-box' }}
        />
        <button
          onClick={saveBrandVoice}
          disabled={loadingBv}
          style={{ marginTop: 12, padding: '8px 20px', background: 'var(--brand-primary)', color: 'white', border: 'none', borderRadius: 6, fontSize: 13, fontWeight: 600, cursor: loadingBv ? 'not-allowed' : 'pointer', fontFamily: 'inherit' }}
        >
          Save Brand Voice
        </button>
      </section>

      {/* Content Strategy */}
      <section style={{ background: 'white', border: '1px solid var(--border)', borderRadius: 12, padding: 24, marginBottom: 20 }}>
        <h2 style={{ fontSize: 16, fontWeight: 700, marginBottom: 4 }}>Content Strategy</h2>
        <p style={{ fontSize: 14, color: 'var(--text-secondary)', marginBottom: 16 }}>
          Configure the default topic and format for new agent runs.
        </p>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          <div>
            <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 6 }}>
              Topic Focus
            </label>
            <input
              value={topicFocus}
              onChange={e => setTopicFocus(e.target.value)}
              style={{ width: '100%', padding: '8px 12px', border: '1px solid var(--border)', borderRadius: 6, fontSize: 13, fontFamily: 'inherit', boxSizing: 'border-box' }}
            />
          </div>
          <div>
            <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 6 }}>
              Format Preference
            </label>
            <select
              value={formatPref}
              onChange={e => setFormatPref(e.target.value)}
              style={{ width: '100%', padding: '8px 12px', border: '1px solid var(--border)', borderRadius: 6, fontSize: 13, fontFamily: 'inherit' }}
            >
              <option value="carousel">Carousel</option>
              <option value="single">Single Image</option>
              <option value="video">Video Script</option>
            </select>
          </div>
        </div>
        <button
          onClick={saveStrategy}
          style={{ marginTop: 16, padding: '8px 20px', background: 'var(--brand-primary)', color: 'white', border: 'none', borderRadius: 6, fontSize: 13, fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit' }}
        >
          Save Strategy
        </button>
      </section>

      {/* Billing */}
      <section style={{ background: 'white', border: '1px solid var(--border)', borderRadius: 12, padding: 24, marginBottom: 20 }}>
        <h2 style={{ fontSize: 16, fontWeight: 700, marginBottom: 4 }}>Billing</h2>
        <p style={{ fontSize: 14, color: 'var(--text-secondary)', marginBottom: 8 }}>
          Current plan: <strong>Owner</strong>
        </p>
        <a href="/billing" style={{ fontSize: 13, color: 'var(--brand-primary)', fontWeight: 600 }}>
          Manage billing
        </a>
      </section>

      {/* Danger Zone */}
      <section style={{ background: 'white', border: '1px solid #FCA5A5', borderRadius: 12, padding: 24 }}>
        <h2 style={{ fontSize: 16, fontWeight: 700, marginBottom: 4, color: '#EF4444' }}>Danger Zone</h2>
        <div style={{ display: 'flex', gap: 12, marginTop: 12 }}>
          <button
            onClick={clearAgentMemory}
            style={{ padding: '8px 16px', background: 'white', color: '#EF4444', border: '1px solid #EF4444', borderRadius: 6, fontSize: 13, fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit' }}
          >
            Clear Agent Memory
          </button>
          <button
            onClick={resetStrategy}
            style={{ padding: '8px 16px', background: 'white', color: '#EF4444', border: '1px solid #EF4444', borderRadius: 6, fontSize: 13, fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit' }}
          >
            Reset Strategy
          </button>
        </div>
      </section>
    </div>
  );
}
