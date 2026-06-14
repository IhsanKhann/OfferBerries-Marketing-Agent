'use client';
import { useState } from 'react';
import { ArrowRight, Check } from 'lucide-react';

export default function DemoPage() {
  const [demoKey, setDemoKey] = useState<string | null>(null);
  const [step, setStep]       = useState(0);
  const [research, setResearch]   = useState<{ trending_angles: string[]; pain_points: string[] } | null>(null);
  const [content, setContent]     = useState<{ copy: string } | null>(null);
  const [visualUrl, setVisualUrl] = useState<string | null>(null);
  const [loading, setLoading]     = useState(false);

  async function startDemo() {
    setLoading(true);
    const res = await fetch('/api/demo/session', { method: 'POST', body: '{}', headers: { 'Content-Type': 'application/json' } });
    if (res.ok) { const d = await res.json(); setDemoKey(d.api_key); setStep(1); }
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
    if (res.ok) { const d = await res.json(); setVisualUrl(d.preview_url); setStep(4); }
    setLoading(false);
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
      <div className="topbar">
        <div>
          <div className="topbar-title">Live Demo</div>
          <div className="topbar-sub">No signup required · 30-minute session</div>
        </div>
        {step > 0 && (
          <div className="topbar-actions">
            {[1,2,3,4].map(i => (
              <div key={i} style={{ width: 8, height: 8, borderRadius: '50%', background: step >= i ? 'var(--success)' : 'var(--border-default)' }} />
            ))}
          </div>
        )}
      </div>

      <div className="content-area" style={{ overflowY: 'auto' }}>
        <div style={{ maxWidth: 720, margin: '0 auto' }}>
          {/* Hero */}
          <div style={{ textAlign: 'center', marginBottom: 48 }}>
            <div style={{ display: 'inline-flex', alignItems: 'center', gap: 8, background: 'var(--hr-bg)', color: 'var(--hr-text)', border: '1px solid var(--hr-border)', borderRadius: 'var(--radius-full)', padding: '4px 14px', fontSize: 12, fontWeight: 700, marginBottom: 16 }}>
              ✦ OfferBerries Marketing Agent
            </div>
            <h1 style={{ fontSize: 36, fontWeight: 800, color: 'var(--text-primary)', lineHeight: 1.2, marginBottom: 16 }}>
              AI-powered marketing for<br />Pakistani SMBs
            </h1>
            <p style={{ fontSize: 16, color: 'var(--text-secondary)', lineHeight: 1.6, maxWidth: 480, margin: '0 auto 32px' }}>
              From topic to published post in minutes — research, write, and schedule content across LinkedIn, Twitter, and Instagram automatically.
            </p>

            {step === 0 && (
              <div>
                <button
                  onClick={startDemo}
                  disabled={loading}
                  className="btn btn-primary btn-lg"
                >
                  {loading ? <><span className="spinner" /> Setting up…</> : <>Try the Demo <ArrowRight size={16} /></>}
                </button>
              </div>
            )}
          </div>

          {/* Steps */}
          {step >= 1 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              {/* Step 1: Research */}
              <div className="card">
                <div className="flex-between" style={{ marginBottom: research ? 16 : 0 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <div style={{ width: 28, height: 28, borderRadius: 'var(--radius-full)', background: step >= 2 ? 'var(--success)' : 'var(--brand-primary)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'white', fontSize: 12, fontWeight: 700 }}>
                      {step >= 2 ? <Check size={14} /> : '1'}
                    </div>
                    <div>
                      <div className="card-title">Research a Topic</div>
                      <div className="card-sub">Topic: payroll automation Pakistan</div>
                    </div>
                  </div>
                  {step < 2 && (
                    <button onClick={doResearch} disabled={loading} className="btn btn-primary btn-sm">
                      {loading ? <><span className="spinner" style={{ width: 10, height: 10 }} /> Researching…</> : 'Research Now'}
                    </button>
                  )}
                </div>
                {research && (
                  <div>
                    <div className="overline" style={{ marginBottom: 8 }}>Trending angles found</div>
                    <ul style={{ margin: 0, padding: 0, listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 6 }}>
                      {research.trending_angles.slice(0, 3).map((a, i) => (
                        <li key={i} style={{ display: 'flex', gap: 8, fontSize: 13, color: 'var(--text-primary)', padding: '8px 12px', background: 'var(--bg-subtle)', borderRadius: 'var(--radius-sm)' }}>
                          <span style={{ color: 'var(--brand-primary)' }}>→</span> {a}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>

              {/* Step 2: Generate */}
              {step >= 2 && (
                <div className="card">
                  <div className="flex-between" style={{ marginBottom: content ? 16 : 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                      <div style={{ width: 28, height: 28, borderRadius: 'var(--radius-full)', background: step >= 3 ? 'var(--success)' : 'var(--brand-primary)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'white', fontSize: 12, fontWeight: 700 }}>
                        {step >= 3 ? <Check size={14} /> : '2'}
                      </div>
                      <div className="card-title">Generate a Post</div>
                    </div>
                    {step < 3 && (
                      <button onClick={doGenerate} disabled={loading} className="btn btn-primary btn-sm">
                        {loading ? <><span className="spinner" style={{ width: 10, height: 10 }} /> Writing…</> : 'Generate Content'}
                      </button>
                    )}
                  </div>
                  {content && (
                    <div style={{ background: 'var(--bg-subtle)', borderRadius: 'var(--radius-md)', padding: 16 }}>
                      <p style={{ fontSize: 14, color: 'var(--text-primary)', lineHeight: 1.6, margin: 0 }}>{content.copy}</p>
                    </div>
                  )}
                </div>
              )}

              {/* Step 3: Visual */}
              {step >= 3 && (
                <div className="card">
                  <div className="flex-between" style={{ marginBottom: visualUrl ? 16 : 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                      <div style={{ width: 28, height: 28, borderRadius: 'var(--radius-full)', background: step >= 4 ? 'var(--success)' : 'var(--brand-primary)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'white', fontSize: 12, fontWeight: 700 }}>
                        {step >= 4 ? <Check size={14} /> : '3'}
                      </div>
                      <div className="card-title">See the Visual</div>
                    </div>
                    {step < 4 && (
                      <button onClick={doVisual} disabled={loading} className="btn btn-primary btn-sm">
                        {loading ? <><span className="spinner" style={{ width: 10, height: 10 }} /> Rendering…</> : 'Generate Visual'}
                      </button>
                    )}
                  </div>
                  {visualUrl && <img src={visualUrl} alt="Generated visual" style={{ maxWidth: '100%', borderRadius: 'var(--radius-md)' }} />}
                </div>
              )}
            </div>
          )}

          {/* Pricing */}
          <div style={{ marginTop: 64, textAlign: 'center' }}>
            <h2 style={{ fontSize: 24, fontWeight: 700, marginBottom: 8 }}>Ready to automate your marketing?</h2>
            <p style={{ fontSize: 15, color: 'var(--text-secondary)', marginBottom: 40 }}>No long-term contracts. Cancel anytime.</p>
            <div style={{ display: 'flex', gap: 20, justifyContent: 'center', flexWrap: 'wrap' }}>
              {[
                { plan: 'Starter', price: 'PKR 4,999', desc: 'Up to 50 posts/month', highlight: false },
                { plan: 'Pro', price: 'PKR 14,999', desc: 'Unlimited posts + analytics', highlight: true },
              ].map(({ plan, price, desc, highlight }) => (
                <div key={plan} className="card" style={{ width: 260, background: highlight ? 'var(--brand-gradient)' : undefined, border: highlight ? 'none' : undefined }}>
                  <div style={{ fontSize: 13, fontWeight: 700, color: highlight ? 'rgba(255,255,255,0.7)' : 'var(--text-muted)', marginBottom: 8 }}>{plan}</div>
                  <div style={{ fontSize: 28, fontWeight: 800, color: highlight ? 'white' : 'var(--text-primary)', marginBottom: 4 }}>{price}</div>
                  <div style={{ fontSize: 13, color: highlight ? 'rgba(255,255,255,0.7)' : 'var(--text-muted)', marginBottom: 20 }}>/month · {desc}</div>
                  <a
                    href="/billing"
                    className="btn"
                    style={{ width: '100%', display: 'flex', justifyContent: 'center', background: highlight ? 'white' : 'var(--brand-gradient)', color: highlight ? 'var(--brand-primary)' : 'white' }}
                  >
                    {highlight ? 'Get Pro' : 'Get Started'}
                  </a>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
