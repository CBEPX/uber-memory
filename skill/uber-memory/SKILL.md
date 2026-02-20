---
name: uber-memory
description: Use long-term project memory stored in Memgraph (graph) and Qdrant (hybrid semantic + BM25). Store and retrieve facts with created_at timestamps. Use when starting a task about the project, when saving decisions/conventions, or when answering "what do we know about X".
---

# Uber-Memory: Project Memory for Agents

Retrieval is the bottleneck: store only useful facts and always search before answering. Prefer **metadata-first** (e.g. filter by project or time) and **temporal scoring** (use `created_at` to rank or explain recency).

## When to Use

- **Start of a task** about the repo or codebase → call `memory_search` with the task/question.
- **User asks** "what do we know about X", "how did we do Y", "why did we choose Z" → `memory_search` then optionally `graph_query` for relations.
- **You learn or decide** something durable (architecture, convention, decision, gotcha) → `memory_upsert` and, if it links entities, `graph_add_fact`.

## MCP Tools

| Tool | When |
|------|------|
| `memory_search` | Hybrid search (dense + sparse/BM25). Pass natural-language or keyword query. Use returned `created_at` for recency. |
| `memory_upsert` | Add one or more facts. Server sets embeddings and `created_at`. Optional: `entity_id`, `source`, `project_id`. |
| `graph_query` | Read-only Cypher on Memgraph. Use to list entities, facts, or relations. Nodes/edges include `created_at`. |
| `graph_add_fact` | Create a fact (node or relation) in the graph with `created_at`. |

## Temporal Metadata

- Every stored fact has **created_at** (Unix milliseconds). Use it to:
  - Prefer recent results when relevant.
  - Cite when a fact was recorded ("as of 2025-02-20").
- Do not overwrite or remove `created_at` in payloads; the server sets it on insert.

## Config

Main config is read-only for the agent: `config/memory_config.yaml` and env (Qdrant URL, Memgraph Bolt URL, collection name, dense size, BM25/sparse modifier). Do not change it unless the user explicitly asks.

## Anti-Patterns

- Do not store everything; store **actionable** facts (decisions, conventions, gotchas).
- Do not skip search at task start when the task is about the project.
- Do not ignore `created_at` when ranking or explaining results.
