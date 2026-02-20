"""
Tests for settings loading. Isolated from host env where possible.
"""

from __future__ import annotations

import pytest

from mcp_server.config import Settings, get_settings, init_settings


def test_settings_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """Defaults apply when env vars are unset."""
    for key in ("QDRANT_URL", "MEMGRAPH_BOLT_URI", "MEMORY_COLLECTION", "EMBEDDING_DIM"):
        monkeypatch.delenv(key, raising=False)
    # Create settings without init_settings (direct instantiation)
    s = Settings()
    assert s.qdrant_url == "http://127.0.0.1:6333"
    assert s.memgraph_bolt_uri == "bolt://127.0.0.1:7687"
    assert s.memory_collection == "project_memory"
    assert s.embedding_dim == 384


def test_settings_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Env vars override defaults."""
    monkeypatch.setenv("QDRANT_URL", "http://custom:6333")
    monkeypatch.setenv("MEMORY_COLLECTION", "custom_memory")
    s = Settings()
    assert s.qdrant_url == "http://custom:6333"
    assert s.memory_collection == "custom_memory"


def test_init_settings_singleton(monkeypatch: pytest.MonkeyPatch) -> None:
    """init_settings sets global singleton; get_settings returns it."""
    for key in ("QDRANT_URL", "MEMGRAPH_BOLT_URI", "MEMORY_COLLECTION", "EMBEDDING_DIM"):
        monkeypatch.delenv(key, raising=False)
    # Reset module state by re-importing would be heavy; instead we test that
    # init_settings returns a Settings and that we can call it once.
    from mcp_server import config

    old = config._settings
    config._settings = None
    try:
        s = init_settings()
        assert isinstance(s, Settings)
        assert get_settings() is s
    finally:
        config._settings = old
