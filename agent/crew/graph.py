"""LangGraph state machine for the OfferBerries marketing agent."""
import json
import logging
import os
from typing import Optional, TypedDict

import httpx
from langgraph.graph import END, START, StateGraph

logger = logging.getLogger("crew.graph")

MCP_URL = os.getenv("MCP_SERVER_URL", "http://mcp-server:8000")
OWNER_KEY = os.getenv("OWNER_API_KEY", "")


class AgentState(TypedDict):
    topic: str
    platform_filter: list[str]
    brief: Optional[dict]
    competitor_data: list[dict]
    platform_content: dict[str, dict]
    visual_assets: dict[str, dict]
    queued_posts: list[dict]
    errors: list[str]
    run_id: str
    dry_run: bool


async def _call_tool(tool_name: str, arguments: dict, api_key: str = None, run_id: str = "") -> dict:
    key = api_key or OWNER_KEY
    # Inject run_id so the MCP server can attribute cost to the right run
    args_with_meta = {**arguments, "__run_id": run_id} if run_id else arguments
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            f"{MCP_URL}/mcp",
            headers={"X-API-Key": key, "Content-Type": "application/json"},
            json={"method": "tools/call", "params": {"name": tool_name, "arguments": args_with_meta}},
        )
        if resp.status_code == 200:
            return resp.json().get("result", {})
        logger.error(f"Tool {tool_name} returned {resp.status_code}: {resp.text[:200]}")
        return {}


async def research_node(state: AgentState) -> AgentState:
    logger.info(f"[{state['run_id']}] Research node starting for topic: {state['topic']}")

    try:
        brief = await _call_tool("research_trends", {"topic": state["topic"], "platform": "all"}, run_id=state["run_id"])
        state["brief"] = brief
    except Exception as e:
        state["errors"].append(f"research_trends error: {e}")
        logger.error(f"[{state['run_id']}] Research failed — cannot proceed without real data: {e}")

    # Scrape competitors for top platforms
    if len(state["errors"]) <= 2:
        strategy_path = "/app/config/content_strategy.json"
        try:
            with open(strategy_path) as f:
                strategy = json.load(f)
            watchlist = strategy.get("competitor_watchlist", [])
        except Exception:
            watchlist = []

        competitor_posts = []
        for handle in watchlist[:2]:
            for platform in state["platform_filter"][:2]:
                try:
                    posts = await _call_tool("scrape_competitor", {"platform": platform, "handle": handle, "limit": 10}, run_id=state["run_id"])
                    if isinstance(posts, list):
                        competitor_posts.extend(posts)
                except Exception as e:
                    state["errors"].append(f"scrape {handle}/{platform}: {e}")

        state["competitor_data"] = competitor_posts
        if competitor_posts and state.get("brief"):
            state["brief"]["platform_notes"] = state["brief"].get("platform_notes", {})
            state["brief"]["platform_notes"]["competitor_insights"] = f"Analysed {len(competitor_posts)} competitor posts"

    logger.info(f"[{state['run_id']}] Research complete: {len(state.get('brief', {}).get('trending_angles', []))} angles")
    return state


async def content_node(state: AgentState) -> AgentState:
    logger.info(f"[{state['run_id']}] Content node starting")
    if len(state["errors"]) > 3:
        logger.warning(f"[{state['run_id']}] Too many errors, skipping content node")
        return state

    brief = state.get("brief", {})
    platform_content = {}

    for platform in state["platform_filter"]:
        run_id = state["run_id"]
        try:
            content = await _call_tool("generate_content", {"brief": brief, "platform": platform}, run_id=run_id)
            if content:
                platform_content[platform] = content

            # For LinkedIn, also generate carousel outline (4 slides)
            if platform == "linkedin":
                carousel_slides = []
                for slide_num in range(1, 5):
                    slide_brief = dict(brief)
                    slide_brief["topic"] = f"Slide {slide_num}: {brief.get('topic', '')}"
                    try:
                        slide_content = await _call_tool(
                            "generate_content",
                            {"brief": slide_brief, "platform": "linkedin"},
                            run_id=run_id,
                        )
                        if slide_content:
                            slide_content["slide_number"] = slide_num
                            carousel_slides.append(slide_content)
                    except Exception as e:
                        state["errors"].append(f"carousel slide {slide_num}: {e}")
                if carousel_slides:
                    platform_content["linkedin_carousel"] = carousel_slides

        except Exception as e:
            state["errors"].append(f"generate_content/{platform}: {e}")

    state["platform_content"] = platform_content
    logger.info(f"[{state['run_id']}] Content generated for: {list(platform_content.keys())}")
    return state


