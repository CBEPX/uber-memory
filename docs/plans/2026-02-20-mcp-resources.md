# MCP Resources Implementation Plan

> **For Claude:** When implementing, use superpowers:executing-plans (or writing-plans) task-by-task.

**Goal:** Expose read-only MCP resources so Cursor (or other clients) can load project memory context and graph schema by URI, without calling tools—enabling auto-context on project open and smaller tool payloads.

**Architecture:** Use the existing lowlevel MCP `Server`: add `@app.list_resources()` and `@app.read_resource()`. URI scheme `memory://` with paths: `memory://project/context`, `memory://project/context?project_id=...`, `memory://graph/schema`. Resources are computed on read (no static files). Optional: resource templates for parameterized URIs; later phase: tools may return `resource_link` for large results.

**Tech Stack:** mcp.types (Resource, ReadResourceResult, TextResourceContents), existing qdrant_helpers (hybrid_search), memgraph_helpers (run_cypher), Python 3.12+.

---

## Cross-project memory and context budget

**Requirement:** Allow using memory from other projects in the current one (e.g. conventions from repo A when working in repo B) without overloading the context window.

**Measures to avoid overload:**

1. **Scope parameter** for `memory://project/context`:
   - `scope=current` (default): only the given `project_id` (or no filter if project_id omitted — then backend returns one project’s worth, see below).
   - `scope=cross`: current project + a short summary from other projects (bounded total size).
   - `scope=all`: all projects with a strict global limit (e.g. total items or chars).

2. **Token/size budget:** One configurable cap for the whole resource body. Skills typically use ~500–3500 tokens each (~2–14 KB); memory should get a **larger** allocation so it can hold many facts. Default target: **~8000–12000 tokens** (≈32–48 KB at ~4 chars/token), configurable via env/settings (e.g. `MEMORY_RESOURCE_MAX_CHARS`). Use this cap (or `MAX_ITEMS` as fallback) when truncating. When `scope=cross` or `scope=all`, distribute the budget: e.g. for `cross`, give more items to the current project (e.g. 12), and fewer per “other” project (e.g. 2–3 per project, max 3 other projects). Format as markdown with clear `## Project: <id>` sections so the model knows which fact belongs to which project.

3. **Prioritization:** Within budget, prefer recency (already supported by `created_at` if we sort by it in hybrid_search or post-filter). Optionally prefer items that mention “convention”, “decision”, “gotcha” (already partly reflected in the search query).

4. **Convention for “current” project:** When the client (e.g. Cursor) opens a repo, it can pass `project_id` = repo path or a stable id. If `project_id` is omitted and scope is `current`, backend can either return nothing or the most recent N items without filter (document the behaviour). So “current only” is: `memory://project/context?project_id=<current_repo_id>` with `scope=current` (default).

5. **Tools (memory_search / memory_upsert):** No change required for cross-project in v1: they already support optional `project_id`. The resource layer adds the scoping and budget; tools remain the low-level API.

**Implementation outline for get_project_context:**

- Parse `scope` from query params: `current` | `cross` | `all` (default `current`).
- Parse `project_id` = “current” project (optional).
- If `scope=current`: hybrid_search(..., limit=current_limit, project_id=project_id). Cap output to MAX_CONTEXT_CHARS.
- If `scope=cross`: (1) hybrid_search for current project (e.g. limit=12); (2) list other project_ids (e.g. from Qdrant payloads or a dedicated small query); (3) for each of up to 3 others, hybrid_search(..., limit=2, project_id=other_id); (4) concatenate with `## Project: <id>` headers; (5) truncate to MAX_CONTEXT_CHARS.
- If `scope=all`: hybrid_search without project_id with limit=MAX_ITEMS, then group by project_id in the payload and format with headers; truncate to MAX_CONTEXT_CHARS.

Expose `scope` and `project_id` in the resource description and in docs so clients know how to request “current only” vs “current + others” without overloading context.

---

## URI scheme and resource list

| URI | Description | Implementation |
|-----|-------------|----------------|
| `memory://project/context` | Recent project memory (default: current project only). Optional: project_id, scope. | read_resource parses URI; get_project_context(project_id, scope) with token budget. |
| `memory://project/context?project_id={id}` | Same, explicit project. | project_id filter; scope=current by default. |
| `memory://project/context?project_id={id}&scope=cross` | Current project + short summary from other projects (bounded). | See “Cross-project memory” above. |
| `memory://project/context?scope=all` | All projects, strict global limit. | hybrid_search without project_id, format by project, truncate. |
| `memory://graph/schema` | Human-readable graph schema (node labels, relationship types). | run_cypher to introspect labels/relationship types, format as markdown. |

