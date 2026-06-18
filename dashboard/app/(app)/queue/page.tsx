'use client';
import { useEffect, useState, useRef, useCallback } from 'react';
import { Linkedin, Twitter, Instagram, Youtube, Mail, CheckCircle, XCircle, Cpu } from 'lucide-react';
import { notify } from '../../../lib/toast';
import AgentErrorBanner from '../../../components/AgentErrorBanner';
import AgentChatThread, { ChatMessage } from './AgentChatThread';
import AgentInputBar from './AgentInputBar';
import ImageAttachPreview from './ImageAttachPreview';
import PostCard from './PostCard';
import PostPreviewPanel from './PostPreviewPanel';
import AgentPipelinePanel from './AgentPipelinePanel';
import { useAgentRun } from '../../../hooks/useAgentRun';
import { useImageAttach } from '../../../hooks/useImageAttach';
import { usePostPreview, PreviewPost } from '../../../hooks/usePostPreview';

const PLATFORMS = ['LinkedIn', 'Twitter', 'Instagram', 'YouTube', 'Email'];

const PLATFORM_ICON: Record<string, React.ElementType> = {
  linkedin: Linkedin, twitter: Twitter, instagram: Instagram,
  youtube: Youtube, email: Mail,
};

const PLATFORM_COLOR: Record<string, string> = {
  linkedin: '#0A66C2', twitter: '#1D9BF0', instagram: '#E1306C',
  youtube: '#FF0000', email: '#6366F1',
};

const INITIAL_MESSAGE: ChatMessage = {
  role: 'assistant',
  content: "Hi! I'm your research assistant. Tell me what topic you'd like to create content about and I'll research trends, competitors, and top-performing posts.",
};

