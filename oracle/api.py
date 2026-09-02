"""Bittensor Oracle REST API — read-only, provenance-rich.

Endpoints:
  GET /api/v1/subnets                — all subnets (latest capture)
  GET /api/v1/subnets/{id}           — full detail
  GET /api/v1/subnets/{id}/emitters  — emitting neurons
  GET /api/v1/subnets/{id}/history   — historical captures
  GET /api/v1/stats                  — network overview
  GET /api/v1/top?metric=X&n=N      — ranked subnets
  GET /api/v1/captures               — list captures
  GET /api/v1/health                 — health + provenance

Run: python3 oracle/api.py
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
from datetime import datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, str(Path(__file__).parent.parent))
from oracle.capture import DB_PATH, get_latest_capture, load_capture

PORT = int(os.environ.get("ORACLE_PORT", "8400"))


class OracleHandler(SimpleHTTPRequestHandler):

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        params = parse_qs(parsed.query)

        routes = {
            "": self.api_info,
            "/api/v1/subnets": self.list_subnets,
            "/api/v1/stats": self.network_stats,
            "/api/v1/captures": self.list_captures,
            "/api/v1/health": self.health,
        }

        if path in routes:
            routes[path](params)
            return

        # /api/v1/subnets/{id}
        if path.startswith("/api/v1/subnets/"):
            parts = path.split("/")
            if len(parts) >= 5 and parts[4].isdigit():
                netuid = int(parts[4])
                if len(parts) == 5:
                    self.subnet_detail(netuid, params)
                elif parts[5] == "emitters":
                    self.subnet_emitters(netuid, params)
                elif parts[5] == "history":
                    self.subnet_history(netuid, params)
            return

        # /api/v1/top
        if path == "/api/v1/top":
            self.top_subnets(params)
            return

        self.send_error(404)

    def api_info(self, params):
        cap = get_latest_capture()
        self.send_json({
            "name": "Bittensor Oracle API",
            "version": "3.0",
            "endpoints": {
                "/api/v1/subnets": "All subnets (latest capture)",
                "/api/v1/subnets/{id}": "Full detail + emitters + hyperparams",
                "/api/v1/subnets/{id}/emitters": "All emitting neurons",
                "/api/v1/subnets/{id}/history": "Historical captures",
                "/api/v1/top": "Ranked subnets by metric",
                "/api/v1/stats": "Network overview",
                "/api/v1/captures": "List all captures",
                "/api/v1/health": "Health + provenance",
            },
            "latest_block": cap.get("block_number") if cap else None,
            "latest_hash": cap.get("content_hash", "")[:12] if cap else None,
            "latest_time": cap.get("captured_at") if cap else None,
        })

    def list_subnets(self, params):
        cap = get_latest_capture()
        if not cap:
            self.send_json({"error": "No captures yet"})
            return

        subnets = cap.get("subnets", {})
        sort_by = params.get("sort", ["contestable_miner_tao_day"])[0]
        limit = int(params.get("limit", ["200"])[0])

        # Convert to list and sort
        items = [s for s in subnets.values() if "error" not in s]
        items.sort(key=lambda x: x.get(sort_by, 0), reverse=True)

        # Slim for listing
        slim = []
        for s in items[:limit]:
            slim.append({
                "netuid": s["netuid"],
                "name": s["name"],
                "burn_tao": s["burn_tao"],
                "neuron_count": s["neuron_count"],
                "miner_count": s["miner_count"],
                "validator_count": s["validator_count"],
                "emitting_count": s["emitting_count"],
                "total_tao_day": s["total_tao_day"],
                "contestable_miner_tao_day": s["contestable_miner_tao_day"],
                "miner_tao_day": s["miner_tao_day"],
                "validator_tao_day": s["validator_tao_day"],
                "alpha_price": s["alpha_price"],
                "tempo": s["tempo"],
                "hhi": s["hhi"],
            })

        self.send_json({
            "block": cap.get("block_number"),
            "hash": cap.get("content_hash", "")[:12],
            "count": len(slim),
            "subnets": slim,
        })

    def subnet_detail(self, netuid: int, params):
        cap = get_latest_capture()
        if not cap:
            self.send_json({"error": "No captures yet"})
            return

        subnet = cap.get("subnets", {}).get(str(netuid))
        if not subnet:
            self.send_error(404, f"Subnet {netuid} not found")
            return

        # Add provenance
        subnet["_provenance"] = {
            "block": cap.get("block_number"),
            "hash": cap.get("content_hash", "")[:12],
            "captured_at": cap.get("captured_at"),
            "schema_version": cap.get("schema_version"),
            "collector": cap.get("collector_version"),
        }
        self.send_json(subnet)

    def subnet_emitters(self, netuid: int, params):
        cap = get_latest_capture()
        if not cap:
            self.send_json({"error": "No captures yet"})
            return

        subnet = cap.get("subnets", {}).get(str(netuid))
        if not subnet:
            self.send_error(404, f"Subnet {netuid} not found")
            return

        self.send_json({
            "netuid": netuid,
            "name": subnet.get("name"),
            "emitting_count": subnet.get("emitting_count"),
            "alpha_price": subnet.get("alpha_price"),
            "total_tao_day": subnet.get("total_tao_day"),
            "contestable_miner_tao_day": subnet.get("contestable_miner_tao_day"),
            "emitters": subnet.get("top_emitters", []),
        })

    def subnet_history(self, netuid: int, params):
        db = sqlite3.connect(str(DB_PATH))
        limit = int(params.get("limit", ["10"])[0])
        cur = db.execute(
            "SELECT block_number, captured_at, content_hash FROM captures ORDER BY block_number DESC LIMIT ?",
            (limit,)
        )
        captures = [{"block": r[0], "time": r[1], "hash": r[2][:12]} for r in cur.fetchall()]
        db.close()
        self.send_json({"netuid": netuid, "captures": captures})

    def top_subnets(self, params):
        cap = get_latest_capture()
        if not cap:
            self.send_json({"error": "No captures yet"})
            return

        metric = params.get("metric", ["contestable_miner_tao_day"])[0]
        n = int(params.get("n", ["20"])[0])

        items = [s for s in cap.get("subnets", {}).values() if "error" not in s]
        items.sort(key=lambda x: x.get(metric, 0), reverse=True)

        self.send_json({
            "metric": metric,
            "block": cap.get("block_number"),
            "top": [{
                "netuid": s["netuid"],
                "name": s["name"],
                "value": s.get(metric, 0),
                "total_tao_day": s.get("total_tao_day"),
                "contestable_miner_tao_day": s.get("contestable_miner_tao_day"),
            } for s in items[:n]],
        })

    def list_captures(self, params):
        db = sqlite3.connect(str(DB_PATH))
        cur = db.execute(
            "SELECT block_number, captured_at, content_hash FROM captures ORDER BY block_number DESC LIMIT 50"
        )
        captures = [{"block": r[0], "time": r[1], "hash": r[2][:12]} for r in cur.fetchall()]
        db.close()
        self.send_json({"count": len(captures), "captures": captures})

    def network_stats(self, params):
        cap = get_latest_capture()
        if not cap:
            self.send_json({"error": "No captures yet"})
            return

        subnets = [s for s in cap.get("subnets", {}).values() if "error" not in s]
        total_tao = sum(s.get("total_tao_day", 0) for s in subnets)
        total_contestable = sum(s.get("contestable_miner_tao_day", 0) for s in subnets)
        total_miners = sum(s.get("miner_count", 0) for s in subnets)
        total_emitting = sum(s.get("emitting_count", 0) for s in subnets)
        with_emissions = [s for s in subnets if s.get("total_tao_day", 0) > 0]

        self.send_json({
            "block": cap.get("block_number"),
            "hash": cap.get("content_hash", "")[:12],
            "captured_at": cap.get("captured_at"),
            "total_subnets": len(subnets),
            "total_neurons": sum(s.get("neuron_count", 0) for s in subnets),
            "total_miners": total_miners,
            "total_emitting": total_emitting,
            "total_tao_day": round(total_tao, 2),
            "total_contestable_miner_tao_day": round(total_contestable, 2),
            "subnets_with_emissions": len(with_emissions),
        })

    def health(self, params):
        cap = get_latest_capture()
        self.send_json({
            "status": "ok",
            "latest_block": cap.get("block_number") if cap else None,
            "latest_hash": cap.get("content_hash", "")[:12] if cap else None,
            "latest_time": cap.get("captured_at") if cap else None,
            "schema_version": cap.get("schema_version") if cap else None,
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
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=PORT)
    args = parser.parse_args()

    server = HTTPServer(("0.0.0.0", args.port), OracleHandler)
    print(f"Bittensor Oracle API on http://localhost:{args.port}")
    print(f"Read-only. No scan triggering. Capture via: python3 -m oracle.capture")
    server.serve_forever()


if __name__ == "__main__":
    main()
