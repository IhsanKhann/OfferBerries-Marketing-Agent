'use client';
import { useEffect, useState, useRef } from 'react';
import { Send, Linkedin, Twitter, Instagram, Youtube, Mail, CheckCircle, XCircle } from 'lucide-react';
import { notify } from '../../../lib/toast';

type Post = {
  postiz_id: string;
  platform: string;
  scheduled_at: string;
  status: string;
  caption?: string;
  preview_url?: string;
};

type ChatMessage = { role: 'user' | 'assistant'; content: string };

const PLATFORMS = ['LinkedIn', 'Twitter', 'Instagram', 'YouTube', 'Email'];

const PLATFORM_ICON: Record<string, React.ElementType> = {
  linkedin: Linkedin, twitter: Twitter, instagram: Instagram,
  youtube: Youtube, email: Mail,
};

const PLATFORM_COLOR: Record<string, string> = {
  linkedin: '#0A66C2', twitter: '#1D9BF0', instagram: '#E1306C',
  youtube: '#FF0000', email: '#6366F1',
};

const STEPS = [
  { label: 'Research',       meta: 'Perplexity API' },
  { label: 'Generate',       meta: 'OpenRouter · Gemini' },
  { label: 'Visual',         meta: 'Renderer · Playwright' },
  { label: 'Queue',          meta: 'Postiz scheduling' },
  { label: 'Analytics',      meta: 'MongoDB telemetry' },
  { label: 'Self-Improve',   meta: 'Pattern extractor' },
];

function stepStatus(idx: number, agentStatus: string, posts: Post[]): 'done' | 'running' | 'pending' | 'failed' {
  if (agentStatus === 'failed') return idx === 0 ? 'failed' : 'pending';
  if (agentStatus === 'completed') return idx <= 3 ? 'done' : 'pending';
  if (agentStatus === 'started' || agentStatus === 'starting') {
    if (idx === 0) return 'running';
    return 'pending';
  }
  if (agentStatus.includes('research') && idx === 0) return 'running';
  if (agentStatus.includes('content') && idx < 1) return 'done';
  if (agentStatus.includes('content') && idx === 1) return 'running';
  if (agentStatus.includes('visual') && idx < 2) return 'done';
  if (agentStatus.includes('visual') && idx === 2) return 'running';
  if (agentStatus.includes('queue') && idx < 3) return 'done';
  if (agentStatus.includes('queue') && idx === 3) return 'running';
  if (posts.length > 0 && idx < 4) return 'done';
  return 'pending';
}

