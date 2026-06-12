'use client';
import { useState } from 'react';

export default function SettingsPage() {
  const [saved, setSaved] = useState('');

  function showSaved(msg: string) {
    setSaved(msg);
    setTimeout(() => setSaved(''), 3000);
  }

  return (
    <div>
      <h1 style={{ fontSize: 28, fontWeight: 700, marginBottom: 8 }}>Settings</h1>
      {saved && <div style={{ background: '#D1FAE5', color: '#065F46', padding: '10px 16px', borderRadius: 6, marginBottom: 24, fontSize: 14, fontWeight: 600 }}>{saved}</div>}

      {/* Social Accounts */}
      <section style={{ background: 'white', border: '1px solid var(--border)', borderRadius: 12, padding: 24, marginBottom: 20 }}>
        <h2 style={{ fontSize: 16, fontWeight: 700, marginBottom: 4 }}>Social Accounts</h2>
        <p style={{ fontSize: 14, color: 'var(--text-secondary)', marginBottom: 16 }}>Connect your social accounts via Postiz to enable publishing.</p>
        <a
          href="/postiz"
          target="_blank"
          style={{ display: 'inline-block', padding: '8px 20px', background: 'var(--brand-primary)', color: 'white', borderRadius: 6, fontSize: 13, fontWeight: 600 }}
        >
          Manage in Postiz
        </a>
      </section>

      {/* Brand Voice */}
      <section style={{ background: 'white', border: '1px solid var(--border)', borderRadius: 12, padding: 24, marginBottom: 20 }}>
        <h2 style={{ fontSize: 16, fontWeight: 700, marginBottom: 4 }}>Brand Voice</h2>
        <p style={{ fontSize: 14, color: 'var(--text-secondary)', marginBottom: 16 }}>Edit the brand voice guidelines used by the AI to generate content.</p>
        <textarea
          rows={8}
          placeholder="Loading brand voice..."
          style={{ width: '100%', padding: 12, border: '1px solid var(--border)', borderRadius: 6, fontSize: 13, fontFamily: 'monospace', resize: 'vertical' }}
        />
        <button
          onClick={() => showSaved('Brand voice saved')}
          style={{ marginTop: 12, padding: '8px 20px', background: 'var(--brand-primary)', color: 'white', border: 'none', borderRadius: 6, fontSize: 13, fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit' }}
        >
          Save
        </button>
      </section>

      {/* Content Strategy */}
      <section style={{ background: 'white', border: '1px solid var(--border)', borderRadius: 12, padding: 24, marginBottom: 20 }}>
        <h2 style={{ fontSize: 16, fontWeight: 700, marginBottom: 4 }}>Content Strategy</h2>
        <p style={{ fontSize: 14, color: 'var(--text-secondary)', marginBottom: 16 }}>Configure the weekly content strategy for the agent.</p>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          <div>
            <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 6 }}>Topic Focus</label>
            <input style={{ width: '100%', padding: '8px 12px', border: '1px solid var(--border)', borderRadius: 6, fontSize: 13, fontFamily: 'inherit' }} defaultValue="hr_payroll" />
          </div>
          <div>
            <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 6 }}>Format Preference</label>
            <select style={{ width: '100%', padding: '8px 12px', border: '1px solid var(--border)', borderRadius: 6, fontSize: 13, fontFamily: 'inherit' }}>
              <option value="carousel">Carousel</option>
              <option value="single">Single Image</option>
              <option value="video">Video Script</option>
            </select>
          </div>
        </div>
        <button
          onClick={() => showSaved('Strategy updated')}
          style={{ marginTop: 16, padding: '8px 20px', background: 'var(--brand-primary)', color: 'white', border: 'none', borderRadius: 6, fontSize: 13, fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit' }}
        >
          Save Strategy
        </button>
      </section>

      {/* Billing */}
      <section style={{ background: 'white', border: '1px solid var(--border)', borderRadius: 12, padding: 24, marginBottom: 20 }}>
        <h2 style={{ fontSize: 16, fontWeight: 700, marginBottom: 4 }}>Billing</h2>
        <p style={{ fontSize: 14, color: 'var(--text-secondary)', marginBottom: 8 }}>Current plan: <strong>Owner</strong></p>
        <a href="/billing" style={{ fontSize: 13, color: 'var(--brand-primary)', fontWeight: 600 }}>Manage billing</a>
      </section>

      {/* Danger Zone */}
      <section style={{ background: 'white', border: '1px solid #FCA5A5', borderRadius: 12, padding: 24 }}>
        <h2 style={{ fontSize: 16, fontWeight: 700, marginBottom: 4, color: '#EF4444' }}>Danger Zone</h2>
        <div style={{ display: 'flex', gap: 12, marginTop: 12 }}>
          <button
            onClick={() => confirm('Clear all agent memory?') && showSaved('Agent memory cleared')}
            style={{ padding: '8px 16px', background: 'white', color: '#EF4444', border: '1px solid #EF4444', borderRadius: 6, fontSize: 13, fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit' }}
          >
            Clear Agent Memory
          </button>
          <button
            onClick={() => confirm('Reset strategy to defaults?') && showSaved('Strategy reset')}
            style={{ padding: '8px 16px', background: 'white', color: '#EF4444', border: '1px solid #EF4444', borderRadius: 6, fontSize: 13, fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit' }}
          >
            Reset Strategy
          </button>
        </div>
      </section>
    </div>
  );
}
