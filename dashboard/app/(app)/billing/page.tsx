'use client';
import { useState } from 'react';

const PLANS = [
  {
    id: 'starter_pkr',
    name: 'Starter',
    price: 'PKR 4,999',
    period: '/month',
    desc: 'For small businesses just getting started with social media',
    features: [
      '50 AI-generated posts/month',
      'LinkedIn + Twitter + Instagram',
      'Brand voice customization',
      '8 visual card templates',
      'Approval queue',
      'Email support',
    ],
    cta: 'Get Started',
    highlight: false,
  },
  {
    id: 'pro_pkr',
    name: 'Pro',
    price: 'PKR 14,999',
    period: '/month',
    desc: 'For growing businesses that need full automation',
    features: [
      'Unlimited posts',
      'All platforms including YouTube',
      'Analytics & pattern extraction',
      'Weekly strategy auto-updates',
      'Competitor tracking (Apify)',
      'Custom visual templates',
      'Priority support',
    ],
    cta: 'Upgrade to Pro',
    highlight: true,
  },
];

export default function BillingPage() {
  const [loading, setLoading] = useState<string | null>(null);
  const [email, setEmail] = useState('');
  const [error, setError] = useState('');

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
      }
    } catch {
      setError('Network error — check your connection.');
    } finally {
      setLoading(null);
    }
  }

  return (
    <div>
      <h1 style={{ fontSize: 28, fontWeight: 700, marginBottom: 8 }}>Billing &amp; Plans</h1>
      <p style={{ color: 'var(--text-secondary)', marginBottom: 40, fontSize: 14 }}>
        No long-term contracts. Cancel anytime. All prices in Pakistani Rupees.
      </p>

      {/* Email field */}
      <div style={{ maxWidth: 400, marginBottom: 40 }}>
        <label style={{ display: 'block', fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 6 }}>
          Account email
        </label>
        <input
          type="email"
          value={email}
          onChange={e => setEmail(e.target.value)}
          placeholder="your@email.com"
          style={{ width: '100%', padding: '10px 14px', border: '1px solid var(--border)', borderRadius: 6, fontSize: 14, fontFamily: 'inherit', boxSizing: 'border-box' }}
        />
        {error && <p style={{ color: '#EF4444', fontSize: 13, marginTop: 6 }}>{error}</p>}
      </div>

      {/* Plan cards */}
      <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap' }}>
        {PLANS.map(plan => (
          <div
            key={plan.id}
            style={{
              background: plan.highlight ? 'var(--brand-primary)' : 'white',
              border: `1px solid ${plan.highlight ? 'var(--brand-primary)' : 'var(--border)'}`,
              borderRadius: 16,
              padding: 32,
              width: 300,
              flex: '0 0 auto',
            }}
          >
            <div style={{ fontSize: 13, fontWeight: 700, color: plan.highlight ? 'rgba(255,255,255,0.6)' : 'var(--text-secondary)', letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: 8 }}>{plan.name}</div>
            <div style={{ fontSize: 36, fontWeight: 800, color: plan.highlight ? 'white' : 'var(--text-primary)', marginBottom: 2 }}>{plan.price}</div>
            <div style={{ fontSize: 13, color: plan.highlight ? 'rgba(255,255,255,0.6)' : 'var(--text-secondary)', marginBottom: 16 }}>{plan.period} · {plan.desc}</div>
            <ul style={{ margin: '0 0 28px', paddingLeft: 18 }}>
              {plan.features.map(f => (
                <li key={f} style={{ fontSize: 14, color: plan.highlight ? 'rgba(255,255,255,0.85)' : 'var(--text-primary)', marginBottom: 8, lineHeight: 1.4 }}>{f}</li>
              ))}
            </ul>
            <button
              onClick={() => checkout(plan.id)}
              disabled={loading === plan.id}
              style={{
                width: '100%',
                padding: '12px 0',
                background: plan.highlight ? 'white' : 'var(--brand-primary)',
                color: plan.highlight ? 'var(--brand-primary)' : 'white',
                border: 'none',
                borderRadius: 8,
                fontSize: 14,
                fontWeight: 700,
                cursor: loading === plan.id ? 'not-allowed' : 'pointer',
                fontFamily: 'inherit',
                opacity: loading === plan.id ? 0.7 : 1,
              }}
            >
              {loading === plan.id ? 'Redirecting...' : plan.cta}
            </button>
          </div>
        ))}
      </div>

      {/* Current plan info */}
      <div style={{ marginTop: 48, background: 'white', border: '1px solid var(--border)', borderRadius: 12, padding: 24 }}>
        <h2 style={{ fontSize: 16, fontWeight: 700, marginBottom: 8 }}>Current Plan</h2>
        <p style={{ fontSize: 14, color: 'var(--text-secondary)', margin: 0 }}>
          You are on the <strong>Owner</strong> plan with unlimited access to all features.
        </p>
      </div>

      {/* Payment note */}
      <p style={{ marginTop: 24, fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
        Payments processed securely via Safepay (Pakistan) or 2Checkout. For support: designwithihsan@gmail.com
      </p>
    </div>
  );
}
