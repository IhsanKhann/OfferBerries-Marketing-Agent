import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { server } from '../../mocks/server';
import { useProjects } from '../../../hooks/useProjects';

const MOCK_PROJECTS = [
  {
    id: 'proj-001',
    name: 'OfferBerries HR',
    description: 'HR payroll content',
    color: '#6366F1',
    icon: '📁',
    run_count: 3,
    created_at: '2026-06-01T00:00:00Z',
  },
  {
    id: 'proj-002',
    name: 'OfferBerries Payroll',
    description: 'Payroll automation content',
    color: '#10B981',
    icon: '💰',
    run_count: 1,
    created_at: '2026-06-10T00:00:00Z',
  },
];

beforeEach(() => {
  server.use(
    http.get('/api/proxy/projects', () => HttpResponse.json(MOCK_PROJECTS)),
    http.post('/api/proxy/projects', async ({ request }) => {
      const body = await request.json() as Record<string, unknown>;
      return HttpResponse.json(
        { ...body, id: 'proj-new', run_count: 0, created_at: new Date().toISOString() },
        { status: 201 }
      );
    }),
  );
});

describe('useProjects — initial state', () => {
  it('starts with empty projects and loading=true', () => {
    const { result } = renderHook(() => useProjects());
    expect(result.current.projects).toEqual([]);
    expect(result.current.loading).toBe(true);
  });

  it('fetches and populates projects on mount', async () => {
    const { result } = renderHook(() => useProjects());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.projects).toHaveLength(2);
    expect(result.current.projects[0].name).toBe('OfferBerries HR');
  });

  it('sets loading=false after fetch completes', async () => {
    const { result } = renderHook(() => useProjects());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.loading).toBe(false);
  });
});

describe('useProjects — error state', () => {
  it('sets error when fetch fails', async () => {
    server.use(
      http.get('/api/proxy/projects', () => HttpResponse.json({ detail: 'Unauthorized' }, { status: 401 }))
    );
    const { result } = renderHook(() => useProjects());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.error).toBeTruthy();
  });

  it('sets loading=false even on error', async () => {
    server.use(
      http.get('/api/proxy/projects', () => HttpResponse.error())
    );
    const { result } = renderHook(() => useProjects());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.loading).toBe(false);
  });
});

describe('useProjects — createProject', () => {
  it('optimistically adds project then confirms with server response', async () => {
    const { result } = renderHook(() => useProjects());
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.createProject({ name: 'New Campaign', default_platforms: ['linkedin'] });
    });

    expect(result.current.projects.some(p => p.id === 'proj-new')).toBe(true);
  });

  it('adds project to the list after creation', async () => {
    const { result } = renderHook(() => useProjects());
    await waitFor(() => expect(result.current.loading).toBe(false));
    const initialCount = result.current.projects.length;

    await act(async () => {
      await result.current.createProject({ name: 'Another Project' });
    });

    expect(result.current.projects.length).toBeGreaterThan(initialCount);
  });

  it('returns the created project from createProject', async () => {
    const { result } = renderHook(() => useProjects());
    await waitFor(() => expect(result.current.loading).toBe(false));

    let created: unknown;
    await act(async () => {
      created = await result.current.createProject({ name: 'Test Project' });
    });

    expect((created as { id: string }).id).toBe('proj-new');
  });

  it('rolls back optimistic update on server error', async () => {
    server.use(
      http.post('/api/proxy/projects', () =>
        HttpResponse.json({ detail: 'Server error' }, { status: 500 })
      )
    );

    const { result } = renderHook(() => useProjects());
    await waitFor(() => expect(result.current.loading).toBe(false));
    const initialCount = result.current.projects.length;

    await act(async () => {
      try {
        await result.current.createProject({ name: 'Bad Project' });
      } catch { /* expected */ }
    });

    await waitFor(() => expect(result.current.projects.length).toBe(initialCount));
  });
});

describe('useProjects — refetch', () => {
  it('refetch re-requests projects from server', async () => {
    const { result } = renderHook(() => useProjects());
    await waitFor(() => expect(result.current.loading).toBe(false));

    server.use(
      http.get('/api/proxy/projects', () =>
        HttpResponse.json([...MOCK_PROJECTS, { id: 'proj-003', name: 'New One', run_count: 0 }])
      )
    );

    await act(async () => { await result.current.refetch(); });

    expect(result.current.projects).toHaveLength(3);
  });
});
