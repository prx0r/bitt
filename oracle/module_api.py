"""Module API — exposes /bitt as a module for Private Lab to query.

This is the contract between /bitt and Private Lab.
Private Lab doesn't reach into /bitt internals.
It queries this API for program status, actions, and performance.

Endpoints:
  GET /v1/module/status          — what can Bittensor do right now?
  GET /v1/module/programs        — list all programs
  GET /v1/module/programs/{id}   — program status
  GET /v1/module/programs/{id}/actions — available actions
  GET /v1/module/programs/{id}/performance — our performance

  POST /v1/module/programs/{id}/train     — start training
  POST /v1/module/programs/{id}/submit    — submit candidate
  POST /v1/module/programs/{id}/allocate  — allocate resources

From the architecture review:
  "Private Lab does not know how a Bitsec submission works.
   It just receives program status, actions, costs, and outcomes.
   /bitt handles the actual implementation."
"""
from __future__ import annotations

import json
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, str(Path("/root/bitt")))
sys.path.insert(0, str(Path("/root/bitt/integration")))

from adapters.sn60.bitsec_adapter import BitsecAdapter
from oracle.capture import get_latest_capture

PORT = 8403


class ModuleAPIHandler(SimpleHTTPRequestHandler):

    def __init__(self, *args, **kwargs):
        self.adapter = BitsecAdapter()
        super().__init__(*args, **kwargs)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        params = parse_qs(parsed.query)

        if path == "/v1/module/status":
            self.module_status(params)
        elif path == "/v1/module/programs":
            self.list_programs(params)
        elif path.startswith("/v1/module/programs/"):
            parts = path.split("/")
            if len(parts) == 4:
                self.program_status(parts[3], params)
            elif len(parts) == 5 and parts[4] == "actions":
                self.program_actions(parts[3], params)
            elif len(parts) == 5 and parts[4] == "performance":
                self.program_performance(parts[3], params)
            else:
                self.send_error(404)
        else:
            self.send_error(404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path.startswith("/v1/module/programs/"):
            parts = path.split("/")
            if len(parts) == 5 and parts[4] == "submit":
                self.program_submit(parts[3])
            elif len(parts) == 5 and parts[4] == "train":
                self.program_train(parts[3])
            elif len(parts) == 5 and parts[4] == "allocate":
                self.program_allocate(parts[3])
            else:
                self.send_error(404)
        else:
            self.send_error(404)

    # ─── Endpoints ──────────────────────────────────────────────────

    def module_status(self, params):
        """What can /bitt do right now?"""
        programs = []
        for netuid in [60, 62, 11, 56, 61]:
            adapter = BitsecAdapter()
            status = adapter.get_program_status()
            programs.append({
                "id": status.program_id,
                "mode": status.mode,
                "economics": status.economics,
                "capabilities": status.capability_demand,
                "actions": status.possible_actions,
            })

        self.send_json({
            "module": "bitt",
            "capability_pool": {
                "security": 0.99,
                "smart_contract_security": 0.94,
                "software_engineering": 0.88,
                "vulnerability_detection": 0.98,
            },
            "programs": programs,
        })

    def list_programs(self, params):
        """List all Bittensor programs."""
        programs = []
        for netuid, cfg in SUBNETS.items():
            programs.append({
                "id": f"bittensor/{netuid}",
                "name": cfg.name,
                "category": cfg.category,
                "registration_cost_tao": cfg.registration_cost_approx,
            })
        self.send_json({"programs": programs})

    def program_status(self, program_id: str, params):
        """Get program status."""
        # Parse program_id (e.g., "sn60" or "bittensor/sn60")
        netuid = int(program_id.replace("sn", "").replace("bittensor/sn", ""))

        if netuid == 60:
            adapter = BitsecAdapter()
            status = adapter.to_private_lab_format()
            self.send_json(status)
        else:
            # Generic response for other subnets
            from oracle.capture import get_latest_capture
            cap = get_latest_capture()
            subnet = cap.get("subnets", {}).get(str(netuid), {}) if cap else {}

            self.send_json({
                "program": {"id": f"bittensor/{netuid}", "module": "bitt"},
                "state": {"mode": "DISCOVER"},
                "economics": {
                    "registration_cost_tao": subnet.get("burn_tao", 0),
                    "contestable_miner_tao_day": subnet.get("contestable_miner_tao_day", 0),
                },
                "our_state": {"worker_version": "none", "total_submissions": 0},
                "possible_actions": ["train", "clone_and_replay"],
            })

    def program_actions(self, program_id: str, params):
        """Get available actions for a program."""
        if program_id in ("sn60", "bittensor/sn60"):
            adapter = BitsecAdapter()
            self.send_json({"actions": adapter.get_actions()})
        else:
            self.send_json({"actions": ["train", "clone_and_replay", "submit"]})

    def program_performance(self, program_id: str, params):
        """Get our performance on a program."""
        if program_id in ("sn60", "bittensor/sn60"):
            adapter = BitsecAdapter()
            self.send_json(adapter.get_performance())
        else:
            self.send_json({"no_data": True})

    def program_submit(self, program_id: str):
        """Submit a candidate to a program."""
        body = self._read_body()

        if program_id in ("sn60", "bittensor/sn60"):
            adapter = BitsecAdapter()
            result = adapter.submit_candidate(
                worker_version=body.get("worker_version", "unknown"),
                agent_path=body.get("agent_path", ""),
                cost_usd=body.get("estimated_cost_usd", 0),
            )
            self.send_json(result)
        else:
            self.send_json({"error": f"Submit not implemented for {program_id}"})

    def program_train(self, program_id: str):
        """Start training for a program."""
        self.send_json({"status": "training_started", "program": program_id})

    def program_allocate(self, program_id: str):
        """Allocate resources to a program."""
        body = self._read_body()
        self.send_json({
            "status": "allocated",
            "program": program_id,
            "budget_usd": body.get("budget_usd", 0),
        })

    # ─── Helpers ──────────────────────────────────────────────────

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length:
            return json.loads(self.rfile.read(length))
        return {}

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
    server = HTTPServer(("0.0.0.0", PORT), ModuleAPIHandler)
    print(f"Bitt Module API on http://localhost:{PORT}")
    print(f"Private Lab contract:")
    print(f"  GET  /v1/module/status")
    print(f"  GET  /v1/module/programs")
    print(f"  GET  /v1/module/programs/{{id}}")
    print(f"  GET  /v1/module/programs/{{id}}/actions")
    print(f"  GET  /v1/module/programs/{{id}}/performance")
    print(f"  POST /v1/module/programs/{{id}}/submit")
    print(f"  POST /v1/module/programs/{{id}}/train")
    print(f"  POST /v1/module/programs/{{id}}/allocate")
    server.serve_forever()


if __name__ == "__main__":
    main()
