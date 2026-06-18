import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import { useAgentRun, RESEARCH_MODELS, CONTENT_MODELS, STEPS } from '../../../hooks/useAgentRun';

describe('useAgentRun — initial state', () => {
  it('starts idle with no run', () => {
    const { result } = renderHook(() =>
      useAgentRun(vi.fn(), vi.fn())
    );
    expect(result.current.runId).toBeNull();
    expect(result.current.runStatus).toBe('idle');
    expect(result.current.running).toBe(false);
  });

  it('defaults to sonar research model', () => {
    const { result } = renderHook(() => useAgentRun(vi.fn(), vi.fn()));
    expect(result.current.researchModel).toBe('sonar');
  });

  it('defaults to claude-sonnet-4-6 content model', () => {
    const { result } = renderHook(() => useAgentRun(vi.fn(), vi.fn()));
    expect(result.current.contentModel).toBe('anthropic/claude-sonnet-4-6');
  });

  it('has 4 steps matching backend STAGE_ORDER', () => {
    expect(STEPS).toHaveLength(4);
    expect(STEPS[0].label).toBe('Research');
    expect(STEPS[1].label).toBe('Content Generation');
    expect(STEPS[2].label).toBe('Visual Generation');
    expect(STEPS[3].label).toBe('Scheduling');
  });

  it('all step statuses are pending when idle', () => {
    const { result } = renderHook(() => useAgentRun(vi.fn(), vi.fn()));
    expect(result.current.stepStatuses).toHaveLength(4);
    result.current.stepStatuses.forEach(s => expect(s).toBe('pending'));
  });
});

describe('useAgentRun — model selection', () => {
  it('exposes RESEARCH_MODELS with 3 options', () => {
    expect(RESEARCH_MODELS).toHaveLength(3);
    const ids = RESEARCH_MODELS.map(m => m.id);
    expect(ids).toContain('sonar');
    expect(ids).toContain('sonar-pro');
    expect(ids).toContain('sonar-deep-research');
  });

  it('exposes CONTENT_MODELS with 3 options', () => {
    expect(CONTENT_MODELS).toHaveLength(3);
    const ids = CONTENT_MODELS.map(m => m.id);
    expect(ids).toContain('anthropic/claude-sonnet-4-6');
    expect(ids).toContain('anthropic/claude-haiku-4-5');
    expect(ids).toContain('google/gemini-2.5-flash');
  });

  it('setResearchModel updates researchModel', () => {
    const { result } = renderHook(() => useAgentRun(vi.fn(), vi.fn()));
    act(() => result.current.setResearchModel('sonar-pro'));
    expect(result.current.researchModel).toBe('sonar-pro');
  });

  it('setContentModel updates contentModel', () => {
    const { result } = renderHook(() => useAgentRun(vi.fn(), vi.fn()));
    act(() => result.current.setContentModel('google/gemini-2.5-flash'));
    expect(result.current.contentModel).toBe('google/gemini-2.5-flash');
  });
});

describe('useAgentRun — startRun', () => {
  beforeEach(() => vi.clearAllMocks());

  it('transitions to pending after successful run creation', async () => {
    const onComplete = vi.fn();
    const onMessage = vi.fn();
    const { result } = renderHook(() => useAgentRun(onComplete, onMessage));

    await act(async () => {
      await result.current.startRun('payroll software', ['linkedin']);
    });

    expect(result.current.runId).toBe('test-run-abc123');
    expect(result.current.runStatus).toBe('pending');
    expect(result.current.running).toBe(true);
  });

  it('calls onMessage with run_id after successful start', async () => {
    const onMessage = vi.fn();
    const { result } = renderHook(() => useAgentRun(vi.fn(), onMessage));

    await act(async () => {
      await result.current.startRun('payroll software', ['linkedin']);
    });

    // run_id "test-run-abc123" sliced to 8 chars = "test-run"
    expect(onMessage).toHaveBeenCalledWith(
      expect.stringContaining('test-run')
    );
  });

  it('reverts to idle on HTTP error', async () => {
    const { server } = await import('../../mocks/server');
    const { http, HttpResponse } = await import('msw');
    server.use(
      http.post('/api/proxy/runs', () => HttpResponse.json({ detail: 'Quota exceeded' }, { status: 429 }))
    );

    const onMessage = vi.fn();
    const { result } = renderHook(() => useAgentRun(vi.fn(), onMessage));

    await act(async () => {
      await result.current.startRun('payroll software', ['linkedin']);
    });

    expect(result.current.runStatus).toBe('idle');
    expect(result.current.running).toBe(false);
    expect(onMessage).toHaveBeenCalledWith(expect.stringContaining('Failed'));
  });

  it('clears agentError on new startRun', async () => {
    const { result } = renderHook(() => useAgentRun(vi.fn(), vi.fn()));
    // First call that fails
    const { server } = await import('../../mocks/server');
    const { http, HttpResponse } = await import('msw');
    server.use(
      http.post('/api/proxy/runs', () => HttpResponse.json({ detail: 'err' }, { status: 500 }), { once: true })
    );
    await act(async () => { await result.current.startRun('topic', ['linkedin']); });

    // Second call succeeds — agentError should be cleared
    await act(async () => { await result.current.startRun('topic', ['linkedin']); });
    expect(result.current.agentError).toBeNull();
  });
});

describe('useAgentRun — clearError', () => {
  it('clearError sets agentError to null', () => {
    const { result } = renderHook(() => useAgentRun(vi.fn(), vi.fn()));
    act(() => result.current.clearError());
    expect(result.current.agentError).toBeNull();
  });
});
