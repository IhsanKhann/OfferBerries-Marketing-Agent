'use client';
import { useState } from 'react';
import { useRouter } from 'next/navigation';

export default function LoginPage() {
  const [apiKey, setApiKey] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      const res = await fetch('/api/auth', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ api_key: apiKey }),
      });
      if (res.ok) {
        router.push('/queue');
      } else {
        setError('Invalid API key. Please check your key and try again.');
      }
    } catch {
      setError('Connection error. Please try again.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--surface-2)' }}>
      <div style={{ background: 'white', border: '1px solid var(--border)', borderRadius: 12, padding: 48, width: 400, maxWidth: '90vw' }}>
        <div style={{ marginBottom: 32 }}>
          <div style={{ fontSize: 20, fontWeight: 800, color: 'var(--brand-primary)', marginBottom: 8 }}>OfferBerries</div>
          <div style={{ fontSize: 24, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 4 }}>Marketing Agent</div>
          <div style={{ fontSize: 14, color: 'var(--text-secondary)' }}>Enter your API key to continue</div>
        </div>
        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: 16 }}>
            <label style={{ display: 'block', fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 6 }}>
              API Key
            </label>
            <input
              type="password"
              value={apiKey}
              onChange={e => setApiKey(e.target.value)}
              placeholder="ofb_owner_..."
              required
              style={{
                width: '100%',
                padding: '10px 14px',
                border: '1px solid var(--border)',
                borderRadius: 6,
                fontSize: 14,
                fontFamily: 'inherit',
                color: 'var(--text-primary)',
                outline: 'none',
              }}
            />
          </div>
          {error && (
            <div style={{ fontSize: 13, color: '#EF4444', marginBottom: 16 }}>{error}</div>
          )}
          <button
            type="submit"
            disabled={loading || !apiKey}
            style={{
              width: '100%',
              padding: '12px 0',
              background: loading || !apiKey ? '#C4B5D9' : 'var(--brand-primary)',
              color: 'white',
              border: 'none',
              borderRadius: 6,
              fontSize: 14,
              fontWeight: 700,
              cursor: loading || !apiKey ? 'not-allowed' : 'pointer',
              fontFamily: 'inherit',
            }}
          >
            {loading ? 'Authenticating...' : 'Sign In'}
          </button>
        </form>
        <div style={{ marginTop: 24, textAlign: 'center' }}>
          <a href="/demo" style={{ fontSize: 13, color: 'var(--brand-primary)', fontWeight: 600 }}>
            Try the demo instead
          </a>
        </div>
      </div>
    </div>
  );
}
