#!/usr/bin/env bash
# bitt setup — install dependencies and verify tooling
set -euo pipefail

BITT_ROOT="$(cd "$(dirname "$0")" && pwd)"
echo "=== Bitt Setup ==="
echo "Root: $BITT_ROOT"

# 1. Python deps
echo ""
echo "--- Python packages ---"
pip install --quiet httpx sqlite3 2>/dev/null || true

# 2. Check btcli
echo ""
echo "--- btcli ---"
if command -v btcli &>/dev/null; then
    echo "  btcli: $(btcli --version 2>/dev/null || echo 'installed')"
elif python3 -c "import bittensor" 2>/dev/null; then
    echo "  bittensor SDK installed"
else
    echo "  WARNING: btcli/bittensor not installed"
    echo "  Install: pip install bittensor"
fi

# 3. Check bitt CLI
echo ""
echo "--- bitt CLI ---"
if [ -f "$BITT_ROOT/cli/bitt.py" ]; then
    echo "  bitt CLI: $BITT_ROOT/cli/bitt.py"
    echo "  Usage: python3 $BITT_ROOT/cli/bitt.py <command>"
    echo "  Or alias: alias bitt='python3 $BITT_ROOT/cli/bitt.py'"
fi

# 4. Wallet directory
echo ""
echo "--- Wallet ---"
WALLET_DIR="${WALLET_DIR:-$HOME/.bittensor/wallets}"
mkdir -p "$WALLET_DIR"
echo "  Wallet dir: $WALLET_DIR"

# 5. Integration package
echo ""
echo "--- Integration ---"
if python3 -c "import sys; sys.path.insert(0, '$BITT_ROOT/integration'); from bittensor_gym import config" 2>/dev/null; then
    echo "  bittensor_gym: OK"
else
    echo "  bittensor_gym: import check failed (may need mwgym/workerkit in path)"
fi

# 6. .env
echo ""
echo "--- Environment ---"
if [ -f "$BITT_ROOT/.env" ]; then
    echo "  .env: exists"
else
    echo "  .env: missing (copy .env.template)"
    cp "$BITT_ROOT/.env.template" "$BITT_ROOT/.env"
    echo "  Created .env from template — edit with your keys"
fi

# 7. Quick test
echo ""
echo "--- Quick test ---"
python3 "$BITT_ROOT/cli/bitt.py" tools 2>/dev/null | head -20

echo ""
echo "=== Setup complete ==="
echo ""
echo "Quick start:"
echo "  python3 $BITT_ROOT/cli/bitt.py tools      # show all tools"
echo "  python3 $BITT_ROOT/cli/bitt.py scan        # scan subnets"
echo "  python3 $BITT_ROOT/cli/bitt.py subnet list # list tracked subnets"
echo "  python3 $BITT_ROOT/cli/bitt.py report      # daily report"
