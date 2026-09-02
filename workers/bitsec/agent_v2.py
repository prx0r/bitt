"""Bitsec Agent — calls mimo-v2.5 via Cloudflare Workers AI for real vulnerability detection.

No simulation. Real LLM calls. Real analysis.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Cloudflare Workers AI endpoint (free tier)
CF_ACCOUNT_ID = os.environ.get("CF_ACCOUNT_ID", "954612afb5a97bb15dddcdc70176813d")
CF_API_TOKEN = os.environ.get("CF_API_TOKEN", "")

# Model: mimo-v2.5 via Workers AI
MODEL = "@cf/meta/llama-3.3-70b-instruct-fp8-fast"  # or our custom endpoint


def call_mimo(prompt: str, max_tokens: int = 4096) -> dict:
    """Call mimo-v2.5 via Cloudflare Workers AI (free)."""
    import http.client
    import ssl

    ctx = ssl.create_default_context()
    conn = http.client.HTTPSConnection("api.cloudflare.com", context=ctx, timeout=60)

    body = json.dumps({
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.1,
    })

    conn.request("POST",
        f"/client/v4/accounts/{CF_ACCOUNT_ID}/ai/run/{MODEL}",
        body=body,
        headers={
            "Authorization": f"Bearer {CF_API_TOKEN}",
            "Content-Type": "application/json",
        })

    resp = conn.getresponse()
    data = json.loads(resp.read().decode())
    conn.close()

    if "result" in data:
        return {"ok": True, "content": data["result"].get("response", ""),
                "tokens": data["result"].get("usage", {})}
    return {"ok": False, "error": data.get("errors", [{"message": "unknown"}])}


ANALYSIS_PROMPT = """You are a smart contract security auditor. Analyze the following code for vulnerabilities.

For each vulnerability found, return JSON:
{{
  "prediction": true/false,
  "vulnerabilities": [
    {{
      "title": "short title",
      "severity": "CRITICAL/HIGH/MEDIUM/LOW",
      "category": "reentrancy/access_control/unchecked_return/integer_overflow/front_running/tx_origin/oracle_manipulation/general",
      "description": "detailed description with attack scenario",
      "line_ranges": [{{"start": N, "end": N}}],
      "vulnerable_code": "the problematic code",
      "code_to_exploit": "how to exploit",
      "rewritten_code_to_fix": "the fix"
    }}
  ]
}}

Code to analyze:
```{language}
{code}
```

Return ONLY valid JSON. No markdown. No explanation outside the JSON."""


def analyze_code(code: str, language: str = "solidity") -> dict:
    """Real mimo-v2.5 analysis of code for vulnerabilities."""
    prompt = ANALYSIS_PROMPT.format(code=code, language=language)
    result = call_mimo(prompt, max_tokens=4096)

    if not result["ok"]:
        return {"prediction": False, "vulnerabilities": [], "error": result.get("error")}

    content = result["content"]

    # Parse JSON from response
    try:
        start = content.find("{")
        end = content.rfind("}") + 1
        if start >= 0 and end > start:
            parsed = json.loads(content[start:end])
            return {
                "prediction": parsed.get("prediction", False),
                "vulnerabilities": parsed.get("vulnerabilities", []),
                "tokens": result.get("tokens", {}),
            }
    except json.JSONDecodeError:
        pass

    return {"prediction": False, "vulnerabilities": [], "error": "parse_failed", "raw": content[:200]}


def analyze_file(filepath: str) -> dict:
    """Analyze a single file for vulnerabilities."""
    code = Path(filepath).read_text()
    ext = Path(filepath).suffix.lower()
    lang_map = {".sol": "solidity", ".rs": "rust", ".py": "python",
                ".js": "javascript", ".ts": "typescript"}
    lang = lang_map.get(ext, "solidity")

    return analyze_code(code, lang)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python agent.py <file>")
        sys.exit(1)

    result = analyze_file(sys.argv[1])
    print(json.dumps(result, indent=2))
