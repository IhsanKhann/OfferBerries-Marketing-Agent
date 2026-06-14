'use client';
import { useState } from 'react';
import { Check } from 'lucide-react';
import { notify } from '../../../lib/toast';

const PLANS = [
  {
    id: 'starter_pkr',
    name: 'Starter',
    price: 'PKR 4,999',
    period: '/month',
    desc: 'For small businesses getting started with social media automation',
    features: ['50 AI-generated posts/month', 'LinkedIn + Twitter + Instagram', 'Brand voice customization', '8 visual card templates', 'Approval queue', 'Email support'],
    highlight: false,
  },
  {
    id: 'pro_pkr',
    name: 'Pro',
    price: 'PKR 14,999',
    period: '/month',
    desc: 'For growing businesses that need full automation and analytics',
    features: ['Unlimited posts', 'All platforms including YouTube', 'Analytics & pattern extraction', 'Weekly strategy auto-updates', 'Competitor tracking (Apify)', 'Custom visual templates', 'Priority support'],
    highlight: true,
  },
];

export default function BillingPage() {
  const [loading, setLoading] = useState<string | null>(null);
  const [email, setEmail]     = useState('');
  const [error, setError]     = useState('');

  async function checkout(planId: string) {
    if (!email.trim()) { setError('Enter your email to continue'); return; }
    setError('');
    setLoading(planId);
    try {
      const res = await fetch('/api/proxy/billing/checkout', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ plan: planId, tenant_email: email }),
      });
      if (res.ok) {
        const data = await res.json();
        if (data.checkout_url) window.location.href = data.checkout_url;
      } else {
        setError('Checkout failed — try again or contact support.');
        notify.error('Checkout failed', 'Try again or contact support');
      }
    } catch {
      setError('Network error — check your connection.');
      notify.error('Network error', 'Check your connection');
    } finally {
      setLoading(null);
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
      <div className="topbar">
        <div>
          <div className="topbar-title">Billing &amp; Plans</div>
          <div className="topbar-sub">No long-term contracts. Cancel anytime. All prices in PKR.</div>
        </div>
        <div className="topbar-actions">
          <div className="avatar-chip">I</div>
        </div>
      </div>

      <div className="content-area">
        {/* Email */}
        <div style={{ maxWidth: 400, marginBottom: 40 }}>
          <label className="field-label">Account email</label>
          <input
            type="email"
            value={email}
            onChange={e => setEmail(e.target.value)}
            placeholder="your@email.com"
            className={`input${error ? ' input-error' : ''}`}
          />
          {error && <div className="alert alert-danger mt-3">{error}</div>}
        </div>

        {/* Plan cards */}
        <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap', marginBottom: 48 }}>
          {PLANS.map(plan => (
            <div
              key={plan.id}
              className="card"
              style={{
                width: 300,
                flex: '0 0 auto',
                background: plan.highlight ? 'var(--brand-gradient)' : undefined,
                border: plan.highlight ? 'none' : undefined,
                boxShadow: plan.highlight ? 'var(--shadow-lg)' : undefined,
              }}
            >
              {plan.highlight && (
                <div style={{ position: 'absolute', top: -1, right: 20, background: 'rgba(255,255,255,0.25)', color: 'white', fontSize: 10, fontWeight: 700, padding: '3px 10px', borderRadius: '0 0 var(--radius-sm) var(--radius-sm)', letterSpacing: '0.06em', textTransform: 'uppercase' }}>Most Popular</div>
              )}
              <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: 8, color: plan.highlight ? 'rgba(255,255,255,0.65)' : 'var(--text-muted)' }}>{plan.name}</div>
              <div style={{ fontSize: 32, fontWeight: 800, color: plan.highlight ? 'white' : 'var(--text-primary)', marginBottom: 2 }}>{plan.price}</div>
              <div style={{ fontSize: 13, color: plan.highlight ? 'rgba(255,255,255,0.65)' : 'var(--text-muted)', marginBottom: 20 }}>{plan.period} · {plan.desc}</div>
              <ul style={{ margin: '0 0 24px', padding: 0, listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 8 }}>
                {plan.features.map(f => (
                  <li key={f} style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>
                    <Check size={14} style={{ color: plan.highlight ? 'rgba(255,255,255,0.8)' : 'var(--success)', flexShrink: 0, marginTop: 1 }} />
                    <span style={{ fontSize: 13, color: plan.highlight ? 'rgba(255,255,255,0.85)' : 'var(--text-primary)', lineHeight: 1.4 }}>{f}</span>
                  </li>
                ))}
              </ul>
              <button
                onClick={() => checkout(plan.id)}
                disabled={loading === plan.id}
                className="btn"
                style={{
                  width: '100%',
                  background: plan.highlight ? 'white' : 'var(--brand-gradient)',
                  color: plan.highlight ? 'var(--brand-primary)' : 'white',
                  padding: '11px 0',
                  fontSize: 14,
                  opacity: loading === plan.id ? 0.7 : 1,
                }}
              >
                {loading === plan.id ? <><span className="spinner" style={{ borderTopColor: plan.highlight ? 'var(--brand-primary)' : 'white' }} /> Redirecting…</> : plan.highlight ? 'Upgrade to Pro' : 'Get Started'}
              </button>
            </div>
          ))}
        </div>

        {/* Current plan */}
        <div className="card" style={{ maxWidth: 640 }}>
          <div className="card-title" style={{ marginBottom: 8 }}>Current Plan</div>
          <p style={{ fontSize: 14, color: 'var(--text-secondary)', margin: 0 }}>
            You are on the <strong>Owner</strong> plan with unlimited access to all features.
          </p>
        </div>

        <p style={{ marginTop: 24, fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.6 }}>
          Payments processed securely via Safepay (Pakistan) · Support: designwithihsan@gmail.com
        </p>
      </div>
    </div>
  );
}
