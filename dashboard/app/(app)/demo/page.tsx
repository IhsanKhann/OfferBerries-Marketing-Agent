'use client';
import { useState } from 'react';

export default function DemoPage() {
  const [demoKey, setDemoKey] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [step, setStep] = useState(0);
  const [research, setResearch] = useState<{ trending_angles: string[]; pain_points: string[] } | null>(null);
  const [content, setContent] = useState<{ copy: string } | null>(null);
  const [visualUrl, setVisualUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function startDemo() {
    setLoading(true);
    const res = await fetch('/api/demo/session', { method: 'POST', body: '{}', headers: { 'Content-Type': 'application/json' } });
    if (res.ok) {
      const data = await res.json();
      setDemoKey(data.api_key);
      setSessionId(data.session_id);
      setStep(1);
    }
    setLoading(false);
  }

  async function doResearch() {
    if (!demoKey) return;
    setLoading(true);
    const res = await fetch('/api/demo/research', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Demo-Key': demoKey },
      body: JSON.stringify({ topic: 'payroll automation Pakistan' }),
    });
    if (res.ok) { setResearch(await res.json()); setStep(2); }
    setLoading(false);
  }

  async function doGenerate() {
    if (!demoKey || !research) return;
    setLoading(true);
    const res = await fetch('/api/demo/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Demo-Key': demoKey },
      body: JSON.stringify({ brief: research }),
    });
    if (res.ok) { setContent(await res.json()); setStep(3); }
    setLoading(false);
  }

  async function doVisual() {
    if (!demoKey || !content) return;
    setLoading(true);
    const res = await fetch('/api/demo/visual', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Demo-Key': demoKey },
      body: JSON.stringify({ content, template_id: 'linkedin-single' }),
    });
    if (res.ok) {
      const data = await res.json();
      setVisualUrl(data.preview_url);
      setStep(4);
    }
    setLoading(false);
  }

  return (
    <div style={{ maxWidth: 800, margin: '0 auto', padding: 40 }}>
      <div style={{ textAlign: 'center', marginBottom: 48 }}>
        <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--brand-primary)', letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: 12 }}>OfferBerries Marketing Agent</div>
        <h1 style={{ fontSize: 40, fontWeight: 800, color: 'var(--text-primary)', lineHeight: 1.15, marginBottom: 16 }}>
          AI-powered marketing for Pakistani SMBs
        </h1>
        <p style={{ fontSize: 18, color: 'var(--text-secondary)', lineHeight: 1.6, maxWidth: 560, margin: '0 auto' }}>
          From topic to published post in minutes. Research, write, and schedule content across LinkedIn, Twitter, and Instagram — automatically.
        </p>
      </div>

      {step === 0 && (
        <div style={{ textAlign: 'center' }}>
          <button
            onClick={startDemo}
            disabled={loading}
            style={{ padding: '16px 40px', background: 'var(--brand-primary)', color: 'white', border: 'none', borderRadius: 8, fontSize: 16, fontWeight: 700, cursor: 'pointer', fontFamily: 'inherit' }}
          >
            {loading ? 'Setting up...' : 'Try the Demo'}
          </button>
          <p style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 12 }}>No signup required. 30-minute session.</p>
        </div>
      )}

      {step >= 1 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {/* Step 1 */}
          <div style={{ background: 'white', border: '1px solid var(--border)', borderRadius: 12, padding: 24 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <h3 style={{ fontSize: 16, fontWeight: 700 }}>1. Research a Topic</h3>
              {step < 2 && (
                <button onClick={doResearch} disabled={loading} style={{ padding: '8px 20px', background: 'var(--brand-primary)', color: 'white', border: 'none', borderRadius: 6, fontSize: 13, fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit' }}>
                  {loading ? 'Researching...' : 'Research Now'}
                </button>
              )}
            </div>
            {research && (
              <div>
                <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 8 }}>Trending angles found:</p>
                <ul style={{ margin: 0, paddingLeft: 20 }}>
                  {research.trending_angles.slice(0, 3).map((a, i) => (
                    <li key={i} style={{ fontSize: 14, color: 'var(--text-primary)', marginBottom: 4 }}>{a}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          {/* Step 2 */}
          {step >= 2 && (
            <div style={{ background: 'white', border: '1px solid var(--border)', borderRadius: 12, padding: 24 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                <h3 style={{ fontSize: 16, fontWeight: 700 }}>2. Generate a Post</h3>
                {step < 3 && (
                  <button onClick={doGenerate} disabled={loading} style={{ padding: '8px 20px', background: 'var(--brand-primary)', color: 'white', border: 'none', borderRadius: 6, fontSize: 13, fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit' }}>
                    {loading ? 'Writing...' : 'Generate Content'}
                  </button>
                )}
              </div>
              {content && (
                <div style={{ background: 'var(--surface-2)', borderRadius: 8, padding: 16 }}>
                  <p style={{ fontSize: 14, color: 'var(--text-primary)', lineHeight: 1.6, margin: 0 }}>{content.copy}</p>
                </div>
              )}
            </div>
          )}

          {/* Step 3 */}
          {step >= 3 && (
            <div style={{ background: 'white', border: '1px solid var(--border)', borderRadius: 12, padding: 24 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                <h3 style={{ fontSize: 16, fontWeight: 700 }}>3. See the Visual</h3>
                {step < 4 && (
                  <button onClick={doVisual} disabled={loading} style={{ padding: '8px 20px', background: 'var(--brand-primary)', color: 'white', border: 'none', borderRadius: 6, fontSize: 13, fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit' }}>
                    {loading ? 'Rendering...' : 'Generate Visual'}
                  </button>
                )}
              </div>
              {visualUrl && <img src={visualUrl} alt="Generated visual" style={{ maxWidth: '100%', borderRadius: 8 }} />}
            </div>
          )}
        </div>
      )}

      {/* Pricing */}
      <div style={{ marginTop: 64, textAlign: 'center' }}>
        <h2 style={{ fontSize: 28, fontWeight: 700, marginBottom: 8 }}>Ready to automate your marketing?</h2>
        <p style={{ fontSize: 16, color: 'var(--text-secondary)', marginBottom: 40 }}>No long-term contracts. Cancel anytime.</p>
        <div style={{ display: 'flex', gap: 20, justifyContent: 'center' }}>
          {[
            { plan: 'Starter', price: 'PKR 4,999', desc: 'Up to 50 posts/month', cta: 'Get Started' },
            { plan: 'Pro', price: 'PKR 14,999', desc: 'Unlimited posts + analytics', cta: 'Get Pro', highlight: true },
          ].map(({ plan, price, desc, cta, highlight }) => (
            <div key={plan} style={{
              background: highlight ? 'var(--brand-primary)' : 'white',
              border: `1px solid ${highlight ? 'var(--brand-primary)' : 'var(--border)'}`,
              borderRadius: 12,
              padding: 32,
              width: 280,
              textAlign: 'left',
            }}>
              <div style={{ fontSize: 14, fontWeight: 700, color: highlight ? 'rgba(255,255,255,0.7)' : 'var(--text-secondary)', marginBottom: 8 }}>{plan}</div>
              <div style={{ fontSize: 32, fontWeight: 800, color: highlight ? 'white' : 'var(--text-primary)', marginBottom: 4 }}>{price}</div>
              <div style={{ fontSize: 14, color: highlight ? 'rgba(255,255,255,0.7)' : 'var(--text-secondary)', marginBottom: 24 }}>/month · {desc}</div>
              <a href="/billing" style={{
                display: 'block',
                padding: '12px 0',
                background: highlight ? 'white' : 'var(--brand-primary)',
                color: highlight ? 'var(--brand-primary)' : 'white',
                borderRadius: 6,
                fontSize: 14,
                fontWeight: 700,
                textAlign: 'center',
              }}>{cta}</a>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
