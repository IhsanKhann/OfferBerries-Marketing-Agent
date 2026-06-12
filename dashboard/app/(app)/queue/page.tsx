'use client';
import { useEffect, useState } from 'react';

type Post = {
  postiz_id: string;
  platform: string;
  scheduled_at: string;
  status: string;
  caption?: string;
  preview_url?: string;
};

const PLATFORM_COLORS: Record<string, string> = {
  linkedin: '#0A66C2',
  twitter: '#1D9BF0',
  instagram: '#E1306C',
  youtube: '#FF0000',
};

export default function QueuePage() {
  const [posts, setPosts] = useState<Post[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('all');
  const [runTopic, setRunTopic] = useState('');
  const [running, setRunning] = useState(false);
  const [runId, setRunId] = useState<string | null>(null);
  const [runStatus, setRunStatus] = useState('');

  useEffect(() => {
    fetchPosts();
  }, [filter]);

  useEffect(() => {
    if (!runId || runStatus === 'completed' || runStatus === 'failed') return;
    const t = setInterval(async () => {
      const res = await fetch(`/api/proxy/agent/status/${runId}`);
      const data = await res.json();
      setRunStatus(data.status);
      if (data.status === 'completed' || data.status === 'failed') {
        clearInterval(t);
        fetchPosts();
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
    fetchPosts();
  }

  async function rejectPost(id: string) {
    await fetch(`/api/proxy/queue/${id}`, { method: 'DELETE' });
    fetchPosts();
  }

  async function runAgent() {
    if (!runTopic.trim()) return;
    setRunning(true);
    setRunStatus('starting');
    const res = await fetch('/api/proxy/agent/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ topic: runTopic, dry_run: false }),
    });
    const data = await res.json();
    setRunId(data.run_id);
    setRunStatus('started');
  }

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 32 }}>
        <div>
          <h1 style={{ fontSize: 28, fontWeight: 700, color: 'var(--text-primary)', margin: 0 }}>Approval Queue</h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: 14, marginTop: 4 }}>{posts.length} post{posts.length !== 1 ? 's' : ''} pending</p>
        </div>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
          <input
            value={runTopic}
            onChange={e => setRunTopic(e.target.value)}
            placeholder="Topic for new run..."
            style={{ padding: '8px 14px', border: '1px solid var(--border)', borderRadius: 6, fontSize: 14, fontFamily: 'inherit', width: 240 }}
          />
          <button
            onClick={runAgent}
            disabled={running || !runTopic.trim()}
            style={{
              padding: '8px 20px',
              background: running ? '#C4B5D9' : 'var(--brand-primary)',
              color: 'white',
              border: 'none',
              borderRadius: 6,
              fontSize: 14,
              fontWeight: 600,
              cursor: running ? 'not-allowed' : 'pointer',
              fontFamily: 'inherit',
            }}
          >
            {running ? `Running... (${runStatus})` : 'Run Agent'}
          </button>
        </div>
      </div>

      {/* Platform filter */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 24 }}>
        {['all', 'linkedin', 'twitter', 'instagram'].map(p => (
          <button
            key={p}
            onClick={() => setFilter(p)}
            style={{
              padding: '6px 16px',
              background: filter === p ? 'var(--brand-primary)' : 'white',
              color: filter === p ? 'white' : 'var(--text-secondary)',
              border: '1px solid var(--border)',
              borderRadius: 20,
              fontSize: 13,
              fontWeight: 500,
              cursor: 'pointer',
              fontFamily: 'inherit',
              textTransform: 'capitalize',
            }}
          >
            {p}
          </button>
        ))}
      </div>

      {loading ? (
        <div style={{ color: 'var(--text-secondary)', padding: 40, textAlign: 'center' }}>Loading...</div>
      ) : posts.length === 0 ? (
        <div style={{ textAlign: 'center', padding: 80, color: 'var(--text-secondary)' }}>
          <div style={{ fontSize: 20, fontWeight: 600, marginBottom: 8 }}>No posts in queue</div>
          <div style={{ fontSize: 14 }}>Enter a topic above and click Run Agent to generate content.</div>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {posts.map(post => (
            <div
              key={post.postiz_id}
              style={{ background: 'white', border: '1px solid var(--border)', borderRadius: 12, padding: 24, display: 'flex', gap: 20, alignItems: 'flex-start' }}
            >
              {post.preview_url && (
                <img src={post.preview_url} alt="preview" style={{ width: 80, height: 80, objectFit: 'cover', borderRadius: 8, flexShrink: 0 }} />
              )}
              <div style={{ flex: 1 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
                  <span style={{ background: PLATFORM_COLORS[post.platform] || 'var(--brand-primary)', color: 'white', fontSize: 11, fontWeight: 700, padding: '2px 10px', borderRadius: 12, textTransform: 'capitalize' }}>
                    {post.platform}
                  </span>
                  <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                    {new Date(post.scheduled_at).toLocaleString('en-PK', { timeZone: 'Asia/Karachi' })}
                  </span>
                  <span style={{
                    fontSize: 11,
                    fontWeight: 600,
                    color: post.status === 'published' ? 'var(--status-published)' : post.status === 'queued' ? 'var(--status-queued)' : 'var(--status-draft)',
                    textTransform: 'uppercase',
                    letterSpacing: '0.05em',
                  }}>
                    {post.status}
                  </span>
                </div>
                <p style={{ fontSize: 14, color: 'var(--text-primary)', lineHeight: 1.5, margin: 0 }}>
                  {post.caption?.substring(0, 200)}{post.caption && post.caption.length > 200 ? '...' : ''}
                </p>
              </div>
              <div style={{ display: 'flex', gap: 8, flexShrink: 0 }}>
                <button
                  onClick={() => approvePost(post.postiz_id)}
                  style={{ padding: '6px 16px', background: '#10B981', color: 'white', border: 'none', borderRadius: 6, fontSize: 13, fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit' }}
                >
                  Approve
                </button>
                <button
                  onClick={() => rejectPost(post.postiz_id)}
                  style={{ padding: '6px 16px', background: 'white', color: '#EF4444', border: '1px solid #EF4444', borderRadius: 6, fontSize: 13, fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit' }}
                >
                  Reject
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
