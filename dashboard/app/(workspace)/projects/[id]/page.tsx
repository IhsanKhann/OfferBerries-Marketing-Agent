'use client';
import { useEffect, useState, useRef, useCallback } from 'react';
import { useParams, useSearchParams, useRouter } from 'next/navigation';
import { Linkedin, Twitter, Instagram, Youtube, Mail, CheckCircle, XCircle, Cpu } from 'lucide-react';
import { toast } from 'sonner';
import AgentErrorBanner from '@/components/AgentErrorBanner';
import AgentChatThread, { ChatMessage } from '@/app/(app)/queue/AgentChatThread';
import AgentInputBar from '@/app/(app)/queue/AgentInputBar';
import ImageAttachPreview from '@/app/(app)/queue/ImageAttachPreview';
import PostCard from '@/app/(app)/queue/PostCard';
import PostPreviewPanel from '@/app/(app)/queue/PostPreviewPanel';
import AgentPipelinePanel from '@/app/(app)/queue/AgentPipelinePanel';
import { useAgentRun } from '@/hooks/useAgentRun';
import { useImageAttach } from '@/hooks/useImageAttach';
import { usePostPreview, PreviewPost } from '@/hooks/usePostPreview';
import { ProjectSidebar } from './ProjectSidebar';
import type { Project } from '@/hooks/useProjects';

const PLATFORMS = ['LinkedIn', 'Twitter', 'Instagram', 'YouTube', 'Email'];

const PLATFORM_ICON: Record<string, React.ElementType> = {
  linkedin: Linkedin, twitter: Twitter, instagram: Instagram,
  youtube: Youtube, email: Mail,
};

const PLATFORM_COLOR: Record<string, string> = {
  linkedin: '#0A66C2', twitter: '#1D9BF0', instagram: '#E1306C',
  youtube: '#FF0000', email: '#6366F1',
};

const LOADER_MESSAGES = [
  'Researching trends…',
  'Analysing competitors…',
  'Crafting content…',
  'Generating visuals…',
  'Queuing posts…',
];

function RunningLoader({ stage }: { stage: string }) {
  const [msgIdx, setMsgIdx] = useState(0);

  useEffect(() => {
    const map: Record<string, number> = {
      research: 0, content_generation: 2, visual_generation: 3, scheduling: 4,
    };
    setMsgIdx(map[stage] ?? 0);
    const t = setInterval(() => setMsgIdx(i => (i + 1) % LOADER_MESSAGES.length), 3000);
    return () => clearInterval(t);
  }, [stage]);

  return (
    <div className="workspace-running-loader">
      <span className="workspace-loader-dot" />
      <span className="workspace-loader-text">{LOADER_MESSAGES[msgIdx]}</span>
    </div>
  );
}

function makeInitialMessage(project: Project): ChatMessage {
  return {
    role: 'assistant',
    content: `Hi! I'm ready to create content for **${project.name}**${project.brand_voice ? ` with your brand voice` : ''}. What topic should I research?${project.memory_enabled ? '\n\n🧠 *Memory is on — I\'ll build on past chats in this project.*' : ''}`,
  };
}

