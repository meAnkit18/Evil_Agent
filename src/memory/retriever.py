"""
Hybrid retriever — lightweight vector store + keyword search.

Uses TF-IDF style bag-of-words for semantic similarity (NO heavy ML models).
Fast on any hardware, persistent to disk, zero external API calls.
"""

import os
import re
import json
import math
from collections import Counter, OrderedDict

# Resolve storage path relative to this file
_DIR = os.path.dirname(os.path.abspath(__file__))
VECTOR_DIR = os.path.join(_DIR, "vector")
INDEX_FILE = os.path.join(VECTOR_DIR, "index.json")


def _tokenize(text: str) -> list[str]:
    """Simple word tokenizer — lowercase, strip punctuation."""
    return re.findall(r'[a-z0-9]+', text.lower())


def _cosine_sim(vec_a: dict, vec_b: dict) -> float:
    """Cosine similarity between two sparse vectors (word→count dicts)."""
    if not vec_a or not vec_b:
        return 0.0
    common = set(vec_a.keys()) & set(vec_b.keys())
    dot = sum(vec_a[k] * vec_b[k] for k in common)
    mag_a = math.sqrt(sum(v * v for v in vec_a.values()))
    mag_b = math.sqrt(sum(v * v for v in vec_b.values()))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


class VectorStore:
    def __init__(self, persist_dir: str | None = None):
        self._dir = persist_dir or VECTOR_DIR
        self._index_file = os.path.join(self._dir, "index.json")
        os.makedirs(self._dir, exist_ok=True)

        self._docs = self._load()  # list of {text, metadata, tokens}

    # --- Persistence ---

    def _load(self) -> list[dict]:
        if os.path.exists(self._index_file):
            with open(self._index_file, "r") as f:
                data = json.load(f)
            # Rebuild token counts from stored text
            for doc in data:
                doc["tokens"] = dict(Counter(_tokenize(doc["text"])))
            return data
        return []

    def _save(self):
        # Save without tokens (regenerated on load)
        to_save = [{"text": d["text"], "metadata": d["metadata"]} for d in self._docs]
        with open(self._index_file, "w") as f:
            json.dump(to_save, f, indent=2)

    # --- Write ---

    def add(self, text: str, metadata: dict | None = None):
        """Add a document with optional metadata."""
        meta = metadata or {}
        # Dedup by exact text
        for d in self._docs:
            if d["text"] == text:
                d["metadata"] = meta  # update metadata
                self._save()
                return

        self._docs.append({
            "text": text,
            "metadata": {k: str(v) for k, v in meta.items()},
            "tokens": dict(Counter(_tokenize(text))),
        })
        self._save()

    # --- Semantic search (TF-IDF cosine) ---

    def vector_search(self, query: str, k: int = 5) -> list[dict]:
        """Bag-of-words cosine similarity search."""
        if not self._docs:
            return []

        query_tokens = dict(Counter(_tokenize(query)))
        scored = []

        for doc in self._docs:
            sim = _cosine_sim(query_tokens, doc["tokens"])
            if sim > 0:
                scored.append({
                    "text": doc["text"],
                    "metadata": doc["metadata"],
                    "score": sim,
                    "source": "semantic",
                })

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:k]

    # --- Keyword search ---

    def keyword_search(self, query: str, k: int = 5) -> list[dict]:
        """Simple text-match search."""
        if not self._docs:
            return []

        keywords = [w.lower() for w in query.split() if len(w) > 2]
        if not keywords:
            return []

        scored = []
        for doc in self._docs:
            doc_lower = doc["text"].lower()
            hits = sum(1 for kw in keywords if kw in doc_lower)
            if hits > 0:
                scored.append({
                    "text": doc["text"],
                    "metadata": doc["metadata"],
                    "score": hits / len(keywords),
                    "source": "keyword",
                })

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:k]

    # --- Hybrid search (the main API) ---

    def hybrid_search(
        self, query: str, k: int = 5, type_filter: str | None = None
    ) -> list[dict]:
        """
        Combine semantic + keyword search, deduplicate, optionally filter by type.
        """
        semantic = self.vector_search(query, k=k * 2)
        keyword = self.keyword_search(query, k=k * 2)

        # Merge & deduplicate (semantic results ranked higher)
        seen = OrderedDict()
        for item in semantic:
            key = item["text"]
            if key not in seen:
                seen[key] = item

        for item in keyword:
            key = item["text"]
            if key not in seen:
                seen[key] = item
            else:
                # boost score if found by both methods
                seen[key]["score"] = min(1.0, seen[key].get("score", 0.5) + 0.2)

        results = list(seen.values())

        # Filter by category if requested
        if type_filter:
            results = [
                r for r in results
                if r.get("metadata", {}).get("category") == type_filter
            ]

        return results[:k]

    # --- Backward-compatible API ---

    def search(self, query: str, k: int = 5) -> list[str]:
        """Returns list of text strings (backward compatible)."""
        results = self.hybrid_search(query, k=k)
        return [r["text"] for r in results]

    def count(self) -> int:
        return len(self._docs)