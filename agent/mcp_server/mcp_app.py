"""
MCP SSE transport layer for the OfferBerries Marketing Agent.

This module imports the existing FastAPI REST app from main.py (which retains
all queue, config, admin, and project endpoints) and ADDS the MCP SSE transport
routes (/sse  and /messages/) on top of it — all on the same port.

Entry point: uvicorn mcp_app:app --host 0.0.0.0 --port 8000

Tools exposed via MCP:
  research_trends, scrape_competitor, generate_content, generate_visual_brief,
  generate_visual, queue_post, get_run_status, list_projects
"""
import json
import logging

# Import main FIRST so sys.modules['main'] is populated before any tool
# function runs.  Every tool does `import main as _m` to reach db,
# redis_client, log_tool_call, and _seed_voice_profiles_for_tenant.
import main as _m  # noqa: F401 — side-effect import

from main import app  # existing FastAPI app (all REST routes intact)

from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import TextContent, Tool
from starlette.requests import Request

logger = logging.getLogger("mcp_server")

# ── MCP server instance ────────────────────────────────────────────────────────

_server = Server("offerberries-marketing")
_sse = SseServerTransport("/messages/")

# ── Tool definitions ───────────────────────────────────────────────────────────

_TOOLS = [
    Tool(
        name="research_trends",
        description=(
            "Research trending topics, pain points, and angles for a subject "
            "on social media using Perplexity AI."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "Subject to research"},
                "platform": {
                    "type": "string",
                    "default": "all",
                    "description": "Platform filter: all | linkedin | twitter | instagram",
                },
                "model": {
                    "type": "string",
                    "default": "sonar",
                    "description": "Perplexity model: sonar | sonar-pro | sonar-reasoning",
                },
                "tenant_id": {"type": "string", "default": ""},
                "run_id": {"type": "string", "default": ""},
            },
            "required": ["topic"],
        },
    ),
    Tool(
        name="scrape_competitor",
        description="Scrape recent posts from a competitor's social media profile via Apify.",
        inputSchema={
            "type": "object",
            "properties": {
                "platform": {
                    "type": "string",
                    "description": "Platform: linkedin | twitter | instagram",
                },
                "handle": {"type": "string", "description": "Username / handle to scrape"},
                "limit": {
                    "type": "integer",
                    "default": 20,
                    "description": "Max posts to return",
                },
            },
            "required": ["platform", "handle"],
        },
    ),
    Tool(
        name="generate_content",
        description=(
            "Generate premium on-brand OfferBerries social media post copy "
            "using a research brief from research_trends."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "brief": {
                    "type": "object",
                    "description": "ResearchBrief dict returned by research_trends",
                    "properties": {
                        "topic": {"type": "string"},
                        "trending_angles": {"type": "array", "items": {"type": "string"}},
                        "pain_points": {"type": "array", "items": {"type": "string"}},
                        "suggested_hooks": {"type": "array", "items": {"type": "string"}},
                        "platform_notes": {"type": "object"},
                    },
                    "required": ["topic"],
                },
                "platform": {
                    "type": "string",
                    "description": "Target platform: linkedin | twitter | instagram | youtube | email",
                },
                "product": {
                    "type": "string",
                    "default": "full_erp",
                    "description": "OfferBerries product feature to highlight",
                },
                "model": {
                    "type": "string",
                    "default": "anthropic/claude-sonnet-4-6",
                    "description": "LLM model for generation (OpenRouter model ID)",
                },
                "tenant_id": {"type": "string", "default": ""},
                "run_id": {"type": "string", "default": ""},
            },
            "required": ["brief", "platform"],
        },
    ),
    Tool(
        name="generate_visual_brief",
        description="Create an LLM-driven visual art direction brief for a social media post.",
        inputSchema={
            "type": "object",
            "properties": {
                "brief": {
                    "type": "object",
                    "description": "Research brief dict from research_trends",
                },
                "content": {
                    "type": "object",
                    "description": "PlatformContent dict from generate_content",
                },
                "platform": {"type": "string", "description": "Target platform"},
                "brand_context": {
                    "type": "object",
                    "default": {},
                    "description": "Optional brand name / primary_color overrides",
                },
                "tenant_id": {"type": "string", "default": ""},
                "run_id": {"type": "string", "default": ""},
            },
            "required": ["brief", "content", "platform"],
        },
    ),
    Tool(
        name="generate_visual",
        description=(
            "Render a visual asset for a post using the template renderer, "
            "OpenDesign, or fal.ai image generation."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "content": {
                    "type": "object",
                    "description": "PlatformContent dict from generate_content",
                },
                "template_id": {
                    "type": "string",
                    "default": "linkedin-single",
                    "description": "Template identifier",
                },
                "source": {
                    "type": "string",
                    "default": "template",
                    "description": "Render backend: template | open_design | fal",
                },
                "visual_brief": {
                    "type": "object",
                    "description": "Optional VisualBrief dict from generate_visual_brief",
                },
            },
            "required": ["content"],
        },
    ),
    Tool(
        name="queue_post",
        description=(
            "Save an approved post to the queue and optionally schedule it "
            "in Postiz for publishing."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "platform": {"type": "string"},
                "caption": {"type": "string"},
                "image_path": {"type": "string", "default": ""},
                "scheduled_at": {
                    "type": "string",
                    "description": "ISO 8601 datetime string (UTC)",
                },
                "tenant_id": {"type": "string", "default": ""},
                "run_id": {"type": "string", "default": ""},
                "preview_url": {"type": "string", "default": ""},
            },
            "required": ["platform", "caption", "scheduled_at"],
        },
    ),
    Tool(
        name="get_run_status",
        description="Check the status and results of a pipeline run by its run_id.",
        inputSchema={
            "type": "object",
            "properties": {
                "run_id": {"type": "string", "description": "Pipeline run ID to look up"},
            },
            "required": ["run_id"],
        },
    ),
    Tool(
        name="list_projects",
        description="List all active projects for a tenant.",
        inputSchema={
            "type": "object",
            "properties": {
                "tenant_id": {"type": "string", "default": ""},
            },
        },
    ),
]


