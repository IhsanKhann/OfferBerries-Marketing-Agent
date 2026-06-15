'use client';
import { useState, useEffect } from 'react';
import { Plus, Pencil, Trash2, X, Eye } from 'lucide-react';
import { notify } from '../../../lib/toast';

/*
 * TODO: Future API endpoints
 * GET  /api/proxy/templates         → returns custom templates for the tenant
 * POST /api/proxy/templates         → { name, description, platform, html, css } → creates custom template
 * DELETE /api/proxy/templates/{id}  → deletes a custom template
 * Custom templates currently live in component state only (lost on refresh).
 */

const BUILT_IN_TEMPLATES = [
  { id: 'linkedin-single',         name: 'LinkedIn Single',          size: '1080×1080', platform: 'LinkedIn',  description: 'Single-image post optimised for LinkedIn feed' },
  { id: 'linkedin-carousel-slide', name: 'LinkedIn Carousel Slide',  size: '1080×1080', platform: 'LinkedIn',  description: 'Carousel slide for multi-page LinkedIn content' },
  { id: 'twitter-stat-card',       name: 'Twitter Stat Card',        size: '1600×900',  platform: 'Twitter',   description: 'Eye-catching stat card for Twitter/X posts' },
  { id: 'instagram-quote',         name: 'Instagram Quote',          size: '1080×1080', platform: 'Instagram', description: 'Bold quote card for Instagram engagement' },
  { id: 'instagram-carousel-slide',name: 'Instagram Carousel Slide', size: '1080×1080', platform: 'Instagram', description: 'Carousel slide formatted for Instagram' },
  { id: 'youtube-thumbnail',       name: 'YouTube Thumbnail',        size: '1280×720',  platform: 'YouTube',   description: 'High-contrast thumbnail for YouTube videos' },
  { id: 'email-header',            name: 'Email Header',             size: '600×200',   platform: 'Email',     description: 'Professional header for email campaigns' },
  { id: 'announcement-card',       name: 'Announcement Card',        size: '1080×1080', platform: 'General',   description: 'Versatile card for product announcements' },
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

type Template = {
  id: string; name: string; description: string; size: string;
  platform: string; isBuiltIn: boolean; html?: string; css?: string;
};

const PLATFORM_FILTER_OPTIONS = ['All', 'LinkedIn', 'Twitter', 'Instagram', 'YouTube', 'Email', 'General'];

const PREVIEW_CLASS: Record<string, string> = {
  LinkedIn: 'template-preview-linkedin', Twitter: 'template-preview-twitter',
  Instagram: 'template-preview-instagram', YouTube: 'template-preview-youtube',
  Email: 'template-preview-email', General: 'template-preview-general',
};

export default function TemplatesPage() {
  const [templates, setTemplates] = useState<Template[]>(
    BUILT_IN_TEMPLATES.map(t => ({ ...t, isBuiltIn: true }))
  );
  const [platformFilter, setPlatformFilter] = useState('All');
  const [previewUrls, setPreviewUrls]         = useState<Record<string, string>>({});
  const [loadingPreviews, setLoadingPreviews] = useState<Set<string>>(new Set());
  const [previewModal, setPreviewModal]     = useState<{ url: string; name: string } | null>(null);
  const [editId, setEditId]                 = useState<string | null>(null);
  const [editValues, setEditValues]         = useState<{ name: string; description: string }>({ name: '', description: '' });
  const [deleteArmed, setDeleteArmed]       = useState<string | null>(null);
  const [deleteTimer, setDeleteTimer]       = useState<ReturnType<typeof setTimeout> | null>(null);
  const [addModal, setAddModal]             = useState(false);
  const [newTemplate, setNewTemplate]       = useState({ name: '', description: '', platform: 'LinkedIn', html: '', css: '' });
  const [addMode, setAddMode]               = useState<'paste' | 'upload'>('paste');

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
      } else {
        notify.error('Preview failed', 'Could not render template preview');
      }
    } catch {
      notify.error('Preview failed', 'Network error');
    } finally {
      setLoadingPreviews(prev => { const s = new Set(prev); s.delete(id); return s; });
    }
  }

  useEffect(() => {
    BUILT_IN_TEMPLATES.forEach(t => fetchPreview(t.id));
    return () => { Object.values(previewUrls).forEach(URL.revokeObjectURL); };
  }, []);

  function startEdit(t: Template) {
    setEditId(t.id);
    setEditValues({ name: t.name, description: t.description });
  }

  function saveEdit(id: string) {
    setTemplates(prev => prev.map(t => t.id === id ? { ...t, ...editValues } : t));
    setEditId(null);
    notify.success('Template updated', 'Changes saved');
  }

  function armDelete(id: string) {
    if (deleteArmed === id) {
      const t = templates.find(x => x.id === id);
      setTemplates(prev => prev.filter(x => x.id !== id));
      setDeleteArmed(null);
      if (deleteTimer) clearTimeout(deleteTimer);
      notify.success('Template deleted', t?.name);
    } else {
      setDeleteArmed(id);
      const timer = setTimeout(() => setDeleteArmed(null), 3000);
      setDeleteTimer(timer);
    }
  }

  function addTemplate() {
    if (!newTemplate.name.trim() || !newTemplate.html.trim()) {
      notify.error('Invalid template', 'Please provide a title and valid HTML');
      return;
    }
    if (!/<[a-z][\s\S]*>/i.test(newTemplate.html)) {
      notify.error('Invalid template', 'HTML must contain at least one tag');
      return;
    }
    const t: Template = {
      id: crypto.randomUUID(), ...newTemplate, size: 'Custom', isBuiltIn: false,
    };
    setTemplates(prev => [...prev, t]);
    setAddModal(false);
    setNewTemplate({ name: '', description: '', platform: 'LinkedIn', html: '', css: '' });
    notify.success('Template added', t.name);
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
      <div className="topbar">
        <div>
          <div className="topbar-title">Content Templates</div>
          <div className="topbar-sub">
            {templates.filter(t => t.isBuiltIn).length} built-in · {templates.filter(t => !t.isBuiltIn).length} custom
          </div>
        </div>
        <div className="topbar-actions">
          {PLATFORM_FILTER_OPTIONS.map(p => (
            <button key={p} onClick={() => setPlatformFilter(p)} className={`chip${platformFilter === p ? ' active' : ''}`}>{p}</button>
          ))}
          <div className="avatar-chip">I</div>
        </div>
      </div>

      <div className="content-area">
        <div className="templates-grid">
          {filtered.map(t => (
            <div key={t.id} className="template-card">
              {/* Preview area */}
              <div className={`template-preview ${PREVIEW_CLASS[t.platform] || 'template-preview-general'}`}>
                {t.isBuiltIn ? (
                  previewUrls[t.id] ? (
                    <img src={previewUrls[t.id]} alt={t.name} />
                  ) : (
                    <div className="skeleton-pulse" style={{ width: '100%', height: '100%' }} />
                  )
                ) : (
                  <iframe
                    srcDoc={t.html + (t.css ? `<style>${t.css}</style>` : '')}
                    sandbox="allow-same-origin"
                    style={{ width: 400, height: 400, transform: 'scale(0.375)', transformOrigin: 'top left', border: 'none', pointerEvents: 'none' }}
                  />
                )}
              </div>

              <div className="template-card-body">
                {editId === t.id ? (
                  <div>
                    <input value={editValues.name} onChange={e => setEditValues(v => ({ ...v, name: e.target.value }))} className="input" style={{ marginBottom: 8 }} />
                    <textarea value={editValues.description} onChange={e => setEditValues(v => ({ ...v, description: e.target.value }))} className="input" rows={2} />
                    <div className="flex-row mt-3">
                      <button onClick={() => saveEdit(t.id)} className="btn btn-primary btn-sm">Save</button>
                      <button onClick={() => setEditId(null)} className="btn btn-secondary btn-sm">Cancel</button>
                    </div>
                  </div>
                ) : (
                  <>
                    <div className="flex-between">
                      <span className="card-title" style={{ fontSize: 14 }}>{t.name}</span>
                      <div className="flex-row gap-2">
                        <button onClick={() => startEdit(t)} className="btn btn-icon" style={{ width: 28, height: 28 }} aria-label="Edit template">
                          <Pencil size={12} style={{ color: 'var(--text-muted)' }} />
                        </button>
                        {!t.isBuiltIn && (
                          <button
                            onClick={() => armDelete(t.id)}
                            className="btn btn-icon"
                            style={{ width: 28, height: 28, background: deleteArmed === t.id ? 'var(--danger-bg)' : undefined }}
                            aria-label={deleteArmed === t.id ? 'Click again to confirm delete' : 'Delete template'}
                          >
                            <Trash2 size={12} style={{ color: deleteArmed === t.id ? 'var(--danger)' : 'var(--text-muted)' }} />
                          </button>
                        )}
                      </div>
                    </div>
                    <div className="card-sub mt-3">{t.description || `${t.size} · ${t.platform}`}</div>
                    <div className="template-actions">
                      <span className={`badge ${t.platform === 'LinkedIn' ? 'badge-hr' : t.platform === 'Instagram' || t.platform === 'YouTube' ? 'badge-ops' : 'badge-fin'}`}>{t.platform}</span>
                      <span className="badge badge-muted">{t.isBuiltIn ? 'Built-in' : 'Custom'}</span>
                    </div>
                    <div className="template-actions-row2">
                      <button
                        onClick={() => {
                          if (t.isBuiltIn) {
                            if (previewUrls[t.id]) setPreviewModal({ url: previewUrls[t.id], name: t.name });
                            else { fetchPreview(t.id); notify.info('Loading preview…', 'Please wait'); }
                          } else {
                            setPreviewModal({ url: '', name: t.name });
                          }
                        }}
                        disabled={loadingPreviews.has(t.id)}
                        className="btn btn-secondary btn-sm"
                      >
                        {loadingPreviews.has(t.id) ? <><span className="spinner spinner-dark" style={{ width: 10, height: 10 }} /> Rendering…</> : <><Eye size={12} /> Preview</>}
                      </button>
                      <button
                        className="btn btn-primary btn-sm"
                        onClick={() => notify.success('Template selected', `Will use ${t.name} for next agent run`)}
                      >
                        Use Template
                      </button>
                    </div>
                  </>
                )}
              </div>
            </div>
          ))}

          {/* Add template card */}
          <div className="template-card dashed" onClick={() => setAddModal(true)}>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8, color: 'var(--text-muted)' }}>
              <Plus size={24} />
              <span style={{ fontSize: 13, fontWeight: 600 }}>Add Template</span>
              <span style={{ fontSize: 12 }}>Upload HTML/CSS</span>
            </div>
          </div>
        </div>
      </div>

      {/* Preview modal */}
      {previewModal && (
        <div className="modal-backdrop" onClick={() => setPreviewModal(null)}>
          <div className="modal-panel" style={{ width: 600 }} onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <span className="modal-title">{previewModal.name}</span>
              <button onClick={() => setPreviewModal(null)} className="btn btn-icon btn-sm"><X size={14} /></button>
            </div>
            <div className="modal-body">
              {previewModal.url ? (
                <img src={previewModal.url} alt="Template preview" style={{ width: '100%', borderRadius: 'var(--radius-md)' }} />
              ) : (
                <div className="empty-state"><div className="empty-sub">Preview not available for custom templates in this view.</div></div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Add template modal */}
      {addModal && (
        <div className="modal-backdrop" onClick={() => setAddModal(false)}>
          <div className="modal-panel" style={{ width: 540 }} onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <span className="modal-title">Add Custom Template</span>
              <button onClick={() => setAddModal(false)} className="btn btn-icon btn-sm"><X size={14} /></button>
            </div>
            <div className="modal-body" style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              <div>
                <label className="field-label">Template Name *</label>
                <input value={newTemplate.name} onChange={e => setNewTemplate(v => ({ ...v, name: e.target.value }))} className="input" placeholder="My Custom Template" />
              </div>
              <div>
                <label className="field-label">Description</label>
                <input value={newTemplate.description} onChange={e => setNewTemplate(v => ({ ...v, description: e.target.value }))} className="input" placeholder="Short description" />
              </div>
              <div>
                <label className="field-label">Platform</label>
                <select value={newTemplate.platform} onChange={e => setNewTemplate(v => ({ ...v, platform: e.target.value }))} className="input">
                  {['LinkedIn', 'Instagram', 'YouTube', 'Twitter', 'Email', 'General'].map(p => (
                    <option key={p} value={p}>{p}</option>
                  ))}
                </select>
              </div>
              <div>
                <div className="flex-row mb-4">
                  <button onClick={() => setAddMode('paste')} className={`chip${addMode === 'paste' ? ' active' : ''}`}>Paste Code</button>
                  <button onClick={() => setAddMode('upload')} className={`chip${addMode === 'upload' ? ' active' : ''}`}>Upload File</button>
                </div>
                <label className="field-label">HTML *</label>
                {addMode === 'paste' ? (
                  <textarea
                    value={newTemplate.html}
                    onChange={e => setNewTemplate(v => ({ ...v, html: e.target.value }))}
                    className="input"
                    rows={6}
                    placeholder="<div>Your template HTML...</div>"
                    style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}
                  />
                ) : (
                  <input
                    type="file"
                    accept=".html"
                    className="input"
                    onChange={e => {
                      const file = e.target.files?.[0];
                      if (file) file.text().then(html => setNewTemplate(v => ({ ...v, html })));
                    }}
                  />
                )}
              </div>
              <div>
                <label className="field-label">CSS (optional — or include &lt;style&gt; tags in HTML)</label>
                <textarea
                  value={newTemplate.css}
                  onChange={e => setNewTemplate(v => ({ ...v, css: e.target.value }))}
                  className="input"
                  rows={3}
                  placeholder="body { font-family: sans-serif; }"
                  style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}
                />
              </div>
              {newTemplate.html && (
                <div>
                  <div className="field-label" style={{ marginBottom: 6 }}>Live Preview</div>
                  <div style={{ height: 160, border: '1px solid var(--border-default)', borderRadius: 'var(--radius-md)', overflow: 'hidden', position: 'relative' }}>
                    <iframe
                      srcDoc={newTemplate.html + (newTemplate.css ? `<style>${newTemplate.css}</style>` : '')}
                      sandbox="allow-same-origin"
                      style={{ width: 400, height: 400, transform: 'scale(0.4)', transformOrigin: 'top left', border: 'none', pointerEvents: 'none' }}
                    />
                  </div>
                </div>
              )}
              <div className="flex-row">
                <button onClick={addTemplate} className="btn btn-primary">Add Template</button>
                <button onClick={() => setAddModal(false)} className="btn btn-secondary">Cancel</button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
