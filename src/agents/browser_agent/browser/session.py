"""
Credential / Session Manager — loads and provides credentials for sites.
LLM uses tokens like __CREDENTIAL_EMAIL__ which the action engine replaces.
"""

import json
import os
from typing import Optional
from urllib.parse import urlparse


class CredentialManager:
    """Load and provide credentials for specific sites."""

    def __init__(self, credentials_path: Optional[str] = None):
        self._credentials: list[dict] = []

        if credentials_path and os.path.exists(credentials_path):
            self._load(credentials_path)

    def _load(self, path: str):
        """Load credentials from a JSON file."""
        try:
            with open(path, "r") as f:
                data = json.load(f)
                if isinstance(data, list):
                    self._credentials = data
                elif isinstance(data, dict):
                    self._credentials = [data]
        except Exception as e:
            print(f"⚠️ Failed to load credentials: {e}")

    def get_for_site(self, url: str) -> dict:
        """
        Get credentials matching a URL's domain.
        Returns: {"email": "...", "password": "...", "username": "..."} or empty dict
        """
        try:
            parsed = urlparse(url)
            domain = parsed.hostname or ""
        except Exception:
            return {}

        for cred in self._credentials:
            site = cred.get("site", "")
            if site in domain or domain in site:
                return {
                    "email": cred.get("email", ""),
                    "password": cred.get("password", ""),
                    "username": cred.get("username", cred.get("email", "")),
                }

        return {}

    def add_credentials(self, site: str, email: str = "", password: str = "", username: str = ""):
        """Add credentials at runtime (not persisted)."""
        self._credentials.append({
            "site": site,
            "email": email,
            "password": password,
            "username": username or email,
        })
