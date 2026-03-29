"""
Memory extractor — decides what to store, classifies it, and abstracts raw logs
into higher-level insights.

Pure rule-based (no LLM calls) to stay fast and hallucination-free.
"""

import re

# --- Noise patterns to reject ---
_NOISE = [
    r"^[\s\-\*]*$",                       # blank / decoration lines
    r"^\[?(INFO|DEBUG)\]",                 # debug spam
    r"^(ok|done|yes|no|y|n)$",            # one-word acks
    r"(loading|fetching|connecting).*\.\.\.",  # progress indicators
]
_NOISE_RE = [re.compile(p, re.IGNORECASE) for p in _NOISE]

# --- Classification keywords ---
_CATEGORIES = {
    "error":     ["error", "exception", "traceback", "failed", "crash", "fatal"],
    "success":   ["success", "completed", "done", "passed", "created"],
    "action":    ["clicked", "navigated", "typed", "submitted", "executed", "ran", "opened"],
    "user_info": ["name is", "email is", "prefer", "i am", "i'm", "my "],
}

# --- Abstraction rules (pattern → higher-level meaning) ---
_ABSTRACTIONS = [
    (r"clicked (?:button |btn )?[#.]?(\S+)",   r"UI interaction: activated \1"),
    (r"navigated to (.+)",                      r"navigation: visited \1"),
    (r"typed (.+) (?:in|into) (.+)",            r"input: entered data into \2"),
    (r"executed (?:command )?[`'\"]?(.+?)[`'\"]?$", r"command execution: \1"),
    (r"error.*?:\s*(.+)",                       r"error encountered: \1"),
    (r"login|logged in|sign.?in",               r"authentication action attempted"),
    (r"timeout|timed out",                      r"operation timed out — may need retry or wait"),
]
_ABSTRACTIONS_RE = [(re.compile(p, re.IGNORECASE), r) for p, r in _ABSTRACTIONS]


def should_store(text: str) -> bool:
    """Gate: reject noise, keep only meaningful content."""
    text = text.strip()

    # too short = noise
    if len(text) < 15:
        return False

    # match any noise pattern = reject
    for pat in _NOISE_RE:
        if pat.search(text):
            return False

    return True


def classify(text: str) -> str:
    """Categorize text into a memory type."""
    lower = text.lower()

    for category, keywords in _CATEGORIES.items():
        if any(kw in lower for kw in keywords):
            return category

    return "observation"


def abstract(text: str) -> str:
    """Turn raw log into a higher-level insight."""
    for pat, replacement in _ABSTRACTIONS_RE:
        match = pat.search(text)
        if match:
            return pat.sub(replacement, text).strip()

    # no specific pattern matched — keep as-is with category prefix
    return text.strip()


def extract_insight(text: str) -> dict | None:
    """
    Full pipeline: filter → classify → abstract.
    Returns dict with keys: text, category, raw
    Returns None if text should not be stored.
    """
    if not should_store(text):
        return None

    category = classify(text)
    abstracted = abstract(text)

    return {
        "text": abstracted,
        "category": category,
        "raw": text.strip(),
    }