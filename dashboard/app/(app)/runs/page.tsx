'use client';
import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Plus, RefreshCw, Clock, CheckCircle, XCircle, Pause, Play, AlertTriangle } from 'lucide-react';
import { notify } from '../../../lib/toast';

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

export default function RunsPage() {
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>('');

  async function fetchRuns() {
    setLoading(true);
    try {
      const url = statusFilter ? `/api/proxy/runs?status=${statusFilter}` : '/api/proxy/runs';
      const resp = await fetch(url);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      setRuns(data.runs ?? data);
    } catch {
      notify.error('Failed to load runs');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { fetchRuns(); }, [statusFilter]);

  return (
    <div className="page-container">
      <div className="page-header">
        <div>
          <h1 className="page-title">Agent Runs</h1>
          <p className="page-subtitle">Manage your AI marketing pipeline runs</p>
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <button onClick={fetchRuns} className="btn btn-secondary btn-sm" style={{ gap: 4 }}>
            <RefreshCw size={13} /> Refresh
          </button>
          <Link href="/runs/new" className="btn btn-primary btn-sm" style={{ gap: 4 }}>
            <Plus size={13} /> New Run
          </Link>
        </div>
      </div>

      {/* Status filter chips */}
      <div style={{ display: 'flex', gap: 6, marginBottom: 16, flexWrap: 'wrap' }}>
        {['', 'running', 'paused_for_review', 'completed', 'failed'].map(s => (
          <button
            key={s}
            onClick={() => setStatusFilter(s)}
            className={`badge ${statusFilter === s ? 'badge-primary' : 'badge-muted'}`}
            style={{ cursor: 'pointer', padding: '4px 10px', fontSize: 12 }}
          >
            {s === '' ? 'All' : (STATUS_CONFIG[s as RunStatus]?.label ?? s)}
          </button>
        ))}
      </div>

      {loading ? (
        <div style={{ textAlign: 'center', padding: 48, color: 'var(--text-muted)', fontSize: 13 }}>
          Loading runs…
        </div>
      ) : runs.length === 0 ? (
        <div className="card" style={{ textAlign: 'center', padding: 48 }}>
          <p style={{ color: 'var(--text-muted)', marginBottom: 12 }}>No runs yet.</p>
          <Link href="/runs/new" className="btn btn-primary btn-sm">
            <Plus size={13} /> Start your first run
          </Link>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {runs.map(run => {
            const cfg = STATUS_CONFIG[run.overall_status] ?? STATUS_CONFIG.pending;
            const Icon = cfg.icon;
            return (
              <Link
                key={run.id}
                href={`/runs/${run.id}`}
                className="card"
                style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '12px 16px', textDecoration: 'none' }}
              >
                <Icon size={16} color={cfg.color} style={{ flexShrink: 0 }} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontWeight: 500, fontSize: 14, marginBottom: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {run.topic}
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--text-muted)', display: 'flex', gap: 8 }}>
                    <span>{run.platforms.join(', ')}</span>
                    <span>·</span>
                    <span style={{ textTransform: 'capitalize' }}>{run.execution_mode}</span>
                    {run.overall_status === 'running' || run.overall_status === 'paused_for_review' ? (
                      <>
                        <span>·</span>
                        <span style={{ textTransform: 'capitalize' }}>{run.current_stage.replace(/_/g, ' ')}</span>
                      </>
                    ) : null}
                  </div>
                </div>
                <div style={{ textAlign: 'right', flexShrink: 0 }}>
                  <span style={{ fontSize: 12, color: cfg.color, fontWeight: 500 }}>{cfg.label}</span>
                  {run.created_at && (
                    <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
                      {new Date(run.created_at).toLocaleDateString()}
                    </div>
                  )}
                </div>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
