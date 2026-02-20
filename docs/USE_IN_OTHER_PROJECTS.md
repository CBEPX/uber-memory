# Using Uber-Memory in Other Projects

Use the same Uber-Memory MCP server, skill, and (optionally) rules from **any other project** in Cursor. One instance of Qdrant and Memgraph on 127.0.0.1 serves all projects.

## Prerequisites

- Uber-Memory repo cloned and set up **once** on your machine.
- From the uber-memory directory: `make install` (or `make install-dev`) and `make up` so Qdrant and Memgraph are running.

## Step 1: Run services (once per machine/session)

From the **uber-memory** repo:

```bash
cd /path/to/uber-memory
make up
make status   # optional: check Qdrant and Memgraph
```

Leave the containers running. All your other projects use the same Qdrant and Memgraph.

## Step 2: Add MCP server in the other project

In your **other project** (e.g. `my-app`), create or edit `.cursor/mcp.json` so the MCP server runs with **cwd** set to the uber-memory directory.

Example `.cursor/mcp.json` in the other project:

```json
{
  "mcpServers": {
    "uber-memory": {
      "command": "uv",
      "args": ["run", "--project", "/absolute/path/to/uber-memory", "python", "-m", "mcp_server"],
      "cwd": "/absolute/path/to/uber-memory",
      "env": {
        "QDRANT_URL": "http://127.0.0.1:6333",
        "MEMGRAPH_BOLT_URI": "bolt://127.0.0.1:7687"
      }
    }
  }
}
```

Replace `/absolute/path/to/uber-memory` with the real path (e.g. `~/project/personal/uber-memory`).

- If you already have other MCP servers, add the `"uber-memory"` block inside `mcpServers` and keep the rest.
- Restart Cursor so it picks up the new server.

## Step 3: Enable the skill (once per machine)

**Option A – Symlink (from uber-memory repo):**

```bash
cd /path/to/uber-memory
make skill-link
```

This links `~/.cursor/skills/uber-memory` to the skill folder, so the skill is available in every Cursor project.

**Option B – Manual copy:**

Copy the folder `uber-memory/skill/uber-memory` to `~/.cursor/skills/uber-memory`.

## Step 4: Optional – Rule in the other project

To tell the agent to use memory at task start and when saving knowledge in **that project**, add a rule.

In the other project, create `.cursor/rules/memory.mdc` with the same content as in this repo’s `.cursor/rules/memory.mdc`, or copy that file.

## Step 5: Optional – SessionStart hook in the other project

To get a session summary (`.cursor/memory_context.md`) when you open the other project, add a hook that runs the script from uber-memory. Cursor usually runs hooks with the **workspace** as current directory, so the summary file is created in that project’s `.cursor/`.

In the other project, create or edit `.cursor/hooks.json`:

```json
{
  "version": 1,
  "hooks": {
    "sessionStart": [
      {
        "command": "/absolute/path/to/uber-memory/scripts/memory_session_start.sh",
        "matcher": ".*"
      }
    ]
  }
}
```

Replace `/absolute/path/to/uber-memory` with the real path. Ensure the script is executable (`chmod +x scripts/memory_session_start.sh` in the uber-memory repo).

## Summary

| Step | What | Where |
|------|------|--------|
| 1 | Start Qdrant + Memgraph | `make up` in uber-memory |
| 2 | Add MCP server with `cwd` = uber-memory path | Other project’s `.cursor/mcp.json` |
| 3 | Install skill (symlink or copy) | `make skill-link` or copy to `~/.cursor/skills/` |
| 4 | Optional: rule | Other project’s `.cursor/rules/memory.mdc` |
| 5 | Optional: sessionStart hook | Other project’s `.cursor/hooks.json` |

One Qdrant + Memgraph instance serves all projects; each project’s agent uses the same memory store. You can filter by `project_id` in the tools (`memory_search`, `memory_upsert`).

## Loading context with Resources

The server exposes read-only MCP resources that Cursor can automatically load to provide project context without explicit tool calls:

- `memory://project/context`: Returns recent memory.
  - Optional query parameter `project_id` limits it to a specific project.
  - Optional query parameter `scope` controls cross-project context:
    - `scope=current` (default): Only the requested `project_id`.
    - `scope=cross`: The requested project plus a summarized view of up to 3 other projects.
    - `scope=all`: Summarized view of all projects.
  - Example URI: `memory://project/context?project_id=my-app&scope=cross`
- `memory://graph/schema`: Returns a markdown summary of node labels and relationship types available in Memgraph.