export default function QueuePage() {
  const [posts, setPosts]     = useState<Post[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter]   = useState('all');
  const [topic, setTopic]     = useState('');
  const [running, setRunning] = useState(false);
  const [runId, setRunId]     = useState<string | null>(null);
  const [runStatus, setRunStatus] = useState('');
  const [messages, setMessages]   = useState<ChatMessage[]>([
    { role: 'assistant', content: 'Hi! I\'m your research assistant. Tell me what topic you\'d like to create content about and I\'ll research trends, competitors, and top-performing posts.' },
  ]);
  const [activePlatforms, setActivePlatforms] = useState<string[]>(['LinkedIn', 'Twitter', 'Instagram']);
  const chatRef = useRef<HTMLDivElement>(null);

  useEffect(() => { fetchPosts(); }, [filter]);

  useEffect(() => {
    if (chatRef.current) chatRef.current.scrollTop = chatRef.current.scrollHeight;
  }, [messages]);

  useEffect(() => {
    if (!runId || runStatus === 'completed' || runStatus === 'failed') return;
    const t = setInterval(async () => {
      const res = await fetch(`/api/proxy/agent/status/${runId}`);
      const data = await res.json();
      setRunStatus(data.status);
      if (data.status === 'completed') {
        clearInterval(t);
        setRunning(false);
        setMessages(m => [...m, { role: 'assistant', content: '✅ Agent pipeline completed! New posts have been added to the queue below.' }]);
        notify.success('Agent completed', 'New posts added to queue');
        fetchPosts();
      }
      if (data.status === 'failed') {
        clearInterval(t);
        setRunning(false);
        setMessages(m => [...m, { role: 'assistant', content: '❌ Agent pipeline failed. Check logs for details.' }]);
        notify.error('Agent failed', 'Check server logs for details');
      }
    }, 5000);
    return () => clearInterval(t);
  }, [runId, runStatus]);

  async function fetchPosts() {
    setLoading(true);
    try {
      const params = filter !== 'all' ? `?platform=${filter}` : '';
      const res = await fetch(`/api/proxy/queue${params}`);
      if (res.ok) setPosts(await res.json());
    } finally {
      setLoading(false);
    }
  }

  async function approvePost(id: string) {
    await fetch(`/api/proxy/queue/${id}/approve`, { method: 'POST' });
    notify.success('Post approved', 'Added to publishing schedule');
    fetchPosts();
  }

  async function rejectPost(id: string) {
    await fetch(`/api/proxy/queue/${id}`, { method: 'DELETE' });
    notify.info('Post rejected', 'Removed from queue');
    fetchPosts();
  }

  async function runAgent() {
    if (!topic.trim()) return;
    const userMsg = topic;
    setTopic('');
    setMessages(m => [...m, { role: 'user', content: userMsg }]);
    setRunning(true);
    setRunStatus('starting');

    const res = await fetch('/api/proxy/agent/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        topic: userMsg,
        platform_filter: activePlatforms.map(p => p.toLowerCase()),
        dry_run: false,
      }),
    });

    if (res.ok) {
      const data = await res.json();
      setRunId(data.run_id);
      setRunStatus('started');
      setMessages(m => [...m, { role: 'assistant', content: `🚀 Agent pipeline started (run ${data.run_id.slice(0, 8)}…). Researching "${userMsg}" — check the Workflow panel for live progress.` }]);
      notify.info('Agent started', `Researching: ${userMsg}`);
    } else {
      setRunning(false);
      setMessages(m => [...m, { role: 'assistant', content: '❌ Failed to start agent. Please try again.' }]);
      notify.error('Failed to start', 'Check your connection and try again');
    }
  }

  function togglePlatform(p: string) {
    setActivePlatforms(prev =>
      prev.includes(p) ? prev.filter(x => x !== p) : [...prev, p]
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
      {/* Topbar */}
      <div className="topbar">
        <div>
          <div className="topbar-title">Content Queue</div>
          <div className="topbar-sub">{posts.length} post{posts.length !== 1 ? 's' : ''} pending review</div>
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
          <div className="avatar-chip">I</div>
        </div>
      </div>

      {/* Body */}
      <div className="content-area" style={{ display: 'flex', gap: 16, flex: 1, minHeight: 0, overflow: 'hidden' }}>
        {/* Left panel */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 16, minWidth: 0, overflow: 'hidden' }}>
          {/* Research chat */}
          <div className="card" style={{ display: 'flex', flexDirection: 'column', height: 340, padding: 0, overflow: 'hidden' }}>
            <div className="flex-between" style={{ padding: '16px 20px 12px', borderBottom: '1px solid var(--border-default)' }}>
              <div>
                <div className="card-title">Research Chat</div>
                <div className="card-sub">Powered by Perplexity</div>
              </div>
              <span className="badge badge-success">● Live</span>
            </div>
            <div className="chat-thread" ref={chatRef} style={{ flex: 1 }}>
              {messages.map((msg, i) => (
                <div key={i} className={`chat-bubble ${msg.role}`}>
                  {msg.role === 'assistant' && <div className="bubble-label">Agent</div>}
                  <div className="bubble-body">{msg.content}</div>
                </div>
              ))}
              {running && (
                <div className="chat-bubble assistant">
                  <div className="bubble-label">Agent</div>
                  <div className="bubble-body" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span className="spinner spinner-dark" />
                    <span style={{ color: 'var(--text-muted)' }}>Running pipeline… ({runStatus})</span>
                  </div>
                </div>
              )}
            </div>
            <div className="composer">
              <textarea
                value={topic}
                onChange={e => setTopic(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey && !running) { e.preventDefault(); runAgent(); } }}
                placeholder="Enter a topic to research and create content about…"
                rows={1}
                disabled={running}
              />
              <button
                onClick={runAgent}
                disabled={running || !topic.trim()}
                className="btn btn-primary btn-sm"
                style={{ flexShrink: 0 }}
              >
                <Send size={14} />
                Run
              </button>
            </div>
          </div>

          {/* Pending posts */}
          <div className="card" style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column', padding: 0 }}>
            <div className="flex-between" style={{ padding: '16px 20px 12px', borderBottom: '1px solid var(--border-default)' }}>
              <div className="flex-row gap-3">
                <span className="card-title">Pending Posts</span>
                {posts.length > 0 && <span className="badge badge-warning">{posts.length} awaiting review</span>}
              </div>
              <div className="flex-row gap-2">
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
            <div style={{ flex: 1, overflowY: 'auto', padding: '8px 0' }}>
              {loading ? (
                <div className="empty-state">
                  <span className="spinner spinner-dark" />
                </div>
              ) : posts.length === 0 ? (
                <div className="empty-state">
                  <div className="empty-icon">📋</div>
                  <div className="empty-title">No posts in queue</div>
                  <div className="empty-sub">Enter a topic above and press Run to generate content.</div>
                </div>
              ) : (
                posts.map(post => {
                  const Icon = PLATFORM_ICON[post.platform] || Mail;
                  const color = PLATFORM_COLOR[post.platform] || 'var(--brand-primary)';
                  return (
                    <div key={post.postiz_id} style={{ display: 'flex', gap: 14, padding: '12px 20px', borderBottom: '1px solid var(--border-subtle)', alignItems: 'flex-start' }}>
                      <div style={{ width: 36, height: 36, borderRadius: 'var(--radius-md)', background: color, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                        <Icon size={16} color="white" />
                      </div>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div className="flex-row gap-2" style={{ marginBottom: 4, flexWrap: 'wrap' }}>
                          <span className="badge" style={{ background: color + '18', color, borderColor: color + '40' }}>{post.platform}</span>
                          <span className={`badge ${post.status === 'approved' ? 'badge-success' : post.status === 'queued' ? 'badge-warning' : 'badge-muted'}`}>{post.status}</span>
                          <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{new Date(post.scheduled_at).toLocaleString('en-PK', { timeZone: 'Asia/Karachi', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}</span>
                        </div>
                        <p style={{ fontSize: 13, color: 'var(--text-primary)', lineHeight: 1.5, margin: 0 }}>
                          {post.caption?.substring(0, 180)}{post.caption && post.caption.length > 180 ? '…' : ''}
                        </p>
                      </div>
                      <div className="flex-row gap-2" style={{ flexShrink: 0 }}>
                        <button onClick={() => approvePost(post.postiz_id)} className="btn btn-sm" style={{ background: 'var(--success-bg)', color: 'var(--success-text)', border: '1px solid var(--success-border)' }}>
                          <CheckCircle size={12} /> Approve
                        </button>
                        <button onClick={() => rejectPost(post.postiz_id)} className="btn btn-danger btn-sm">
                          <XCircle size={12} /> Reject
                        </button>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </div>

        {/* Right workflow panel */}
        <div style={{ width: 276, flexShrink: 0, display: 'flex', flexDirection: 'column', gap: 12, overflowY: 'auto' }}>
          {/* Agent pipeline stepper */}
          <div className="card">
            <div className="card-title" style={{ marginBottom: 16 }}>Agent Pipeline</div>
            <div className="stepper">
              {STEPS.map((step, i) => {
                const status = stepStatus(i, runStatus, posts);
                return (
                  <div key={i} className="step-item">
                    <div className={`step-dot ${status}`}>
                      {status === 'done' ? '✓' : status === 'running' ? <span className="spinner" style={{ width: 10, height: 10, borderWidth: 1.5 }} /> : status === 'failed' ? '✗' : i + 1}
                    </div>
                    <div className="step-content">
                      <div className="step-title">{step.label}</div>
                      <div className="step-meta">{step.meta}</div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Upload zone (future) */}
          <div className="card" style={{ padding: 16 }}>
            <div className="card-title" style={{ marginBottom: 4 }}>Visual References</div>
            <div className="card-sub" style={{ marginBottom: 12 }}>Upload inspiration images for the agent</div>
            <div
              style={{
                border: '1.5px dashed var(--border-strong)',
                borderRadius: 'var(--radius-md)',
                padding: '20px 12px',
                textAlign: 'center',
                color: 'var(--text-muted)',
                fontSize: 12,
                cursor: 'pointer',
                transition: 'border-color var(--transition-fast), background var(--transition-fast)',
              }}
              onDragOver={e => { e.preventDefault(); (e.currentTarget as HTMLElement).style.borderColor = 'var(--border-focus)'; }}
              onDragLeave={e => { (e.currentTarget as HTMLElement).style.borderColor = 'var(--border-strong)'; }}
            >
              Drop images here<br />
              <span style={{ fontSize: 11, color: 'var(--text-placeholder)' }}>PNG, JPG up to 20 files</span>
            </div>
            {/* TODO: POST /api/proxy/agent/references with FormData once backend implemented */}
          </div>

          {/* Help widget */}
          <div className="card" style={{ background: 'linear-gradient(135deg, var(--sidebar-bg), #1E1B4B)', borderColor: '#334155', padding: 16 }}>
            <div style={{ fontSize: 13, fontWeight: 700, color: 'white', marginBottom: 4 }}>Need help?</div>
            <div style={{ fontSize: 12, color: 'rgba(255,255,255,0.5)', marginBottom: 12 }}>Contact the OfferBerries team</div>
            <textarea
              className="input"
              placeholder="Describe your issue…"
              rows={3}
              style={{ fontSize: 12, background: 'rgba(255,255,255,0.07)', border: '1px solid rgba(255,255,255,0.12)', color: 'rgba(255,255,255,0.8)', minHeight: 'unset' }}
            />
            <button
              className="btn btn-primary btn-sm"
              style={{ width: '100%', marginTop: 8 }}
              onClick={() => notify.success('Message sent', 'Our team will reply within 24h')}
            >
              Send Message
            </button>
            {/* TODO: POST /api/proxy/contact once backend implemented */}
          </div>
        </div>
      </div>
    </div>
  );
}
