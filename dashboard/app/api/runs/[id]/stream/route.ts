import { NextRequest } from 'next/server';

const CREW_URL = process.env.CREW_RUNNER_URL || 'http://crew-runner:8001';

function getApiKey(request: NextRequest): string | null {
  const cookie = request.cookies.get('ofb_session');
  if (!cookie) return null;
  try {
    return Buffer.from(cookie.value, 'base64').toString('utf-8');
  } catch {
    return null;
  }
}

export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  const apiKey = getApiKey(request);
  if (!apiKey) {
    return new Response('Unauthorized', { status: 401 });
  }

  const upstream = await fetch(`${CREW_URL}/runs/${params.id}/stream`, {
    headers: { 'X-API-Key': apiKey },
    // Pass abort signal so the upstream connection closes when the client disconnects
    signal: request.signal,
  });

  if (!upstream.ok || !upstream.body) {
    return new Response('Stream unavailable', { status: upstream.status });
  }

  return new Response(upstream.body, {
    status: 200,
    headers: {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      'X-Accel-Buffering': 'no',
    },
  });
}
