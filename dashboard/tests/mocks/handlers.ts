import { http, HttpResponse } from 'msw';

export const handlers = [
  http.get('/api/proxy/runs/:runId', ({ params }) => {
    return HttpResponse.json({
      run_id: params.runId,
      overall_status: 'running',
      current_stage: 'research',
    });
  }),

  http.post('/api/proxy/runs', () => {
    return HttpResponse.json({ run_id: 'test-run-abc123' }, { status: 201 });
  }),

  http.put('/api/proxy/config/research-model', () => HttpResponse.json({ ok: true })),
  http.put('/api/proxy/config/content-model', () => HttpResponse.json({ ok: true })),

  http.get('/api/proxy/posts', () => {
    return HttpResponse.json({ posts: [] });
  }),

  http.post('/api/proxy/runs/:runId/stages/:stage/approve', () => {
    return HttpResponse.json({ ok: true });
  }),

  http.post('/api/proxy/runs/:runId/stages/:stage/reject', () => {
    return HttpResponse.json({ ok: true });
  }),

  // fire-and-forget analytics events
  http.post('/api/proxy/events', () => HttpResponse.json({ ok: true })),
];
