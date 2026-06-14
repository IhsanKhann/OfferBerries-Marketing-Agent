import { NextRequest, NextResponse } from 'next/server';

const MCP_URL = process.env.MCP_SERVER_URL || 'http://mcp-server:8000';

export async function POST(request: NextRequest) {
  const demoKey = request.headers.get('X-Demo-Key');
  if (!demoKey) {
    return NextResponse.json({ error: 'Missing demo key' }, { status: 401 });
  }

  const { brief, platform = 'linkedin' } = await request.json();

  const res = await fetch(`${MCP_URL}/mcp`, {
    method: 'POST',
    headers: { 'X-API-Key': demoKey, 'Content-Type': 'application/json' },
    body: JSON.stringify({
      method: 'tools/call',
      params: { name: 'generate_content', arguments: { brief, platform } },
    }),
  });

  if (!res.ok) {
    return NextResponse.json({ error: 'Content generation failed' }, { status: 500 });
  }

  const data = await res.json();
  return NextResponse.json(data.result || {});
}
