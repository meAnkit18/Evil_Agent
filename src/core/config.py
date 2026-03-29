"""
Centralized configuration — loads .env and exposes all settings.
Single source of truth for API keys, model names, and feature flags.
"""

import os
from dotenv import load_dotenv

# Load .env from src/ directory
_SRC_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(_SRC_DIR, ".env"))


class Config:
    """Immutable configuration singleton."""

    # ─── API Keys ────────────────────────────────────────────────
    OPENROUTER_API_KEY: str = os.environ.get("OPENROUTER_API_KEY", "")
    NVIDIA_API_KEY: str = os.environ.get("NVIDIA_API_KEY", "")
    GROQ_API_KEY: str = os.environ.get("GROQ_API_KEY", "")

    # ─── Default LLM Provider ───────────────────────────────────
    # Priority: NVIDIA (primary) → GROQ → OPENROUTER
    @classmethod
    def get_api_key(cls) -> str:
        """Return the best available API key."""
        return cls.NVIDIA_API_KEY or cls.GROQ_API_KEY or cls.OPENROUTER_API_KEY

    @classmethod
    def get_provider(cls) -> str:
        """Return the active provider name."""
        if cls.NVIDIA_API_KEY:
            return "nvidia"
        if cls.GROQ_API_KEY:
            return "groq"
        if cls.OPENROUTER_API_KEY:
            return "openrouter"
        return "none"

    # ─── Model Defaults ─────────────────────────────────────────
    PLANNER_MODEL: str = os.environ.get("PLANNER_MODEL", "openai/gpt-oss-120b")
    ROUTER_MODEL: str = os.environ.get("ROUTER_MODEL", "openai/gpt-oss-120b")
    REPLY_MODEL: str = os.environ.get("REPLY_MODEL", "openai/gpt-oss-120b")

    # ─── Execution Limits ────────────────────────────────────────
    MAX_PLAN_STEPS: int = int(os.environ.get("MAX_PLAN_STEPS", "15"))
    MAX_RETRIES_PER_STEP: int = int(os.environ.get("MAX_RETRIES_PER_STEP", "3"))
    MAX_REPLANS: int = int(os.environ.get("MAX_REPLANS", "3"))
    STEP_TIMEOUT_SECONDS: int = int(os.environ.get("STEP_TIMEOUT_SECONDS", "60"))

    # ─── Feature Flags ──────────────────────────────────────────
    ENABLE_BROWSER: bool = os.environ.get("ENABLE_BROWSER", "true").lower() == "true"
    ENABLE_VISION: bool = os.environ.get("ENABLE_VISION", "false").lower() == "true"
    VERBOSE_LOGGING: bool = os.environ.get("VERBOSE_LOGGING", "true").lower() == "true"

    # ─── Paths ───────────────────────────────────────────────────
    SRC_DIR: str = _SRC_DIR
    PROJECT_DIR: str = os.path.dirname(_SRC_DIR)

    @classmethod
    def validate(cls) -> list[str]:
        """Return list of config issues (empty = all good)."""
        issues = []
        if not cls.get_api_key():
            issues.append("No API key found — set OPENROUTER_API_KEY, GROQ_API_KEY, or NVIDIA_API_KEY in .env")
        return issues

    @classmethod
    def summary(cls) -> str:
        """Pretty-print current config."""
        key = cls.get_api_key()
        key_preview = f"...{key[-6:]}" if key else "MISSING"
        return (
            f"Provider: {cls.get_provider()} ({key_preview})\n"
            f"Planner model: {cls.PLANNER_MODEL}\n"
            f"Max steps: {cls.MAX_PLAN_STEPS} | Max retries: {cls.MAX_RETRIES_PER_STEP} | Max replans: {cls.MAX_REPLANS}\n"
            f"Browser: {'ON' if cls.ENABLE_BROWSER else 'OFF'} | Vision: {'ON' if cls.ENABLE_VISION else 'OFF'}"
        )
