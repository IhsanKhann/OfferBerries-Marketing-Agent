import { NextRequest, NextResponse } from 'next/server';

const MCP_URL = process.env.MCP_SERVER_URL || 'http://mcp-server:8000';

export async function POST(request: NextRequest) {
  const demoKey = request.headers.get('X-Demo-Key');
  if (!demoKey) {
    return NextResponse.json({ error: 'Missing demo key' }, { status: 401 });
  }

  const { content, template_id = 'linkedin-single' } = await request.json();

  const res = await fetch(`${MCP_URL}/mcp`, {
    method: 'POST',
    headers: { 'X-API-Key': demoKey, 'Content-Type': 'application/json' },
    body: JSON.stringify({
      method: 'tools/call',
      params: {
        name: 'generate_visual',
        arguments: { content, template_id, source: 'template' },
      },
    }),
  });

  if (!res.ok) {
    return NextResponse.json({ error: 'Visual generation failed' }, { status: 500 });
  }

  const data = await res.json();
  const asset = data.result || {};
  // Return preview_url matching what the demo page expects
  return NextResponse.json({ ...asset, preview_url: asset.url });
}
