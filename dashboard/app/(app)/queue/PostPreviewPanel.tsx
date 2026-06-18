'use client';
import { useState, useEffect } from 'react';
import { X, Linkedin, Twitter, Instagram, Youtube, Mail, Copy, Download, RefreshCw, CheckCircle } from 'lucide-react';
import { PreviewPost } from '../../../hooks/usePostPreview';
import { notify } from '../../../lib/toast';

const PLATFORM_ICON: Record<string, React.ElementType> = {
  linkedin: Linkedin, twitter: Twitter, instagram: Instagram,
  youtube: Youtube, email: Mail,
};

const PLATFORM_COLOR: Record<string, string> = {
  linkedin: '#0A66C2', twitter: '#1D9BF0', instagram: '#E1306C',
  youtube: '#FF0000', email: '#6366F1',
};

interface Props {
  post: PreviewPost | null;
  isOpen: boolean;
  onClose: () => void;
  onApprove?: (id: string) => Promise<void>;
  onReject?: (id: string) => Promise<void>;
}

export default function PostPreviewPanel({ post, isOpen, onClose, onApprove, onReject }: Props) {
  const [editMode, setEditMode] = useState(false);
  const [editedCaption, setEditedCaption] = useState('');
  const [editedHashtags, setEditedHashtags] = useState<string[]>([]);
  const [newHashtag, setNewHashtag] = useState('');
  const [approving, setApproving] = useState(false);
  const [rejecting, setRejecting] = useState(false);

  useEffect(() => {
    if (post) {
      setEditedCaption(post.copy ?? post.caption ?? '');
      setEditedHashtags(post.hashtags ?? []);
    }
    setEditMode(false);
    setNewHashtag('');
  }, [post]);

  function addHashtag() {
    const raw = newHashtag.trim();
    if (!raw) return;
    const tag = raw.startsWith('#') ? raw : `#${raw}`;
    if (!editedHashtags.includes(tag)) setEditedHashtags(h => [...h, tag]);
    setNewHashtag('');
  }

  function removeHashtag(tag: string) {
    setEditedHashtags(h => h.filter(t => t !== tag));
  }

  if (!post) return <div className={`post-preview-panel${isOpen ? ' open' : ''}`}><div className="post-preview-panel__inner" /></div>;

  const Icon  = PLATFORM_ICON[post.platform] ?? Mail;
  const color = PLATFORM_COLOR[post.platform] ?? 'var(--brand-primary)';

  async function handleApprove() {
    if (!onApprove) return;
    setApproving(true);
    await onApprove(post!.postiz_id).catch(() => {});
    setApproving(false);
    onClose();
  }

  async function handleReject() {
    if (!onReject) return;
    setRejecting(true);
    await onReject(post!.postiz_id).catch(() => {});
    setRejecting(false);
    onClose();
  }

  function handleCopy() {
    navigator.clipboard.writeText(editedCaption).catch(() => {});
    notify.success('Copied', 'Caption copied to clipboard');
  }

  function handleDownload() {
    if (!post?.preview_url) return;
    const a = document.createElement('a');
    a.href = post.preview_url;
    a.download = `${post.platform}-post.png`;
    a.click();
  }

  return (
    <div className={`post-preview-panel${isOpen ? ' open' : ''}`}>
      <div className="post-preview-panel__inner">
        {/* Header */}
        <div className="post-preview-panel__header">
          <div
            style={{
              width: 28, height: 28, borderRadius: 'var(--radius-md)',
              background: color, display: 'flex', alignItems: 'center', justifyContent: 'center',
              flexShrink: 0,
            }}
          >
            <Icon size={14} color="white" />
          </div>
          <div>
            <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)', textTransform: 'capitalize' }}>
              {post.platform}
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
              {new Date(post.scheduled_at).toLocaleString('en-PK', { timeZone: 'Asia/Karachi', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
            </div>
          </div>
          <span className="esc-hint">Esc</span>
          <button type="button" className="input-icon-btn" onClick={onClose} title="Close (Escape)">
            <X size={16} />
          </button>
        </div>

        {/* Body */}
        <div className="post-preview-panel__body">
          {/* Caption */}
          <div>
            <div className="preview-field-label">Caption</div>
            <textarea
              className="preview-textarea"
              value={editedCaption}
              onChange={e => setEditedCaption(e.target.value)}
              readOnly={!editMode}
              rows={8}
            />
          </div>

          {/* Hashtags (stored as a separate field, not parsed from caption) */}
          <div>
            <div className="preview-field-label">Hashtags</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, alignItems: 'center' }}>
              {editedHashtags.length > 0 ? (
                editedHashtags.map((tag) => (
                  <span key={tag} className="badge badge-muted" style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                    {tag}
                    {editMode && (
                      <button
                        type="button"
                        onClick={() => removeHashtag(tag)}
                        title="Remove hashtag"
                        style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0, display: 'flex', color: 'inherit' }}
                      >
                        <X size={11} />
                      </button>
                    )}
                  </span>
                ))
              ) : (
                <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>No hashtags</span>
              )}
            </div>
            {editMode && (
              <div style={{ display: 'flex', gap: 6, marginTop: 8 }}>
                <input
                  type="text"
                  value={newHashtag}
                  onChange={e => setNewHashtag(e.target.value)}
                  onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addHashtag(); } }}
                  placeholder="Add hashtag…"
                  className="preview-textarea"
                  style={{ flex: 1, minHeight: 0, height: 30, padding: '4px 8px' }}
                />
                <button type="button" className="btn btn-secondary btn-sm" onClick={addHashtag}>Add</button>
              </div>
            )}
          </div>

          {/* Visual preview */}
          {post.preview_url && (
            <div>
              <div className="preview-field-label">Visual</div>
              <div className="preview-visual">
                <img src={post.preview_url} alt={`${post.platform} visual`} />
              </div>
            </div>
          )}

          {/* Status */}
          <div>
            <div className="preview-field-label">Status</div>
            <span className={`badge ${post.status === 'approved' ? 'badge-success' : post.status === 'queued' ? 'badge-warning' : 'badge-muted'}`}>
              {post.status}
            </span>
          </div>
        </div>

        {/* Actions */}
        <div className="post-preview-panel__actions">
          {onApprove && post.status !== 'approved' && (
            <button
              type="button"
              className="btn btn-primary btn-sm"
              onClick={handleApprove}
              disabled={approving}
              style={{ gap: 4 }}
            >
              <CheckCircle size={12} />
              {approving ? 'Scheduling…' : 'Approve & Schedule'}
            </button>
          )}
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={() => setEditMode(m => !m)}
            style={{ gap: 4 }}
          >
            {editMode ? 'Lock' : 'Edit'}
          </button>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={handleCopy}
            style={{ gap: 4 }}
          >
            <Copy size={12} /> Copy
          </button>
          {post.preview_url && (
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={handleDownload}
              style={{ gap: 4 }}
            >
              <Download size={12} /> Download
            </button>
          )}
          {onReject && (
            <button
              type="button"
              className="btn btn-danger btn-sm"
              onClick={handleReject}
              disabled={rejecting}
              style={{ gap: 4 }}
            >
              <RefreshCw size={12} />
              {rejecting ? 'Removing…' : 'Reject'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
