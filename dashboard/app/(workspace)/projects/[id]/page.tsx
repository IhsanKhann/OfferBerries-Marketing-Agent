'use client';
import { useEffect, useState, useRef, useCallback } from 'react';
import { useParams, useSearchParams, useRouter } from 'next/navigation';
import { Linkedin, Twitter, Instagram, Youtube, Mail, CheckCircle, XCircle, Cpu, X, Images } from 'lucide-react';
import { toast } from 'sonner';
import AgentErrorBanner from '@/components/AgentErrorBanner';
import AgentChatThread, { ChatMessage } from '@/app/(app)/queue/AgentChatThread';
import AgentInputBar from '@/app/(app)/queue/AgentInputBar';
import ImageAttachPreview from '@/app/(app)/queue/ImageAttachPreview';
import PostPreviewPanel from '@/app/(app)/queue/PostPreviewPanel';
import { useAgentRun, STEPS } from '@/hooks/useAgentRun';
import { useImageAttach } from '@/hooks/useImageAttach';
import { usePostPreview, PreviewPost } from '@/hooks/usePostPreview';
import { ProjectSidebar } from './ProjectSidebar';
import { OptionsModal } from './OptionsModal';
import type { Project } from '@/hooks/useProjects';
import type { StepStatus } from '@/hooks/useAgentRun';

const GREETINGS = [
  'Start when you are ready',
  'What would you like to create today',
  'Ready to research and publish',
  "Let's build something great",
  'What should we research today',
];

const PLATFORM_ICON: Record<string, React.ElementType> = {
  linkedin: Linkedin, twitter: Twitter, instagram: Instagram,
  youtube: Youtube, email: Mail,
};

const PLATFORM_COLOR: Record<string, string> = {
  linkedin: '#0A66C2', twitter: '#1D9BF0', instagram: '#E1306C',
  youtube: '#FF0000', email: '#6366F1',
};

