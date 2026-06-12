'use client';
import { useState } from 'react';

const BUILT_IN_TEMPLATES = [
  { id: 'linkedin-single', name: 'LinkedIn Single', size: '1080×1080' },
  { id: 'linkedin-carousel-slide', name: 'LinkedIn Carousel Slide', size: '1080×1080' },
  { id: 'twitter-stat-card', name: 'Twitter Stat Card', size: '1600×900' },
  { id: 'instagram-quote', name: 'Instagram Quote', size: '1080×1080' },
  { id: 'instagram-carousel-slide', name: 'Instagram Carousel Slide', size: '1080×1080' },
  { id: 'youtube-thumbnail', name: 'YouTube Thumbnail', size: '1280×720' },
  { id: 'email-header', name: 'Email Header', size: '600×200' },
  { id: 'announcement-card', name: 'Announcement Card', size: '1080×1080' },
];

const SAMPLE_DATA = {
  copy: 'OfferBerries automates payroll for Pakistani SMBs',
  title: 'Introducing OfferBerries HR',
  stat_value: '94%',
  stat_label: 'of Pakistani SMBs waste time on manual payroll',
  quote: 'OfferBerries saved us 3 days every month.',
  attribution: 'CEO, Karachi Textiles',
  hook: 'Stop Wasting 3 Days on Payroll',
  emoji: '🚀',
  body: 'Announcement body text here.',
  week_label: 'This Week',
  module_color: 'hr',
  slide_number: 1,
  total_slides: 4,
  slide_title: 'Step 1: Get Started',
  slide_body: 'Connect your team in under 5 minutes.',
  step_number: 1,
  total_steps: 4,
  step_title: 'Automate Payroll',
  step_body: 'Let OfferBerries handle the rest.',
};

export default function TemplatesPage() {
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [loading, setLoading] = useState<string | null>(null);

  async function previewTemplate(templateId: string) {
    setLoading(templateId);
    const res = await fetch('/api/proxy/render', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ template_id: templateId, content_data: SAMPLE_DATA }),
    });
    if (res.ok) {
      const blob = await res.blob();
      setPreviewUrl(URL.createObjectURL(blob));
      setPreviewOpen(true);
    }
    setLoading(null);
  }

  return (
    <div>
      <h1 style={{ fontSize: 28, fontWeight: 700, marginBottom: 8 }}>Template Manager</h1>
      <p style={{ color: 'var(--text-secondary)', marginBottom: 32, fontSize: 14 }}>
        {BUILT_IN_TEMPLATES.length} built-in templates
      </p>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 16 }}>
        {BUILT_IN_TEMPLATES.map(t => (
          <div key={t.id} style={{ background: 'white', border: '1px solid var(--border)', borderRadius: 12, padding: 24 }}>
            <div style={{ marginBottom: 16 }}>
              <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 4 }}>{t.name}</div>
              <div style={{ fontSize: 12, color: 'var(--text-secondary)', fontWeight: 500 }}>{t.size} · Built-in</div>
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <button
                onClick={() => previewTemplate(t.id)}
                disabled={loading === t.id}
                style={{
                  flex: 1,
                  padding: '8px 0',
                  background: loading === t.id ? '#E2E8F0' : 'var(--brand-primary)',
                  color: loading === t.id ? 'var(--text-secondary)' : 'white',
                  border: 'none',
                  borderRadius: 6,
                  fontSize: 13,
                  fontWeight: 600,
                  cursor: loading === t.id ? 'not-allowed' : 'pointer',
                  fontFamily: 'inherit',
                }}
              >
                {loading === t.id ? 'Rendering...' : 'Preview'}
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Preview lightbox */}
      {previewOpen && previewUrl && (
        <div
          onClick={() => setPreviewOpen(false)}
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.8)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 100,
            cursor: 'pointer',
          }}
        >
          <img src={previewUrl} alt="Template preview" style={{ maxWidth: '90vw', maxHeight: '90vh', borderRadius: 8 }} />
        </div>
      )}
    </div>
  );
}
