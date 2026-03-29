"""
Memory Manager — unified interface for the memory system.

Flow: action → log (file) → filter → classify/abstract → store (facts + vector)
Later: hybrid search → inject relevant memory into LLM prompt.
"""

import os
import json
import uuid
from datetime import datetime

from memory.extractor import extract_insight, classify
from memory.retriever import VectorStore
from memory.vault import Vault

# Resolve paths relative to this file
_DIR = os.path.dirname(os.path.abspath(__file__))


class MemoryManager:
    def __init__(self, session_id: str | None = None):
        self.vector = VectorStore()
        self.vault = Vault()
        self.session_id = session_id or uuid.uuid4().hex[:12]
        self._session_start = datetime.now().isoformat()

        # Ensure directories exist
        for sub in ["logs", "facts", "sessions"]:
            os.makedirs(os.path.join(_DIR, sub), exist_ok=True)

        # Start session log
        self._log_session_start()

    # ===================== LOGGING (file-first) =====================

    def log(self, text: str):
        """Append raw log to today's markdown file."""
        date = datetime.now().strftime("%Y-%m-%d")
        path = os.path.join(_DIR, "logs", f"{date}.md")
        ts = datetime.now().strftime("%H:%M:%S")

        with open(path, "a") as f:
            f.write(f"- [{ts}] {text}\n")

    # ===================== SESSION TRACKING =====================

    def _log_session_start(self):
        """Create a session entry."""
        path = os.path.join(_DIR, "sessions", f"{self.session_id}.json")
        data = {
            "id": self.session_id,
            "started": self._session_start,
            "entries": [],
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def _append_to_session(self, entry: dict):
        """Add an entry to the current session file."""
        path = os.path.join(_DIR, "sessions", f"{self.session_id}.json")
        if not os.path.exists(path):
            return

        with open(path, "r") as f:
            data = json.load(f)

        data["entries"].append({
            "time": datetime.now().isoformat(),
            **entry,
        })

        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    # ===================== STORE MEMORY =====================

    def store(self, raw_text: str, metadata: dict | None = None):
        """
        Full pipeline:
        1. Log raw text to file
        2. Filter (reject noise)
        3. Classify + abstract
        4. Store in vector DB + session
        """
        meta = metadata or {}

        # 1. Always log raw (file-first)
        self.log(raw_text)

        # 2-3. Extract insight (filter + classify + abstract)
        insight = extract_insight(raw_text)

        if not insight:
            return  # Rejected by filter — too noisy

        # Add session context
        meta["category"] = insight["category"]
        meta["session_id"] = self.session_id

        # 4. Store in vector DB
        self.vector.add(insight["text"], meta)

        # 4b. Track in session
        self._append_to_session({
            "category": insight["category"],
            "text": insight["text"],
        })

        # 4c. Auto-extract user info to facts
        if insight["category"] == "user_info":
            self._store_fact("auto_extracted", insight["text"])

    # ===================== FACTS =====================

    def _store_fact(self, key: str, value):
        """Persist a fact to the facts JSON store."""
        path = os.path.join(_DIR, "facts", "user_profile.json")

        data = {}
        if os.path.exists(path):
            with open(path, "r") as f:
                data = json.load(f)

        # For auto-extracted facts, append to a list
        if key == "auto_extracted":
            facts = data.get("auto_extracted", [])
            if value not in facts:  # dedup
                facts.append(value)
            data["auto_extracted"] = facts
        else:
            data[key] = value

        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def save_user_info(self, key: str, value: str, sensitive: bool = False):
        """Save user info — sensitive data goes to vault, rest to facts."""
        if sensitive:
            self.vault.store(key, value)
        else:
            self._store_fact(key, value)

    def get_user_info(self, key: str) -> str | None:
        """Retrieve user info from facts or vault."""
        path = os.path.join(_DIR, "facts", "user_profile.json")

        if os.path.exists(path):
            with open(path, "r") as f:
                data = json.load(f)
                if key in data:
                    return data[key]

        return self.vault.get(key)

    # ===================== SEARCH =====================

    def search(self, query: str, k: int = 5, type_filter: str | None = None) -> list[dict]:
        """Hybrid search with optional category filter."""
        return self.vector.hybrid_search(query, k=k, type_filter=type_filter)

    # ===================== CONTEXT INJECTION =====================

    def inject_context(self, query: str, k: int = 3) -> str:
        """
        Single call to get relevant memory formatted for an LLM prompt.
        Returns a string you can paste directly into the system/user message.
        """
        results = self.search(query, k=k)
        facts = self._load_facts()

        lines = []

        if facts:
            lines.append("## Known Facts")
            for key, val in facts.items():
                if key == "auto_extracted":
                    for item in val[-5:]:  # last 5 auto facts
                        lines.append(f"- {item}")
                else:
                    lines.append(f"- {key}: {val}")

        if results:
            lines.append("\n## Relevant Memory")
            for r in results:
                cat = r.get("metadata", {}).get("category", "")
                prefix = f"[{cat}] " if cat else ""
                lines.append(f"- {prefix}{r['text']}")

        if not lines:
            return ""

        return "\n".join(lines)

    def _load_facts(self) -> dict:
        """Load all facts from disk."""
        path = os.path.join(_DIR, "facts", "user_profile.json")
        if os.path.exists(path):
            with open(path, "r") as f:
                return json.load(f)
        return {}

    # ===================== SESSION INFO =====================

    def get_session_summary(self) -> dict:
        """Get current session info."""
        path = os.path.join(_DIR, "sessions", f"{self.session_id}.json")
        if os.path.exists(path):
            with open(path, "r") as f:
                return json.load(f)
        return {"id": self.session_id, "entries": []}