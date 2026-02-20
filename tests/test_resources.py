import pytest
from pydantic import AnyUrl

from mcp_server.resources import (
    PATH_GRAPH_SCHEMA,
    PATH_PROJECT_CONTEXT,
    RESOURCE_LIST,
    SCHEME,
    build_uri,
    parse_memory_uri,
)


def test_build_uri():
    assert build_uri("test/path") == "memory://test/path"
    assert build_uri("test/path", {"id": "123"}) == "memory://test/path?id=123"


def test_parse_memory_uri():
    uri = AnyUrl("memory://project/context?project_id=abc&scope=cross")
    path, query = parse_memory_uri(uri)
    assert path == "project/context"
    assert query == {"project_id": ["abc"], "scope": ["cross"]}


def test_resource_list_contains_expected_uris():
    uris = [str(r.uri) for r in RESOURCE_LIST]
    assert "memory://project/context" in uris
    assert "memory://graph/schema" in uris
