import { NextRequest, NextResponse } from 'next/server';

const MCP_URL = process.env.MCP_SERVER_URL || 'http://mcp-server:8000';
const CREW_URL = process.env.CREW_RUNNER_URL || 'http://crew-runner:8001';
const RENDERER_URL = process.env.RENDERER_URL || 'http://renderer:3001';

function getApiKey(request: NextRequest): string | null {
  const cookie = request.cookies.get('ofb_session');
  if (!cookie) return null;
  try {
    return Buffer.from(cookie.value, 'base64').toString('utf-8');
  } catch {
    return null;
  }
}

function getTargetUrl(path: string[]): string {
  const joined = path.join('/');
  if (joined.startsWith('agent/') || joined === 'agent') {
    return `${CREW_URL}/${joined}`;
  }
  if (joined.startsWith('analytics/') || joined === 'analytics') {
    return `${CREW_URL}/${joined}`;
  }
  if (joined.startsWith('runs/') || joined === 'runs') {
    return `${CREW_URL}/${joined}`;
  }
  if (joined === 'render' || joined.startsWith('render/')) {
    return `${RENDERER_URL}/${joined}`;
  }
  return `${MCP_URL}/${joined}`;
}

async function proxyRequest(request: NextRequest, path: string[]) {
  const apiKey = getApiKey(request);
  if (!apiKey) {
    return NextResponse.json({ error: 'Not authenticated' }, { status: 401 });
  }

  const targetUrl = getTargetUrl(path);
  const url = new URL(targetUrl);
  const searchParams = request.nextUrl.searchParams;
  searchParams.forEach((v, k) => url.searchParams.set(k, v));

  const headers: Record<string, string> = {
    'X-API-Key': apiKey,
    'Content-Type': 'application/json',
  };

  let body: string | undefined;
  if (request.method !== 'GET' && request.method !== 'HEAD') {
    try {
      body = JSON.stringify(await request.json());
    } catch {
      body = undefined;
    }
  }

  const upstream = await fetch(url.toString(), {
    method: request.method,
    headers,
    body,
  });

  const contentType = upstream.headers.get('Content-Type') || 'application/json';

  // Pass binary responses through without UTF-8 corruption
  let responseBody: BodyInit;
  if (contentType.startsWith('image/') || contentType === 'application/octet-stream') {
    responseBody = await upstream.arrayBuffer();
  } else {
    responseBody = await upstream.text();
  }

  return new NextResponse(responseBody, {
    status: upstream.status,
    headers: { 'Content-Type': contentType },
  });
}

export async function GET(request: NextRequest, { params }: { params: { path: string[] } }) {
  return proxyRequest(request, params.path);
}

export async function POST(request: NextRequest, { params }: { params: { path: string[] } }) {
  return proxyRequest(request, params.path);
}

export async function PUT(request: NextRequest, { params }: { params: { path: string[] } }) {
  return proxyRequest(request, params.path);
}

export async function DELETE(request: NextRequest, { params }: { params: { path: string[] } }) {
  return proxyRequest(request, params.path);
}
