import { NextResponse } from 'next/server';

const MCP_URL = process.env.MCP_SERVER_URL || 'http://mcp-server:8000';
const OWNER_KEY = process.env.OWNER_API_KEY || '';

export async function POST() {
  if (!OWNER_KEY) {
    return NextResponse.json({ error: 'Server not configured' }, { status: 500 });
  }

  const res = await fetch(`${MCP_URL}/admin/tenants/demo`, {
    method: 'POST',
    headers: { 'X-API-Key': OWNER_KEY, 'Content-Type': 'application/json' },
    body: '{}',
  });

  if (!res.ok) {
    return NextResponse.json({ error: 'Failed to create demo session' }, { status: 500 });
  }

  return NextResponse.json(await res.json());
}
