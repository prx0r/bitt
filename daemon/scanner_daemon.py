"""Scanner daemon — continuous monitoring of Bittensor subnets.

Runs hourly scans, detects material changes, triggers alerts.
Stores all snapshots in SQLite for history.
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path("/root/bitt/integration")))

from bittensor_gym.oracle.engine import BittensorOracle, TARGET_SUBNETS
from bittensor_gym.oracle.scanner import ScannerStore
from bittensor_gym.config import SUBNETS

PID_FILE = Path("/root/bitt/daemon.pid")
LOG_FILE = Path("/root/bitt/daemon.log")
ALERT_THRESHOLDS = {
    "burn_change_pct": 25,        # alert if burn changes >25%
    "pool_change_pct": 15,        # alert if pool changes >15%
    "new_champion": True,         # alert on champion change
    "recommendation_change": True, # alert on rec change
}


class ScannerDaemon:
    """Continuous subnet scanner with alerting."""

    def __init__(self):
        self.store = ScannerStore()
        self.oracle = BittensorOracle()
        self._running = False

    def start(self, interval_minutes: int = 60):
        """Start daemon in background."""
        if self._is_running():
            print("Daemon already running.")
            return

        print(f"Starting scanner daemon (interval={interval_minutes}m)...")

        # Fork to background
        pid = os.fork()
        if pid > 0:
            # Parent
            PID_FILE.write_text(str(pid))
            print(f"Daemon started (PID {pid})")
            return
        else:
            # Child
            os.setsid()
            self._run_loop(interval_minutes)

    def stop(self):
        """Stop daemon."""
        if not PID_FILE.exists():
            print("No daemon running.")
            return

        pid = int(PID_FILE.read_text().strip())
        try:
            os.kill(pid, signal.SIGTERM)
            PID_FILE.unlink()
            print(f"Daemon stopped (PID {pid})")
        except ProcessLookupError:
            print(f"Process {pid} not found. Cleaning up.")
            PID_FILE.unlink()

    def status(self):
        """Check daemon status."""
        if not PID_FILE.exists():
            print("Daemon not running.")
            return

        pid = int(PID_FILE.read_text().strip())
        try:
            os.kill(pid, 0)
            print(f"Daemon running (PID {pid})")
        except ProcessLookupError:
            print(f"PID {pid} exists but process not found. Cleaning up.")
            PID_FILE.unlink()

    def run_once(self):
        """Run a single scan cycle."""
        print(f"[{datetime.utcnow().isoformat()}] Running scan...")
        start = time.time()

        result = self.oracle.run_full_scan()

        duration = time.time() - start
        n_assessed = len(result["assessments"])
        n_flags = sum(len(a.discrepancy_flags) if hasattr(a, 'discrepancy_flags') else 0
                      for a in result["assessments"])

        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "duration_s": round(duration, 2),
            "subnets_scanned": n_assessed,
            "flags": n_flags,
            "top_recommendation": result["assessments"][0].recommendation if result["assessments"] else "none",
        }

        self._log(json.dumps(log_entry))

        # Check for material changes
        alerts = self._detect_changes(result)
        if alerts:
            for alert in alerts:
                self._alert(alert)

        print(f"  Done in {duration:.1f}s. {n_assessed} subnets, {n_flags} flags.")

    def _run_loop(self, interval_minutes: int):
        """Main daemon loop."""
        self._running = True
        signal.signal(signal.SIGTERM, lambda *_: setattr(self, '_running', False))

        while self._running:
            try:
                self.run_once()
            except Exception as e:
                self._log(f"ERROR: {e}")

            # Sleep in small increments so we can catch SIGTERM
            for _ in range(interval_minutes * 60):
                if not self._running:
                    break
                time.sleep(1)

    def _detect_changes(self, result: dict) -> list[str]:
        """Detect material changes since last scan."""
        alerts = []
        for assessment in result["assessments"]:
            prev = self.store.get_latest(assessment.netuid)
            if not prev:
                continue

            # Check burn change
            if prev.registration_burn_tao > 0:
                curr_burn = float(prev.registration_burn_tao)
                # Would need current burn from scan — skip for now

            # Check pool change
            if prev.miner_pool_tao_equiv_day and prev.miner_pool_tao_equiv_day > 0:
                prev_pool = float(prev.miner_pool_tao_equiv_day)
                # Would need current pool from scan — skip for now

            # Check recommendation change
            if hasattr(prev, 'recommendation') and prev.recommendation != assessment.recommendation:
                alerts.append(
                    f"SN{assessment.netuid} {assessment.name}: "
                    f"recommendation changed '{prev.recommendation}' → '{assessment.recommendation}'"
                )

        return alerts

    def _log(self, message: str):
        """Write to daemon log."""
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a") as f:
            f.write(f"[{datetime.utcnow().isoformat()}] {message}\n")

    def _alert(self, message: str):
        """Send alert (log + optional Telegram)."""
        self._log(f"ALERT: {message}")
        print(f"  ALERT: {message}")

        # Telegram alert if configured
        tg_token = os.environ.get("TELEGRAM_BOT_TOKEN")
        tg_chat = os.environ.get("TELEGRAM_CHAT_ID")
        if tg_token and tg_chat:
            try:
                import http.client
                conn = http.client.HTTPSConnection("api.telegram.org", timeout=10)
                body = json.dumps({
                    "chat_id": tg_chat,
                    "text": f"🚨 Bittensor Alert\n{message}",
                })
                conn.request("POST", f"/bot{tg_token}/sendMessage",
                           body=body,
                           headers={"Content-Type": "application/json"})
                conn.getresponse()
                conn.close()
            except Exception:
                pass

    def _is_running(self) -> bool:
        if not PID_FILE.exists():
            return False
        pid = int(PID_FILE.read_text().strip())
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False

    def get_recent_logs(self, n: int = 50) -> list[str]:
        """Get recent log entries."""
        if not LOG_FILE.exists():
            return []
        lines = LOG_FILE.read_text().strip().split("\n")
        return lines[-n:]
