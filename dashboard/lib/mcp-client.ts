const MCP_URL = process.env.MCP_SERVER_URL || 'http://mcp-server:8000';
const CREW_URL = process.env.CREW_RUNNER_URL || 'http://crew-runner:8001';

export async function callMcpTool(toolName: string, args: Record<string, unknown>, apiKey: string) {
  const res = await fetch(`${MCP_URL}/mcp`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': apiKey,
    },
    body: JSON.stringify({
      method: 'tools/call',
      params: { name: toolName, arguments: args },
    }),
  });
  if (!res.ok) {
    throw new Error(`MCP tool call failed: ${res.status} ${await res.text()}`);
  }
  const data = await res.json();
  return data.result;
}

export async function startAgentRun(
  topic: string,
  platformFilter: string[],
  dryRun: boolean,
  apiKey: string,
) {
  const res = await fetch(`${CREW_URL}/agent/run`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': apiKey,
    },
    body: JSON.stringify({ topic, platform_filter: platformFilter, dry_run: dryRun }),
  });
  if (!res.ok) throw new Error(`Agent run failed: ${res.status}`);
  return res.json();
}

export async function getAgentStatus(runId: string, apiKey: string) {
  const res = await fetch(`${CREW_URL}/agent/status/${runId}`, {
    headers: { 'X-API-Key': apiKey },
  });
  if (!res.ok) throw new Error(`Status check failed: ${res.status}`);
  return res.json();
}

export async function getMcpHealth(apiKey: string) {
  const res = await fetch(`${MCP_URL}/health`, {
    headers: { 'X-API-Key': apiKey },
  });
  return res.json();
}
