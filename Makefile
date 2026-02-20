# Uber-Memory: one Makefile for setup, daily use, and development.
# Requirements: make, Docker, uv (https://docs.astral.sh/uv/)

.PHONY: help install install-dev work up down status run test lint format check clean \
        mcp-config skill-link use-in-other-projects

# Default target
help:
	@echo "Uber-Memory Makefile"
	@echo ""
	@echo "One command for work:"
	@echo "  make work          Install (if needed), start containers, show status. Use this to start the day."
	@echo ""
	@echo "Initial setup (once):"
	@echo "  make install       Create .venv, install deps, .env from example, fix script permissions."
	@echo "  make install-dev   Same + dev deps (pytest, ruff, mypy)."
	@echo ""
	@echo "Daily use:"
	@echo "  make up            Start Qdrant and Memgraph (Docker)."
	@echo "  make down          Stop containers."
	@echo "  make status        Show container and service health."
	@echo "  make run           Run MCP server (stdio); Cursor usually runs this automatically."
	@echo ""
	@echo "Development:"
	@echo "  make test          Run pytest."
	@echo "  make lint          Ruff check (fix) + format."
	@echo "  make format        Ruff format only."
	@echo "  make check         Lint + test."
	@echo ""
	@echo "Cursor integration:"
	@echo "  make mcp-config    Print instructions to add MCP server in Cursor."
	@echo "  make skill-link    Create symlink of skill into ~/.cursor/skills/uber-memory (if dir exists)."
	@echo ""
	@echo "Other:"
	@echo "  make clean         Remove .venv, __pycache__, .pytest_cache, memory_context.md."
	@echo "  make use-in-other-projects  Show how to use uber-memory from another project."
	@echo ""

# --- Initial setup ---

install: .venv .env
	@chmod +x scripts/memory_session_start.sh 2>/dev/null || true
	@echo "Install done. Run: make up && make status"

install-dev: install
	uv sync --extra dev
	@echo "Dev install done. Run: make check"

.venv:
	uv venv
	uv sync

.env:
	@if [ ! -f .env ]; then cp .env.example .env; echo "Created .env from .env.example"; else echo ".env already exists"; fi

# --- Daily use ---

# One command: ensure env + deps, start containers, show status. Idempotent.
work: install up status
	@echo ""
	@echo "Ready. Open this repo in Cursor; MCP will use memory_search/memory_upsert."
	@echo ""
	@echo "Example .cursor/mcp.json (copy to .cursor/mcp.json in this or another project):"
	@printf '%s\n' '{"mcpServers":{"uber-memory":{"command":"uv","args":["run","--project","'$(shell pwd)'","python","-m","mcp_server"],"cwd":"'$(shell pwd)'","env":{"QDRANT_URL":"http://127.0.0.1:6333","MEMGRAPH_BOLT_URI":"bolt://127.0.0.1:7687","MEMORY_RESOURCE_MAX_CHARS":"40000"}}}}'
	@echo ""

up:
	docker compose up -d

down:
	docker compose down

status:
	@echo "=== Docker containers ==="
	@docker compose ps 2>/dev/null || true
	@echo ""
	@echo "=== Qdrant (127.0.0.1:6333) ==="
	@curl -sf http://127.0.0.1:6333/collections 2>/dev/null && echo "OK" || echo "Not reachable"
	@echo ""
	@echo "=== Memgraph (bolt://127.0.0.1:7687) ==="
	@echo "Use mgconsole or a Bolt client to verify."

run: .venv
	uv run python -m mcp_server

# --- Development ---

test: .venv
	uv sync --extra dev 2>/dev/null || uv sync
	uv run pytest tests/ -v

lint: .venv
	uv run ruff check mcp_server/ tests/ --fix
	uv run ruff format mcp_server/ tests/

format: .venv
	uv run ruff format mcp_server/ tests/

check: lint test
	@echo "Lint and test passed."

# --- Cursor integration ---

mcp-config:
	@echo "Add MCP server in Cursor:"
	@echo "  1. Copy .cursor/mcp.json.example to .cursor/mcp.json in THIS repo,"
	@echo "     or in another project set \"cwd\" to the absolute path of uber-memory."
	@echo "  2. In .cursor/mcp.json use \"cwd\": \"$(shell cd . 2>/dev/null && pwd)\" for this repo,"
	@echo "     or \"cwd\": \"/path/to/uber-memory\" when using from another project."
	@echo "  3. Restart Cursor."

skill-link:
	@mkdir -p ~/.cursor/skills 2>/dev/null || true
	@if [ -d ~/.cursor/skills ]; then \
		rm -rf ~/.cursor/skills/uber-memory 2>/dev/null; \
		ln -sf "$(shell pwd)/skill/uber-memory" ~/.cursor/skills/uber-memory; \
		echo "Linked skill/uber-memory -> ~/.cursor/skills/uber-memory"; \
	else \
		echo "~/.cursor/skills not found; create it or copy skill/uber-memory manually."; \
	fi

# --- Clean ---

clean:
	rm -rf .venv
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache
	rm -f .cursor/memory_context.md
	@echo "Cleaned."

# --- Docs ---

use-in-other-projects:
	@echo "=== Using Uber-Memory in other projects ==="
	@echo ""
	@echo "1. Have uber-memory installed (clone repo, run 'make install', 'make up')."
	@echo ""
	@echo "2. In your OTHER project (e.g. my-app):"
	@echo "   - Create .cursor/mcp.json (or merge into existing) with:"
	@echo "     \"uber-memory\": {"
	@echo "       \"command\": \"uv\","
	@echo "       \"args\": [\"run\", \"--project\", \".\", \"python\", \"-m\", \"mcp_server\"],"
	@echo "       \"cwd\": \"$(shell pwd)\","
	@echo "       \"env\": { \"QDRANT_URL\": \"http://127.0.0.1:6333\", \"MEMGRAPH_BOLT_URI\": \"bolt://127.0.0.1:7687\" }"
	@echo "     }"
	@echo "   - Use the ABSOLUTE path of uber-memory for \"cwd\" so the server runs from that directory."
	@echo ""
	@echo "3. Enable the skill: copy skill/uber-memory to ~/.cursor/skills/uber-memory (or run 'make skill-link' from uber-memory)."
	@echo ""
	@echo "4. Optional: add a rule in the other project .cursor/rules/memory.mdc that tells the agent to use memory_search at task start and memory_upsert when saving knowledge (see this repo's .cursor/rules/memory.mdc)."
	@echo ""
	@echo "5. Ensure Qdrant and Memgraph are running (from uber-memory: make up). One instance serves all projects using the same .env endpoints."
	@echo ""
	@echo "See docs/USE_IN_OTHER_PROJECTS.md for full steps."
