# Uber-Memory: Top-Down and Bottom-Up Analysis

Verification that all instructions and code are aligned and ready for use. Uses agent-memory-systems, skill-creator, and create-rule principles.

---

## Top-Down (Plan → Instructions → Code)

### 1. Goals (from original plan)

- Long-term project memory for agents via **Memgraph** (graph) and **Qdrant** (hybrid semantic + BM25).
- Docker on 127.0.0.1; BM25 + semantic in main config; **created_at** in graph and Qdrant.
- Shareable skill; Cursor integration (rules, hooks); memory used consistently.

**Status**: Met. Docker binds to 127.0.0.1; config (env + YAML schema) defines collection and BM25/semantic; all writes set `created_at`; skill is in `skill/uber-memory/`; rule and sessionStart hook are in place.

### 2. Instruction layer

| Artifact | Role | Consistency |
|----------|------|--------------|
| **AGENTS.md** | Main agent instructions: when to search/upsert, tools, session summary, config. | Refers to skill and rule; tools and flow match server. |
| **.cursor/rules/memory.mdc** | Always-apply rule: search at task start, upsert on new knowledge, use `memory_context.md`. | Points to AGENTS.md and SKILL.md; no contradiction. |
| **skill/uber-memory/SKILL.md** | When to use, tool table, temporal metadata, config, anti-patterns. | Frontmatter and body align with AGENTS.md; `created_at` described as Unix ms (matches code). |
| **README.md** | Setup, quick start, sharing, dev commands. | Explains .env as runtime config and YAML as schema; references AGENTS.md and skill. |
| **config/memory_config.yaml** | Schema/reference for collection and BM25/semantic. | Comment states runtime config is .env. |

**Cross-references**: AGENTS.md → skill, rule → AGENTS.md + SKILL, README → AGENTS.md + skill + DESIGN. All closed.

### 3. Integration (Cursor)

- **MCP**: `.cursor/mcp.json.example` documents server command (`uv run python -m mcp_server`), cwd, env. Server exposes `memory_search`, `memory_upsert`, `graph_query`, `graph_add_fact`.
- **Hooks**: `sessionStart` runs `scripts/memory_session_start.sh`, which writes `.cursor/memory_context.md` (fail-safe if curl or Qdrant unavailable).
- **Skill**: Installable by copying `skill/uber-memory/`; name and description allow Cursor to trigger it.

**Status**: Instructions and integration are consistent; no extra hooks or subagents required for “memory constantly used” beyond rule + sessionStart + agent following the skill.

---

## Bottom-Up (Code → Behaviour → Instructions)

### 4. MCP server behaviour

- **Config**: `config.py` loads from `.env` via pydantic-settings; no YAML parsing. YAML is documentation only.
- **Qdrant**: Dense (sentence-transformers) + sparse (stable hash `zlib.crc32`) with `Modifier.IDF`; `created_at` in payload as integer (Unix ms). Retry in `ensure_collection`.
- **Memgraph**: Neo4j driver; `add_fact` creates `Fact` with `content`, `created_at`, `entity_id`, `source`; `run_cypher` returns rows with `_labels`/`_type` for nodes/relationships.
- **Validation**: All tool args validated in `validators.py`; errors returned as messages, not exceptions.
- **Logging**: One event per tool call (tool, duration_ms, outcome).

**Instruction alignment**: AGENTS.md and SKILL say “search first, upsert when saving knowledge” and “created_at for recency”; server implements exactly that. SKILL and config comments now state `created_at` is Unix ms and that runtime config is .env.

### 5. Sharp edges (agent-memory-systems)

- **Temporal scoring**: Documented (use `created_at` to prefer recent facts); payloads and graph nodes expose it.
- **Metadata-first**: Documented (filter by project_id, etc.); `memory_search` supports `project_id` filter.
- **Store only actionable facts**: In SKILL anti-patterns; no code change needed.
- **Retrieval as bottleneck**: SKILL and AGENTS.md both say “search first” and “retrieval is the bottleneck”.

### 6. Skill-creator and create-rule

- **SKILL.md**: Single file, clear when-to-use, tool table, no redundant docs; under 500 lines.
- **Rule**: `.mdc` with `description` and `alwaysApply: true`; content is short and points to full instructions.

---

## Fixes applied in this pass

1. **SKILL.md – Temporal Metadata**: “Unix ms or ISO8601” → “Unix milliseconds” to match implementation.
2. **README – Config**: Clarified that the MCP server reads from `.env` and that `config/memory_config.yaml` is the schema reference.
3. **config/memory_config.yaml**: Comment added that runtime config is `.env` and this file is reference.

---

## Readiness summary

- **Plan and architecture**: Implemented; Docker, dual store (Qdrant + Memgraph), BM25 + semantic, `created_at` everywhere.
- **Instructions**: AGENTS.md, rule, SKILL, README, and config comments are consistent and reference each other; temporal and config semantics match the code.
- **Code**: Validation, config, resilience (retry), observability (logging), stable sparse hash, graph serialization with labels/type; tests cover validators and config.
- **Sharing**: Repo can be cloned; README describes setup, MCP, skill, and rule; `.cursor/mcp.json.example` is the only template (no secrets).

The project is ready for use and for sharing the skill and setup.
