'use client';
import { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import { Plus, Trash2, X, Eye } from 'lucide-react';
import { notify } from '@/lib/toast';
import { ProjectFrame } from '../_components/ProjectFrame';

const BUILT_IN_TEMPLATES = [
  { id: 'linkedin-single',          name: 'LinkedIn Single',          size: '1080×1080', platform: 'LinkedIn',  description: 'Single-image post optimised for LinkedIn feed' },
  { id: 'linkedin-carousel-slide',  name: 'LinkedIn Carousel Slide',  size: '1080×1080', platform: 'LinkedIn',  description: 'Carousel slide for multi-page LinkedIn content' },
  { id: 'twitter-stat-card',        name: 'Twitter Stat Card',        size: '1600×900',  platform: 'Twitter',   description: 'Eye-catching stat card for Twitter/X posts' },
  { id: 'instagram-quote',          name: 'Instagram Quote',          size: '1080×1080', platform: 'Instagram', description: 'Bold quote card for Instagram engagement' },
  { id: 'instagram-carousel-slide', name: 'Instagram Carousel Slide', size: '1080×1080', platform: 'Instagram', description: 'Carousel slide formatted for Instagram' },
  { id: 'youtube-thumbnail',        name: 'YouTube Thumbnail',        size: '1280×720',  platform: 'YouTube',   description: 'High-contrast thumbnail for YouTube videos' },
  { id: 'email-header',             name: 'Email Header',             size: '600×200',   platform: 'Email',     description: 'Professional header for email campaigns' },
  { id: 'announcement-card',        name: 'Announcement Card',        size: '1080×1080', platform: 'General',   description: 'Versatile card for product announcements' },
];

const SAMPLE_DATA = {
  copy: 'OfferBerries automates payroll for Pakistani SMBs',
  title: 'Introducing OfferBerries HR', stat_value: '94%',
  stat_label: 'of Pakistani SMBs waste time on manual payroll',
  quote: 'OfferBerries saved us 3 days every month.',
  attribution: 'CEO, Karachi Textiles',
  hook: 'Stop Wasting 3 Days on Payroll', emoji: '🚀',
  body: 'Announcement body text here.', week_label: 'This Week',
  module_color: 'hr', slide_number: 1, total_slides: 4,
  slide_title: 'Step 1: Get Started', slide_body: 'Connect your team in under 5 minutes.',
  step_number: 1, total_steps: 4, step_title: 'Automate Payroll', step_body: 'Let OfferBerries handle the rest.',
};

type Template = { id: string; name: string; description: string; size: string; platform: string; isBuiltIn: boolean; };

const PLATFORM_FILTER_OPTIONS = ['All', 'LinkedIn', 'Twitter', 'Instagram', 'YouTube', 'Email', 'General'];

const PLATFORM_COLOR: Record<string, string> = {
  LinkedIn: '#0A66C2', Twitter: '#1D9BF0', Instagram: '#E1306C',
  YouTube: '#FF0000', Email: '#6366F1', General: '#6B7280',
};

function ProjectTemplatesContent() {
  const [templates] = useState<Template[]>(BUILT_IN_TEMPLATES.map(t => ({ ...t, isBuiltIn: true })));
  const [platformFilter, setPlatformFilter] = useState('All');
  const [previewUrls, setPreviewUrls] = useState<Record<string, string>>({});
  const [loadingPreviews, setLoadingPreviews] = useState<Set<string>>(new Set());
  const [previewModal, setPreviewModal] = useState<{ url: string; name: string } | null>(null);
  const [deleteArmed, setDeleteArmed] = useState<string | null>(null);

  const filtered = templates.filter(t => platformFilter === 'All' || t.platform === platformFilter);

  async function fetchPreview(id: string) {
    if (previewUrls[id] || loadingPreviews.has(id)) return;
    setLoadingPreviews(prev => new Set(prev).add(id));
    try {
      const res = await fetch('/api/proxy/render', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ template_id: id, content_data: SAMPLE_DATA }),
      });
      if (res.ok) {
        const blob = await res.blob();
        setPreviewUrls(prev => ({ ...prev, [id]: URL.createObjectURL(blob) }));
      }
    } catch {
      /* non-fatal */
    } finally {
      setLoadingPreviews(prev => { const s = new Set(prev); s.delete(id); return s; });
    }
  }

  useEffect(() => {
    BUILT_IN_TEMPLATES.forEach(t => fetchPreview(t.id));
    return () => { Object.values(previewUrls).forEach(URL.revokeObjectURL); };
  }, []);

  function armDelete(id: string) {
    setDeleteArmed(id);
    setTimeout(() => setDeleteArmed(null), 3000);
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div className="topbar">
        <div>
          <div className="topbar-title">Templates</div>
          <div className="topbar-sub">Visual templates used when generating posts</div>
        </div>
        <div className="topbar-actions">
          {PLATFORM_FILTER_OPTIONS.map(p => (
            <button key={p} onClick={() => setPlatformFilter(p)} className={`chip${platformFilter === p ? ' active' : ''}`} style={{ fontSize: 11 }}>{p}</button>
          ))}
        </div>
      </div>

      <div className="page-container" style={{ flex: 1, overflowY: 'auto' }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 16 }}>
          {filtered.map(t => {
            const url = previewUrls[t.id];
            const loading = loadingPreviews.has(t.id);
            const color = PLATFORM_COLOR[t.platform] ?? '#6B7280';
            return (
              <div key={t.id} className="card" style={{ padding: 0, overflow: 'hidden' }}>
                {/* Preview area */}
                <div
                  style={{ height: 140, background: url ? 'var(--bg-subtle)' : color + '12', display: 'flex', alignItems: 'center', justifyContent: 'center', position: 'relative', cursor: url ? 'pointer' : 'default' }}
                  onClick={() => url && setPreviewModal({ url, name: t.name })}
                >
                  {loading ? (
                    <span className="spinner spinner-dark" />
                  ) : url ? (
                    <>
                      <img src={url} alt={t.name} style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain' }} />
                      <div style={{ position: 'absolute', top: 6, right: 6, background: 'rgba(0,0,0,0.5)', borderRadius: 6, padding: '3px 6px', fontSize: 10, color: 'white', display: 'flex', alignItems: 'center', gap: 4 }}>
                        <Eye size={10} /> Preview
                      </div>
                    </>
                  ) : (
                    <span style={{ fontSize: 11, color: color, fontWeight: 600 }}>{t.platform}</span>
                  )}
                </div>
                {/* Info */}
                <div style={{ padding: '12px 14px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
                    <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>{t.name}</span>
                    <span style={{ fontSize: 10, color: color, fontWeight: 600, background: color + '15', padding: '2px 6px', borderRadius: 9999 }}>{t.platform}</span>
                  </div>
                  <p style={{ fontSize: 11, color: 'var(--text-muted)', margin: '0 0 8px', lineHeight: 1.4 }}>{t.description}</p>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>{t.size}</span>
                    {!t.isBuiltIn && (
                      <button
                        className="btn btn-danger btn-sm"
                        style={{ fontSize: 11, padding: '3px 8px' }}
                        onClick={() => deleteArmed === t.id ? notify.info('Template deleted') : armDelete(t.id)}
                      >
                        <Trash2 size={10} />
                        {deleteArmed === t.id ? 'Confirm?' : 'Delete'}
                      </button>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Preview modal */}
      {previewModal && (
        <div className="modal-backdrop" onClick={() => setPreviewModal(null)}>
          <div style={{ background: 'white', borderRadius: 12, padding: 24, maxWidth: '90vw', maxHeight: '90vh', overflow: 'auto', position: 'relative' }}>
            <button className="modal-close" onClick={() => setPreviewModal(null)} style={{ position: 'absolute', top: 12, right: 12 }}><X size={18} /></button>
            <h3 style={{ marginBottom: 16, fontSize: 16, fontWeight: 700 }}>{previewModal.name}</h3>
            <img src={previewModal.url} alt={previewModal.name} style={{ maxWidth: '100%', borderRadius: 8 }} />
          </div>
        </div>
      )}
    </div>
  );
}

export default function ProjectTemplatesPage() {
  const { id: projectId } = useParams<{ id: string }>();
  return (
    <ProjectFrame projectId={projectId}>
      <ProjectTemplatesContent />
    </ProjectFrame>
  );
}
