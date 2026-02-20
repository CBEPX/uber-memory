"""
Unit tests for MCP tool argument validators. AAA pattern.
"""

from __future__ import annotations

from mcp_server.validators import (
    validate_graph_add_fact,
    validate_graph_query,
    validate_memory_search,
    validate_memory_upsert,
)


class TestValidateMemorySearch:
    """memory_search argument validation."""

    def test_valid(self, sample_memory_search_args: dict) -> None:
        assert validate_memory_search(sample_memory_search_args) is None

    def test_missing_query(self) -> None:
        assert "query" in (validate_memory_search({}) or "")

    def test_empty_query(self) -> None:
        assert validate_memory_search({"query": ""}) is not None
        assert validate_memory_search({"query": "   "}) is not None

    def test_limit_out_of_range(self) -> None:
        assert validate_memory_search({"query": "x", "limit": 0}) is not None
        assert validate_memory_search({"query": "x", "limit": 101}) is not None

    def test_limit_ok(self) -> None:
        assert validate_memory_search({"query": "x", "limit": 1}) is None
        assert validate_memory_search({"query": "x", "limit": 100}) is None


class TestValidateMemoryUpsert:
    """memory_upsert argument validation."""

    def test_valid(self, sample_memory_upsert_args: dict) -> None:
        assert validate_memory_upsert(sample_memory_upsert_args) is None

    def test_missing_items(self) -> None:
        assert "items" in (validate_memory_upsert({}) or "")

    def test_items_not_list(self) -> None:
        assert validate_memory_upsert({"items": "x"}) is not None

    def test_item_missing_text(self) -> None:
        assert validate_memory_upsert({"items": [{}]}) is not None
        assert validate_memory_upsert({"items": [{"text": ""}]}) is not None

    def test_item_not_dict(self) -> None:
        assert validate_memory_upsert({"items": ["x"]}) is not None


class TestValidateGraphQuery:
    """graph_query argument validation."""

    def test_valid(self, sample_graph_query_args: dict) -> None:
        assert validate_graph_query(sample_graph_query_args) is None

    def test_missing_cypher_query(self) -> None:
        assert "cypher_query" in (validate_graph_query({}) or "")

    def test_empty_cypher_query(self) -> None:
        assert validate_graph_query({"cypher_query": ""}) is not None
        assert validate_graph_query({"cypher_query": "   "}) is not None


class TestValidateGraphAddFact:
    """graph_add_fact argument validation."""

    def test_valid(self, sample_graph_add_fact_args: dict) -> None:
        assert validate_graph_add_fact(sample_graph_add_fact_args) is None

    def test_missing_content(self) -> None:
        assert "content" in (validate_graph_add_fact({}) or "")

    def test_empty_content(self) -> None:
        assert validate_graph_add_fact({"content": ""}) is not None
        assert validate_graph_add_fact({"content": "   "}) is not None
