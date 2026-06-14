'use client';
import { useEffect, useState, useCallback, useRef } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import {
  ArrowLeft, CheckCircle, XCircle, Pause, Play, AlertTriangle,
  Clock, RefreshCw, StopCircle,
} from 'lucide-react';
import { notify } from '../../../../lib/toast';
import ResearchBriefReview, { type ResearchBrief } from '../../../../components/ResearchBriefReview';

type StageStatus = 'pending' | 'running' | 'paused' | 'approved' | 'failed' | 'skipped';
type OverallStatus = 'pending' | 'running' | 'paused_for_review' | 'completed' | 'failed' | 'cancelled';

interface StageState {
  status: StageStatus;
  output: Record<string, unknown> | null;
  error: { message: string } | null;
  started_at: string | null;
  completed_at: string | null;
}

interface AgentRun {
  id: string;
  topic: string;
  platforms: string[];
  execution_mode: string;
  overall_status: OverallStatus;
  current_stage: string;
  stages: Record<string, StageState>;
  stages_enabled: Record<string, boolean>;
  created_at: string | null;
  updated_at: string | null;
}

const STAGE_ORDER = ['research', 'content_generation', 'visual_generation', 'scheduling'];

const STAGE_LABEL: Record<string, string> = {
  research: 'Research',
  content_generation: 'Content Generation',
  visual_generation: 'Visual Generation',
  scheduling: 'Scheduling',
};

const STATUS_ICON: Record<StageStatus, React.ElementType> = {
  pending:  Clock,
  running:  RefreshCw,
  paused:   Pause,
  approved: CheckCircle,
  failed:   AlertTriangle,
  skipped:  XCircle,
};

const STATUS_COLOR: Record<StageStatus, string> = {
  pending:  'var(--text-muted)',
  running:  '#3B82F6',
  paused:   '#F59E0B',
  approved: '#10B981',
  failed:   '#EF4444',
  skipped:  'var(--text-muted)',
};

const OVERALL_STATUS_COLOR: Record<OverallStatus, string> = {
  pending:           'var(--text-muted)',
  running:           '#3B82F6',
  paused_for_review: '#F59E0B',
  completed:         '#10B981',
  failed:            '#EF4444',
  cancelled:         'var(--text-muted)',
};

