"""CF Groq Harness — mwgym HarnessAdapter using free Cloudflare/Groq inference.

Drops into the mwgym wired_loop exactly like PydanticBATSHarness.
Uses CF Workers AI (unlimited free) + Groq (8k tok/min free).
"""
from __future__ import annotations

import http.client
import json
import os
import ssl
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path("/root/mwgym")))
from mwgym.harnesses.base import HarnessInstance, HarnessRun

sys.path.insert(0, str(Path("/root/bitt")))
from vault import Vault

_v = Vault()
CF_ACCOUNT = "954612afb5a97bb15dddcdc70176813d"
CF_TOKEN = _v.get("cf_api_token") or ""
GROQ_KEY = _v.get("groq_api_key") or ""

CF_MODEL = "@cf/meta/llama-3.3-70b-instruct-fp8-fast"
GROQ_MODEL = "qwen/qwen3.6-27b"


def _call_cf(prompt: str, max_tokens: int = 2000) -> dict:
    """Call CF Workers AI (free, unlimited)."""
    ctx = ssl.create_default_context()
    conn = http.client.HTTPSConnection("api.cloudflare.com", context=ctx, timeout=60)
    body = json.dumps({"messages": [{"role": "user", "content": prompt}],
                       "max_tokens": max_tokens, "temperature": 0.1})
    conn.request("POST", f"/client/v4/accounts/{CF_ACCOUNT}/ai/run/{CF_MODEL}",
        body=body, headers={"Authorization": f"Bearer {CF_TOKEN}", "Content-Type": "application/json"})
    resp = conn.getresponse()
    data = json.loads(resp.read().decode())
    conn.close()
    if "result" in data:
        return {"ok": True, "content": data["result"].get("response", ""),
                "tokens": data["result"].get("usage", {})}
    return {"ok": False, "error": str(data.get("errors", "unknown"))}


def _call_groq(prompt: str, max_tokens: int = 1200) -> dict:
    """Call Groq (free tier, 8k tok/min)."""
    ctx = ssl.create_default_context()
    conn = http.client.HTTPSConnection("api.groq.com", context=ctx, timeout=60)
    body = json.dumps({"model": GROQ_MODEL, "messages": [{"role": "user", "content": prompt}],
                       "max_tokens": max_tokens, "temperature": 0.1})
    conn.request("POST", "/openai/v1/chat/completions", body=body,
        headers={"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json",
                 "User-Agent": "bitt-agent/1.0"})
    resp = conn.getresponse()
    data = json.loads(resp.read().decode())
    conn.close()
    if "choices" in data:
        content = data["choices"][0]["message"].get("content", "")
        if "<think>" in content:
            parts = content.split("</think>")
            content = parts[-1].strip() if len(parts) > 1 else content.split("<think>")[-1].strip()
        return {"ok": True, "content": content, "tokens": data.get("usage", {})}
    return {"ok": False, "error": str(data.get("error", "unknown"))}


class CFGroqHarness:
    """mwgym-compatible harness using CF/Groq (free).

    Implements the HarnessAdapter protocol.
    Drop-in replacement for PydanticBATSHarness.
    """

    def __init__(self):
        pass

    async def provision(self, genome, worker_id: str) -> HarnessInstance:
        return HarnessInstance(harness="cf-groq", worker_id=worker_id)

    async def run(self, instance: HarnessInstance, task: str, workspace: str) -> HarnessRun:
        t0 = time.time()

        result = _call_groq(task, max_tokens=2000)
        if not result["ok"]:
            result = _call_cf(task, max_tokens=2000)

        duration_ms = int((time.time() - t0) * 1000)
        content = result.get("content", "")
        tokens = result.get("tokens", {})
        total = tokens.get("prompt_tokens", 0) + tokens.get("completion_tokens", 0)

        return HarnessRun(
            ok=result["ok"],
            output=content,
            duration_ms=duration_ms,
            cost_usd=0.0,
            total_tokens=total,
            metadata={"provider": result.get("provider", "unknown"), "model": GROQ_MODEL},
        )

    async def snapshot(self, instance):
        from mwgym.harnesses.base import StateSnapshot
        return StateSnapshot()

    async def restore(self, snapshot):
        return HarnessInstance()

    async def close(self, instance):
        pass
