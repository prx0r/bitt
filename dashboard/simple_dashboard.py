"""Simple monitoring dashboard — terminal + optional web UI.

No React/Next.js needed. Pure Python + HTML.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

sys.path.insert(0, str(Path("/root/bitt/integration")))

from bittensor_gym.oracle.engine import BittensorOracle
from bittensor_gym.oracle.scanner import ScannerStore

DASHBOARD_HTML = """<!DOCTYPE html>
<html>
<head>
    <title>Bitt Dashboard</title>
    <meta http-equiv="refresh" content="300">
    <style>
        body { font-family: monospace; background: #1a1a2e; color: #e0e0e0; margin: 20px; }
        h1 { color: #00d4ff; }
        table { border-collapse: collapse; width: 100%; margin: 20px 0; }
        th, td { border: 1px solid #333; padding: 8px 12px; text-align: left; }
        th { background: #16213e; color: #00d4ff; }
        tr:nth-child(even) { background: #1a1a2e; }
        tr:nth-child(odd) { background: #0f3460; }
        .good { color: #00ff88; }
        .warn { color: #ffaa00; }
        .bad { color: #ff4444; }
        .rec { font-weight: bold; padding: 2px 8px; border-radius: 4px; }
        .rec-TRAIN { background: #004400; color: #00ff88; }
        .rec-CLONE { background: #003344; color: #00aaff; }
        .rec-REGISTER { background: #444400; color: #ffff00; }
        .rec-LIVE { background: #004400; color: #00ff88; }
        .rec-WATCH { background: #333; color: #aaa; }
        .rec-IGNORE { background: #222; color: #666; }
        #updated { color: #666; font-size: 0.8em; }
    </style>
</head>
<body>
    <h1>Bitt — Bittensor Operation Center</h1>
    <p id="updated">Updated: {timestamp}</p>

    <h2>Subnet Rankings</h2>
    <table>
        <tr>
            <th>Rank</th><th>SN</th><th>Name</th>
            <th>Recommendation</th><th>Econ</th><th>Lab</th>
            <th>Difficulty</th><th>Exp TAO/day</th><th>P(top5)</th>
            <th>Capital Risk</th><th>Confidence</th>
        </tr>
        {rows}
    </table>

    <h2>Quick Actions</h2>
    <pre>
bitt scan              # Full scan + daily report
bitt scan --json       # Machine-readable output
bitt subnet list       # List all tracked subnets
bitt subnet inspect --netuid 118  # Inspect Ditto
bitt register check --netuid 118  # Check registration burn
bitt register dry-run --netuid 118  # Simulate registration
bitt daemon start      # Start hourly scanner
bitt daemon status     # Check daemon
bitt report            # Generate daily report
bitt tools             # Show available tools
    </pre>

    <h2>Wallet</h2>
    <pre>
bitt wallet create     # Create new coldkey
bitt wallet list       # List wallets
bitt wallet balance --name default
bitt wallet proxy --name default --proxy-type registration
    </pre>
</body>
</html>"""


def generate_dashboard_html() -> str:
    """Generate dashboard HTML from latest oracle data."""
    oracle = BittensorOracle()
    result = oracle.run_full_scan()

    rows = []
    for a in result["assessments"]:
        rec_class = a.recommendation.split("_")[0] if "_" in a.recommendation else a.recommendation
        rows.append(f"""
        <tr>
            <td>{a.priority_rank}</td>
            <td>{a.netuid}</td>
            <td>{a.name}</td>
            <td><span class="rec rec-{rec_class}">{a.recommendation}</span></td>
            <td class="{'good' if a.economic_score > 0.5 else 'warn' if a.economic_score > 0.3 else 'bad'}">{a.economic_score:.3f}</td>
            <td class="{'good' if a.lab_value > 0.6 else 'warn' if a.lab_value > 0.4 else 'bad'}">{a.lab_value:.3f}</td>
            <td>{a.difficulty:.3f}</td>
            <td>{a.expected_tao_day:.3f}</td>
            <td>{a.p_top5:.2f}</td>
            <td class="{'good' if a.capital_risk < 0.3 else 'warn' if a.capital_risk < 0.6 else 'bad'}">{a.capital_risk:.3f}</td>
            <td>{a.confidence:.2f}</td>
        </tr>""")

    return DASHBOARD_HTML.format(
        timestamp=datetime.utcnow().isoformat(),
        rows="\n".join(rows),
    )


class DashboardHandler(SimpleHTTPRequestHandler):
    """HTTP handler for dashboard."""

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            html = generate_dashboard_html()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(html.encode())
        elif self.path == "/api/assessments":
            oracle = BittensorOracle()
            result = oracle.run_full_scan()
            data = [
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
                    "capital_risk": a.capital_risk,
                    "confidence": a.confidence,
                }
                for a in result["assessments"]
            ]
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(data, indent=2).encode())
        else:
            self.send_error(404)

    def log_message(self, format, *args):
        pass  # Silence request logs


def run_dashboard(port: int = 8501):
    """Run the web dashboard."""
    server = HTTPServer(("0.0.0.0", port), DashboardHandler)
    print(f"Dashboard running at http://localhost:{port}")
    print(f"API endpoint: http://localhost:{port}/api/assessments")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


def print_terminal_dashboard():
    """Print a terminal-based dashboard (no web server needed)."""
    oracle = BittensorOracle()
    result = oracle.run_full_scan()

    print("\n" + "=" * 90)
    print("BITT — BITTENSOR OPERATION CENTER")
    print(f"Updated: {datetime.utcnow().isoformat()}")
    print("=" * 90)

    header = f"{'Rank':<5} {'SN':<5} {'Name':<15} {'Rec':<20} {'Econ':<8} {'Lab':<8} {'Diff':<8} {'TAO/d':<10} {'P5':<6}"
    print(header)
    print("-" * 90)

    for a in result["assessments"]:
        print(
            f"{a.priority_rank:<5} {a.netuid:<5} {a.name:<15} {a.recommendation:<20} "
            f"{a.economic_score:<8.3f} {a.lab_value:<8.3f} {a.difficulty:<8.3f} "
            f"{a.expected_tao_day:<10.3f} {a.p_top5:<6.2f}"
        )

    print("-" * 90)
    print(f"Top: {result['assessments'][0].name} — {result['assessments'][0].recommendation}")
    print()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8501)
    parser.add_argument("--terminal", action="store_true", help="Print to terminal instead of web")
    args = parser.parse_args()

    if args.terminal:
        print_terminal_dashboard()
    else:
        run_dashboard(args.port)
