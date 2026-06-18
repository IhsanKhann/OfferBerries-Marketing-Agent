'use client';
import { Linkedin, Twitter, Instagram, Youtube, Mail, Copy, Download, CheckCircle, Clock } from 'lucide-react';
import { PreviewPost } from '../../../hooks/usePostPreview';

const PLATFORM_ICON: Record<string, React.ElementType> = {
  linkedin: Linkedin, twitter: Twitter, instagram: Instagram,
  youtube: Youtube, email: Mail,
};

const PLATFORM_COLOR: Record<string, string> = {
  linkedin: '#0A66C2', twitter: '#1D9BF0', instagram: '#E1306C',
  youtube: '#FF0000', email: '#6366F1',
};

interface Props {
  post: PreviewPost;
  onClick: () => void;
  onCopy?: () => void;
}

export default function PostCard({ post, onClick, onCopy }: Props) {
  const Icon  = PLATFORM_ICON[post.platform] ?? Mail;
  const color = PLATFORM_COLOR[post.platform] ?? 'var(--brand-primary)';
  const StatusIcon = post.status === 'approved' ? CheckCircle : Clock;

  function handleCopy(e: React.MouseEvent) {
    e.stopPropagation();
    if (post.caption) navigator.clipboard.writeText(post.caption).catch(() => {});
    onCopy?.();
  }

  function handleDownload(e: React.MouseEvent) {
    e.stopPropagation();
    if (!post.preview_url) return;
    const a = document.createElement('a');
    a.href = post.preview_url;
    a.download = `${post.platform}-post.png`;
    a.click();
  }

  return (
    <div className="post-card" onClick={onClick} role="button" tabIndex={0} onKeyDown={e => e.key === 'Enter' && onClick()}>
      <div className="post-card__header">
        <div
          className="post-card__platform-badge"
          style={{ background: color }}
        >
          <Icon size={14} color="white" />
        </div>
        <span className="post-card__platform-label">{post.platform}</span>
        <span className="post-card__status">
          <StatusIcon
            size={13}
            color={post.status === 'approved' ? 'var(--success)' : 'var(--text-muted)'}
          />
        </span>
      </div>

      <p className="post-card__body">
        {post.caption ?? 'No content preview available.'}
      </p>

      <div className="post-card__footer">
        <span className="post-card__reach">Queued</span>
        <button
          type="button"
          className="post-card__action-btn"
          onClick={handleCopy}
          title="Copy caption"
        >
          <Copy size={12} />
        </button>
        {post.preview_url && (
          <button
            type="button"
            className="post-card__action-btn"
            onClick={handleDownload}
            title="Download image"
          >
            <Download size={12} />
          </button>
        )}
      </div>
    </div>
  );
}
