"""bitt — Bittensor operation center. One CLI to rule all subnets.

Wraps: btcli, btt (Rust), subnet repos, oracle, wallet, dashboard.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

BITT_ROOT = Path(__file__).parent.parent
TOOLING = BITT_ROOT / "tooling"
CORE = BITT_ROOT / "core"
SUBNETS = BITT_ROOT / "subnets"
INTEGRATION = BITT_ROOT / "integration"

# Add integration to path
sys.path.insert(0, str(INTEGRATION))


def _run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, **kwargs)


def cmd_wallet(args):
    """Wallet operations."""
    from wallet.manager import WalletManager
    wm = WalletManager()

    if args.wallet_action == "create":
        name = input("Wallet name: ") if not args.name else args.name
        wm.create_coldkey(name)
    elif args.wallet_action == "list":
        wm.list_wallets()
    elif args.wallet_action == "balance":
        name = args.name or "default"
        wm.get_balance(name)
    elif args.wallet_action == "proxy":
        name = args.name or "default"
        wm.create_proxy(name, args.proxy_type or "registration")
    else:
        print(f"Unknown wallet action: {args.wallet_action}")


def cmd_scan(args):
    """Run subnet scanner."""
    from bittensor_gym.oracle.engine import BittensorOracle

    oracle = BittensorOracle()
    netuids = [int(n) for n in args.subnets.split(",")] if args.subnets else None
    result = oracle.run_full_scan(netuids)

    if args.json:
        print(json.dumps({
            "generated_at": result["generated_at"],
            "assessments": [
                {
                    "rank": a.priority_rank,
                    "name": a.name,
                    "netuid": a.netuid,
                    "recommendation": a.recommendation,
                    "economic_score": a.economic_score,
                    "lab_value": a.lab_value,
                    "difficulty": a.difficulty,
                    "expected_tao_day": a.expected_tao_day,
                    "p_top5": a.p_top5,
                }
                for a in result["assessments"]
            ]
        }, indent=2))
    else:
        print(result["daily_report"])


def cmd_register(args):
    """Register on a subnet."""
    from wallet.registration import RegistrationManager
    rm = RegistrationManager()

    if args.dry_run:
        rm.dry_run(args.netuid)
    elif args.action == "check":
        rm.check_burn(args.netuid)
    elif args.action == "register":
        rm.register(args.netuid, wallet_name=args.wallet or "default")
    elif args.action == "cost":
        rm.estimate_cost(args.netuid)
    else:
        print(f"Unknown register action: {args.action}")


def cmd_miner(args):
    """Run a miner on a subnet."""
    subnet_dir = SUBNETS / f"sn{args.netuid}-*"
    matches = list(SUBNETS.glob(f"sn{args.netuid}-*"))
    if not matches:
        print(f"No cloned subnet found for SN{args.netuid}")
        return

    subnet_path = matches[0]
    print(f"Running miner on {subnet_path.name}...")

    # Check for miner script
    for script in ["run_miner.sh", "miner.py", "neurons/miner.py"]:
        p = subnet_path / script
        if p.exists():
            if script.endswith(".sh"):
                subprocess.run(["bash", str(p)], cwd=str(subnet_path))
            else:
                subprocess.run([sys.executable, str(p)], cwd=str(subnet_path))
            return

    print(f"No miner script found in {subnet_path}")
    print(f"Available files: {[f.name for f in subnet_path.iterdir() if f.is_file()][:10]}")


def cmd_daemon(args):
    """Start/stop/status the scanner daemon."""
    from daemon.scanner_daemon import ScannerDaemon
    daemon = ScannerDaemon()

    if args.daemon_action == "start":
        daemon.start(interval_minutes=args.interval)
    elif args.daemon_action == "stop":
        daemon.stop()
    elif args.daemon_action == "status":
        daemon.status()
    elif args.daemon_action == "run":
        # Single run, no daemon
        daemon.run_once()
    else:
        print(f"Unknown daemon action: {args.daemon_action}")


def cmd_dashboard(args):
    """Launch the monitoring dashboard."""
    port = args.port or 8501
    print(f"Starting Bittensor dashboard on http://localhost:{port}")

    # Try bittensor-labs dashboard first
    labs_dir = TOOLING / "bittensor-labs-dashboard"
    if (labs_dir / "package.json").exists():
        print(f"Using bittensor-labs dashboard from {labs_dir}")
        subprocess.run(["npm", "run", "dev"], cwd=str(labs_dir))
        return

    # Fallback: simple Python dashboard
    from dashboard.simple_dashboard import run_dashboard
    run_dashboard(port=port)


def cmd_report(args):
    """Generate daily report."""
    from bittensor_gym.oracle.engine import BittensorOracle

    oracle = BittensorOracle()
    result = oracle.run_full_scan()

    report_path = BITT_ROOT / "reports"
    report_path.mkdir(exist_ok=True)

    from datetime import datetime
    filename = f"report-{datetime.utcnow().strftime('%Y-%m-%d')}.md"
    filepath = report_path / filename
    filepath.write_text(result["daily_report"])

    print(f"Report saved to {filepath}")
    print(result["daily_report"])


def cmd_subnet(args):
    """List/inspect subnets."""
    if args.subnet_action == "list":
        from bittensor_gym.config import SUBNETS as cfg_subnets
        print(f"{'SN':<5} {'Name':<15} {'Family':<30} {'Burn':<10} {'Pool/day':<12}")
        print("-" * 72)
        for netuid, cfg in sorted(cfg_subnets.items()):
            print(f"{netuid:<5} {cfg.name:<15} {cfg.family_id:<30} "
                  f"{cfg.registration_cost_approx:<10.3f} {cfg.emission_per_day_approx:<12.1f}")

    elif args.subnet_action == "inspect":
        netuid = args.netuid
        if not netuid:
            print("--netuid required")
            return
        from bittensor_gym.oracle.engine import BittensorOracle
        oracle = BittensorOracle()
        result = oracle.run_full_scan([netuid])
        if result["assessments"]:
            a = result["assessments"][0]
            print(f"\nSN{netuid} — {a.name}")
            print(f"  Recommendation: {a.recommendation}")
            print(f"  Economic: {a.economic_score:.3f}")
            print(f"  Lab value: {a.lab_value:.3f}")
            print(f"  Difficulty: {a.difficulty:.3f}")
            print(f"  Expected: {a.expected_tao_day:.3f} TAO/day")
            print(f"  P(top5): {a.p_top5:.2f}")
            print(f"  Capital risk: {a.capital_risk:.3f}")
            print(f"  Reason: {a.recommendation_reason}")

    elif args.subnet_action == "clone":
        netuid = args.netuid
        if not netuid:
            print("--netuid required")
            return
        # Clone subnet repo
        from bittensor_gym.config import SUBNETS as cfg_subnets
        cfg = cfg_subnets.get(netuid)
        if cfg and cfg.official_repo:
            target = SUBNETS / f"sn{netuid}-{cfg.name.lower()}"
            if target.exists():
                print(f"Already cloned at {target}")
            else:
                print(f"Cloning {cfg.official_repo} → {target}")
                subprocess.run(["git", "clone", cfg.official_repo, str(target)])
        else:
            print(f"No official repo known for SN{netuid}")


def cmd_tools(args):
    """Show available tools."""
    print("\n=== Bittensor Tools in bitt ===\n")

    tools = [
        ("btt (Rust CLI)", TOOLING / "btt-rust-cli", "Wallet, stake, chain ops — fast JSON-native"),
        ("auto-register", TOOLING / "auto-register", "Multi-subnet registration bot"),
        ("bittensor-labs", TOOLING / "bittensor-labs-dashboard", "Terminal-style dashboard + ML predictions"),
        ("bittensor-dashboard", TOOLING / "bittensor-nextjs-dashboard", "Next.js subnet intelligence"),
        ("miner-spy", TOOLING / "miner-spy", "Decentralization analysis"),
        ("investing-agent", TOOLING / "investing-agent", "PM2 portfolio monitor + Telegram alerts"),
        ("metagraphed", TOOLING / "metagraphed", "Subnet integration registry + API"),
        ("OpenTaoAPI", TOOLING / "opentaoapi", "Self-hosted Taostats alternative"),
        ("chainwake", TOOLING / "chainwake", "Event-driven chain monitoring"),
        ("miner-automation", TOOLING / "miner-automation-toolkit", "RunPod/Vast.ai miner setup"),
        ("subtensor-labs", TOOLING / "subtensor-labs", "Portfolio + predictive analytics"),
    ]

    for name, path, desc in tools:
        status = "✓" if path.exists() else "✗"
        commits = ""
        if (path / ".git").exists():
            r = _run(["git", "-C", str(path), "rev-list", "--count", "HEAD"])
            commits = f" ({r.stdout.strip()} commits)" if r.returncode == 0 else ""
        print(f"  {status} {name:<30} {desc}{commits}")

    print(f"\n=== Core ===\n")
    core_tools = [
        ("btcli", CORE / "btcli", "Official Bittensor CLI"),
        ("bittensor SDK", CORE / "bittensor-sdk", "Python SDK (import bittensor)"),
        ("subnet template", CORE / "subnet-template", "Build your own subnet"),
        ("subtensor monorepo", CORE / "subtensor-monorepo", "Chain + SDK + docs"),
    ]
    for name, path, desc in core_tools:
        status = "✓" if path.exists() else "✗"
        print(f"  {status} {name:<30} {desc}")

    print(f"\n=== Subnets Cloned ===\n")
    for d in sorted(SUBNETS.iterdir()):
        if d.is_dir() and not d.name.startswith("."):
            print(f"  ✓ {d.name}")


def main():
    parser = argparse.ArgumentParser(
        prog="bitt",
        description="Bittensor operation center — wallet, scan, register, mine, monitor",
    )
    sub = parser.add_subparsers(dest="command")

    # wallet
    p_wallet = sub.add_parser("wallet", help="Wallet operations")
    p_wallet.add_argument("wallet_action", choices=["create", "list", "balance", "proxy"])
    p_wallet.add_argument("--name", help="Wallet name")
    p_wallet.add_argument("--proxy-type", help="Proxy type (registration, nomination)")

    # scan
    p_scan = sub.add_parser("scan", help="Scan subnets for opportunities")
    p_scan.add_argument("--subnets", help="Comma-separated netuids (default: all targets)")
    p_scan.add_argument("--json", action="store_true", help="JSON output")

    # register
    p_reg = sub.add_parser("register", help="Register on a subnet")
    p_reg.add_argument("action", choices=["check", "register", "cost"])
    p_reg.add_argument("--netuid", type=int, required=True)
    p_reg.add_argument("--wallet", help="Wallet name")
    p_reg.add_argument("--dry-run", action="store_true")

    # miner
    p_miner = sub.add_parser("miner", help="Run a miner")
    p_miner.add_argument("--netuid", type=int, required=True)

    # daemon
    p_daemon = sub.add_parser("daemon", help="Scanner daemon")
    p_daemon.add_argument("daemon_action", choices=["start", "stop", "status", "run"])
    p_daemon.add_argument("--interval", type=int, default=60, help="Minutes between scans")

    # dashboard
    p_dash = sub.add_parser("dashboard", help="Launch dashboard")
    p_dash.add_argument("--port", type=int, default=8501)

    # report
    sub.add_parser("report", help="Generate daily report")

    # subnet
    p_subnet = sub.add_parser("subnet", help="List/inspect/clone subnets")
    p_subnet.add_argument("subnet_action", choices=["list", "inspect", "clone"])
    p_subnet.add_argument("--netuid", type=int)

    # tools
    sub.add_parser("tools", help="Show available tools")

    args = parser.parse_args()

    commands = {
        "wallet": cmd_wallet,
        "scan": cmd_scan,
        "register": cmd_register,
        "miner": cmd_miner,
        "daemon": cmd_daemon,
        "dashboard": cmd_dashboard,
        "report": cmd_report,
        "subnet": cmd_subnet,
        "tools": cmd_tools,
    }

    if args.command in commands:
        commands[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