function PipelinePanel({ stepStatuses, runId }: { stepStatuses: StepStatus[]; runId: string | null }) {
  return (
    <div className="ws-pipeline-body">
      <div className="stepper">
        {STEPS.map((step, i) => {
          const status = stepStatuses[i] ?? 'pending';
          const isRunning = status === 'running';
          const prevDone = i > 0 && (stepStatuses[i - 1] ?? 'pending') === 'done';
          return (
            <div key={i}>
              {i > 0 && <div className={`pipeline-connector${prevDone ? ' pipeline-connector--done' : ''}`} />}
              <div className={`step-item${isRunning ? ' pipeline-node--running' : ''}`}>
                <div className={`step-dot ${status}`}>
                  {status === 'done'
                    ? '✓'
                    : status === 'running'
                    ? <span className="spinner" style={{ width: 10, height: 10, borderWidth: 1.5 }} />
                    : status === 'failed'
                    ? '✗'
                    : i + 1}
                </div>
                <div className="step-content">
                  <div className="step-title">{step.label}</div>
                  <div className="step-meta">{step.meta}</div>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function ProjectWorkspacePage() {
  const { id: projectId } = useParams<{ id: string }>();
  const searchParams = useSearchParams();
  const activeRunId = searchParams.get('run');
  const router = useRouter();

  const [project, setProject]           = useState<Project | null>(null);
  const [projectLoading, setProjectLoading] = useState(true);
  const [posts, setPosts]               = useState<PreviewPost[]>([]);
  const [postsLoading, setPostsLoading] = useState(false);
  const [filter, setFilter]             = useState('all');
  const [topic, setTopic]               = useState('');
  const [activePlatforms, setActivePlatforms] = useState<string[]>(['LinkedIn', 'Instagram']);
  const [rightTab, setRightTab]         = useState<null | 'pipeline' | 'posts'>(null);
  const [optionsOpen, setOptionsOpen]   = useState(false);
  const [messages, setMessages]         = useState<ChatMessage[]>([]);

  const [greetingText] = useState(
    () => GREETINGS[Math.floor(Math.random() * GREETINGS.length)]
  );

  const chatRef = useRef<HTMLDivElement>(null);

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
    agentError, clearError, startRun, stepStatuses,
  } = useAgentRun(fetchPosts, addMessage);

  const { images: attachedImages, addImages, removeImage } = useImageAttach();
  const { selectedPost, isOpen: previewOpen, openPost, closePost } = usePostPreview();

  useEffect(() => { fetchPosts(); }, [fetchPosts]);

  useEffect(() => {
    if (chatRef.current) chatRef.current.scrollTop = chatRef.current.scrollHeight;
  }, [messages, running]);

  // Auto-open pipeline panel when agent starts
  useEffect(() => {
    if (running) setRightTab('pipeline');
  }, [running]);

  // Switch to posts panel when run completes and posts are available
  useEffect(() => {
    if (runStatus === 'completed' && posts.length > 0) setRightTab('posts');
  }, [runStatus, posts.length]);

  function togglePlatform(p: string) {
    setActivePlatforms(prev =>
      prev.includes(p) ? prev.filter(x => x !== p) : [...prev, p]
    );
  }

  function togglePanel(tab: 'pipeline' | 'posts') {
    setRightTab(prev => prev === tab ? null : tab);
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
    setMessages([]);
    setTopic('');
    setPosts([]);
    setRightTab(null);
  }

  // --- Skeleton loading ---
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

  const hasUserMessages = messages.some(m => m.role === 'user');

  return (
    <div className="workspace-shell">
      <ProjectSidebar
        project={project}
        activeRunId={activeRunId ?? runId ?? undefined}
        onNewChat={handleNewChat}
      />

      <div className="workspace-main">
        {/* Minimal topbar — only pipeline + posts buttons */}
        <div className="ws-bar">
          <div className="ws-bar-end">
            <button
              className={`ws-panel-btn${rightTab === 'posts' ? ' active' : ''}`}
              onClick={() => togglePanel('posts')}
            >
              <Images size={13} />
              Posts
              {posts.length > 0 && <span className="ws-count">{posts.length}</span>}
            </button>
            <button
              className={`ws-panel-btn${rightTab === 'pipeline' ? ' active' : ''}`}
              onClick={() => togglePanel('pipeline')}
            >
              <Cpu size={13} />
              Pipeline
            </button>
          </div>
        </div>

        {/* Body: chat + optional right panel */}
        <div className="ws-body">
          {/* Chat column */}
          <div className="ws-chat">
            {agentError && (
              <div className="ws-error-banner">
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
              header={!hasUserMessages ? (
                <div className="ws-greeting">
                  <div className="ws-greeting-title">{greetingText}</div>
                  <div className="ws-greeting-sub">
                    Choose platforms &amp; models via <strong>Options</strong>, then type a topic to begin.
                  </div>
                </div>
              ) : undefined}
            />

            <div className="ws-input-wrap">
              <ImageAttachPreview images={attachedImages} onRemove={removeImage} />
              <AgentInputBar
                topic={topic}
                setTopic={setTopic}
                running={running}
                onRun={runAgent}
                onOpenOptions={() => setOptionsOpen(true)}
                onAttachFiles={addImages}
                onAttachImages={addImages}
              />
            </div>
          </div>

          {/* Right panel */}
          {rightTab && (
            <div className="ws-right-panel">
              <div className="ws-right-panel-hd">
                <div className="ws-right-tabs">
                  <button
                    className={`ws-right-tab${rightTab === 'pipeline' ? ' active' : ''}`}
                    onClick={() => setRightTab('pipeline')}
                  >
                    Pipeline
                  </button>
                  <button
                    className={`ws-right-tab${rightTab === 'posts' ? ' active' : ''}`}
                    onClick={() => setRightTab('posts')}
                  >
                    Posts
                    {posts.length > 0 && <span className="ws-count">{posts.length}</span>}
                  </button>
                </div>
                <button className="ws-right-close" onClick={() => setRightTab(null)}>
                  <X size={14} />
                </button>
              </div>

              <div className="ws-right-panel-body">
                {rightTab === 'pipeline' && (
                  <PipelinePanel stepStatuses={stepStatuses} runId={runId} />
                )}

                {rightTab === 'posts' && (
                  <div className="ws-posts">
                    <div style={{ display: 'flex', gap: 4, marginBottom: 12, flexWrap: 'wrap' }}>
                      {([['all', 'All'], ['linkedin', 'LinkedIn'], ['twitter', 'Twitter'], ['instagram', 'Instagram']] as [string, string][]).map(([val, lbl]) => (
                        <button
                          key={val}
                          className={`chip${filter === val ? ' active' : ''}`}
                          style={{ fontSize: 11 }}
                          onClick={() => setFilter(val)}
                        >
                          {lbl}
                        </button>
                      ))}
                    </div>

                    {postsLoading ? (
                      <div className="empty-state"><span className="spinner spinner-dark" /></div>
                    ) : posts.length === 0 ? (
                      <div className="ws-posts-empty">
                        <div style={{ fontSize: 28 }}>📋</div>
                        <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>No posts yet</div>
                        <div>Run the agent to generate content</div>
                      </div>
                    ) : (
                      posts.map(post => {
                        const Icon  = PLATFORM_ICON[post.platform] ?? Mail;
                        const color = PLATFORM_COLOR[post.platform] ?? 'var(--brand-primary)';
                        return (
                          <div key={post.postiz_id} className="ws-post-card">
                            <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
                              <div style={{ width: 30, height: 30, borderRadius: 8, background: color, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                                <Icon size={14} color="white" />
                              </div>
                              <div style={{ flex: 1, minWidth: 0 }}>
                                <div style={{ display: 'flex', gap: 4, marginBottom: 4, flexWrap: 'wrap', alignItems: 'center' }}>
                                  <span className="badge" style={{ background: color + '18', color, borderColor: color + '40' }}>
                                    {post.platform.charAt(0).toUpperCase() + post.platform.slice(1)}
                                  </span>
                                  <span className={`badge ${post.status === 'approved' ? 'badge-success' : post.status === 'queued' ? 'badge-warning' : 'badge-muted'}`}>
                                    {post.status}
                                  </span>
                                </div>
                                <p style={{ fontSize: 12, color: 'var(--text-primary)', lineHeight: 1.5, margin: 0, overflow: 'hidden', display: '-webkit-box', WebkitLineClamp: 3, WebkitBoxOrient: 'vertical' }}>
                                  {post.caption}
                                </p>
                              </div>
                            </div>
                            <div style={{ display: 'flex', gap: 6, marginTop: 10 }}>
                              <button
                                onClick={() => approvePost(post.postiz_id)}
                                className="btn btn-sm"
                                style={{ flex: 1, background: 'var(--success-bg)', color: 'var(--success-text)', border: '1px solid var(--success-border)', gap: 4 }}
                              >
                                <CheckCircle size={11} /> Approve
                              </button>
                              <button
                                onClick={() => openPost(post)}
                                className="btn btn-secondary btn-sm"
                                style={{ flex: 1 }}
                              >
                                Preview
                              </button>
                              <button
                                onClick={() => rejectPost(post.postiz_id)}
                                className="btn btn-danger btn-sm"
                              >
                                <XCircle size={11} />
                              </button>
                            </div>
                          </div>
                        );
                      })
                    )}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Options modal */}
      <OptionsModal
        open={optionsOpen}
        onClose={() => setOptionsOpen(false)}
        activePlatforms={activePlatforms}
        onTogglePlatform={togglePlatform}
        researchModel={researchModel}
        setResearchModel={setResearchModel}
        contentModel={contentModel}
        setContentModel={setContentModel}
      />

      {/* Post preview */}
      <PostPreviewPanel
        post={selectedPost}
        isOpen={previewOpen}
        onClose={closePost}
        onApprove={approvePost}
        onReject={rejectPost}
      />
    </div>
  );
}
