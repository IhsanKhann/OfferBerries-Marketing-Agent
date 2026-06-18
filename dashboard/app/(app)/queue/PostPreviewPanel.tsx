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

type PerformanceRating = 'high' | 'medium' | 'low';

interface Props {
  post: PreviewPost | null;
  isOpen: boolean;
  onClose: () => void;
  onApprove?: (id: string) => Promise<void>;
  onReject?: (id: string) => Promise<void>;
  onRate?: (id: string, rating: PerformanceRating) => Promise<void>;
}

export default function PostPreviewPanel({ post, isOpen, onClose, onApprove, onReject, onRate }: Props) {
  const [editMode, setEditMode] = useState(false);
  const [editedCaption, setEditedCaption] = useState('');
  const [editedHashtags, setEditedHashtags] = useState<string[]>([]);
  const [newHashtag, setNewHashtag] = useState('');
  const [approving, setApproving] = useState(false);
  const [rejecting, setRejecting] = useState(false);
  const [selectedRating, setSelectedRating] = useState<PerformanceRating | null>(null);

  useEffect(() => {
    if (post) {
      setEditedCaption(post.copy ?? post.caption ?? '');
      setEditedHashtags(post.hashtags ?? []);
    }
    setEditMode(false);
    setNewHashtag('');
    setSelectedRating(null);
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

  async function handleRate(rating: PerformanceRating) {
    if (!onRate) return;
    setSelectedRating(rating);
    await onRate(post!.postiz_id, rating).catch(() => {});
  }

  return (
    <div className={`post-preview-panel${isOpen ? ' open' : ''}`}>
      <div className="post-preview-panel__inner">
        {/* Header */}
        <div className="post-preview-panel__header">
          <div className="preview-platform-icon" style={{ background: color }}>
            <Icon size={14} color="white" />
          </div>
          <div>
            <div className="preview-platform-name">{post.platform}</div>
            <div className="preview-platform-time">
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
            <div className="preview-hashtags">
              {editedHashtags.length > 0 ? (
                editedHashtags.map((tag) => (
                  <span key={tag} className="badge badge-muted preview-hashtag-badge">
                    {tag}
                    {editMode && (
                      <button
                        type="button"
                        onClick={() => removeHashtag(tag)}
                        title="Remove hashtag"
                        className="preview-hashtag-remove"
                      >
                        <X size={11} />
                      </button>
                    )}
                  </span>
                ))
              ) : (
                <span className="preview-hashtags-empty">No hashtags</span>
              )}
            </div>
            {editMode && (
              <div className="preview-add-hashtag-row">
                <input
                  type="text"
                  value={newHashtag}
                  onChange={e => setNewHashtag(e.target.value)}
                  onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addHashtag(); } }}
                  placeholder="Add hashtag…"
                  className="preview-textarea preview-add-hashtag-input"
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

        {/* Rating buttons — shown for approved/published posts */}
        {onRate && post.status === 'approved' && (
          <div className="post-preview-panel__rating">
            <div className="preview-field-label">How did it perform?</div>
            <div className="preview-rating-buttons">
              {([
                { rating: 'high' as const, emoji: '🔥', label: 'High performance' },
                { rating: 'medium' as const, emoji: '👍', label: 'Medium performance' },
                { rating: 'low' as const, emoji: '👎', label: 'Low performance' },
              ] as const).map(({ rating, emoji, label }) => (
                <button
                  key={rating}
                  type="button"
                  className={`btn btn-secondary btn-sm preview-rating-btn${selectedRating === rating ? ' active' : ''}`}
                  title={label}
                  onClick={() => handleRate(rating)}
                >
                  {emoji}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Actions */}
        <div className="post-preview-panel__actions">
          {onApprove && post.status !== 'approved' && (
            <button
              type="button"
              className="btn btn-primary btn-sm"
              onClick={handleApprove}
              disabled={approving}
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
