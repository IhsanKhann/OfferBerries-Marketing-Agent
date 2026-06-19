'use client';
import { useState, useEffect, useCallback, useRef } from 'react';
import { notify } from '../lib/toast';
import type { AgentError } from '../components/AgentErrorBanner';

export type RunStatus = 'idle' | 'starting' | 'pending' | 'running' | 'paused_for_review' | 'completed' | 'failed' | 'cancelled';

export type StepStatus = 'done' | 'running' | 'pending' | 'failed';

export type { AgentError };

const STAGE_NAMES = ['research', 'content_generation', 'visual_generation', 'scheduling'];

function computeStepStatus(idx: number, overall: RunStatus, currentStage: string): StepStatus {
  if (overall === 'failed' || overall === 'cancelled') return idx === 0 ? 'failed' : 'pending';
  if (overall === 'completed') return idx <= 3 ? 'done' : 'pending';
  if (overall === 'running' || overall === 'paused_for_review') {
    const curIdx = STAGE_NAMES.indexOf(currentStage);
    if (curIdx < 0) return idx === 0 ? 'running' : 'pending';
    if (idx < curIdx) return 'done';
    if (idx === curIdx) return 'running';
    return 'pending';
  }
  return 'pending';
}

export const RESEARCH_MODELS = [
  { id: 'sonar-pro',           label: 'Sonar Pro',     badge: '−$0.004' },
  { id: 'sonar',               label: 'Sonar',         badge: '−$0.001' },
  { id: 'sonar-deep-research', label: 'Deep Research', badge: '−$0.056' },
];

export const CONTENT_MODELS = [
  { id: 'anthropic/claude-sonnet-4-6', label: 'Claude Sonnet' },
  { id: 'anthropic/claude-haiku-4-5',  label: 'Claude Haiku' },
  { id: 'google/gemini-2.5-flash',     label: 'Gemini Flash' },
];

// Exactly mirrors the backend STAGE_ORDER (research, content_generation,
// visual_generation, scheduling). No fake Analytics/Self-Improve steps.
export const STEPS = [
  { label: 'Research',           meta: 'Perplexity' },
  { label: 'Content Generation', meta: 'OpenRouter · Claude' },
  { label: 'Visual Generation',  meta: 'Renderer · Playwright' },
  { label: 'Scheduling',         meta: 'Postiz' },
];

const STAGE_MESSAGES: Record<string, string> = {
  research:           '🔍 Researching trends with Perplexity…',
  content_generation: '✍️ Generating content with Claude…',
  visual_generation:  '🎨 Rendering visuals…',
  scheduling:         '📅 Scheduling posts…',
};

async function fetchCitations(runId: string): Promise<string[]> {
  try {
    const res = await fetch(`/api/proxy/runs/${runId}`);
    if (!res.ok) return [];
    const data = await res.json();
    const researchOutput = data.stages?.research?.output;
    if (!researchOutput) return [];
    const raw = researchOutput.platform_notes?.citations ?? researchOutput.citations ?? '';
    if (!raw) return [];
    const parsed = typeof raw === 'string' ? JSON.parse(raw) : raw;
    return Array.isArray(parsed) ? parsed.filter(Boolean) : [];
  } catch {
    return [];
  }
}

export function useAgentRun(onComplete: () => void, onMessage: (msg: string) => void) {
  const [runId, setRunId]           = useState<string | null>(null);
  const [runStatus, setRunStatus]   = useState<RunStatus>('idle');
  const [currentStage, setCurrentStage] = useState('');
  const prevStageRef = useRef('');
  const [running, setRunning]       = useState(false);
  const [researchModel, setResearchModel] = useState('sonar-pro');
  const [contentModel, setContentModel]   = useState('anthropic/claude-sonnet-4-6');
  const [agentError, setAgentError] = useState<AgentError | null>(null);

  const stepStatuses: StepStatus[] = STEPS.map((_, i) =>
    computeStepStatus(i, runStatus, currentStage)
  );

  // Poll for status updates
  useEffect(() => {
    if (!runId || runStatus === 'completed' || runStatus === 'failed' || runStatus === 'cancelled' || runStatus === 'idle') return;
    const t = setInterval(async () => {
      try {
        const res = await fetch(`/api/proxy/runs/${runId}`);
        if (!res.ok) return;
        const data = await res.json();
        const status: RunStatus = data.overall_status ?? 'idle';
        const stage: string = data.current_stage ?? '';
        setRunStatus(status);
        setCurrentStage(stage);

        // Announce stage transitions
        if (stage && stage !== prevStageRef.current) {
          const stageMsg = STAGE_MESSAGES[stage];
          if (stageMsg) onMessage(stageMsg);

          // When research finishes (moving to content_generation), show citations
          if (prevStageRef.current === 'research' && stage === 'content_generation') {
            fetchCitations(runId).then(citations => {
              if (citations.length > 0) {
                const citationText = '📚 **Sources from Perplexity:**\n' +
                  citations.map((url, idx) => `[${idx + 1}] ${url}`).join('\n');
                onMessage(citationText);
              }
            });
          }
          prevStageRef.current = stage;
        }

        if (status === 'completed') {
          clearInterval(t);
          setRunning(false);
          onMessage('✅ Agent pipeline completed! New posts have been added to the queue below.');
          notify.success('Agent completed', 'New posts added to queue');
          onComplete();
        }
        if (status === 'failed' || status === 'cancelled') {
          clearInterval(t);
          setRunning(false);
          onMessage(`❌ Agent pipeline ${status}. Check the run detail page for error information.`);
          notify.error(`Agent ${status}`, 'Check run details for more info');
        }
      } catch { /* swallow network blips */ }
    }, 5000);
    return () => clearInterval(t);
  }, [runId, runStatus, onComplete, onMessage]);

  const startRun = useCallback(async (topic: string, platforms: string[], projectId?: string) => {
    setRunning(true);
    setRunStatus('starting');
    setCurrentStage('');
    prevStageRef.current = '';
    setAgentError(null);

    try {
      await Promise.all([
        fetch('/api/proxy/config/research-model', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ model_id: researchModel }),
        }),
        fetch('/api/proxy/config/content-model', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ model_id: contentModel }),
        }),
      ]);
    } catch { /* non-fatal */ }

    const body: Record<string, unknown> = { topic, platforms, execution_mode: 'automated' };
    if (projectId) body.project_id = projectId;

    const res = await fetch('/api/proxy/runs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });

    if (res.ok) {
      const data = await res.json();
      setRunId(data.run_id);
      setRunStatus('pending');
      onMessage(`🚀 Run ${data.run_id.slice(0, 8)}… started for "${topic}". Watch the pipeline panel for live progress.`);
      notify.info('Agent started', `Researching: ${topic}`);
    } else {
      setRunning(false);
      setRunStatus('idle');
      let parsed: { detail?: AgentError | string } | null = null;
      try { parsed = await res.json(); } catch { /* ignore */ }
      const detail = parsed?.detail;
      if (detail && typeof detail === 'object' && 'error_type' in detail) {
        setAgentError(detail as AgentError);
        onMessage(`Research failed: ${(detail as AgentError).message}`);
      } else {
        const msg = typeof detail === 'string' ? detail : `HTTP ${res.status}`;
        onMessage(`❌ Failed to start run: ${msg}`);
        notify.error('Failed to start', msg);
      }
    }
  }, [researchModel, contentModel, onMessage, onComplete]);

  const clearError = useCallback(() => setAgentError(null), []);

  return { runId, runStatus, currentStage, running, researchModel, setResearchModel, contentModel, setContentModel, agentError, clearError, startRun, stepStatuses };
}
