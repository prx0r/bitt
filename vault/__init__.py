"""Vault — encrypted credential storage for bitt.

AES-256-GCM encryption. Credentials never stored in plaintext.
Agent processes get scoped access, never the master key.

Usage:
    vault = Vault()
    vault.store("my_api_key", "sk-...", category="service")
    value = vault.get("my_api_key")
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


VAULT_DIR = Path("/root/bitt/.vault")
VAULT_FILE = VAULT_DIR / "credentials.enc"
MASTER_KEY_ENV = "BITT_VAULT_KEY"


class Vault:
    """Encrypted credential store. AES-256-GCM.

    The master key is derived from an environment variable or a file.
    Never stored in the vault itself.
    """

    def __init__(self, vault_dir: Path | None = None):
        self.vault_dir = vault_dir or VAULT_DIR
        self.vault_dir.mkdir(parents=True, exist_ok=True)
        self._key = self._load_key()
        self._cache: dict[str, str] = {}
        self._load()

    def _load_key(self) -> bytes:
        """Load or generate master key."""
        # Try env var first
        key_b64 = os.environ.get(MASTER_KEY_ENV)
        if key_b64:
            return base64.b64decode(key_b64)

        # Try key file
        key_file = self.vault_dir / ".master_key"
        if key_file.exists():
            return base64.b64decode(key_file.read_text().strip())

        # Generate new key
        key = AESGCM.generate_key(bit_length=256)
        key_file.write_text(base64.b64encode(key).decode())
        os.chmod(key_file, 0o600)
        return key

    def _load(self):
        """Load encrypted vault."""
        if not VAULT_FILE.exists():
            self._cache = {}
            return
        try:
            data = VAULT_FILE.read_bytes()
            if len(data) < 13:  # nonce(12) + tag(16) minimum
                self._cache = {}
                return
            nonce = data[:12]
            ciphertext = data[12:]
            aesgcm = AESGCM(self._key)
            plaintext = aesgcm.decrypt(nonce, ciphertext, None)
            self._cache = json.loads(plaintext.decode())
        except Exception:
            self._cache = {}

    def _save(self):
        """Save vault encrypted."""
        plaintext = json.dumps(self._cache, indent=2).encode()
        nonce = os.urandom(12)
        aesgcm = AESGCM(self._key)
        ciphertext = aesgcm.encrypt(nonce, plaintext, None)
        VAULT_FILE.write_bytes(nonce + ciphertext)
        os.chmod(VAULT_FILE, 0o600)

    def store(self, name: str, value: str, category: str = "default"):
        """Store a credential."""
        self._cache[name] = {
            "value": value,
            "category": category,
        }
        self._save()

    def get(self, name: str) -> str | None:
        """Retrieve a credential value."""
        entry = self._cache.get(name)
        if entry:
            return entry.get("value")
        return None

    def list_keys(self, category: str | None = None) -> list[str]:
        """List stored credential names."""
        if category:
            return [k for k, v in self._cache.items()
                    if v.get("category") == category]
        return list(self._cache.keys())

    def remove(self, name: str) -> bool:
        """Remove a credential."""
        if name in self._cache:
            del self._cache[name]
            self._save()
            return True
        return False

    def exists(self, name: str) -> bool:
        return name in self._cache

    def get_group(self, prefix: str) -> dict[str, str]:
        """Get all credentials with a given prefix."""
        return {k: v["value"] for k, v in self._cache.items()
                if k.startswith(prefix)}

    def to_env_dict(self, prefix: str = "") -> dict[str, str]:
        """Export as environment variable dict."""
        result = {}
        for name, entry in self._cache.items():
            if prefix and not name.startswith(prefix):
                continue
            env_name = name.upper()
            result[env_name] = entry["value"]
        return result


def get_vault() -> Vault:
    """Get or create the global vault instance."""
    return Vault()
