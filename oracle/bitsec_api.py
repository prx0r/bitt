"""Bitsec API — exposes everything Bitsec-related via REST.

Checkpoints:
  1. Subnet data + competition (chain)     ← WE ARE HERE
  2. Our submissions + tracking
  3. Leaderboard analysis
  4. Tool status (Slither/Mythril/etc)
  5. CGE experiment results

Endpoints:
  GET /api/bitsec/              — overview
  GET /api/bitsec/subnet        — live chain data
  GET /api/bitsec/competition   — who's winning, what it takes
  GET /api/bitsec/submissions   — our submission history
  GET /api/bitsec/tools         — tool status
  GET /api/bitsec/experiments   — CGE experiment results
  GET /api/bitsec/leaderboard   — current leaderboard
"""
from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, str(Path(__file__).parent.parent))
from oracle.capture import DB_PATH, get_latest_capture

PORT = 8402
NETUID = 60  # Bitsec


class BitsecHandler(SimpleHTTPRequestHandler):

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        params = parse_qs(parsed.query)

        routes = {
            "/api/bitsec": self.overview,
            "/api/bitsec/subnet": self.subnet_data,
            "/api/bitsec/competition": self.competition,
            "/api/bitsec/submissions": self.submissions,
            "/api/bitsec/tools": self.tools,
            "/api/bitsec/experiments": self.experiments,
            "/api/bitsec/leaderboard": self.leaderboard,
        }

        if path in routes:
            routes[path](params)
        else:
            self.send_error(404)

    def overview(self, params):
        """Bitsec overview — all key metrics in one call."""
        cap = get_latest_capture()
        subnet = cap.get("subnets", {}).get(str(NETUID), {}) if cap else {}

        self.send_json({
            "subnet": "Bitsec (SN60)",
            "block": cap.get("block_number") if cap else None,
            "chain": {
                "burn_tao": subnet.get("burn_tao", 0),
                "tempo": subnet.get("tempo", 360),
                "alpha_price": subnet.get("alpha_price", 0),
                "neuron_count": subnet.get("neuron_count", 0),
                "miner_count": subnet.get("miner_count", 0),
                "emitting_count": subnet.get("emitting_count", 0),
            },
            "economics": {
                "total_tao_day": subnet.get("total_tao_day", 0),
                "contestable_miner_tao_day": subnet.get("contestable_miner_tao_day", 0),
                "miner_tao_day": subnet.get("miner_tao_day", 0),
                "validator_tao_day": subnet.get("validator_tao_day", 0),
                "owner_cut_pct": subnet.get("owner_cut_pct", 18),
            },
            "competition": {
                "hhi": subnet.get("hhi", 0),
                "effective_earners": subnet.get("effective_earners", 0),
                "top_emitters": subnet.get("top_emitters", [])[:5],
            },
            "our_submissions": self._load_submissions(),
            "tools": self._load_tool_status(),
        })

    def subnet_data(self, params):
        """Live chain data for Bitsec."""
        cap = get_latest_capture()
        subnet = cap.get("subnets", {}).get(str(NETUID), {}) if cap else {}

        self.send_json({
            "netuid": NETUID,
            "name": "Bitsec",
            "block": cap.get("block_number") if cap else None,
            "chain": {
                "burn_tao": subnet.get("burn_tao", 0),
                "tempo": subnet.get("tempo", 360),
                "alpha_price": subnet.get("alpha_price", 0),
                "epochs_per_day": subnet.get("epochs_per_day", 20),
                "epoch_index": subnet.get("epoch_index", 0),
                "blocks_remaining": subnet.get("blocks_remaining", 0),
            },
            "neurons": {
                "total": subnet.get("neuron_count", 0),
                "active": subnet.get("active_count", 0),
                "validators": subnet.get("validator_count", 0),
                "miners": subnet.get("miner_count", 0),
                "emitting": subnet.get("emitting_count", 0),
            },
            "emissions": {
                "total_alpha_epoch": subnet.get("total_alpha_epoch", 0),
                "total_alpha_day": subnet.get("total_alpha_day", 0),
                "total_tao_day": subnet.get("total_tao_day", 0),
                "miner_alpha_epoch": subnet.get("miner_alpha_epoch", 0),
                "miner_tao_day": subnet.get("miner_tao_day", 0),
                "contestable_miner_tao_day": subnet.get("contestable_miner_tao_day", 0),
            },
            "hyperparams": subnet.get("hyperparams", {}),
            "identity": subnet.get("identity"),
            "weights": subnet.get("weights", {}),
            "bonds": subnet.get("bonds", {}),
        })

    def competition(self, params):
        """Competition analysis — what it takes to earn."""
        cap = get_latest_capture()
        subnet = cap.get("subnets", {}).get(str(NETUID), {}) if cap else {}

        emitters = subnet.get("top_emitters", [])
        contestable = subnet.get("contestable_miner_tao_day", 0)

        fifth = emitters[4] if len(emitters) >= 5 else None
        first = emitters[0] if emitters else None

        self.send_json({
            "netuid": NETUID,
            "contestable_miner_tao_day": contestable,
            "emitting_count": subnet.get("emitting_count", 0),
            "miner_count": subnet.get("miner_count", 0),
            "champion": {
                "uid": first.get("uid") if first else None,
                "incentive": first.get("incentive", 0) if first else 0,
                "tao_day": first.get("emission_tao_day", 0) if first else 0,
                "hotkey": first.get("hotkey", "")[:16] if first else "",
            },
            "fifth_place": {
                "uid": fifth.get("uid") if fifth else None,
                "incentive": fifth.get("incentive", 0) if fifth else 0,
                "tao_day": fifth.get("emission_tao_day", 0) if fifth else 0,
            },
            "analysis": {
                "enter_above_incentive": fifth.get("incentive", 0) if fifth else 0,
                "daily_income_if_paid_usd": round(
                    (fifth.get("emission_tao_day", 0) if fifth else 0) * 230, 2
                ),
                "hhi_interpretation": "concentrated" if subnet.get("hhi", 0) > 0.5 else "distributed",
                "cost_to_enter_tao": subnet.get("burn_tao", 0),
                "cost_to_enter_usd": round(subnet.get("burn_tao", 0) * 230, 2),
            },
        })

    def submissions(self, params):
        """Our submission history."""
        subs = self._load_submissions()
        self.send_json({
            "netuid": NETUID,
            "total_submissions": len(subs),
            "submissions": subs,
        })

    def tools(self, params):
        """Tool status — what we have available."""
        tools = self._load_tool_status()
        self.send_json({
            "netuid": NETUID,
            "tools": tools,
        })

    def experiments(self, params):
        """CGE experiment results."""
        # Check for experiment data
        exp_dir = Path("/root/bitt/data/experiments")
        experiments = []
        if exp_dir.exists():
            for f in sorted(exp_dir.glob("*.json")):
                try:
                    experiments.append(json.loads(f.read_text()))
                except Exception:
                    pass

        self.send_json({
            "netuid": NETUID,
            "experiment_count": len(experiments),
            "experiments": experiments[-10:],  # last 10
        })

    def leaderboard(self, params):
        """Current leaderboard from chain data."""
        cap = get_latest_capture()
        subnet = cap.get("subnets", {}).get(str(NETUID), {}) if cap else {}

        emitters = subnet.get("top_emitters", [])
        weights = subnet.get("weights", {})

        # Build leaderboard from emitters + weights
        leaderboard = []
        for e in emitters:
            leaderboard.append({
                "uid": e.get("uid"),
                "incentive": e.get("incentive", 0),
                "emission_tao_day": e.get("emission_tao_day", 0),
                "emission_alpha_epoch": e.get("emission_alpha_epoch", 0),
                "active": e.get("active", False),
                "validator_permit": e.get("validator_permit", False),
                "total_stake": e.get("total_stake", "0"),
                "hotkey": e.get("hotkey", "")[:16],
            })

        # Who votes for whom
        weight_detail = {}
        for val_uid, miner_weights in weights.items():
            weight_detail[val_uid] = miner_weights

        self.send_json({
            "netuid": NETUID,
            "leaderboard": leaderboard,
            "total_emitting": len(emitters),
            "weight_detail": weight_detail,
            "last_updated": cap.get("captured_at") if cap else None,
        })

    # ─── Data loaders ──────────────────────────────────────────────

    def _load_submissions(self) -> list[dict]:
        """Load our submission history from SQLite."""
        db_path = Path("/root/bitt/data/bitsec_submissions.db")
        if not db_path.exists():
            return []

        try:
            conn = sqlite3.connect(str(db_path))
            cur = conn.execute(
                "SELECT * FROM submissions ORDER BY submitted_at DESC LIMIT 50"
            )
            cols = [d[0] for d in cur.description]
            subs = [dict(zip(cols, row)) for row in cur.fetchall()]
            conn.close()
            return subs
        except Exception:
            return []

    def _load_tool_status(self) -> dict:
        """Check which tools are available."""
        tools = {}
        tool_checks = {
            "slither": "/root/bitt/subnets/sn60-bitsec/tools/slither",
            "mythril": "/root/bitt/subnets/sn60-bitsec/tools/mythril",
            "scabench": "/root/bitt/subnets/sn60-bitsec/tools/scabench",
            "shieldscan": "/root/bitt/subnets/sn60-bitsec/tools/shieldscan",
            "scone-bench": "/root/bitt/subnets/sn60-bitsec/tools/scone-bench",
            "audit-skill": "/root/bitt/subnets/sn60-bitsec/tools/audit-skill",
        }
        for name, path in tool_checks.items():
            p = Path(path)
            tools[name] = {
                "installed": p.exists(),
                "path": str(p),
                "has_readme": (p / "README.md").exists() if p.exists() else False,
            }

        # Our agent
        agent_path = Path("/root/bitt/workers/bitsec/agent.py")
        tools["our_agent"] = {
            "installed": agent_path.exists(),
            "path": str(agent_path),
            "version": "v1",
        }

        return tools

    def send_json(self, data):
        body = json.dumps(data, default=str).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass


def main():
    server = HTTPServer(("0.0.0.0", PORT), BitsecHandler)
    print(f"Bitsec API on http://localhost:{PORT}")
    print(f"Endpoints:")
    print(f"  GET /api/bitsec              — overview")
    print(f"  GET /api/bitsec/subnet       — live chain data")
    print(f"  GET /api/bitsec/competition  — what it takes to earn")
    print(f"  GET /api/bitsec/submissions  — our submission history")
    print(f"  GET /api/bitsec/tools        — tool status")
    print(f"  GET /api/bitsec/experiments  — CGE results")
    print(f"  GET /api/bitsec/leaderboard  — current leaderboard")
    server.serve_forever()


if __name__ == "__main__":
    main()
