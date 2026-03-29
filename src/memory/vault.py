"""
Encrypted secrets vault using Fernet (AES-128-CBC).
Auto-generates key on first use. Secrets persist as encrypted JSON.
"""

import os
import json
from cryptography.fernet import Fernet

# Resolve paths relative to this file, not CWD
_DIR = os.path.dirname(os.path.abspath(__file__))
VAULT_DIR = os.path.join(_DIR, "vault")
KEY_FILE = os.path.join(VAULT_DIR, ".vault_key")
SECRETS_FILE = os.path.join(VAULT_DIR, "secrets.enc")


class Vault:
    def __init__(self):
        os.makedirs(VAULT_DIR, exist_ok=True)
        self._fernet = Fernet(self._load_or_create_key())

    # --- Key management ---

    def _load_or_create_key(self) -> bytes:
        if os.path.exists(KEY_FILE):
            with open(KEY_FILE, "rb") as f:
                return f.read()

        key = Fernet.generate_key()
        with open(KEY_FILE, "wb") as f:
            f.write(key)
        # restrict permissions (owner-only)
        os.chmod(KEY_FILE, 0o600)
        return key

    # --- Internal helpers ---

    def _read_secrets(self) -> dict:
        if not os.path.exists(SECRETS_FILE):
            return {}
        with open(SECRETS_FILE, "rb") as f:
            encrypted = f.read()
        decrypted = self._fernet.decrypt(encrypted)
        return json.loads(decrypted.decode())

    def _write_secrets(self, data: dict):
        raw = json.dumps(data).encode()
        encrypted = self._fernet.encrypt(raw)
        with open(SECRETS_FILE, "wb") as f:
            f.write(encrypted)

    # --- Public API ---

    def store(self, key: str, value: str):
        """Encrypt and persist a secret."""
        secrets = self._read_secrets()
        secrets[key] = value
        self._write_secrets(secrets)

    def get(self, key: str) -> str | None:
        """Decrypt and return a secret, or None."""
        secrets = self._read_secrets()
        return secrets.get(key)

    def delete(self, key: str) -> bool:
        """Remove a secret. Returns True if it existed."""
        secrets = self._read_secrets()
        if key in secrets:
            del secrets[key]
            self._write_secrets(secrets)
            return True
        return False

    def list_keys(self) -> list[str]:
        """List all stored secret keys (not values)."""
        return list(self._read_secrets().keys())
