'use client';
import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { notify } from '../../../lib/toast';

export default function LoginPage() {
  const [apiKey, setApiKey] = useState('');
  const [error, setError]   = useState('');
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
        notify.success('Welcome back!', 'Redirecting to dashboard…');
        router.push('/queue');
      } else {
        setError('Invalid API key — check your key and try again.');
        notify.error('Invalid API key', 'Check your key and try again');
      }
    } catch {
      setError('Connection error. Please try again.');
      notify.error('Connection error', 'Please check your network');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="login-shell">
      {/* Left — auth card */}
      <div className="login-left">
        <div className="login-form-wrap">
          {/* Logo */}
          <div className="login-logo">
            <div className="login-logo-mark">O</div>
            <div>
              <div className="login-logo-name">OfferBerries</div>
            </div>
          </div>

          <h1 className="login-heading">Welcome back</h1>
          <p className="login-sub">Sign in to your Marketing Agent dashboard</p>

          <form onSubmit={handleSubmit}>
            <div style={{ marginBottom: 16 }}>
              <label className="field-label" htmlFor="apikey">API Key</label>
              <input
                id="apikey"
                type="password"
                value={apiKey}
                onChange={e => setApiKey(e.target.value)}
                placeholder="ofb_owner_..."
                required
                className={`input ${error ? 'input-error' : ''}`}
              />
            </div>

            {error && (
              <div className="alert alert-danger" role="alert">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading || !apiKey.trim()}
              className="btn btn-primary"
              style={{ width: '100%', marginTop: 4 }}
            >
              {loading ? (
                <>
                  <span className="spinner" />
                  Authenticating…
                </>
              ) : 'Sign In'}
            </button>
          </form>

          <div className="login-divider"><span>or</span></div>

          <a href="/demo" className="btn btn-secondary" style={{ width: '100%', textAlign: 'center', display: 'flex', justifyContent: 'center' }}>
            Try the demo instead
          </a>

          <p className="login-footer">
            By signing in you agree to OfferBerries Terms of Service
          </p>
        </div>
      </div>

      {/* Right — branded visual panel */}
      <div className="login-right">
        {/* Decorative floating cards */}
        <div className="login-panel-cards">
          {/* Queue card */}
          <div className="panel-card" style={{ top: '18%', left: '12%', width: 200 }}>
            <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.6)', fontWeight: 700, letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: 8 }}>Queue · 3 pending</div>
            {['LinkedIn post', 'Twitter thread', 'Instagram reel'].map((p, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '5px 0', borderBottom: i < 2 ? '1px solid rgba(255,255,255,0.1)' : 'none' }}>
                <div style={{ width: 6, height: 6, borderRadius: '50%', background: ['#0A66C2','#1D9BF0','#E1306C'][i] }} />
                <span style={{ fontSize: 12, color: 'rgba(255,255,255,0.85)' }}>{p}</span>
              </div>
            ))}
          </div>

          {/* Analytics card */}
          <div className="panel-card" style={{ top: '30%', right: '8%', width: 170 }}>
            <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.6)', fontWeight: 700, letterSpacing: '0.06em', marginBottom: 8, textTransform: 'uppercase' }}>This Week</div>
            <div style={{ fontSize: 28, fontWeight: 800, color: 'white', lineHeight: 1 }}>94%</div>
            <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.6)', marginTop: 4 }}>engagement rate</div>
            <div style={{ marginTop: 12, height: 4, borderRadius: 9999, background: 'rgba(255,255,255,0.15)', overflow: 'hidden' }}>
              <div style={{ height: '100%', width: '94%', borderRadius: 9999, background: 'rgba(255,255,255,0.7)' }} />
            </div>
          </div>

          {/* Stepper card */}
          <div className="panel-card" style={{ bottom: '24%', left: '18%', width: 190 }}>
            <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.6)', fontWeight: 700, letterSpacing: '0.06em', marginBottom: 10, textTransform: 'uppercase' }}>Agent Pipeline</div>
            {['Research', 'Generate', 'Queue'].map((step, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: i < 2 ? 8 : 0 }}>
                <div style={{ width: 18, height: 18, borderRadius: '50%', background: i === 0 ? 'rgba(255,255,255,0.9)' : i === 1 ? 'rgba(255,255,255,0.4)' : 'rgba(255,255,255,0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  {i === 0 && <span style={{ fontSize: 10, color: '#4F46E5', fontWeight: 800 }}>✓</span>}
                </div>
                <span style={{ fontSize: 12, color: i === 0 ? 'rgba(255,255,255,0.95)' : 'rgba(255,255,255,0.5)' }}>{step}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Bottom tagline */}
        <div style={{ position: 'relative', zIndex: 2, textAlign: 'center' }}>
          <p style={{ fontSize: 18, fontWeight: 700, color: 'white', marginBottom: 6, lineHeight: 1.4 }}>
            Research, generate, and publish — on autopilot.
          </p>
          <p style={{ fontSize: 13, color: 'rgba(255,255,255,0.65)', lineHeight: 1.5 }}>
            AI-powered social content for Pakistani SMBs
          </p>
        </div>
      </div>
    </div>
  );
}