@_server.list_tools()
async def list_tools() -> list[Tool]:
    return _TOOLS


@_server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        result = await _dispatch(name, arguments or {})
        return [TextContent(type="text", text=json.dumps(result, default=str))]
    except Exception as exc:
        logger.error("MCP tool %s failed: %s", name, exc)
        return [TextContent(type="text", text=json.dumps({"error": str(exc)}))]


async def _dispatch(name: str, args: dict) -> dict:
    if name == "research_trends":
        from tools.research import tool_research_trends
        return await tool_research_trends(
            topic=args["topic"],
            platform=args.get("platform", "all"),
            model=args.get("model", "sonar"),
            run_id=args.get("run_id", ""),
            tenant_id=args.get("tenant_id", ""),
        )

    if name == "scrape_competitor":
        from tools.research import tool_scrape_competitor
        return await tool_scrape_competitor(
            platform=args["platform"],
            handle=args["handle"],
            limit=args.get("limit", 20),
        )

    if name == "generate_content":
        from tools.content import tool_generate_content
        from schemas import ResearchBrief
        brief = args["brief"]
        if isinstance(brief, dict):
            brief = ResearchBrief(**brief)
        return await tool_generate_content(
            brief=brief,
            platform=args["platform"],
            product=args.get("product", "full_erp"),
            model=args.get("model", "anthropic/claude-sonnet-4-6"),
            tenant_id=args.get("tenant_id", ""),
            run_id=args.get("run_id", ""),
        )

    if name == "generate_visual_brief":
        from tools.visual import tool_generate_visual_brief
        return await tool_generate_visual_brief(
            brief=args["brief"],
            content=args["content"],
            platform=args["platform"],
            brand_context=args.get("brand_context", {}),
            run_id=args.get("run_id", ""),
            tenant_id=args.get("tenant_id", ""),
        )

    if name == "generate_visual":
        from tools.visual import tool_generate_visual
        from schemas import PlatformContent
        content = args["content"]
        if isinstance(content, dict):
            content = PlatformContent(**content)
        return await tool_generate_visual(
            content=content,
            template_id=args.get("template_id", "linkedin-single"),
            source=args.get("source", "template"),
            visual_brief=args.get("visual_brief"),
        )

    if name == "queue_post":
        from tools.queue import tool_queue_post
        return await tool_queue_post(
            platform=args["platform"],
            caption=args["caption"],
            image_path=args.get("image_path", ""),
            scheduled_at=args["scheduled_at"],
            tenant_id=args.get("tenant_id", ""),
            run_id=args.get("run_id", ""),
            preview_url=args.get("preview_url", ""),
        )

    if name == "get_run_status":
        run = await _m.db["agent_runs"].find_one({"_id": args["run_id"]})
        if run:
            run.pop("_id", None)
        return run or {"error": "Run not found"}

    if name == "list_projects":
        projects = await _m.db["projects"].find(
            {"tenant_id": args.get("tenant_id", ""), "is_active": True},
            {"_id": 0},
        ).to_list(50)
        return {"projects": projects}

    raise ValueError(f"Unknown tool: {name}")


# ── SSE route handler ──────────────────────────────────────────────────────────
#
# FIX (was a 500/AttributeError on every /sse request):
#   `request.send` does not exist on starlette.requests.Request — only
#   `.scope` and `.receive` are public. The raw ASGI `send` callable is
#   stored internally as `request._send`. SseServerTransport.connect_sse()
#   needs the raw ASGI triple (scope, receive, send), so we pull the
#   underscore-prefixed attribute here. This is the standard workaround used
#   when wiring `mcp.server.sse.SseServerTransport` into a Starlette/FastAPI
#   route defined with the high-level `Request` signature instead of the
#   raw ASGI (scope, receive, send) signature.

async def _handle_sse(request: Request):
    async with _sse.connect_sse(
        request.scope, request.receive, request._send
    ) as streams:
        await _server.run(
            streams[0], streams[1], _server.create_initialization_options()
        )


# ── Mount SSE routes on the existing FastAPI app ───────────────────────────────
# The app variable IS main.app — all existing REST endpoints are preserved.
# Uvicorn's lifespan events still reach main.app, so startup() fires normally.

app.add_route("/sse", _handle_sse, methods=["GET"])
app.mount("/messages/", _sse.handle_post_message)