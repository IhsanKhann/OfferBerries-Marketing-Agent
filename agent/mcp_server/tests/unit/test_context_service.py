"""C-CS: Unit tests for context_service — TDD Phase 2."""
import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ── FakeDB helpers ─────────────────────────────────────────────────────────────

class FakeCollection:
    def __init__(self):
        self._docs: list[dict] = []

    async def insert_one(self, doc):
        self._docs.append(dict(doc))

    async def find_one(self, query, projection=None):
        for doc in self._docs:
            if all(doc.get(k) == v for k, v in query.items()):
                return doc
        return None

    def find(self, query=None, projection=None):
        query = query or {}
        results = [d for d in self._docs if all(d.get(k) == v for k, v in query.items())]
        return FakeCursor(results)

    async def count_documents(self, query=None):
        query = query or {}
        return sum(1 for d in self._docs if all(d.get(k) == v for k, v in query.items()))


class FakeCursor:
    def __init__(self, docs):
        self._docs = docs

    async def to_list(self, length=None):
        return self._docs[:length] if length else self._docs


class FakeDB:
    def __init__(self):
        self._collections: dict[str, FakeCollection] = {}

    def __getitem__(self, name):
        if name not in self._collections:
            self._collections[name] = FakeCollection()
        return self._collections[name]


MOCK_EMBEDDING = [0.1, 0.2, 0.3, 0.4, 0.5] * 307  # 1535 dims + extra → 1537, but we'll use list


def make_embedding(seed: float = 0.1):
    """Make a unit-normalised fake embedding."""
    import math
    raw = [seed + i * 0.001 for i in range(512)]
    norm = math.sqrt(sum(x * x for x in raw))
    return [x / norm for x in raw]


# ── embed_text ─────────────────────────────────────────────────────────────────

class TestEmbedText:
    @pytest.mark.asyncio
    async def test_calls_openai_embedding_api(self):
        from services.context_service import embed_text
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "data": [{"embedding": make_embedding(0.1)}]
        }
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_resp)
            cls.return_value = mock_client

            result = await embed_text("payroll automation for SMBs", api_key="test-key")

        assert isinstance(result, list)
        assert len(result) == 512

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_api_key(self):
        from services.context_service import embed_text
        result = await embed_text("some text", api_key="")
        assert result == []

    @pytest.mark.asyncio
    async def test_returns_empty_list_on_api_error(self):
        from services.context_service import embed_text
        with patch("httpx.AsyncClient") as cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(side_effect=Exception("network error"))
            cls.return_value = mock_client

            result = await embed_text("text", api_key="key")
        assert result == []


# ── store_chunk ────────────────────────────────────────────────────────────────

class TestStoreChunk:
    @pytest.mark.asyncio
    async def test_stores_document_in_project_context_chunks(self):
        from services.context_service import store_chunk
        db = FakeDB()
        chunk_id = await store_chunk(
            db=db,
            tenant_id="t1",
            project_id="proj-123",
            text="OfferBerries is Pakistan's leading payroll platform.",
            chunk_type="brand_voice",
            embedding=[],
        )
        assert isinstance(chunk_id, str)
        assert len(chunk_id) > 0
        coll = db["project_context_chunks"]
        assert len(coll._docs) == 1

    @pytest.mark.asyncio
    async def test_stored_doc_has_required_fields(self):
        from services.context_service import store_chunk
        db = FakeDB()
        await store_chunk(
            db=db,
            tenant_id="t1",
            project_id="proj-123",
            text="Some brand voice text.",
            chunk_type="brand_voice",
            embedding=[0.1, 0.2],
            metadata={"source": "brand_voice.md"},
        )
        doc = db["project_context_chunks"]._docs[0]
        assert doc["tenant_id"] == "t1"
        assert doc["project_id"] == "proj-123"
        assert doc["text"] == "Some brand voice text."
        assert doc["chunk_type"] == "brand_voice"
        assert doc["embedding"] == [0.1, 0.2]
        assert doc["metadata"]["source"] == "brand_voice.md"
        assert "chunk_id" in doc
        assert "created_at" in doc

    @pytest.mark.asyncio
    async def test_returns_unique_chunk_ids(self):
        from services.context_service import store_chunk
        db = FakeDB()
        id1 = await store_chunk(db, "t1", "p1", "text one", "brand_voice", [])
        id2 = await store_chunk(db, "t1", "p1", "text two", "brand_voice", [])
        assert id1 != id2

    @pytest.mark.asyncio
    async def test_metadata_defaults_to_empty_dict(self):
        from services.context_service import store_chunk
        db = FakeDB()
        await store_chunk(db, "t1", "p1", "text", "research", [])
        doc = db["project_context_chunks"]._docs[0]
        assert doc["metadata"] == {}


# ── retrieve_relevant_context ──────────────────────────────────────────────────

