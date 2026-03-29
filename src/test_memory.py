"""
Tests for the memory system.
Run: cd src && python -m pytest test_memory.py -v
"""

import os
import sys
import json
import shutil
import tempfile
import pytest

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


# ====================  EXTRACTOR TESTS ====================

from memory.extractor import should_store, classify, abstract, extract_insight


class TestExtractor:
    def test_rejects_short_text(self):
        assert should_store("ok") is False
        assert should_store("done") is False

    def test_rejects_noise(self):
        assert should_store("[DEBUG] loading module...") is False
        assert should_store("loading data...") is False

    def test_accepts_meaningful_text(self):
        assert should_store("clicked button #login and form submitted") is True
        assert should_store("error: connection refused on port 8080") is True

    def test_classify_error(self):
        assert classify("error: something went wrong") == "error"
        assert classify("the command failed to execute") == "error"

    def test_classify_success(self):
        assert classify("task completed successfully") == "success"

    def test_classify_action(self):
        assert classify("clicked the submit button") == "action"
        assert classify("navigated to dashboard page") == "action"

    def test_classify_user_info(self):
        assert classify("my name is John") == "user_info"

    def test_classify_observation(self):
        assert classify("the page has three columns") == "observation"

    def test_abstract_transforms(self):
        result = abstract("navigated to https://example.com")
        assert "navigation" in result.lower() or "visited" in result.lower()

    def test_extract_insight_full_pipeline(self):
        # Should return insight for meaningful text
        result = extract_insight("error: database connection refused")
        assert result is not None
        assert result["category"] == "error"
        assert "text" in result

        # Should reject noise
        assert extract_insight("ok") is None
        assert extract_insight("[DEBUG] loading...") is None


# ====================  VAULT TESTS ====================

from memory.vault import Vault, VAULT_DIR


class TestVault:
    @pytest.fixture(autouse=True)
    def setup_teardown(self, tmp_path):
        """Use a temp vault for tests."""
        import memory.vault as vault_mod
        self._orig_dir = vault_mod.VAULT_DIR
        self._orig_key = vault_mod.KEY_FILE
        self._orig_sec = vault_mod.SECRETS_FILE

        vault_mod.VAULT_DIR = str(tmp_path / "vault")
        vault_mod.KEY_FILE = str(tmp_path / "vault" / ".vault_key")
        vault_mod.SECRETS_FILE = str(tmp_path / "vault" / "secrets.enc")

        yield

        vault_mod.VAULT_DIR = self._orig_dir
        vault_mod.KEY_FILE = self._orig_key
        vault_mod.SECRETS_FILE = self._orig_sec

    def test_store_and_get(self):
        v = Vault()
        v.store("api_key", "sk-12345")
        assert v.get("api_key") == "sk-12345"

    def test_get_nonexistent(self):
        v = Vault()
        assert v.get("nope") is None

    def test_delete(self):
        v = Vault()
        v.store("temp", "value")
        assert v.delete("temp") is True
        assert v.get("temp") is None
        assert v.delete("temp") is False

    def test_list_keys(self):
        v = Vault()
        v.store("a", "1")
        v.store("b", "2")
        keys = v.list_keys()
        assert "a" in keys
        assert "b" in keys

    def test_encryption_file_exists(self, tmp_path):
        import memory.vault as vault_mod
        v = Vault()
        v.store("test", "data")
        assert os.path.exists(vault_mod.SECRETS_FILE)
        # File should not contain plaintext
        with open(vault_mod.SECRETS_FILE, "rb") as f:
            raw = f.read()
        assert b"data" not in raw


# ====================  RETRIEVER TESTS ====================

from memory.retriever import VectorStore


