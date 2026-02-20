import pytest

from mcp_server.resource_handlers import (
    ALL_PROJECTS_LIMIT,
    CROSS_CURRENT_LIMIT,
    CROSS_MAX_OTHER_PROJECTS,
    CROSS_OTHER_LIMIT,
    get_graph_schema,
    get_project_context,
)

import mcp_server.config

# ensure config is set up
mcp_server.config.init_settings()

@pytest.mark.anyio
async def test_get_project_context_current(monkeypatch):
    def mock_hybrid(*args, **kwargs):
        return "mock current results"
    monkeypatch.setattr("mcp_server.resource_handlers.hybrid_search", mock_hybrid)
    
    res = await get_project_context(project_id="test_proj", scope="current")
    assert "Project: test_proj" in res
    assert "mock current results" in res


@pytest.mark.anyio
async def test_get_project_context_cross(monkeypatch):
    def mock_hybrid(*args, **kwargs):
        return "mock results"
    monkeypatch.setattr("mcp_server.resource_handlers.hybrid_search", mock_hybrid)
    
    def mock_list_projects(*args, **kwargs):
        return ["p1", "p2"]
    monkeypatch.setattr("mcp_server.qdrant_helpers.list_project_ids", mock_list_projects)
    
    res = await get_project_context(project_id="test_proj", scope="cross")
    
    assert "Project: test_proj" in res
    assert "Project: p1" in res
    assert "Project: p2" in res


@pytest.mark.anyio
async def test_get_project_context_all(monkeypatch):
    def mock_hybrid(*args, **kwargs):
        return "all results"
    monkeypatch.setattr("mcp_server.resource_handlers.hybrid_search", mock_hybrid)
    
    res = await get_project_context(scope="all")
    assert "All Projects" in res
    assert "all results" in res


@pytest.mark.anyio
async def test_get_graph_schema(monkeypatch):
    def mock_run_cypher(query):
        if "labels" in query:
            return '[{"label":"NodeA"}]'
        return '[{"relationshipType":"REL_B"}]'
    monkeypatch.setattr("mcp_server.resource_handlers.run_cypher", mock_run_cypher)
    
    res = await get_graph_schema()
    assert "Node Labels" in res
    assert "`NodeA`" in res
    assert "Relationship Types" in res
    assert "`REL_B`" in res