'use client';
import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { Plus, RefreshCw, Clock, CheckCircle, XCircle, Pause, Play, AlertTriangle } from 'lucide-react';
import { notify } from '@/lib/toast';
import { ProjectFrame } from '../_components/ProjectFrame';

type RunStatus = 'pending' | 'running' | 'paused_for_review' | 'completed' | 'failed' | 'cancelled';

interface RunSummary {
  id: string;
  topic: string;
  platforms: string[];
  execution_mode: string;
  overall_status: RunStatus;
  current_stage: string;
  created_at: string | null;
}

const STATUS_CONFIG: Record<RunStatus, { icon: React.ElementType; color: string; label: string }> = {
  pending:           { icon: Clock,         color: 'var(--text-muted)',  label: 'Pending' },
  running:           { icon: Play,          color: '#3B82F6',            label: 'Running' },
  paused_for_review: { icon: Pause,         color: '#F59E0B',            label: 'Awaiting Review' },
  completed:         { icon: CheckCircle,   color: '#10B981',            label: 'Completed' },
  failed:            { icon: AlertTriangle, color: '#EF4444',            label: 'Failed' },
  cancelled:         { icon: XCircle,       color: 'var(--text-muted)',  label: 'Cancelled' },
};

function ProjectRunsContent({ projectId }: { projectId: string }) {
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('');

  async function fetchRuns() {
    setLoading(true);
    try {
      const params = new URLSearchParams({ project_id: projectId });
      if (statusFilter) params.set('status', statusFilter);
      const resp = await fetch(`/api/proxy/runs?${params}`);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      setRuns(data.runs ?? data);
    } catch {
      notify.error('Failed to load runs');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { fetchRuns(); }, [statusFilter, projectId]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div className="topbar">
        <div>
          <div className="topbar-title">Runs</div>
          <div className="topbar-sub">Agent pipeline runs for this project</div>
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <button onClick={fetchRuns} className="btn btn-secondary btn-sm" style={{ gap: 4 }}>
            <RefreshCw size={13} /> Refresh
          </button>
          <Link href={`/projects/${projectId}`} className="btn btn-primary btn-sm" style={{ gap: 4 }}>
            <Plus size={13} /> New Chat
          </Link>
        </div>
      </div>

      <div className="page-container" style={{ flex: 1, overflowY: 'auto' }}>
        {/* Status filters */}
        <div style={{ display: 'flex', gap: 6, marginBottom: 16, flexWrap: 'wrap' }}>
          {(['', 'running', 'paused_for_review', 'completed', 'failed'] as const).map(s => (
            <button
              key={s}
              onClick={() => setStatusFilter(s)}
              className={`chip${statusFilter === s ? ' active' : ''}`}
            >
              {s === '' ? 'All' : STATUS_CONFIG[s as RunStatus]?.label ?? s}
            </button>
          ))}
        </div>

        {loading ? (
          <div className="empty-state" style={{ padding: '48px 0' }}>
            <span className="spinner spinner-dark" />
          </div>
        ) : runs.length === 0 ? (
          <div className="empty-state" style={{ padding: '48px 0' }}>
            <div className="empty-title">No runs yet</div>
            <div className="empty-sub">Start a new chat to create your first run.</div>
            <Link href={`/projects/${projectId}`} className="btn btn-primary" style={{ marginTop: 16 }}>
              <Plus size={14} /> New Chat
            </Link>
          </div>
        ) : (
          <div className="card" style={{ overflow: 'hidden', padding: 0 }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border-default)' }}>
                  {['Topic', 'Status', 'Stage', 'Platforms', 'Created'].map(h => (
                    <th key={h} style={{ padding: '10px 16px', textAlign: 'left', fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {runs.map((run, i) => {
                  const cfg = STATUS_CONFIG[run.overall_status] ?? STATUS_CONFIG.pending;
                  const Icon = cfg.icon;
                  return (
                    <tr
                      key={run.id}
                      style={{ borderBottom: i < runs.length - 1 ? '1px solid var(--border-subtle)' : 'none', cursor: 'pointer', transition: 'background 0.1s' }}
                      onClick={() => window.location.href = `/runs/${run.id}`}
                      onMouseEnter={e => (e.currentTarget.style.background = 'var(--bg-subtle)')}
                      onMouseLeave={e => (e.currentTarget.style.background = '')}
                    >
                      <td style={{ padding: '12px 16px', fontSize: 13, fontWeight: 500, color: 'var(--text-primary)', maxWidth: 260, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {run.topic || '—'}
                      </td>
                      <td style={{ padding: '12px 16px' }}>
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 12, color: cfg.color, fontWeight: 500 }}>
                          <Icon size={13} /> {cfg.label}
                        </span>
                      </td>
                      <td style={{ padding: '12px 16px', fontSize: 12, color: 'var(--text-secondary)' }}>
                        {run.current_stage?.replace(/_/g, ' ') || '—'}
                      </td>
                      <td style={{ padding: '12px 16px' }}>
                        <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                          {(run.platforms ?? []).map(p => (
                            <span key={p} className="badge badge-muted" style={{ fontSize: 10 }}>{p}</span>
                          ))}
                        </div>
                      </td>
                      <td style={{ padding: '12px 16px', fontSize: 12, color: 'var(--text-muted)' }}>
                        {run.created_at ? new Date(run.created_at).toLocaleDateString() : '—'}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

export default function ProjectRunsPage() {
  const { id: projectId } = useParams<{ id: string }>();
  return (
    <ProjectFrame projectId={projectId}>
      <ProjectRunsContent projectId={projectId} />
    </ProjectFrame>
  );
}
