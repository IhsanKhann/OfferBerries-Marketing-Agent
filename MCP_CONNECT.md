# OfferBerries Marketing Agent — MCP Connection Guide

The MCP server runs on port 8000 alongside the REST API.
Both transports share the same process:

| Path | Purpose |
|------|---------|
| `GET  /sse` | MCP SSE stream (clients connect here) |
| `POST /messages/` | MCP message channel |
| `GET  /health` | Health check (includes tool list) |
| `POST /mcp` | Legacy JSON-RPC endpoint (crew-runner) |

---

## Local (Docker Compose)

Start the stack:
```bash
docker compose up -d
```

Verify:
```bash
curl http://localhost:8000/health
# → {"status":"ok","server":"offerberries-marketing-mcp","tools":[...]}

curl -I http://localhost:8000/sse
# → HTTP/1.1 200 OK  Content-Type: text/event-stream
```

Test with MCP Inspector:
```bash
npx @modelcontextprotocol/inspector http://localhost:8000/sse
# Opens http://localhost:5173 — all 8 tools should appear
```

---

## Claude Code CLI

Edit (or create) `~/.claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "offerberries": {
      "type": "sse",
      "url": "http://localhost:8000/sse"
    }
  }
}
```

Verify in a new session:
```bash
claude mcp list
# offerberries   http://localhost:8000/sse   connected
```

---

## Claude Desktop App

Config file location:
- **Mac / Linux**: `~/.claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

Add the same block as above, then restart Claude Desktop.

---

## Claude.ai Browser (remote)

1. Open Claude.ai → Settings → Integrations
2. Click **Add custom integration**
3. Fill in:
   - **Name**: OfferBerries Marketing Agent
   - **URL**: `https://agent.offerberriesvo.com/sse`
4. Click Connect

> The `/sse` and `/messages/*` routes are proxied directly through Caddy
> to mcp-server:8000, bypassing the Next.js app (which cannot stream SSE).

---

## Cursor IDE

Cursor Settings → Features → MCP → Add new MCP server

| Field | Value |
|-------|-------|
| Name  | offerberries |
| Type  | sse |
| URL   | `http://localhost:8000/sse` |

---

## Continue.dev (VS Code)

Add to `~/.continue/config.json`:

```json
{
  "mcpServers": [
    {
      "name": "offerberries",
      "transport": {
        "type": "sse",
        "url": "http://localhost:8000/sse"
      }
    }
  ]
}
```

---

## Production (remote access)

The Caddyfile already routes:
- `https://agent.offerberriesvo.com/sse` → `mcp-server:8000/sse`
- `https://agent.offerberriesvo.com/messages/*` → `mcp-server:8000/messages/*`

Use these URLs in any client's MCP config to connect remotely.

Verify:
```bash
curl https://agent.offerberriesvo.com/health
npx @modelcontextprotocol/inspector https://agent.offerberriesvo.com/sse
```

---

## Available Tools

| Tool | Description |
|------|-------------|
| `research_trends` | Research trending topics via Perplexity AI |
| `scrape_competitor` | Scrape competitor posts via Apify |
| `generate_content` | Generate on-brand post copy via OpenRouter |
| `generate_visual_brief` | Create visual art direction brief via LLM |
| `generate_visual` | Render assets (template / OpenDesign / fal.ai) |
| `queue_post` | Save post to queue + schedule in Postiz |
| `get_run_status` | Check pipeline run status from MongoDB |
| `list_projects` | List tenant projects from MongoDB |

### Recommended workflow

```
research_trends(topic) 
  → generate_content(brief, platform)
  → generate_visual_brief(brief, content, platform)   # optional
  → generate_visual(content, template_id)             # optional
  → queue_post(platform, caption, scheduled_at)
```