class TestRetrieveRelevantContext:
    @pytest.mark.asyncio
    async def test_returns_top_k_most_similar_chunks(self):
        from services.context_service import store_chunk, retrieve_relevant_context
        db = FakeDB()

        # Store 3 chunks with known embeddings
        e_payroll = make_embedding(0.9)  # high similarity to query
        e_unrelated = make_embedding(0.1)  # low similarity

        await store_chunk(db, "t1", "p1", "Payroll automation saves time.", "brand_voice", e_payroll)
        await store_chunk(db, "t1", "p1", "Weather is nice today.", "brand_voice", e_unrelated)
        await store_chunk(db, "t1", "p1", "EOBI compliance is important.", "brand_voice", e_payroll)

        # Query with embedding similar to e_payroll
        query_embedding = make_embedding(0.89)

        with patch("services.context_service.embed_text", return_value=query_embedding):
            results = await retrieve_relevant_context(
                db=db,
                tenant_id="t1",
                project_id="p1",
                query_text="payroll automation",
                api_key="test-key",
                k=2,
            )

        assert len(results) == 2
        # Payroll-related chunks should be top-ranked
        assert any("Payroll" in r or "EOBI" in r for r in results)

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_chunks_exist(self):
        from services.context_service import retrieve_relevant_context
        db = FakeDB()
        with patch("services.context_service.embed_text", return_value=make_embedding(0.5)):
            results = await retrieve_relevant_context(
                db=db, tenant_id="t1", project_id="p1",
                query_text="anything", api_key="key", k=5,
            )
        assert results == []

    @pytest.mark.asyncio
    async def test_returns_empty_when_embedding_fails(self):
        from services.context_service import store_chunk, retrieve_relevant_context
        db = FakeDB()
        await store_chunk(db, "t1", "p1", "Some text", "brand_voice", make_embedding(0.5))

        with patch("services.context_service.embed_text", return_value=[]):
            results = await retrieve_relevant_context(
                db=db, tenant_id="t1", project_id="p1",
                query_text="anything", api_key="", k=5,
            )
        assert results == []

    @pytest.mark.asyncio
    async def test_only_returns_chunks_for_correct_project(self):
        from services.context_service import store_chunk, retrieve_relevant_context
        db = FakeDB()
        e = make_embedding(0.5)
        await store_chunk(db, "t1", "proj-A", "Text for project A.", "brand_voice", e)
        await store_chunk(db, "t1", "proj-B", "Text for project B.", "brand_voice", e)

        with patch("services.context_service.embed_text", return_value=e):
            results = await retrieve_relevant_context(
                db=db, tenant_id="t1", project_id="proj-A",
                query_text="anything", api_key="key", k=5,
            )
        assert len(results) == 1
        assert "project A" in results[0]


# ── store_run_context ──────────────────────────────────────────────────────────

class TestStoreRunContext:
    @pytest.mark.asyncio
    async def test_stores_research_brief_as_chunk(self):
        from services.context_service import store_run_context
        db = FakeDB()

        run = {
            "id": "run-001",
            "project_id": "proj-123",
            "tenant_id": "t1",
            "topic": "payroll automation",
        }
        research_brief = {
            "topic": "payroll automation",
            "trending_angles": ["Saves 3 days/month", "EOBI compliance"],
            "pain_points": ["Manual spreadsheets"],
        }
        posts = [
            {"copy": "OfferBerries payroll post #1", "hashtags": ["#Payroll"]},
        ]

        with patch("services.context_service.embed_text", return_value=make_embedding(0.5)):
            await store_run_context(
                db=db,
                run=run,
                research_brief=research_brief,
                posts=posts,
                api_key="test-key",
            )

        chunks = db["project_context_chunks"]._docs
        assert len(chunks) >= 1
        types = {c["chunk_type"] for c in chunks}
        assert "research" in types

    @pytest.mark.asyncio
    async def test_skips_if_no_project_id(self):
        from services.context_service import store_run_context
        db = FakeDB()
        run = {"id": "run-001", "project_id": None, "tenant_id": "t1", "topic": "payroll"}
        with patch("services.context_service.embed_text", return_value=make_embedding(0.5)):
            await store_run_context(db=db, run=run, research_brief={}, posts=[], api_key="key")
        assert len(db["project_context_chunks"]._docs) == 0

    @pytest.mark.asyncio
    async def test_stores_post_chunks(self):
        from services.context_service import store_run_context
        db = FakeDB()
        run = {"id": "run-001", "project_id": "proj-1", "tenant_id": "t1", "topic": "hr"}
        posts = [
            {"copy": "Post 1 copy text", "platform": "linkedin"},
            {"copy": "Post 2 copy text", "platform": "instagram"},
        ]
        with patch("services.context_service.embed_text", return_value=make_embedding(0.5)):
            await store_run_context(
                db=db, run=run, research_brief={"topic": "hr", "trending_angles": []},
                posts=posts, api_key="key",
            )
        types = [c["chunk_type"] for c in db["project_context_chunks"]._docs]
        assert types.count("post") >= 2


# ── cosine_similarity ──────────────────────────────────────────────────────────

class TestCosineSimilarity:
    def test_identical_vectors_give_1(self):
        from services.context_service import cosine_similarity
        v = make_embedding(0.5)
        assert abs(cosine_similarity(v, v) - 1.0) < 1e-6

    def test_orthogonal_vectors_give_0(self):
        from services.context_service import cosine_similarity
        v1 = [1.0, 0.0]
        v2 = [0.0, 1.0]
        assert abs(cosine_similarity(v1, v2)) < 1e-9

    def test_opposite_vectors_give_minus_1(self):
        from services.context_service import cosine_similarity
        v1 = [1.0, 0.0]
        v2 = [-1.0, 0.0]
        assert abs(cosine_similarity(v1, v2) + 1.0) < 1e-6

    def test_empty_vectors_give_0(self):
        from services.context_service import cosine_similarity
        assert cosine_similarity([], []) == 0.0
