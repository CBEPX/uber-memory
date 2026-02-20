"""
Memgraph over Bolt (neo4j driver). created_at on nodes and relations.
"""

from __future__ import annotations

import json
import time
from typing import Any

from neo4j import Driver, GraphDatabase

from .config import get_settings

__all__ = ["run_cypher", "add_fact"]

_driver: Driver | None = None


def _get_driver() -> Driver:
    global _driver
    if _driver is None:
        s = get_settings()
        _driver = GraphDatabase.driver(s.memgraph_bolt_uri)
    return _driver


def _now_ms() -> int:
    return int(time.time() * 1000)


def _serialize_record(record: Any) -> dict[str, Any]:
    """Convert neo4j record to JSON-serializable dict. Preserves node labels and relationship type."""
    out: dict[str, Any] = {}
    for key in record:
        val = record[key]
        if hasattr(val, "labels") and hasattr(val, "items"):
            out[key] = {"_labels": list(val.labels), **dict(val.items())}
        elif hasattr(val, "type") and hasattr(val, "items"):
            out[key] = {"_type": val.type, **dict(val.items())}
        elif hasattr(val, "items"):
            out[key] = dict(val)
        elif hasattr(val, "__iter__") and not isinstance(val, (str, bytes)):
            out[key] = list(val)
        else:
            out[key] = val
    return out


def run_cypher(cypher_query: str) -> str:
    """
    Execute a read-only Cypher query. Returns JSON array of record dicts.

    Args:
        cypher_query: Cypher query (e.g. MATCH (n:Fact) RETURN n LIMIT 20).

    Returns:
        JSON string of rows.
    """
    if not cypher_query or not cypher_query.strip():
        return json.dumps([])
    driver = _get_driver()
    with driver.session() as session:
        result = session.run(cypher_query)
        rows = [_serialize_record(r) for r in result]
    return json.dumps(rows, ensure_ascii=False, indent=2, default=str)


def add_fact(
    content: str,
    entity_id: str | None = None,
    source: str | None = None,
) -> str:
    """
    Create a Fact node with content and created_at.

    Args:
        content: Fact text.
        entity_id: Optional entity id.
        source: Optional source label.

    Returns:
        JSON with created_at and content preview.
    """
    if not content or not content.strip():
        return json.dumps({"error": "content is required and must be non-empty"})
    driver = _get_driver()
    now = _now_ms()
    with driver.session() as session:
        session.run(
            """
            CREATE (f:Fact {
                content: $content,
                created_at: $created_at,
                entity_id: $entity_id,
                source: $source
            })
            RETURN f
            """,
            content=content.strip(),
            created_at=now,
            entity_id=entity_id or "",
            source=source or "",
        )
    return json.dumps({"created_at": now, "content": content.strip()[:100]})
