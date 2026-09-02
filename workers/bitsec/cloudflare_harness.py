"""CloudflareBATS + Groq — harness using free inference APIs.

CF Workers AI: unlimited free models
Groq: gpt-oss-120b free tier (8000 tok/min), qwen3.6-27b reasoning
"""
from __future__ import annotations

import http.client
import json
import os
import ssl
import time
from dataclasses import dataclass
from pathlib import Path
import sys

sys.path.insert(0, str(Path("/root/bitt")))
from vault import Vault

# Load keys from vault
_v = Vault()
CF_ACCOUNT = "954612afb5a97bb15dddcdc70176813d"
CF_TOKEN = _v.get("cf_api_token") or ""
GROQ_KEY = _v.get("groq_api_key") or ""

# CF models (free)
CF_MODELS = {
    "mimo": "@cf/meta/llama-3.3-70b-instruct-fp8-fast",
    "llama-70b": "@cf/meta/llama-3.3-70b-instruct-fp8-fast",
}

# Groq models (free tier, 8k tok/min)
GROQ_MODELS = {
    "gpt-oss-120b": "openai/gpt-oss-120b",
    "gpt-oss-20b": "openai/gpt-oss-20b",
    "qwen3.6-27b": "qwen/qwen3.6-27b",
}


def call_cf(model_key: str, prompt: str, max_tokens: int = 4096) -> dict:
    """Call Cloudflare Workers AI (free)."""
    model = CF_MODELS.get(model_key, CF_MODELS["mimo"])
    ctx = ssl.create_default_context()
    conn = http.client.HTTPSConnection("api.cloudflare.com", context=ctx, timeout=60)

    body = json.dumps({
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.1,
    })

    conn.request("POST", f"/client/v4/accounts/{CF_ACCOUNT}/ai/run/{model}",
        body=body,
        headers={"Authorization": f"Bearer {CF_TOKEN}", "Content-Type": "application/json"})

    resp = conn.getresponse()
    data = json.loads(resp.read().decode())
    conn.close()

    if "result" in data:
        return {"ok": True, "content": data["result"].get("response", ""),
                "tokens": data["result"].get("usage", {}), "provider": "cf"}
    return {"ok": False, "error": str(data.get("errors", "unknown"))}


def call_groq(model_key: str, prompt: str, max_tokens: int = 1200) -> dict:
    """Call Groq free tier (gpt-oss-120b, qwen3.6-27b)."""
    model = GROQ_MODELS.get(model_key, GROQ_MODELS["qwen3.6-27b"])
    ctx = ssl.create_default_context()
    conn = http.client.HTTPSConnection("api.groq.com", context=ctx, timeout=60)

    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.1,
    })

    conn.request("POST", "/openai/v1/chat/completions",
        body=body,
        headers={
            "Authorization": f"Bearer {GROQ_KEY}",
            "Content-Type": "application/json",
            "User-Agent": "bitt-agent/1.0",
        })

    resp = conn.getresponse()
    data = json.loads(resp.read().decode())
    conn.close()

    if "choices" in data:
        content = data["choices"][0]["message"].get("content", "")
        # Strip <think> tags from qwen
        if "<think>" in content:
            content = content.split("</think>")[-1].strip() if "</think>" in content else content.split("<think>")[-1].strip()
        return {"ok": True, "content": content,
                "tokens": data.get("usage", {}), "provider": "groq"}
    return {"ok": False, "error": str(data.get("error", "unknown"))}


def call_model(model: str, prompt: str, max_tokens: int = 1200) -> dict:
    """Route to the right provider based on model name."""
    if model in CF_MODELS:
        return call_cf(model, prompt, max_tokens)
    elif model in GROQ_MODELS or model.startswith("openai/") or model.startswith("qwen/"):
        return call_groq(model, prompt, max_tokens)
    else:
        return call_groq("qwen3.6-27b", prompt, max_tokens)


class CloudflareBATSHarness:
    """MWGym harness using Cloudflare Workers AI (free).

    Same interface as PydanticBATSHarness but uses CF instead of paid APIs.
    """

    def __init__(self, model: str = "mimo-v2.5"):
        self.model = model

    def run(self, task: str, workspace: str,
            limits=None, world_genome_id: str = "",
            worker_genome_id: str = "", family_id: str = "",
            uncertainty: float = 0.5,
            capability_scores: dict | None = None,
            context: str = "") -> tuple[HarnessRun, object]:
        """Execute task via CF Workers AI."""
        t0 = time.time()

        # Build prompt
        system = "You are a security analyst. Analyze code for vulnerabilities. Return JSON."
        user_msg = task
        if context:
            user_msg += f"\n\nContext:\n{context}"
        user_msg += "\n\nReturn JSON with prediction (bool) and vulnerabilities list."

        prompt = f"{system}\n\n{user_msg}"

        # Call CF Workers AI
        result = call_cf(self.model, prompt)

        duration_ms = int((time.time() - t0) * 1000)

        if not result["ok"]:
            run = HarnessRun(
                ok=False,
                output=f"Error: {result.get('error', 'unknown')}",
                duration_ms=duration_ms,
                cost_usd=0.0,  # CF is free
                total_tokens=0,
                metadata={"model": self.model, "provider": "cloudflare_workers_ai"},
            )
            return run, None

        # Parse response
        content = result["content"]
        tokens = result.get("tokens", {})
        total_tokens = tokens.get("prompt_tokens", 0) + tokens.get("completion_tokens", 0)

        # Try to parse as JSON
        parsed = None
        try:
            start = content.find("{")
            end = content.rfind("}") + 1
            if start >= 0 and end > start:
                parsed = json.loads(content[start:end])
        except Exception:
            pass

        run = HarnessRun(
            ok=True,
            output=content,
            duration_ms=duration_ms,
            cost_usd=0.0,  # CF is free
            total_tokens=total_tokens,
            metadata={
                "model": self.model,
                "provider": "cloudflare_workers_ai",
                "parsed": parsed,
            },
        )

        return run, parsed