async def visual_node(state: AgentState) -> AgentState:
    logger.info(f"[{state['run_id']}] Visual node starting")
    if len(state["errors"]) > 3:
        return state

    template_map = {
        "linkedin": "linkedin-single",
        "twitter": "twitter-stat-card",
        "instagram": "instagram-quote",
        "youtube": "youtube-thumbnail",
        "email": "email-header",
    }

    visual_assets = {}
    brief = state.get("brief") or {}
    for platform, content in state["platform_content"].items():
        if platform == "linkedin_carousel":
            continue
        if not isinstance(content, dict):
            continue
        template_id = template_map.get(platform, "announcement-card")
        source = "open_design" if platform == "instagram" else "template"
        run_id = state["run_id"]

        # D1: Generate visual brief to give the renderer richer context
        visual_brief = None
        try:
            visual_brief = await _call_tool("generate_visual_brief", {
                "brief": brief,
                "content": content,
                "platform": platform,
                "brand_context": {},
            }, run_id=run_id)
        except Exception as e:
            logger.warning(f"[{run_id}] Visual brief skipped for {platform}: {e}")

        try:
            asset = await _call_tool("generate_visual", {
                "content": content,
                "template_id": template_id,
                "source": source,
                "visual_brief": visual_brief,
            }, run_id=run_id)
            if asset:
                visual_assets[platform] = asset
        except Exception as e:
            state["errors"].append(f"generate_visual/{platform}: {e}")
            # Fallback to template source without visual brief
            try:
                asset = await _call_tool("generate_visual", {
                    "content": content,
                    "template_id": template_id,
                    "source": "template",
                }, run_id=run_id)
                if asset:
                    visual_assets[platform] = asset
            except Exception:
                pass

    state["visual_assets"] = visual_assets
    logger.info(f"[{state['run_id']}] Visuals generated for: {list(visual_assets.keys())}")
    return state


async def queue_node(state: AgentState) -> AgentState:
    logger.info(f"[{state['run_id']}] Queue node starting (dry_run={state.get('dry_run', False)})")
    if len(state["errors"]) > 3 or state.get("dry_run", False):
        logger.info(f"[{state['run_id']}] Queue node skipped (dry_run or too many errors)")
        return state

    strategy_path = "/app/config/content_strategy.json"
    try:
        with open(strategy_path) as f:
            strategy = json.load(f)
        schedule = strategy.get("posting_schedule", {})
    except Exception:
        schedule = {}

    from datetime import datetime, timezone, timedelta

    def _next_slot(platform: str) -> str:
        slots = schedule.get(platform, [])
        if not slots:
            return (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
        day_map = {"Monday": 0, "Tuesday": 1, "Wednesday": 2, "Thursday": 3, "Friday": 4, "Saturday": 5, "Sunday": 6}
        now = datetime.now(timezone.utc)
        for slot in slots:
            parts = slot.split()
            if len(parts) >= 2:
                day_name, time_str = parts[0], parts[1]
                hour, minute = map(int, time_str.split(":"))
                target_weekday = day_map.get(day_name, 0)
                days_ahead = (target_weekday - now.weekday()) % 7
                if days_ahead == 0 and (hour < now.hour or (hour == now.hour and minute <= now.minute)):
                    days_ahead = 7
                target = now.replace(hour=hour, minute=minute, second=0, microsecond=0) + timedelta(days=days_ahead)
                return target.isoformat()
        return (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()

    queued = []
    run_id = state["run_id"]
    for platform, content in state["platform_content"].items():
        if platform == "linkedin_carousel":
            continue
        visual = state["visual_assets"].get(platform)
        if not visual or not content:
            continue
        try:
            scheduled_at = _next_slot(platform)
            result = await _call_tool("queue_post", {
                "platform": platform,
                "caption": content.get("copy", ""),
                "image_path": visual.get("path", ""),
                "preview_url": visual.get("url", ""),
                "scheduled_at": scheduled_at,
            }, run_id=run_id)
            if result:
                queued.append(result)
        except Exception as e:
            state["errors"].append(f"queue_post/{platform}: {e}")

    state["queued_posts"] = queued
    logger.info(f"[{state['run_id']}] Queued {len(queued)} posts")
    return state


def _should_continue(state: AgentState) -> str:
    if len(state.get("errors", [])) > 3:
        logger.warning(f"Too many errors ({len(state['errors'])}), skipping to END")
        return END
    return "continue"


def build_graph() -> StateGraph:
    graph = StateGraph(AgentState)

    graph.add_node("research_node", research_node)
    graph.add_node("content_node", content_node)
    graph.add_node("visual_node", visual_node)
    graph.add_node("queue_node", queue_node)

    graph.add_edge(START, "research_node")
    graph.add_conditional_edges("research_node", _should_continue, {"continue": "content_node", END: END})
    graph.add_conditional_edges("content_node", _should_continue, {"continue": "visual_node", END: END})
    graph.add_conditional_edges("visual_node", _should_continue, {"continue": "queue_node", END: END})
    graph.add_edge("queue_node", END)

    return graph.compile()