export default function RunDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [run, setRun] = useState<AgentRun | null>(null);
  const [loading, setLoading] = useState(true);
  const [approvingStage, setApprovingStage] = useState<string | null>(null);
  const [cancelling, setCancelling] = useState(false);
  const eventSourceRef = useRef<EventSource | null>(null);

  const fetchRun = useCallback(async () => {
    try {
      const resp = await fetch(`/api/proxy/runs/${id}`);
      if (resp.status === 404) { router.push('/runs'); return; }
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      setRun(data);
    } catch {
      notify.error('Failed to load run');
    } finally {
      setLoading(false);
    }
  }, [id, router]);

  useEffect(() => {
    fetchRun();
  }, [fetchRun]);

  // SSE stream for live updates
  useEffect(() => {
    if (!id) return;
    const es = new EventSource(`/api/runs/${id}/stream`);
    eventSourceRef.current = es;
    es.onmessage = (e) => {
      try {
        const event = JSON.parse(e.data);
        if (event.type === 'status_change' || event.type === 'stage_update') {
          fetchRun();
        }
      } catch {}
    };
    es.onerror = () => {
      es.close();
    };
    return () => es.close();
  }, [id, fetchRun]);

  async function approveStage(stageName: string, editedOutput?: unknown) {
    setApprovingStage(stageName);
    try {
      const resp = await fetch(`/api/proxy/runs/${id}/stage/${stageName}/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ edited_output: editedOutput ?? null }),
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      notify.success('Stage approved');
      await fetchRun();
    } catch {
      notify.error('Failed to approve stage');
    } finally {
      setApprovingStage(null);
    }
  }

  async function rejectStage(stageName: string) {
    try {
      const resp = await fetch(`/api/proxy/runs/${id}/stage/${stageName}/reject`, {
        method: 'POST',
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      notify.success('Stage will be re-run');
      await fetchRun();
    } catch {
      notify.error('Failed to reject stage');
    }
  }

  async function cancelRun() {
    if (!confirm('Cancel this run? This cannot be undone.')) return;
    setCancelling(true);
    try {
      const resp = await fetch(`/api/proxy/runs/${id}`, { method: 'DELETE' });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      notify.success('Run cancelled');
      router.push('/runs');
    } catch {
      notify.error('Failed to cancel run');
      setCancelling(false);
    }
  }

  if (loading) {
    return (
      <div className="page-container" style={{ textAlign: 'center', paddingTop: 80 }}>
        <div style={{ color: 'var(--text-muted)', fontSize: 13 }}>Loading run…</div>
      </div>
    );
  }

  if (!run) return null;

  const isTerminal = ['completed', 'failed', 'cancelled'].includes(run.overall_status);

  return (
    <div className="page-container" style={{ maxWidth: 800, margin: '0 auto' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12, marginBottom: 24 }}>
        <Link href="/runs" style={{ color: 'var(--text-muted)', display: 'flex', marginTop: 3 }}>
          <ArrowLeft size={16} />
        </Link>
        <div style={{ flex: 1, minWidth: 0 }}>
          <h1 className="page-title" style={{ margin: 0, marginBottom: 4, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {run.topic}
          </h1>
          <div style={{ display: 'flex', gap: 8, fontSize: 12, color: 'var(--text-muted)', flexWrap: 'wrap' }}>
            <span style={{ color: OVERALL_STATUS_COLOR[run.overall_status], fontWeight: 500, textTransform: 'capitalize' }}>
              {run.overall_status.replace(/_/g, ' ')}
            </span>
            <span>·</span>
            <span>{run.platforms.join(', ')}</span>
            <span>·</span>
            <span style={{ textTransform: 'capitalize' }}>{run.execution_mode}</span>
          </div>
        </div>
        {!isTerminal && (
          <button
            onClick={cancelRun}
            disabled={cancelling}
            className="btn btn-secondary btn-sm"
            style={{ gap: 4, color: '#EF4444', flexShrink: 0 }}
          >
            <StopCircle size={13} />
            {cancelling ? 'Cancelling…' : 'Cancel'}
          </button>
        )}
      </div>

      {/* Stage pipeline */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {STAGE_ORDER.map((stageName, idx) => {
          const stage = run.stages[stageName];
          if (!stage) return null;
          const Icon = STATUS_ICON[stage.status] ?? Clock;
          const color = STATUS_COLOR[stage.status] ?? 'var(--text-muted)';
          const isPaused = stage.status === 'paused';
          const isResearch = stageName === 'research';

          return (
            <div key={stageName} className="card">
              {/* Stage header */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: isPaused ? 16 : 0 }}>
                <div style={{
                  width: 24, height: 24, borderRadius: '50%',
                  background: 'var(--surface-raised)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  flexShrink: 0,
                }}>
                  <Icon
                    size={13}
                    color={color}
                    style={{ animation: stage.status === 'running' ? 'spin 1s linear infinite' : undefined }}
                  />
                </div>
                <div style={{ flex: 1 }}>
                  <span style={{ fontWeight: 500, fontSize: 14 }}>{STAGE_LABEL[stageName] ?? stageName}</span>
                </div>
                <span style={{ fontSize: 12, color, fontWeight: 500, textTransform: 'capitalize' }}>
                  {stage.status}
                </span>
              </div>

              {/* Error message */}
              {stage.status === 'failed' && stage.error && (
                <div style={{
                  marginTop: 8, padding: '8px 12px',
                  background: 'rgba(239,68,68,0.08)',
                  borderRadius: 6, fontSize: 12,
                  color: '#EF4444',
                }}>
                  {stage.error.message}
                </div>
              )}

              {/* Research brief review UI */}
              {isPaused && isResearch && stage.output && (
                <ResearchBriefReview
                  brief={stage.output as unknown as ResearchBrief}
                  runId={run.id}
                  stage={stageName}
                  onApprove={(edited) => approveStage(stageName, edited)}
                  onReject={() => rejectStage(stageName)}
                  approving={approvingStage === stageName}
                />
              )}

              {/* Generic paused stage: approve/reject buttons */}
              {isPaused && !isResearch && (
                <div>
                  <pre style={{
                    fontSize: 11, background: 'var(--surface-raised)',
                    padding: 10, borderRadius: 6,
                    overflow: 'auto', maxHeight: 200,
                    margin: '0 0 12px 0',
                    color: 'var(--text-muted)',
                  }}>
                    {JSON.stringify(stage.output, null, 2)}
                  </pre>
                  <div style={{ display: 'flex', gap: 8 }}>
                    <button
                      onClick={() => approveStage(stageName)}
                      disabled={approvingStage === stageName}
                      className="btn btn-primary btn-sm"
                      style={{ gap: 4 }}
                    >
                      <CheckCircle size={13} />
                      {approvingStage === stageName ? 'Approving…' : 'Approve'}
                    </button>
                    <button
                      onClick={() => rejectStage(stageName)}
                      className="btn btn-secondary btn-sm"
                      style={{ gap: 4 }}
                    >
                      <RefreshCw size={13} />
                      Redo
                    </button>
                  </div>
                </div>
              )}

              {/* Approved output preview (non-research) */}
              {stage.status === 'approved' && !isResearch && stage.output && (
                <div style={{ marginTop: 8 }}>
                  <pre style={{
                    fontSize: 11, background: 'var(--surface-raised)',
                    padding: 10, borderRadius: 6,
                    overflow: 'auto', maxHeight: 120,
                    margin: 0,
                    color: 'var(--text-muted)',
                  }}>
                    {JSON.stringify(stage.output, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {run.overall_status === 'completed' && (
        <div style={{
          marginTop: 16, padding: '12px 16px',
          background: 'rgba(16,185,129,0.08)',
          border: '1px solid rgba(16,185,129,0.2)',
          borderRadius: 8, textAlign: 'center',
          color: '#10B981', fontWeight: 500, fontSize: 14,
        }}>
          Run completed successfully
        </div>
      )}
    </div>
  );
}
