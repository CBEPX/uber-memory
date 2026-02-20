"""
Pytest fixtures for uber-memory MCP server tests.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def isolate_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Avoid leaking env from host into tests that depend on defaults."""
    pass  # Tests that need clean env can monkeypatch explicitly


@pytest.fixture
def sample_memory_search_args() -> dict:
    """Valid arguments for memory_search."""
    return {"query": "test query", "limit": 5}


@pytest.fixture
def sample_memory_upsert_args() -> dict:
    """Valid arguments for memory_upsert."""
    return {"items": [{"text": "A fact"}, {"text": "Another", "source": "test"}]}


@pytest.fixture
def sample_graph_query_args() -> dict:
    """Valid arguments for graph_query."""
    return {"cypher_query": "MATCH (n:Fact) RETURN n LIMIT 10"}


@pytest.fixture
def sample_graph_add_fact_args() -> dict:
    """Valid arguments for graph_add_fact."""
    return {"content": "A new fact", "source": "test"}