export default function ProjectWorkspacePage() {
  const { id: projectId } = useParams<{ id: string }>();
  const searchParams = useSearchParams();
  const activeRunId = searchParams.get('run');
  const router = useRouter();

  const [project, setProject] = useState<Project | null>(null);
  const [projectLoading, setProjectLoading] = useState(true);

  const [posts, setPosts] = useState<PreviewPost[]>([]);
  const [postsLoading, setPostsLoading] = useState(false);
  const [filter, setFilter] = useState('all');
  const [topic, setTopic] = useState('');
  const [activePlatforms, setActivePlatforms] = useState<string[]>(['LinkedIn', 'Instagram']);
  const [pipelineOpen, setPipelineOpen] = useState(true);
  const [messages, setMessages] = useState<ChatMessage[]>([]);

  const chatRef = useRef<HTMLDivElement>(null);

  // Load project
  useEffect(() => {
    setProjectLoading(true);
    fetch(`/api/proxy/projects/${projectId}`)
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (data) {
          setProject(data);
          setActivePlatforms(
            (data.default_platforms ?? ['linkedin', 'instagram'])
              .map((p: string) => p.charAt(0).toUpperCase() + p.slice(1))
          );
          setMessages([makeInitialMessage(data)]);
        }
      })
      .finally(() => setProjectLoading(false));
  }, [projectId]);

  const addMessage = useCallback((content: string) => {
    setMessages(m => [...m, { role: 'assistant', content }]);
  }, []);

  const fetchPosts = useCallback(async () => {
    setPostsLoading(true);
    try {
      const params = filter !== 'all' ? `?platform=${filter}` : '';
      const res = await fetch(`/api/proxy/queue${params}`);
      if (res.ok) setPosts(await res.json());
    } finally {
      setPostsLoading(false);
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
    if (!topic.trim() || running || !project) return;
    const userMsg = topic;
    setTopic('');
    setMessages(m => [...m, { role: 'user', content: userMsg }]);
    await startRun(userMsg, activePlatforms.map(p => p.toLowerCase()), projectId);
  }

  async function approvePost(id: string) {
    await fetch(`/api/proxy/queue/${id}/approve`, { method: 'POST' });
    toast.success('Post approved — scheduled for publishing');
    fetchPosts();
  }

  async function rejectPost(id: string) {
    await fetch(`/api/proxy/queue/${id}`, { method: 'DELETE' });
    toast.info('Post removed from queue');
    fetchPosts();
  }

  function handleNewChat() {
    router.push(`/projects/${projectId}`);
    setMessages(project ? [makeInitialMessage(project)] : []);
    setTopic('');
    setPosts([]);
  }

  if (projectLoading) {
    return (
      <div className="workspace-shell">
        <div className="workspace-sidebar-skeleton">
          <div className="skeleton skeleton-title" style={{ margin: '20px 16px' }} />
          <div className="skeleton skeleton-text" style={{ margin: '8px 16px' }} />
          <div className="skeleton skeleton-text" style={{ margin: '8px 16px', width: '60%' }} />
        </div>
        <div className="workspace-main">
          <div className="workspace-loading-center">
            <span className="workspace-loader-dot workspace-loader-dot--lg" />
          </div>
        </div>
      </div>
    );
  }

  if (!project) {
    return (
      <div className="workspace-shell">
        <div className="workspace-main workspace-error">
          <p>Project not found.</p>
          <button className="btn-primary" onClick={() => router.push('/projects')}>
            Back to projects
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="workspace-shell">
      <ProjectSidebar
        project={project}
        activeRunId={activeRunId ?? runId ?? undefined}
        onNewChat={handleNewChat}
      />

      <div className="workspace-main">
        <div className="queue-shell" style={{ height: '100%' }}>
          {/* Topbar */}
          <div className="topbar">
            <div>
              <div className="topbar-title">{project.name}</div>
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
                onClick={() => { setPipelineOpen(o => !o); if (previewOpen) closePost(); }}
              >
                <Cpu size={13} />
                Pipeline
              </button>
            </div>
          </div>

          {/* Body */}
          <div className="queue-body">
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

                <AgentChatThread
                  messages={messages}
                  running={running}
                  currentStage={currentStage}
                  runStatus={runStatus}
                  chatRef={chatRef}
                />

                {running && <RunningLoader stage={currentStage} />}

                {!postsLoading && posts.length > 0 && runStatus === 'completed' && (
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
                          onCopy={() => toast.success('Caption copied to clipboard')}
                        />
                      ))}
                    </div>
                  </div>
                )}

                <ImageAttachPreview images={attachedImages} onRemove={removeImage} />

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

                {/* Pending posts */}
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
                    {postsLoading ? (
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
                                </div>
                                <p style={{ fontSize: 12, color: 'var(--text-primary)', lineHeight: 1.5, margin: 0, overflow: 'hidden', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical' }}>
                                  {post.caption}
                                </p>
                              </div>
                              <div style={{ display: 'flex', flexDirection: 'column', gap: 4, flexShrink: 0 }}>
                                <button onClick={() => approvePost(post.postiz_id)} className="btn btn-sm" style={{ background: 'var(--success-bg)', color: 'var(--success-text)', border: '1px solid var(--success-border)', gap: 4 }}>
                                  <CheckCircle size={11} /> Approve
                                </button>
                                <button onClick={() => rejectPost(post.postiz_id)} className="btn btn-danger btn-sm" style={{ gap: 4 }}>
                                  <XCircle size={11} /> Reject
                                </button>
                                <button onClick={() => { openPost(post); setPipelineOpen(false); }} className="btn btn-secondary btn-sm" style={{ gap: 4 }}>
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

            <PostPreviewPanel
              post={selectedPost}
              isOpen={previewOpen}
              onClose={closePost}
              onApprove={approvePost}
              onReject={rejectPost}
            />

            <AgentPipelinePanel
              open={pipelineOpen}
              onClose={() => setPipelineOpen(false)}
              stepStatuses={stepStatuses}
              runId={runId}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
