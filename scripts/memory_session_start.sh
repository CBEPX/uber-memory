#!/usr/bin/env bash
# sessionStart hook: write a short memory summary to .cursor/memory_context.md
# so the agent has initial context. For deeper search the agent uses MCP memory_search.

set -e
CONTEXT_FILE=".cursor/memory_context.md"
mkdir -p .cursor

# If MCP/server not available or Qdrant down, leave a stub
if ! command -v curl &>/dev/null; then
  echo "# Project memory" > "$CONTEXT_FILE"
  echo "_Session summary skipped (curl not available)._" >> "$CONTEXT_FILE"
  exit 0
fi

# Try to get recent points from Qdrant (optional: requires collection and API)
if curl -sf "http://127.0.0.1:6333/collections/project_memory" &>/dev/null; then
  # Simple scroll for latest; in production the MCP can expose a "summary" endpoint
  echo "# Project memory (session summary)" > "$CONTEXT_FILE"
  echo "" >> "$CONTEXT_FILE"
  echo "Qdrant and Memgraph are available. Use MCP **memory_search** for task-specific retrieval." >> "$CONTEXT_FILE"
  echo "Stored facts include \`created_at\`; use them for recency." >> "$CONTEXT_FILE"
else
  echo "# Project memory" > "$CONTEXT_FILE"
  echo "" >> "$CONTEXT_FILE"
  echo "Start services with \`docker compose up -d\` and ensure the MCP server is running." >> "$CONTEXT_FILE"
fi
