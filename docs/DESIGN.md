# Design Notes

Short architecture and patterns used in the MCP server (aligned with Python design, testing, and resilience skills).

## Module layout

- **config**: Typed settings from env (pydantic-settings). Single source of truth for URLs and collection params.
- **validators**: Pure validation of tool arguments; return error message or `None`. Testable without Qdrant/Memgraph.
- **qdrant_helpers** / **memgraph_helpers**: Storage only. No validation; assume callers pass valid data.
- **server**: MCP entrypoint; wires validation → helpers, logs one event per tool call (tool, duration_ms, outcome).

## Single responsibility

- Validators: “is this input valid?”
- Helpers: “perform this storage operation.”
- Server: “dispatch tool, validate, call helper, log.”

## Validation

- All tool arguments validated at the boundary (validators module). Invalid input returns a clear message to the client; no exception path for validation.
- Validation is unit-tested; no need for Qdrant/Memgraph in those tests.

## Resilience

- **ensure_collection** (Qdrant): up to 3 attempts with 1s delay on `ConnectionError`, `TimeoutError`, `OSError`. Other errors (e.g. bad config) are not retried.
- Retry is only in this one place (no double retry).

## Observability

- One log event per tool call in `call_tool`: `tool`, `duration_ms`, `outcome` (success/error). On error, `error` is logged in the same flow. Structured `extra={...}` for grep/aggregation.

## Testing

- **Unit**: Validators and config (defaults, env override). No external services.
- **Integration**: Not in repo; run manually against local Docker (Qdrant + Memgraph) if needed.
- AAA in tests: Arrange (args/fixtures), Act (call validator), Assert (error message or None).

## Anti-patterns avoided

- No hardcoded config: all in `Settings` and `.env`.
- No scattered timeouts/retries: single retry in `ensure_collection`.
- No logic in validation: validators return a string or `None`, no side effects.
