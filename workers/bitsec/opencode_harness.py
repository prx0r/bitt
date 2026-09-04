"""OpenCode Go API — Free inference via OpenCode Go subscription.

Endpoint: https://opencode.ai/zen/go/v1/chat/completions
Model: mimo-v2.5
"""
from __future__ import annotations

import http.client
import json
import ssl
import time
from typing import Any

# OpenCode Go API
OPENCODE_HOST = "opencode.ai"
OPENCODE_PATH = "/zen/go/v1/chat/completions"
OPENCODE_KEY = "sk-A5QHR5MRtUNec7BWqiRsZ0GAYck0CRT2Movsk7Q6U3UwcV77Y6G3TMXOhhyKh855"
OPENCODE_MODEL = "mimo-v2.5"


def call_opencode(prompt: str, max_tokens: int = 4096, temperature: float = 0.1, retries: int = 3) -> dict:
    """Call OpenCode Go API (mimo-v2.5)."""
    for attempt in range(retries):
        try:
            ctx = ssl.create_default_context()
            conn = http.client.HTTPSConnection(OPENCODE_HOST, context=ctx, timeout=120)
            
            body = json.dumps({
                "model": OPENCODE_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": temperature,
            })
            
            conn.request("POST", OPENCODE_PATH,
                body=body,
                headers={
                    "Authorization": f"Bearer {OPENCODE_KEY}",
                    "Content-Type": "application/json",
                    "User-Agent": "bitt-agent/1.0",
                })
            
            resp = conn.getresponse()
            data = json.loads(resp.read().decode())
            conn.close()
            
            if "choices" in data:
                content = data["choices"][0]["message"].get("content", "") or ""
                # Strip <think> tags if present
                if "<think>" in content:
                    content = content.split("</think>")[-1].strip() if "</think>" in content else content.split("<think>")[-1].strip()
                return {"ok": True, "content": content,
                        "tokens": data.get("usage", {}), "provider": "opencode-go"}
            return {"ok": False, "error": str(data.get("error", "unknown"))}
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
                continue
            return {"ok": False, "error": str(e)}


def call_model(model: str, prompt: str, max_tokens: int = 4096) -> dict:
    """Route to OpenCode Go (all models go through mimo-v2.5)."""
    return call_opencode(prompt, max_tokens)
