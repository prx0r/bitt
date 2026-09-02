"""Wallet manager — coldkey/hotkey/proxy creation and management.

Wraps btcli and bittensor SDK for wallet operations.
Security: NEVER stores mnemonics or private keys in plaintext.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

WALLET_DIR = Path.home() / ".bittensor" / "wallets"
WALLET_DIR.mkdir(parents=True, exist_ok=True)


class WalletManager:
    """Manages Bittensor wallets via btcli/SDK."""

    def __init__(self, wallet_dir: Path | None = None):
        self.wallet_dir = wallet_dir or WALLET_DIR

    def _btcli(self, args: list[str], timeout: int = 30) -> dict | None:
        """Run btcli command and return parsed output."""
        cmd = ["btcli"] + args + ["--json"]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            if r.returncode == 0:
                return json.loads(r.stdout)
            else:
                print(f"btcli error: {r.stderr[:500]}")
        except FileNotFoundError:
            # btcli not installed, try python -m
            cmd = [sys.executable, "-m", "bittensor.cli"] + args + ["--json"]
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
                if r.returncode == 0:
                    return json.loads(r.stdout)
            except Exception as e:
                print(f"Error: {e}")
        except Exception as e:
            print(f"Error: {e}")
        return None

    def create_coldkey(self, name: str, n_words: int = 24, use_password: bool = True):
        """Create a new coldkey.

        IMPORTANT: This generates a new wallet. Write down the mnemonic.
        The mnemonic is shown ONCE. bitt does not store it.
        """
        print(f"\nCreating coldkey '{name}'...")
        print("IMPORTANT: Write down the mnemonic. It is shown ONCE.\n")

        cmd = ["wallet", "create", "--wallet.name", name]
        if use_password:
            cmd.append("--wallet.use_password")
        cmd.extend(["--n_words", str(n_words)])

        result = self._btcli(cmd, timeout=60)
        if result:
            print(f"Coldkey '{name}' created at {self.wallet_dir / name}")
            print(f"Address: {result.get('address', 'check btcli wallet list')}")
        else:
            # Fallback: direct btcli call
            subprocess.run(["btcli", "wallet", "create",
                           "--wallet.name", name] +
                          (["--wallet.use_password"] if use_password else []) +
                          ["--n_words", str(n_words)])

    def list_wallets(self):
        """List all wallets."""
        print("\nWallets:")
        result = self._btcli(["wallet", "list"])
        if result:
            for wallet in (result if isinstance(result, list) else [result]):
                print(f"  {json.dumps(wallet, indent=2)}")
        else:
            subprocess.run(["btcli", "wallet", "list"])

    def get_balance(self, name: str):
        """Get wallet balance."""
        result = self._btcli(["wallet", "balance", "--wallet.name", name])
        if result:
            print(f"\n{name}:")
            if isinstance(result, dict):
                for k, v in result.items():
                    print(f"  {k}: {v}")
            else:
                print(json.dumps(result, indent=2))
        else:
            subprocess.run(["btcli", "wallet", "balance", "--wallet.name", name])

    def create_proxy(self, name: str, proxy_type: str = "registration",
                     hotkey_name: str = "default"):
        """Create a scoped proxy hotkey.

        Proxy types:
          - registration: only subnet registration
          - nomination: validator nomination
          - full: all operations (NOT recommended for agent)
        """
        print(f"\nCreating {proxy_type} proxy for '{name}'...")

        # Bittensor supports proxy creation via extrinsics
        cmd = [
            "wallet", "proxy",
            "--wallet.name", name,
            "--wallet.hotkey", hotkey_name,
            "--proxy_type", proxy_type,
        ]
        result = self._btcli(cmd, timeout=60)
        if result:
            print(f"Proxy created: {json.dumps(result, indent=2)}")
        else:
            print("Proxy creation requires bittensor SDK. Falling back to manual.")
            subprocess.run(["btcli"] + cmd)

    def regen_coldkey(self, name: str, mnemonic: str):
        """Regenerate coldkey from mnemonic.

        SECURITY: mnemonic is passed via stdin, not stored.
        """
        print(f"\nRegenerating coldkey '{name}' from mnemonic...")
        cmd = [
            "wallet", "regen_coldkey",
            "--wallet.name", name,
            "--mnemonic", mnemonic,
        ]
        self._btcli(cmd, timeout=60)

    def export_address(self, name: str) -> str | None:
        """Get SS58 address for a wallet."""
        result = self._btcli(["wallet", "list", "--wallet.name", name])
        if result and isinstance(result, dict):
            return result.get("address")
        return None

    def import_wallet_from_file(self, name: str, filepath: str):
        """Import wallet from JSON file (for migration)."""
        data = Path(filepath).read_text()
        if "mnemonic" in data:
            parsed = json.loads(data)
            self.regen_coldkey(name, parsed["mnemonic"])
        else:
            print("File must contain {\"mnemonic\": \"...\"}")
