from __future__ import annotations

import asyncio

from .config import get_settings
from .memgraph_helpers import run_cypher
from .qdrant_helpers import hybrid_search

# Limits for scope=cross and scope=all
CROSS_CURRENT_LIMIT = 12
CROSS_OTHER_LIMIT = 2
CROSS_MAX_OTHER_PROJECTS = 3
ALL_PROJECTS_LIMIT = 25


async def get_project_context(project_id: str | None = None, scope: str = "current") -> str:
    """Get project context bounded by budget. Supports scope=current|cross|all."""
    scope = scope.lower().strip()
    if scope not in {"current", "cross", "all"}:
        scope = "current"

    # We will build parts, then concatenate and truncate
    parts: list[str] = []

    if scope == "current":
        results = await asyncio.to_thread(
            hybrid_search, "project decisions conventions gotchas", 15, project_id
        )
        parts.append(f"## Project: {project_id or 'all'}\n{results}")

    elif scope == "cross":
        # 1. Fetch current project
        results = await asyncio.to_thread(
            hybrid_search, "project decisions conventions gotchas", CROSS_CURRENT_LIMIT, project_id
        )
        parts.append(f"## Project: {project_id or 'all'}\n{results}")

        # 2. Get list of other project_ids
        from .qdrant_helpers import list_project_ids
        other_projects = await asyncio.to_thread(list_project_ids, exclude=project_id, limit=CROSS_MAX_OTHER_PROJECTS)
        
        # 3. For each other project, hybrid_search
        for other_id in other_projects:
            other_results = await asyncio.to_thread(
                hybrid_search, "project decisions conventions gotchas", CROSS_OTHER_LIMIT, other_id
            )
            parts.append(f"## Project: {other_id}\n{other_results}")

    elif scope == "all":
        # hybrid_search doesn't group by project_id in its formatted output easily.
        # For v1, we just return the global top N. 
        results = await asyncio.to_thread(
            hybrid_search, "project decisions conventions gotchas", ALL_PROJECTS_LIMIT, None
        )
        parts.append(f"## All Projects (Top {ALL_PROJECTS_LIMIT})\n{results}")

    # Combine and truncate
    max_chars = get_settings().memory_resource_max_chars
    combined = "\n\n".join(parts)
    if len(combined) > max_chars:
        combined = combined[:max_chars] + "\n\n... (truncated due to context limits)"
    
    return combined


async def get_graph_schema() -> str:
    """Return human-readable graph schema using Memgraph introspection."""
    # db.labels() and db.relationshipTypes() are standard in Neo4j/Memgraph
    try:
        labels_json = await asyncio.to_thread(run_cypher, "CALL db.labels()")
        rel_types_json = await asyncio.to_thread(run_cypher, "CALL db.relationshipTypes()")
        
        # Parse the JSON arrays back to list
        import json
        labels_data = json.loads(labels_json)
        rels_data = json.loads(rel_types_json)
        
        parts: list[str] = ["## Graph Schema\n"]
        parts.append("### Node Labels")
        for row in labels_data:
            label = row.get("label") or row.get("name")
            if label:
                parts.append(f"- `{label}`")
                
        parts.append("\n### Relationship Types")
        for row in rels_data:
            rel = row.get("relationshipType") or row.get("name")
            if rel:
                parts.append(f"- `{rel}`")
                
        return "\n".join(parts)
    except Exception as e:
        return f"Error fetching schema: {e}"
