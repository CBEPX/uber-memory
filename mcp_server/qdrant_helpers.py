"""
Qdrant: collection with dense + sparse (BM25/IDF). created_at in payload.
"""

from __future__ import annotations

import json
import re
import time
import uuid
import zlib
from collections import Counter
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.models import (
    FieldCondition,
    Filter,
    MatchValue,
    Modifier,
    NamedVector,
    PointStruct,
    SparseVector,
    SparseVectorParams,
    VectorParams,
)
from sentence_transformers import SentenceTransformer

from .config import get_settings

__all__ = ["ensure_collection", "hybrid_search", "upsert_points", "list_project_ids"]

_client: QdrantClient | None = None
_model: SentenceTransformer | None = None


def _get_client() -> QdrantClient:
    global _client
    if _client is None:
        s = get_settings()
        _client = QdrantClient(url=s.qdrant_url)
    return _client


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def _tokenize(text: str) -> list[str]:
    """Extract word tokens for sparse vector."""
    return re.findall(r"\b\w+\b", text.lower())


def _stable_hash(text: str) -> int:
    """Stable hash for token index (survives process restarts; Python hash() does not)."""
    return zlib.crc32(text.encode("utf-8")) % (2**31)


def _sparse_vector(text: str) -> SparseVector:
    """Build sparse vector (tf-style) for BM25/IDF index."""
    tokens = _tokenize(text)
    if not tokens:
        return SparseVector(indices=[0], values=[0.0])
    counts: Counter[str] = Counter(tokens)
    indices, values = [], []
    for token, count in counts.most_common(500):
        idx = _stable_hash(token)
        indices.append(idx)
        values.append(float(count))
    return SparseVector(indices=indices, values=values)


def _now_ms() -> int:
    return int(time.time() * 1000)


def ensure_collection() -> None:
    """Create Qdrant collection with dense + sparse vectors if it does not exist.
    Retries up to 3 times on transient connection errors (1s delay).
    """
    s = get_settings()
    transient = (ConnectionError, TimeoutError, OSError)
    last: BaseException | None = None
    for attempt in range(3):
        try:
            client = _get_client()
            try:
                client.get_collection(s.memory_collection)
                return
            except Exception:
                pass
            client.create_collection(
                collection_name=s.memory_collection,
                vectors_config={"dense": VectorParams(size=s.embedding_dim, distance="Cosine")},
                sparse_vectors_config={"sparse": SparseVectorParams(modifier=Modifier.IDF)},
            )
            return
        except transient as e:
            last = e
            if attempt < 2:
                time.sleep(1)
    if last:
        raise last


def hybrid_search(
    query: str,
    limit: int = 10,
    project_id: str | None = None,
) -> str:
    """
    Run hybrid (dense) search. Returns JSON array of {text, created_at, payload}.

    Args:
        query: Natural language or keyword query.
        limit: Max results (1–100).
        project_id: Optional filter by project_id payload.

    Returns:
        JSON string of results.
    """
    if not query or not query.strip():
        return json.dumps([])
    if not 1 <= limit <= 100:
        limit = min(max(1, limit), 100)
    client = _get_client()
    model = _get_model()
    s = get_settings()
    dense_vec = model.encode(query).tolist()
    filter_ = (
        Filter(must=[FieldCondition(key="project_id", match=MatchValue(value=project_id))])
        if project_id
        else None
    )
    results = client.query_points(
        collection_name=s.memory_collection,
        query=NamedVector(name="dense", vector=dense_vec),
        limit=limit,
        query_filter=filter_,
    )
    out = []
    for r in results.points:
        payload = r.payload or {}
        out.append(
            {
                "text": payload.get("text", ""),
                "created_at": payload.get("created_at", ""),
                "payload": payload,
            }
        )
    return json.dumps(out, ensure_ascii=False, indent=2)


def upsert_points(items: list[dict[str, Any]]) -> str:
    """
    Upsert facts into Qdrant with dense + sparse vectors and created_at.

    Args:
        items: List of dicts with "text" (required) and optional entity_id, source, project_id.

    Returns:
        JSON with upserted count and created_at_ms.
    """
    if not items:
        return json.dumps({"upserted": 0, "created_at_ms": _now_ms()})
    client = _get_client()
    model = _get_model()
    s = get_settings()
    points = []
    for item in items:
        text = (item.get("text") or "").strip()
        if not text:
            continue
        now = _now_ms()
        payload: dict[str, Any] = {
            "text": text,
            "created_at": now,
            "entity_id": item.get("entity_id"),
            "source": item.get("source"),
            "project_id": item.get("project_id"),
        }
        payload = {k: v for k, v in payload.items() if v is not None}
        dense = model.encode(text).tolist()
        sparse = _sparse_vector(text)
        points.append(
            PointStruct(
                id=str(uuid.uuid4()),
                vector={"dense": dense, "sparse": sparse},
                payload=payload,
            )
        )
    if points:
        client.upsert(collection_name=s.memory_collection, points=points)
    return json.dumps({"upserted": len(points), "created_at_ms": _now_ms()})


def list_project_ids(exclude: str | None = None, limit: int = 5) -> list[str]:
    """Get a list of unique project_ids from memory, excluding the given one."""
    client = _get_client()
    s = get_settings()
    projects: set[str] = set()
    offset = None
    while True:
        points, offset = client.scroll(
            collection_name=s.memory_collection,
            limit=100,
            with_payload=True,
            offset=offset,
        )
        for p in points:
            pid = p.payload.get("project_id") if p.payload else None
            if pid and pid != exclude:
                projects.add(str(pid))
                if len(projects) >= limit:
                    return list(projects)
        if offset is None:
            break
    return list(projects)

