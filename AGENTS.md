# Uber-Memory: Agent Instructions

This project provides **long-term project memory** for agents via Memgraph (graph) and Qdrant (hybrid semantic + BM25 search). All stored knowledge includes `created_at` timestamps.

## Your Role

When working in this repo you are both a **user** of project memory and its **maintainer**. Use the Uber-Memory skill and MCP tools to read and write project knowledge so that future sessions and other agents can benefit.

## Memory Usage (Mandatory)

1. **At the start of a task** about this project or the codebase:
   - Call MCP `memory_search` with the user’s question or a short task description.
   - Use the returned facts (and their `created_at`) in your reasoning. Prefer recent knowledge when relevant.

2. **When you learn or decide something worth keeping** (architecture, conventions, decisions, gotchas):
   - Call `memory_upsert` with the fact(s). Each item will get `created_at` automatically.
   - For relationships between entities (e.g. “service A depends on B”), use the graph tools (`graph_add_fact`, `graph_query`) so the graph stays consistent.

3. **Session start**: If `.cursor/memory_context.md` exists, it contains a short memory summary for this session. Use it as initial context; for deeper or task-specific search, use MCP `memory_search`.

## MCP Tools (Uber-Memory)

| Tool | Use |
|------|-----|
| `memory_search` | Hybrid search (semantic + BM25) by query. Returns text, `created_at`, and optional payload. |
| `memory_upsert` | Store one or more facts. Dense + sparse vectors and `created_at` are set server-side. |
| `graph_query` | Run a read-only Cypher query on Memgraph (e.g. list facts, entities, relations). |
| `graph_add_fact` | Add a fact (node/relation) to the graph with `created_at`. |

Temporal metadata is first-class: use `created_at` to rank or explain when a fact was recorded.

## Skill

The **uber-memory** skill (see `skill/uber-memory/SKILL.md`) defines when and how to use these tools in more detail. Follow it when storing or retrieving project knowledge.

## Config and Infrastructure

- **Config**: `config/memory_config.yaml` and env (see `.env.example`) define Qdrant collection, BM25/semantic settings, and endpoints. Do not change the main config unless the user asks; use it as read-only.
- **Services**: Qdrant at `http://127.0.0.1:6333`, Memgraph at `bolt://127.0.0.1:7687`. Start with `docker compose up -d` if they are not running.

## Summary

- **Search first** when starting a task; **upsert** when you create durable knowledge.
- **Always** rely on `created_at` in metadata for recency and traceability.
- **Combine** the session summary (`.cursor/memory_context.md`) with on-demand `memory_search` and graph queries for full use of project memory.
