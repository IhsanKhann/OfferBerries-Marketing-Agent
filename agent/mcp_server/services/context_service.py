"""Project context service — embed, store, and retrieve context chunks."""
import logging
import math
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

logger = logging.getLogger("mcp_server.context_service")

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_API_URL = "https://api.openai.com/v1/embeddings"
CHUNK_COLLECTION = "project_context_chunks"


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two vectors. Returns 0 for empty inputs."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(x * x for x in b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


async def embed_text(text: str, api_key: str) -> list[float]:
    """Call OpenAI embeddings API. Returns [] on any failure or missing key."""
    if not api_key:
        return []
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                EMBEDDING_API_URL,
                headers={"Authorization": f"Bearer {api_key}"},
                json={"input": text, "model": EMBEDDING_MODEL},
            )
            resp.raise_for_status()
            data = resp.json()
            return data["data"][0]["embedding"]
    except Exception as exc:
        logger.warning("embed_text failed: %s", exc)
        return []


async def store_chunk(
    db: Any,
    tenant_id: str,
    project_id: str,
    text: str,
    chunk_type: str,
    embedding: list[float],
    metadata: Optional[dict] = None,
) -> str:
    """Insert a context chunk and return its chunk_id."""
    chunk_id = str(uuid.uuid4())
    doc = {
        "chunk_id": chunk_id,
        "tenant_id": tenant_id,
        "project_id": project_id,
        "text": text,
        "chunk_type": chunk_type,
        "embedding": embedding,
        "metadata": metadata or {},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db[CHUNK_COLLECTION].insert_one(doc)
    return chunk_id


async def retrieve_relevant_context(
    db: Any,
    tenant_id: str,
    project_id: str,
    query_text: str,
    api_key: str,
    k: int = 5,
) -> list[str]:
    """Return top-k most relevant chunk texts using cosine similarity."""
    query_embedding = await embed_text(query_text, api_key)
    if not query_embedding:
        return []

    cursor = db[CHUNK_COLLECTION].find({"tenant_id": tenant_id, "project_id": project_id})
    chunks = await cursor.to_list(length=500)
    if not chunks:
        return []

    scored = []
    for chunk in chunks:
        emb = chunk.get("embedding", [])
        score = cosine_similarity(query_embedding, emb) if emb else 0.0
        scored.append((score, chunk["text"]))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [text for _, text in scored[:k]]


async def store_run_context(
    db: Any,
    run: dict,
    research_brief: dict,
    posts: list[dict],
    api_key: str,
) -> None:
    """Store research + post chunks for a completed run. No-op if no project_id."""
    project_id = run.get("project_id")
    if not project_id:
        return

    tenant_id = run.get("tenant_id", "")
    run_id = run.get("id", "")
    topic = run.get("topic", "")

    # Store research brief as a chunk
    if research_brief:
        angles = research_brief.get("trending_angles", [])
        pain_points = research_brief.get("pain_points", [])
        brief_text = (
            f"Topic: {topic}\n"
            f"Trending angles: {', '.join(angles)}\n"
            f"Pain points: {', '.join(pain_points)}"
        ).strip()
        if brief_text:
            emb = await embed_text(brief_text, api_key)
            await store_chunk(
                db=db,
                tenant_id=tenant_id,
                project_id=project_id,
                text=brief_text,
                chunk_type="research",
                embedding=emb,
                metadata={"run_id": run_id, "topic": topic},
            )

    # Store each post as a chunk
    for post in posts:
        copy = post.get("copy", "")
        if not copy:
            continue
        platform = post.get("platform", "")
        emb = await embed_text(copy, api_key)
        await store_chunk(
            db=db,
            tenant_id=tenant_id,
            project_id=project_id,
            text=copy,
            chunk_type="post",
            embedding=emb,
            metadata={"run_id": run_id, "platform": platform},
        )
