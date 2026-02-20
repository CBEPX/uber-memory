"""
Input validation for MCP tool arguments. Single responsibility: validate and return error message or None.
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "validate_memory_search",
    "validate_memory_upsert",
    "validate_graph_query",
    "validate_graph_add_fact",
]


def validate_memory_search(args: dict[str, Any]) -> str | None:
    """Return error message if invalid, else None."""
    query = args.get("query")
    if query is None:
        return "memory_search requires 'query'"
    if not isinstance(query, str) or not query.strip():
        return "memory_search 'query' must be a non-empty string"
    limit = args.get("limit", 10)
    if isinstance(limit, (int, float)) and not (1 <= int(limit) <= 100):
        return "memory_search 'limit' must be between 1 and 100"
    return None


def validate_memory_upsert(args: dict[str, Any]) -> str | None:
    """Return error message if invalid, else None."""
    if "items" not in args:
        return "memory_upsert requires 'items'"
    items = args["items"]
    if not isinstance(items, list):
        return "memory_upsert 'items' must be a list"
    for i, it in enumerate(items):
        if not isinstance(it, dict):
            return f"memory_upsert items[{i}] must be a dict"
        if "text" not in it or not str(it.get("text", "")).strip():
            return f"memory_upsert items[{i}] must have non-empty 'text'"
    return None


def validate_graph_query(args: dict[str, Any]) -> str | None:
    """Return error message if invalid, else None."""
    cypher = args.get("cypher_query")
    if cypher is None:
        return "graph_query requires 'cypher_query'"
    if not isinstance(cypher, str) or not cypher.strip():
        return "graph_query 'cypher_query' must be a non-empty string"
    return None


def validate_graph_add_fact(args: dict[str, Any]) -> str | None:
    """Return error message if invalid, else None."""
    content = args.get("content")
    if content is None:
        return "graph_add_fact requires 'content'"
    if not isinstance(content, str) or not content.strip():
        return "graph_add_fact 'content' must be a non-empty string"
    return None
