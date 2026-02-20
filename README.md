# Uber-Memory

Long-term project memory for agents: **Memgraph** (graph) + **Qdrant** (hybrid semantic + BM25). All stored data includes `created_at` timestamps. Works in Cursor via MCP, a rule, and the uber-memory skill.

**AGENTS.md** in the repo root is the main agent instructions: it defines when to call `memory_search` and `memory_upsert`, and how to use the session summary (`.cursor/memory_context.md`) and graph tools.

## Requirements

- **make** (GNU Make)
- **Docker** (for Qdrant and Memgraph)
- **uv** (Python package manager: https://docs.astral.sh/uv/)
- Python 3.11+ (for MCP server)
- Cursor with MCP and rules enabled

## Quick start (Makefile)

All setup and daily use is driven by the Makefile. Run `make help` to see targets.

### One command to start working

```bash
make work           # Install (if needed), start containers, show status. Use this every time you start working.
```

This ensures `.venv` and `.env` exist, starts Qdrant and Memgraph, and prints their status. Safe to run repeatedly.

### Initial setup (once, or step by step)

```bash
make install        # Create .venv, install deps, .env from example, fix script permissions
make up             # Start Qdrant and Memgraph on 127.0.0.1
make status         # Check that services are reachable
```

- **Qdrant**: http://127.0.0.1:6333 (REST), port 6334 (gRPC)
- **Memgraph**: Bolt at `bolt://127.0.0.1:7687`

Containers use `restart: unless-stopped`: after one `make up`, they start automatically when Docker starts (e.g. after reboot). To stop them for good, run `make down`.

Config: the MCP server reads from `.env` (created from `.env.example` by `make install`). Edit `.env` if you need different URLs or collection name. The file `config/memory_config.yaml` documents the schema.

### Cursor integration (this repo)

1. **MCP server**: Copy `.cursor/mcp.json.example` to `.cursor/mcp.json`. Set `"cwd"` to this repo’s absolute path (or `${workspaceFolder}` when this repo is the workspace). Restart Cursor. Or run `make mcp-config` for a reminder.
2. **Skill**: Run `make skill-link` to symlink the skill into `~/.cursor/skills/uber-memory`, or copy `skill/uber-memory/` there manually.
3. **Rule**: This repo already includes `.cursor/rules/memory.mdc` (always apply).
4. **AGENTS.md**: Root agent instructions; Cursor uses them when this repo is the workspace.
5. **SessionStart hook**: `.cursor/hooks.json` runs `scripts/memory_session_start.sh`; `make install` makes the script executable.

## Using Uber-Memory in other projects

To use the same memory (Qdrant + Memgraph) from **another project** in Cursor (e.g. a different repo):

1. Keep Qdrant and Memgraph running from this repo: `make up` (once per machine/session).
2. In the **other project**, add the MCP server in `.cursor/mcp.json` with **cwd** set to the **absolute path of this uber-memory repo** (so the server runs from here).
3. Enable the skill once: `make skill-link` from this repo, or copy `skill/uber-memory/` to `~/.cursor/skills/uber-memory`.
4. Optionally copy `.cursor/rules/memory.mdc` and/or add a sessionStart hook in the other project.

Full steps and examples: **[docs/USE_IN_OTHER_PROJECTS.md](docs/USE_IN_OTHER_PROJECTS.md)**. From this repo you can also run `make use-in-other-projects` to print a short checklist.

## Sharing

- Share the repo: others clone it, run `make install` and `make up`, add the MCP server in Cursor, and use the skill + rule.
- The **skill** is in `skill/uber-memory/SKILL.md` and can be copied to any Cursor skills folder.
- Do not commit `.env` or `.cursor/mcp.json` (use `.cursor/mcp.json.example` as a template).

## MCP tools

| Tool | Description |
|------|-------------|
| `memory_search` | Hybrid search (dense + sparse/BM25). Returns facts with `created_at`. |
| `memory_upsert` | Store facts; server sets embeddings and `created_at`. |
| `graph_query` | Run read-only Cypher on Memgraph. |
| `graph_add_fact` | Add a fact (node/relation) with `created_at`. |

See `AGENTS.md` and `skill/uber-memory/SKILL.md` for when and how to use them.

## Development (Makefile)

- **Tests**: `make test`
- **Lint + format**: `make lint` or `make format`
- **Full check**: `make check` (lint + test)
- **Clean**: `make clean` (removes .venv, caches, .cursor/memory_context.md)

**Design**: See [docs/DESIGN.md](docs/DESIGN.md) for architecture and patterns.
