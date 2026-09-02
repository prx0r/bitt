"""Bitsec MCP Server — exposes Bitsec data as tools for AI agents.

Tools:
  bitsec_overview     — all key metrics
  bitsec_subnet       — full chain data
  bitsec_competition  — what it takes to earn
  bitsec_leaderboard  — current leaderboard
  bitsec_submissions  — our submission history
  bitsec_tools        — available analysis tools
  bitsec_experiment   — CGE experiment results

Usage:
  python3 oracle/bitsec_mcp.py
  
  Or add to Claude/Cursor MCP config:
  {
    "mcpServers": {
      "bitsec": {
        "command": "python3",
        "args": ["/root/bitt/oracle/bitsec_mcp.py"]
      }
    }
  }
"""
from __future__ import annotations

import http.client
import json
import sys
from typing import Any

BITSEC_API = "localhost"
BITSEC_PORT = 8402


def query_api(endpoint: str) -> dict:
    """Query the Bitsec API."""
    conn = http.client.HTTPSConnection(BITSEC_API, BITSEC_PORT, timeout=10)
    try:
        conn.request("GET", f"/api/bitsec{endpoint}")
        resp = conn.getresponse()
        return json.loads(resp.read().decode())
    except Exception as e:
        return {"error": str(e)}
    finally:
        conn.close()


# ─── Tool definitions for MCP ──────────────────────────────────────

TOOLS = [
    {
        "name": "bitsec_overview",
        "description": "Get overview of Bitsec SN60: chain data, economics, competition, tools, submissions",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "bitsec_subnet",
        "description": "Get full chain data for Bitsec SN60: weights, bonds, hyperparameters, identity",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "bitsec_competition",
        "description": "Get competition analysis: who's winning, what #5 earns, cost to enter",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "bitsec_leaderboard",
        "description": "Get current leaderboard with UID, incentive, TAO/day, weight detail",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "bitsec_submissions",
        "description": "Get our Bitsec submission history",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "bitsec_tools",
        "description": "Get available security analysis tools and their status",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "bitsec_experiments",
        "description": "Get CGE experiment results for Bitsec",
        "inputSchema": {"type": "object", "properties": {}},
    },
]

ENDPOINT_MAP = {
    "bitsec_overview": "",
    "bitsec_subnet": "/subnet",
    "bitsec_competition": "/competition",
    "bitsec_leaderboard": "/leaderboard",
    "bitsec_submissions": "/submissions",
    "bitsec_tools": "/tools",
    "bitsec_experiments": "/experiments",
}


def handle_request(request: dict) -> dict:
    """Handle an MCP JSON-RPC request."""
    method = request.get("method", "")
    params = request.get("params", {})
    req_id = request.get("id")

    if method == "tools/list":
        return {"tools": TOOLS}

    elif method == "tools/call":
        tool_name = params.get("name", "")
        if tool_name in ENDPOINT_MAP:
            data = query_api(ENDPOINT_MAP[tool_name])
            return {
                "content": [{"type": "text", "text": json.dumps(data, indent=2, default=str)}]
            }
        return {"error": f"Unknown tool: {tool_name}"}

    return {"error": f"Unknown method: {method}"}


def main():
    """Run MCP server over stdio."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
            response = handle_request(request)
            response["jsonrpc"] = "2.0"
            response["id"] = request.get("id")
            print(json.dumps(response))
            sys.stdout.flush()
        except Exception as e:
            print(json.dumps({"error": str(e), "jsonrpc": "2.0"}))
            sys.stdout.flush()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        # Test mode: print tool list
        print(json.dumps({"tools": TOOLS}, indent=2))
    else:
        main()
