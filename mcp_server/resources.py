from __future__ import annotations

import urllib.parse
from typing import Any

from mcp.types import Resource
from pydantic import AnyUrl

SCHEME = "memory"
PATH_PROJECT_CONTEXT = "project/context"
PATH_GRAPH_SCHEMA = "graph/schema"


def build_uri(path: str, query: dict[str, str] | None = None) -> str:
    uri = f"{SCHEME}://{path}"
    if query:
        qs = urllib.parse.urlencode(query)
        uri = f"{uri}?{qs}"
    return uri


def parse_memory_uri(uri: AnyUrl) -> tuple[str, dict[str, list[str]]]:
    """Parse URI into path and query params. Combines host and path."""
    path = ""
    if uri.host:
        path += uri.host
    if uri.path:
        path += uri.path
    if path.startswith("/"):
        path = path[1:]
    
    query_params: dict[str, list[str]] = {}
    if uri.query:
        query_params = urllib.parse.parse_qs(uri.query)
        
    return path, query_params


RESOURCE_LIST: list[Resource] = [
    Resource(
        uri=AnyUrl(build_uri(PATH_PROJECT_CONTEXT)),
        name="project_context",
        description="Recent project memory (decisions, conventions). Query: project_id (current project), scope=current|cross|all (default current). Cross/all use a token budget to avoid overload.",
        mimeType="text/markdown",
    ),
    Resource(
        uri=AnyUrl(build_uri(PATH_GRAPH_SCHEMA)),
        name="graph_schema",
        description="Graph schema: node labels and relationship types in Memgraph.",
        mimeType="text/markdown",
    ),
]