No resource templates in v1 (static list of resources only). Add templates in a follow-up if we want dynamic URIs (e.g. `memory://search/{query}`).

---

## Task 1: Resource types and list_resources

**Files:**
- Modify: `mcp_server/server.py` (imports, register list_resources)
- Create: `mcp_server/resources.py` (RESOURCE_LIST, URI constants)

**Step 1: Add resources module and URI constants**

Create `mcp_server/resources.py`:

- `SCHEME = "memory"`
- `PATH_PROJECT_CONTEXT = "project/context"`
- `PATH_GRAPH_SCHEMA = "graph/schema"`
- Helper `build_uri(path: str, query: dict[str, str] | None = None) -> str` returning `memory://path` or `memory://path?k=v`
- `RESOURCE_LIST: list[Resource]` with two entries (use `mcp.types.Resource`):
  - `uri=memory://project/context`, description="Recent project memory (decisions, conventions). Query: project_id (current project), scope=current|cross|all (default current). Cross/all use a token budget to avoid overload."
  - `uri=memory://graph/schema`, description="Graph schema: node labels and relationship types in Memgraph."
- Use `Resource(uri=..., name=..., description=...)`; ensure `uri` is a valid AnyUrl (e.g. from string `"memory://project/context"`). `mcp.types.Resource` has required `uri`; optional `name`, `description`, `mimeType`.

**Step 2: Register list_resources in server**

In `mcp_server/server.py`:

- Import `Resource` from `mcp.types` and `RESOURCE_LIST` from `.resources`.
- Add `@app.list_resources()` / `async def list_resources() -> list[Resource]: return RESOURCE_LIST`.

**Step 3: Manual smoke test**

Run server, connect with MCP client (or Cursor), call `list_resources` and assert two resources with the URIs above.

---

## Task 2: read_resource handler and URI routing

**Files:**
- Modify: `mcp_server/server.py` (read_resource handler)
- Modify: `mcp_server/resources.py` (parse_uri, route logic or keep routing in server)

**Step 1: URI parsing helper**

In `mcp_server/resources.py`:

- Add `parse_memory_uri(uri: AnyUrl) -> tuple[str, dict[str, str]]` returning (path, query_params). Path = uri.path or "/" (strip leading slash for comparison). Query params from `uri.query` (e.g. `urllib.parse.parse_qs`).

**Step 2: read_resource handler**

In `mcp_server/server.py`:

- Import `ReadResourceContents` from `mcp.server.lowlevel.helper_types`. Handler receives `uri: AnyUrl`, returns `Iterable[ReadResourceContents]` (e.g. `[ReadResourceContents(content=text, mime_type="text/plain")]`).
- Register `@app.read_resource()` async def read_resource(uri: AnyUrl): parse URI; if scheme != "memory" or host, return single content "Unsupported URI" (or 404-style message). Else dispatch by path to implementations in next tasks; for now return "Not implemented" for both paths.

**Step 3: Wire path dispatch**

- If path is `project/context`: call `get_project_context(project_id=query_params.get("project_id"), scope=query_params.get("scope", "current"))` (implement in Task 3).
- If path is `graph/schema`: call `get_graph_schema()` (implement in Task 4).
- Return one TextResourceContents (via ReadResourceContents) with the string result.

---

## Task 3: Resource memory://project/context (with scope and budget)

**Files:**
- Create or modify: `mcp_server/resource_handlers.py` (get_project_context, constants)
- Modify: `mcp_server/server.py` (call get_project_context from read_resource with scope)
- Use: `mcp_server/qdrant_helpers.py` (hybrid_search)

**Constants (resource_handlers or config):**

- `MAX_CONTEXT_CHARS`: configurable (env/settings). Default from target token budget for memory: **~10_000 tokens ≈ 40_000 chars** (larger than typical skill size so memory has room for many facts). Hard cap for the whole resource body.
- For `scope=cross`: current project limit=12, other projects max 3, limit=2 per other.
- For `scope=all`: total items cap (e.g. 25), then truncate to MAX_CONTEXT_CHARS.

**Step 1: get_project_context**

In `mcp_server/resource_handlers.py`:

