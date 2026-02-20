"""
Uber-Memory MCP server: memory_search, memory_upsert, graph_query, graph_add_fact.
Uses Qdrant (dense + sparse/BM25) and Memgraph (Bolt). All payloads/nodes use created_at.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from mcp.server.lowlevel.helper_types import ReadResourceContents
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    GetPromptResult,
    Prompt,
    PromptArgument,
    PromptMessage,
    Resource,
    TextContent,
    Tool,
)
from pydantic import AnyUrl

from .config import init_settings
from .memgraph_helpers import add_fact, run_cypher
from .qdrant_helpers import ensure_collection, hybrid_search, upsert_points
from .resource_handlers import get_graph_schema, get_project_context
from .resources import (
    PATH_GRAPH_SCHEMA,
    PATH_PROJECT_CONTEXT,
    RESOURCE_LIST,
    SCHEME,
    parse_memory_uri,
)
from .validators import (
    validate_graph_add_fact,
    validate_graph_query,
    validate_memory_search,
    validate_memory_upsert,
)

__all__ = ["app", "main"]

logger = logging.getLogger(__name__)
app = Server("uber-memory")


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="memory_search",
            description="Hybrid search (semantic + BM25) in project memory. Returns facts with text, created_at, and optional payload. Use at task start or when answering 'what do we know about X'.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Natural language or keyword query"},
                    "limit": {
                        "type": "integer",
                        "description": "Max results (default 10)",
                        "default": 10,
                    },
                    "project_id": {
                        "type": "string",
                        "description": "Optional filter by project_id",
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="memory_upsert",
            description="Store one or more facts. Server sets dense + sparse vectors and created_at. Use when saving decisions, conventions, or gotchas.",
            inputSchema={
                "type": "object",
                "properties": {
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "text": {"type": "string"},
                                "entity_id": {"type": "string"},
                                "source": {"type": "string"},
                                "project_id": {"type": "string"},
                            },
                            "required": ["text"],
                        },
                    },
                },
                "required": ["items"],
            },
        ),
        Tool(
            name="graph_query",
            description="Run a read-only Cypher query on Memgraph. Returns nodes/relations; use for listing facts, entities, or relations. All nodes/edges include created_at when present.",
            inputSchema={
                "type": "object",
                "properties": {
                    "cypher_query": {
                        "type": "string",
                        "description": "Cypher read-only query (e.g. MATCH (n:Fact) RETURN n LIMIT 20)",
                    },
                },
                "required": ["cypher_query"],
            },
        ),
        Tool(
            name="graph_add_fact",
            description="Add a fact (node or relation) to the graph with created_at. Use for entities and relationships.",
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "Fact content or node label/name"},
                    "entity_id": {"type": "string"},
                    "source": {"type": "string"},
                },
                "required": ["content"],
            },
        ),
    ]


# --- Prompts (MCP): guide when to search/save memory and load context ---

PROMPTS: list[Prompt] = [
    Prompt(
        name="memory_recall",
        description="Recall what we know about a topic. Use at task start or when answering 'what do we know about X'. Triggers hybrid search in project memory.",
        arguments=[
            PromptArgument(name="topic", description="Topic or question to look up (e.g. 'auth', 'API conventions')", required=True),
            PromptArgument(name="project_id", description="Optional project filter", required=False),
        ],
    ),
    Prompt(
        name="memory_save",
        description="Store a fact for later retrieval. Use when saving decisions, conventions, or gotchas.",
        arguments=[
            PromptArgument(name="text", description="Fact or note to remember", required=True),
            PromptArgument(name="source", description="Optional source (e.g. file, discussion)", required=False),
            PromptArgument(name="project_id", description="Optional project id", required=False),
        ],
    ),
    Prompt(
        name="task_start_context",
        description="Load relevant project memory before starting a task. Encourages memory_search so the agent has context.",
        arguments=[
            PromptArgument(name="query", description="What to look up (e.g. 'this project', 'recent decisions')", required=False),
            PromptArgument(name="project_id", description="Optional project filter", required=False),
        ],
    ),
]


@app.list_prompts()
async def list_prompts() -> list[Prompt]:
    return PROMPTS


@app.get_prompt()
async def get_prompt(name: str, arguments: dict[str, str] | None) -> GetPromptResult:
    args = arguments or {}
    if name == "memory_recall":
        topic = (args.get("topic") or "").strip() or "this project"
        project_id = (args.get("project_id") or "").strip() or None
        text = f"Before answering, search project memory for: «{topic}». Use memory_search with query=\"{topic}\""
        if project_id:
            text += f" and project_id=\"{project_id}\""
        text += ". Summarize what we know and use it in your answer."
        return GetPromptResult(
            description="Recall what we know about the topic",
            messages=[PromptMessage(role="user", content=TextContent(type="text", text=text))],
        )
    if name == "memory_save":
        text = (args.get("text") or "").strip() or "this"
        source = (args.get("source") or "").strip() or None
        project_id = (args.get("project_id") or "").strip() or None
        user_text = f"Save this to project memory so we can recall it later: «{text}». Use memory_upsert with one item (text, optionally source and project_id)."
        if source:
            user_text += f" Source: {source}."
        if project_id:
            user_text += f" project_id: {project_id}."
        return GetPromptResult(
            description="Store a fact in project memory",
            messages=[PromptMessage(role="user", content=TextContent(type="text", text=user_text))],
        )
    if name == "task_start_context":
        query = (args.get("query") or "").strip() or "this project and recent decisions"
        project_id = (args.get("project_id") or "").strip() or None
        user_text = f"At the start of this task, load relevant context from project memory. Use memory_search with query=\"{query}\""
        if project_id:
            user_text += f", project_id=\"{project_id}\""
        user_text += ". Then proceed using that context."
        return GetPromptResult(
            description="Load project memory before starting the task",
            messages=[PromptMessage(role="user", content=TextContent(type="text", text=user_text))],
        )
    return GetPromptResult(description="", messages=[PromptMessage(role="user", content=TextContent(type="text", text=f"Unknown prompt: {name}"))])


@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    start = time.perf_counter()
    outcome: list[str] = ["success"]
    try:
        if name == "memory_search":
            err = validate_memory_search(arguments)
            if err:
                return [TextContent(type="text", text=f"Validation error: {err}")]
            query = str(arguments.get("query", "")).strip()
            limit = max(1, min(100, int(arguments.get("limit", 10))))
            project_id = arguments.get("project_id")
            if project_id is not None:
                project_id = str(project_id).strip() or None
            results = await asyncio.to_thread(hybrid_search, query, limit, project_id)
            return [TextContent(type="text", text=results)]

        if name == "memory_upsert":
            err = validate_memory_upsert(arguments)
            if err:
                return [TextContent(type="text", text=f"Validation error: {err}")]
            result = await asyncio.to_thread(upsert_points, arguments["items"])
            return [TextContent(type="text", text=result)]

        if name == "graph_query":
            err = validate_graph_query(arguments)
            if err:
                return [TextContent(type="text", text=f"Validation error: {err}")]
            cypher = str(arguments.get("cypher_query", "")).strip()
            result = await asyncio.to_thread(run_cypher, cypher)
            return [TextContent(type="text", text=result)]

        if name == "graph_add_fact":
            err = validate_graph_add_fact(arguments)
            if err:
                return [TextContent(type="text", text=f"Validation error: {err}")]
            content = str(arguments.get("content", "")).strip()
            entity_id = arguments.get("entity_id")
            source = arguments.get("source")
            if entity_id is not None:
                entity_id = str(entity_id).strip() or None
            if source is not None:
                source = str(source).strip() or None
            result = await asyncio.to_thread(add_fact, content, entity_id, source)
            return [TextContent(type="text", text=result)]

        return [TextContent(type="text", text=f"Unknown tool: {name}")]
    except Exception as e:
        outcome[0] = "error"
        logger.warning("tool_call", extra={"tool": name, "outcome": "error", "error": str(e)})
        return [TextContent(type="text", text=f"Error: {e}")]
    finally:
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.info(
            "tool_call",
            extra={"tool": name, "duration_ms": duration_ms, "outcome": outcome[0]},
        )


# --- Resources (MCP): read-only memory and schema via URI ---

@app.list_resources()
async def list_resources() -> list[Resource]:
    return RESOURCE_LIST


@app.read_resource()
async def read_resource(uri: AnyUrl) -> list[ReadResourceContents]:
    if uri.scheme != SCHEME:
        return [ReadResourceContents(content=f"Unsupported scheme: {uri.scheme}", mime_type="text/plain")]
    
    path, query_params = parse_memory_uri(uri)
    
    if path == PATH_PROJECT_CONTEXT:
        project_id = query_params.get("project_id", [None])[0]
        scope = query_params.get("scope", ["current"])[0]
        result = await get_project_context(project_id, scope)
        return [ReadResourceContents(content=result, mime_type="text/markdown")]
    
    if path == PATH_GRAPH_SCHEMA:
        result = await get_graph_schema()
        return [ReadResourceContents(content=result, mime_type="text/markdown")]

    return [ReadResourceContents(content=f"Unknown resource path: {path}", mime_type="text/plain")]


async def main() -> None:
    """Run MCP server. Initializes settings and Qdrant collection, then serves stdio."""
    init_settings()
    ensure_collection()
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())
