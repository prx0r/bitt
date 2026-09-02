"""Subnet API — feeds live chain data to each target subnet.

For each target subnet, provides:
  - Live chain data from latest capture
  - Competition metrics
  - Registration status
  - Entry cost tracking
  - Submission tracking (when we start submitting)

GET /api/v1/sub/{netuid}           — live chain data + competition
GET /api/v1/sub/{netuid}/entry     — registration + cost analysis
GET /api/v1/sub/{netuid}/compete   — who's winning, what it takes
GET /api/v1/sub/{netuid}/mine      — submission interface (future)
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, str(Path(__file__).parent.parent))
from oracle.capture import DB_PATH, get_latest_capture

PORT = 8401

# Target subnets
TARGETS = {
    60: {"name": "Bitsec", "priority": 1, "category": "security", "transfer": "bug_bounties"},
    62: {"name": "Ridges", "priority": 2, "category": "swe_coding", "transfer": "software_work"},
    11: {"name": "TrajectoryRL", "priority": 3, "category": "agent_learning", "transfer": "all_workers"},
    118: {"name": "Ditto", "priority": 4, "category": "agent_memory", "transfer": "memory_systems"},
    56: {"name": "Gradients", "priority": 5, "category": "optimization", "transfer": "the_lab_itself"},
}


class SubnetHandler(SimpleHTTPRequestHandler):

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        params = parse_qs(parsed.query)

        # /api/v1/sub/{id}
        if path.startswith("/api/v1/sub/"):
            parts = path.split("/")
            if len(parts) >= 4 and parts[3].isdigit():
                netuid = int(parts[3])
                if len(parts) == 4:
                    self.sub_live(netuid, params)
                elif parts[4] == "entry":
                    self.sub_entry(netuid)
                elif parts[4] == "compete":
                    self.sub_compete(netuid)
                elif parts[4] == "mine":
                    self.sub_mine(netuid)
            return

        # /api/v1/targets
        if path == "/api/v1/targets":
            self.targets()
            return

        # /api/v1/overview
        if path == "/api/v1/overview":
            self.overview()
            return

        self.send_error(404)

    def targets(self):
        """List all target subnets with live data."""
        cap = get_latest_capture()
        if not cap:
            self.send_json({"error": "No captures"})
            return

        result = []
        for netuid, meta in sorted(TARGETS.items(), key=lambda x: x[1]["priority"]):
            subnet = cap.get("subnets", {}).get(str(netuid), {})
            if "error" in subnet:
                result.append({"netuid": netuid, "name": meta["name"], "error": "not in capture"})
                continue

            result.append({
                "netuid": netuid,
                "name": meta["name"],
                "priority": meta["priority"],
                "category": meta["category"],
                "transfer": meta["transfer"],
                "live": {
                    "burn_tao": subnet.get("burn_tao", 0),
                    "total_tao_day": subnet.get("total_tao_day", 0),
                    "contestable_miner_tao_day": subnet.get("contestable_miner_tao_day", 0),
                    "miner_count": subnet.get("miner_count", 0),
                    "emitting_count": subnet.get("emitting_count", 0),
                    "alpha_price": subnet.get("alpha_price", 0),
                },
            })

        self.send_json({
            "block": cap.get("block_number"),
            "targets": result,
        })

    def sub_live(self, netuid: int, params):
        """Live chain data for a subnet."""
        cap = get_latest_capture()
        if not cap:
            self.send_json({"error": "No captures"})
            return

        subnet = cap.get("subnets", {}).get(str(netuid))
        if not subnet:
            self.send_error(404, f"Subnet {netuid} not in capture")
            return

        meta = TARGETS.get(netuid, {})

        self.send_json({
            "netuid": netuid,
            "name": subnet.get("name"),
            "target_meta": meta,
            "chain": {
                "block": cap.get("block_number"),
                "burn_tao": subnet.get("burn_tao"),
                "tempo": subnet.get("tempo"),
                "alpha_price": subnet.get("alpha_price"),
                "neuron_count": subnet.get("neuron_count"),
                "active_count": subnet.get("active_count"),
                "miner_count": subnet.get("miner_count"),
                "validator_count": subnet.get("validator_count"),
                "emitting_count": subnet.get("emitting_count"),
            },
            "emissions": {
                "total_tao_day": subnet.get("total_tao_day"),
                "miner_tao_day": subnet.get("miner_tao_day"),
                "validator_tao_day": subnet.get("validator_tao_day"),
                "contestable_miner_tao_day": subnet.get("contestable_miner_tao_day"),
                "owner_cut_pct": subnet.get("owner_cut_pct"),
            },
            "competition": {
                "hhi": subnet.get("hhi"),
                "effective_earners": subnet.get("effective_earners"),
                "weight_validators": subnet.get("weight_validators"),
            },
            "top_emitters": subnet.get("top_emitters", [])[:5],
            "hyperparams": subnet.get("hyperparams", {}),
            "identity": subnet.get("identity"),
        })

    def sub_entry(self, netuid: int):
        """Entry cost analysis."""
        cap = get_latest_capture()
        if not cap:
            self.send_json({"error": "No captures"})
            return

        subnet = cap.get("subnets", {}).get(str(netuid))
        if not subnet:
            self.send_error(404)
            return

        hp = subnet.get("hyperparams", {})
        burn = subnet.get("burn_tao", 0)
        min_burn = (hp.get("min_burn") or 0) / 1e9
        max_burn = (hp.get("max_burn") or 0) / 1e9

        self.send_json({
            "netuid": netuid,
            "name": subnet.get("name"),
            "registration_cost_tao": burn,
            "min_burn_tao": min_burn,
            "max_burn_tao": max_burn,
            "registration_allowed": hp.get("registration_allowed"),
            "immunity_blocks": hp.get("immunity_period"),
            "max_validators": hp.get("max_validators"),
            "tempo": subnet.get("tempo"),
            "entry_assessment": {
                "cost_tao": burn,
                "cost_usd_approx": round(burn * 230, 2),
                "burn_range": f"{min_burn:.6f} — {max_burn:.2f}",
                "is_at_floor": burn <= min_burn * 1.1,
            },
        })

    def sub_compete(self, netuid: int):
        """Competition analysis — what it takes to earn."""
        cap = get_latest_capture()
        if not cap:
            self.send_json({"error": "No captures"})
            return

        subnet = cap.get("subnets", {}).get(str(netuid))
        if not subnet:
            self.send_error(404)
            return

        emitters = subnet.get("top_emitters", [])
        contestable = subnet.get("contestable_miner_tao_day", 0)

        # What the #5 emitter earns
        fifth = emitters[4] if len(emitters) >= 5 else None
        fifth_tao_day = fifth.get("emission_tao_day", 0) if fifth else 0

        # What the #1 emitter earns
        first = emitters[0] if emitters else None
        first_tao_day = first.get("emission_tao_day", 0) if first else 0

        self.send_json({
            "netuid": netuid,
            "name": subnet.get("name"),
            "contestable_miner_tao_day": contestable,
            "top5_cutoff_tao_day": round(fifth_tao_day, 4),
            "champion_tao_day": round(first_tao_day, 4),
            "champion_incentive": first.get("incentive", 0) if first else 0,
            "emitting_count": subnet.get("emitting_count", 0),
            "miner_count": subnet.get("miner_count", 0),
            "competition_density": round(subnet.get("emitting_count", 0) / max(subnet.get("miner_count", 1), 1), 3),
            "analysis": {
                "enter_above": f"UID with incentive > {fifth.get('incentive', 0):.4f}" if fifth else "unknown",
                "daily_income_if_paid": round(fifth_tao_day * 230, 2) if fifth else 0,
                "hhi_interpretation": "concentrated" if subnet.get("hhi", 0) > 0.5 else "distributed",
            },
        })

    def sub_mine(self, netuid: int):
        """Mining interface info."""
        self.send_json({
            "netuid": netuid,
            "status": "not_started",
            "message": "Wire this to actual submission tracking when we start mining",
            "tracking": {
                "submissions": [],
                "total_cost_tao": 0,
                "total_rewards_tao": 0,
                "current_rank": None,
            },
        })

    def overview(self):
        """Overview across all 5 targets."""
        cap = get_latest_capture()
        if not cap:
            self.send_json({"error": "No captures"})
            return

        targets = []
        for netuid, meta in sorted(TARGETS.items(), key=lambda x: x[1]["priority"]):
            subnet = cap.get("subnets", {}).get(str(netuid), {})
            if "error" in subnet:
                continue

            targets.append({
                "netuid": netuid,
                "name": meta["name"],
                "priority": meta["priority"],
                "category": meta["category"],
                "burn_tao": subnet.get("burn_tao", 0),
                "contestable_tao_day": subnet.get("contestable_miner_tao_day", 0),
                "emitting": subnet.get("emitting_count", 0),
                "miners": subnet.get("miner_count", 0),
                "alpha_price": subnet.get("alpha_price", 0),
                "transfer": meta["transfer"],
            })

        total_contestable = sum(t["contestable_tao_day"] for t in targets)

        self.send_json({
            "block": cap.get("block_number"),
            "targets_count": len(targets),
            "total_contestable_tao_day": round(total_contestable, 2),
            "targets": targets,
        })

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
    server = HTTPServer(("0.0.0.0", PORT), SubnetHandler)
    print(f"Subnet API on http://localhost:{PORT}")
    print(f"Endpoints:")
    print(f"  GET /api/v1/targets              — all 5 targets with live data")
    print(f"  GET /api/v1/overview             — overview across targets")
    print(f"  GET /api/v1/sub/{{id}}            — live chain data")
    print(f"  GET /api/v1/sub/{{id}}/entry      — registration + cost")
    print(f"  GET /api/v1/sub/{{id}}/compete    — competition analysis")
    print(f"  GET /api/v1/sub/{{id}}/mine       — submission tracking")
    server.serve_forever()


if __name__ == "__main__":
    main()
