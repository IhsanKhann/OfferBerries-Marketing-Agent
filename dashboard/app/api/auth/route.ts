import { NextRequest, NextResponse } from 'next/server';

const MCP_URL = process.env.MCP_SERVER_URL || 'http://mcp-server:8000';

export async function POST(request: NextRequest) {
  const { api_key } = await request.json();
  if (!api_key) {
    return NextResponse.json({ error: 'api_key required' }, { status: 400 });
  }

  // Validate against MCP server
  const mcpRes = await fetch(`${MCP_URL}/mcp`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-API-Key': api_key },
    body: JSON.stringify({ method: 'tools/list' }),
  });

  if (!mcpRes.ok) {
    return NextResponse.json({ authenticated: false, error: 'Invalid API key' }, { status: 401 });
  }

  const response = NextResponse.json({ authenticated: true });

  // Store API key in HttpOnly cookie (server-side session)
  response.cookies.set('ofb_session', Buffer.from(api_key).toString('base64'), {
    httpOnly: true,
    secure: process.env.NODE_ENV === 'production',
    sameSite: 'lax',
    maxAge: 60 * 60 * 8, // 8 hours
    path: '/',
  });

  return response;
}

export async function DELETE() {
  const response = NextResponse.json({ authenticated: false });
  response.cookies.delete('ofb_session');
  return response;
}