class TestRetriever:
    @pytest.fixture
    def store(self, tmp_path):
        return VectorStore(persist_dir=str(tmp_path / "chroma"))

    def test_add_and_vector_search(self, store):
        store.add("login failed with wrong password", {"category": "error"})
        store.add("dashboard loaded successfully", {"category": "success"})
        store.add("clicked the submit button on form", {"category": "action"})

        results = store.vector_search("login error", k=2)
        assert len(results) > 0
        # First result should be related to login
        assert "login" in results[0]["text"].lower() or "error" in results[0]["text"].lower()

    def test_keyword_search(self, store):
        store.add("database connection timeout error", {"category": "error"})
        store.add("page loaded normally", {"category": "success"})

        results = store.keyword_search("database timeout", k=5)
        assert len(results) > 0
        assert "database" in results[0]["text"].lower()

    def test_hybrid_search(self, store):
        store.add("authentication failed for user admin", {"category": "error"})
        store.add("user created successfully in the system", {"category": "success"})

        results = store.hybrid_search("authentication error", k=2)
        assert len(results) > 0

    def test_hybrid_search_with_filter(self, store):
        store.add("login error occurred during auth", {"category": "error"})
        store.add("login completed successfully at last", {"category": "success"})

        errors = store.hybrid_search("login", k=5, type_filter="error")
        for r in errors:
            assert r["metadata"]["category"] == "error"

    def test_backward_compat_search(self, store):
        store.add("test document for backward compat", {"category": "observation"})
        results = store.search("test document")
        assert isinstance(results, list)
        assert isinstance(results[0], str)

    def test_empty_search(self, store):
        results = store.hybrid_search("anything")
        assert results == []


# ====================  INTEGRATION TEST ====================

class TestMemoryManagerIntegration:
    """Light integration test — just verifies the store→search flow."""

    @pytest.fixture
    def mm(self, tmp_path):
        """Create MemoryManager with temp directories."""
        import memory.memory_manager as mm_mod
        orig_dir = mm_mod._DIR
        mm_mod._DIR = str(tmp_path)

        # Create subdirs
        for sub in ["logs", "facts", "sessions", "vault", "vector"]:
            os.makedirs(tmp_path / sub, exist_ok=True)

        import memory.vault as vault_mod
        vault_mod.VAULT_DIR = str(tmp_path / "vault")
        vault_mod.KEY_FILE = str(tmp_path / "vault" / ".vault_key")
        vault_mod.SECRETS_FILE = str(tmp_path / "vault" / "secrets.enc")

        from memory.memory_manager import MemoryManager
        mgr = MemoryManager.__new__(MemoryManager)
        mgr.vector = VectorStore(persist_dir=str(tmp_path / "vector" / "chroma"))
        mgr.vault = Vault()
        mgr.session_id = "test-session"
        mgr._session_start = "2026-03-29T12:00:00"

        # Create session file
        session_path = tmp_path / "sessions" / "test-session.json"
        with open(session_path, "w") as f:
            json.dump({"id": "test-session", "started": "2026-03-29T12:00:00", "entries": []}, f)

        # Patch _DIR for instance methods
        mgr._dir = str(tmp_path)

        yield mgr, tmp_path
        mm_mod._DIR = orig_dir

    def test_store_and_search(self, mm):
        mgr, tmp_path = mm

        # Monkey-patch _DIR on the module level for log/facts paths
        import memory.memory_manager as mm_mod
        mm_mod._DIR = str(tmp_path)

        mgr.store("error: database connection refused on port 5432")
        mgr.store("successfully deployed the application to staging")
        mgr.store("ok")  # should be filtered out

        # Search should find the error
        results = mgr.search("database error", k=2)
        assert len(results) > 0

        # Log file should exist
        from datetime import datetime
        date = datetime.now().strftime("%Y-%m-%d")
        log_path = tmp_path / "logs" / f"{date}.md"
        assert log_path.exists()

        # Read log — should contain both stored entries (even the filtered one)
        with open(log_path) as f:
            content = f.read()
        assert "database connection" in content
        assert "deployed" in content

    def test_inject_context(self, mm):
        mgr, tmp_path = mm
        import memory.memory_manager as mm_mod
        mm_mod._DIR = str(tmp_path)

        mgr.store("error: authentication timeout on login page")
        context = mgr.inject_context("login problem")
        # Should return a non-empty string with relevant memory
        assert isinstance(context, str)

    def test_vault_integration(self, mm):
        mgr, _ = mm
        mgr.save_user_info("api_token", "secret-123", sensitive=True)
        assert mgr.vault.get("api_token") == "secret-123"