export default function QueuePage() {
  const [posts, setPosts]     = useState<PreviewPost[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter]   = useState('all');
  const [topic, setTopic]     = useState('');
  const [activePlatforms, setActivePlatforms] = useState<string[]>(['LinkedIn', 'Twitter', 'Instagram']);
  const [pipelineOpen, setPipelineOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([INITIAL_MESSAGE]);

  const chatRef = useRef<HTMLDivElement>(null);

  const addMessage = useCallback((content: string) => {
    setMessages(m => [...m, { role: 'assistant', content }]);
  }, []);

  const fetchPosts = useCallback(async () => {
    setLoading(true);
    try {
      const params = filter !== 'all' ? `?platform=${filter}` : '';
      const res = await fetch(`/api/proxy/queue${params}`);
      if (res.ok) setPosts(await res.json());
    } finally {
      setLoading(false);
    }
  }, [filter]);

  const {
    runId, runStatus, currentStage, running,
    researchModel, setResearchModel,
    contentModel, setContentModel,
    agentError, clearError,
    startRun, stepStatuses,
  } = useAgentRun(fetchPosts, addMessage);

  const { images: attachedImages, addImages, removeImage } = useImageAttach();
  const { selectedPost, isOpen: previewOpen, openPost, closePost } = usePostPreview();

  useEffect(() => { fetchPosts(); }, [fetchPosts]);

  useEffect(() => {
    if (chatRef.current) chatRef.current.scrollTop = chatRef.current.scrollHeight;
  }, [messages, running]);

  function togglePlatform(p: string) {
    setActivePlatforms(prev =>
      prev.includes(p) ? prev.filter(x => x !== p) : [...prev, p]
    );
  }

  async function runAgent() {
    if (!topic.trim() || running) return;
    const userMsg = topic;
    setTopic('');
    setMessages(m => [...m, { role: 'user', content: userMsg }]);
    await startRun(userMsg, activePlatforms.map(p => p.toLowerCase()));
  }

  async function approvePost(id: string) {
    await fetch(`/api/proxy/queue/${id}/approve`, { method: 'POST' });
    notify.success('Post approved', 'Scheduled for publishing in Postiz');
    fetchPosts();
  }

  async function rejectPost(id: string) {
    await fetch(`/api/proxy/queue/${id}`, { method: 'DELETE' });
    notify.info('Post removed', 'Deleted from queue');
    fetchPosts();
  }

  const panelOpen = previewOpen || pipelineOpen;

  return (
    <div className="queue-shell">
      {/* Topbar */}
      <div className="topbar">
        <div>
          <div className="topbar-title">Content Queue</div>
          <div className="topbar-sub">
            {posts.length} post{posts.length !== 1 ? 's' : ''} pending review
          </div>
        </div>
        <div className="topbar-actions">
          {PLATFORMS.map(p => (
            <button
              key={p}
              onClick={() => togglePlatform(p)}
              className={`chip${activePlatforms.includes(p) ? ' active' : ''}`}
            >
              {p}
            </button>
          ))}
          <button
            type="button"
            className={`pipeline-toggle-btn${pipelineOpen ? ' active' : ''}`}
            onClick={() => {
              setPipelineOpen(o => !o);
              if (previewOpen) closePost();
            }}
          >
            <Cpu size={13} />
            Pipeline
          </button>
          <div className="avatar-chip">I</div>
        </div>
      </div>

      {/* Body: chat column + panels */}
      <div className="queue-body">
        {/* Chat column */}
        <div className="chat-column">
          <div className="chat-column-inner">
            {agentError && (
              <div style={{ paddingTop: 16, flexShrink: 0 }}>
                <AgentErrorBanner
                  error={agentError}
                  onDismiss={clearError}
                  onRetry={() => { clearError(); runAgent(); }}
                  onResume={() => { clearError(); runAgent(); }}
                />
              </div>
            )}

            {/* Messages */}
            <AgentChatThread
              messages={messages}
              running={running}
              currentStage={currentStage}
              runStatus={runStatus}
              chatRef={chatRef}
            />

            {/* Inline post cards after run completes */}
            {!loading && posts.length > 0 && runStatus === 'completed' && (
              <div style={{ paddingBottom: 8, flexShrink: 0 }}>
                <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 6, fontWeight: 600 }}>
                  Generated Posts
                </div>
                <div className="post-cards-row">
                  {posts.map(post => (
                    <PostCard
                      key={post.postiz_id}
                      post={post}
                      onClick={() => { openPost(post); setPipelineOpen(false); }}
                      onCopy={() => notify.success('Copied', 'Caption copied to clipboard')}
                    />
                  ))}
                </div>
              </div>
            )}

            {/* Image attach previews */}
            <ImageAttachPreview images={attachedImages} onRemove={removeImage} />

            {/* Input bar */}
            <AgentInputBar
              topic={topic}
              setTopic={setTopic}
              running={running}
              onRun={runAgent}
              researchModel={researchModel}
              setResearchModel={setResearchModel}
              contentModel={contentModel}
              setContentModel={setContentModel}
              onAttachFiles={addImages}
              onAttachImages={addImages}
            />

            {/* Pending posts section */}
            <div className="pending-posts-section">
              <div className="pending-posts-header">
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span className="card-title" style={{ fontSize: 13 }}>Pending Posts</span>
                  {posts.length > 0 && (
                    <span className="badge badge-warning">{posts.length} awaiting review</span>
                  )}
                </div>
                <div style={{ display: 'flex', gap: 4 }}>
                  {['all', 'linkedin', 'twitter', 'instagram'].map(p => (
                    <button
                      key={p}
                      onClick={() => setFilter(p)}
                      className={`chip${filter === p ? ' active' : ''}`}
                      style={{ fontSize: 11 }}
                    >
                      {p === 'all' ? 'All' : p}
                    </button>
                  ))}
                </div>
              </div>

              <div className="pending-posts-scroll">
                {loading ? (
                  <div className="empty-state" style={{ padding: '24px 0' }}>
                    <span className="spinner spinner-dark" />
                  </div>
                ) : posts.length === 0 ? (
                  <div className="empty-state" style={{ padding: '32px 0' }}>
                    <div className="empty-icon" style={{ fontSize: 28 }}>📋</div>
                    <div className="empty-title">No posts in queue</div>
                    <div className="empty-sub">
                      Enter a topic above and press Run to generate content.
                    </div>
                  </div>
                ) : (
                  <div className="post-cards-grid">
                    {posts.map(post => {
                      const Icon  = PLATFORM_ICON[post.platform] ?? Mail;
                      const color = PLATFORM_COLOR[post.platform] ?? 'var(--brand-primary)';
                      return (
                        <div
                          key={post.postiz_id}
                          style={{ border: '1px solid var(--border-default)', borderRadius: 'var(--radius-lg)', padding: '12px 14px', background: 'var(--bg-canvas)', display: 'flex', gap: 12, alignItems: 'flex-start' }}
                        >
                          <div style={{ width: 32, height: 32, borderRadius: 'var(--radius-md)', background: color, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                            <Icon size={15} color="white" />
                          </div>
                          <div style={{ flex: 1, minWidth: 0 }}>
                            <div style={{ display: 'flex', gap: 4, marginBottom: 4, flexWrap: 'wrap', alignItems: 'center' }}>
                              <span className="badge" style={{ background: color + '18', color, borderColor: color + '40' }}>{post.platform}</span>
                              <span className={`badge ${post.status === 'approved' ? 'badge-success' : post.status === 'queued' ? 'badge-warning' : 'badge-muted'}`}>{post.status}</span>
                              <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>
                                {new Date(post.scheduled_at).toLocaleString('en-PK', { timeZone: 'Asia/Karachi', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
                              </span>
                            </div>
                            <p style={{ fontSize: 12, color: 'var(--text-primary)', lineHeight: 1.5, margin: 0, overflow: 'hidden', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical' }}>
                              {post.caption}
                            </p>
                          </div>
                          <div style={{ display: 'flex', flexDirection: 'column', gap: 4, flexShrink: 0 }}>
                            <button
                              onClick={() => approvePost(post.postiz_id)}
                              className="btn btn-sm"
                              style={{ background: 'var(--success-bg)', color: 'var(--success-text)', border: '1px solid var(--success-border)', gap: 4 }}
                              title="Approve: schedules this post"
                            >
                              <CheckCircle size={11} /> Approve
                            </button>
                            <button
                              onClick={() => rejectPost(post.postiz_id)}
                              className="btn btn-danger btn-sm"
                              style={{ gap: 4 }}
                              title="Reject: deletes from queue"
                            >
                              <XCircle size={11} /> Reject
                            </button>
                            <button
                              onClick={() => { openPost(post); setPipelineOpen(false); }}
                              className="btn btn-secondary btn-sm"
                              style={{ gap: 4 }}
                            >
                              Preview
                            </button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Post preview panel (in-flow, causes chat to narrow) */}
        <PostPreviewPanel
          post={selectedPost}
          isOpen={previewOpen}
          onClose={closePost}
          onApprove={approvePost}
          onReject={rejectPost}
        />

        {/* Pipeline panel (absolute overlay) */}
        <AgentPipelinePanel
          open={pipelineOpen}
          onClose={() => setPipelineOpen(false)}
          stepStatuses={stepStatuses}
          runId={runId}
        />
      </div>
    </div>
  );
}