- `async def get_project_context(project_id: str | None = None, scope: str = "current") -> str:`
- Normalize `scope` to one of `current`, `cross`, `all` (default `current`).
- **scope=current:** `hybrid_search("project decisions conventions gotchas", limit=15, project_id=project_id)`. Format as markdown list; truncate to MAX_CONTEXT_CHARS.
- **scope=cross:** (1) fetch current project (limit=12, project_id=project_id); (2) get list of other project_ids — e.g. in `qdrant_helpers` add `list_project_ids(limit=10)` that scrolls the collection and returns unique `project_id` from payloads (excluding current), or use a small hybrid_search without project_id and collect distinct project_ids from results; take up to 3 others; (3) for each other, hybrid_search(..., limit=2, project_id=other_id); (4) concatenate with `## Project: <id>` sections; (5) truncate to MAX_CONTEXT_CHARS.
- **scope=all:** hybrid_search(..., limit=25, project_id=None); group results by payload project_id; format with `## Project: <id>`; truncate to MAX_CONTEXT_CHARS.
- All I/O via `asyncio.to_thread(hybrid_search, ...)`. Return a single string (markdown).

**Step 2: Integrate in read_resource**

In `mcp_server/server.py`, when path is `project/context`, call `get_project_context(project_id=query_params.get("project_id"), scope=query_params.get("scope", "current"))` and return its result as resource content.

**Step 3: Test**

- Unit test: mock hybrid_search, call get_project_context with scope=current, assert output structure and length ≤ MAX_CONTEXT_CHARS.
- Unit test: scope=cross with two projects, assert two `## Project:` sections and bounded size.
- Manual: read_resource("memory://project/context?scope=cross") returns markdown with current + others, not oversized.

---

## Task 4: Resource memory://graph/schema

**Files:**
- Modify: `mcp_server/resource_handlers.py` (get_graph_schema)
- Modify: `mcp_server/memgraph_helpers.py` (optional: add run_cypher for introspection) or use existing run_cypher with CALL db.labels() / db.relationshipTypes() (Memgraph may support these or use equivalent).

**Step 1: Introspection queries**

Memgraph (Neo4j-compatible): `CALL db.labels()` and `CALL db.relationshipTypes()` or equivalent. If not available, use a safe `MATCH (n) RETURN DISTINCT labels(n)` and `MATCH ()-[r]->() RETURN DISTINCT type(r)` with LIMIT. Implement in `get_graph_schema()` in `mcp_server/resource_handlers.py`, using `run_cypher` via `asyncio.to_thread`.

**Step 2: get_graph_schema**

- `async def get_graph_schema() -> str:` returns markdown: "## Node labels\n- Label1\n- Label2\n\n## Relationship types\n- TYPE1\n- TYPE2".

**Step 3: Integrate and test**

- read_resource("memory://graph/schema") returns that markdown.
- Unit test with mocked run_cypher.

---

## Task 5: Tests and docs

**Files:**
- Create: `tests/test_resources.py` (test list_resources, test read_resource for both URIs with mocks)
- Modify: `docs/USE_IN_OTHER_PROJECTS.md` or `README` — add short "Resources" section: list URIs and usage (e.g. "Cursor can load memory://project/context on project open").

**Step 1: Tests**

- test_list_resources_returns_memory_uris
- test_read_resource_project_context_calls_hybrid_search (mock)
- test_read_resource_project_context_scope_cross_bounded (mock, assert sections and length)
- test_read_resource_graph_schema_returns_markdown (mock run_cypher)
- test_read_resource_unknown_path_returns_error_message

**Step 2: Docs**

- Subsection describing `memory://project/context` and `memory://graph/schema`.
- Document query params: `project_id` (current project), `scope=current|cross|all` and that cross/all keep context bounded (token budget).

---

## Optional / later phases

- **Resource templates:** `list_resource_templates()` with e.g. `memory://project/context{?project_id}` (RFC 6570) so clients can build URIs with parameters.
- **Tool returns resource_link:** For `memory_search` with large limit, return a `resource_link` to `memory://search/{request_id}` and store result in a short-lived cache; client reads resource to get full result (reduces tool result size).
- **Notifications:** If memory or graph changes, send `ResourceListChangedNotification` or `ResourceUpdatedNotification` so clients refresh (optional, lower priority).

---

## Checklist before implementation

- [ ] MCP SDK: `list_resources` returns `list[Resource]`; `read_resource(uri)` returns `Iterable[ReadResourceContents]` (content: str | bytes, mime_type, meta).
- [ ] AnyUrl: use `yarl.URL` or `pydantic.AnyUrl` for Resource.uri; in read_resource, `uri` is already AnyUrl, parse with `.path`, `.query`.
- [ ] No blocking in async: use `asyncio.to_thread(hybrid_search, ...)` and `asyncio.to_thread(run_cypher, ...)` in resource handlers.
- [ ] Cross-project: implement `scope=current|cross|all` and MAX_CONTEXT_CHARS; for scope=cross, add way to get other project_ids (e.g. `list_project_ids` in qdrant_helpers) and cap items per project.
