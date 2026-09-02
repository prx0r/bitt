"""Bitsec Miner v3 — Scout/Senior architecture with CF/Groq inference.

Architecture from bitsec-scanner + hound:
  Scout: Fast exploration, identify high-risk areas
  Senior: Deep analysis, precise vulnerability detection

Models (all free):
  Scout: CF Workers AI llama-3.3-70b
  Senior: Groq qwen3.6-27b (reasoning)

Submission: btcli subnet register + python -m neurons.miner
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path("/root/bitt")))
from workers.bitsec.cloudflare_harness import call_model


# ─── Vulnerability types ────────────────────────────────────────────

VULN_TYPES = [
    "reentrancy", "access_control", "unchecked_return", "integer_overflow",
    "front_running", "tx_origin", "oracle_manipulation", "flash_loan",
    "price_manipulation", "governance_attack", "logic_error", "business_logic",
]


# ─── Scout: Fast exploration ────────────────────────────────────────

SCOUT_PROMPT = """You are a security scout. Quickly identify HIGH-RISK areas in this code.

For each high-risk area, return JSON:
{{
  "risk_areas": [
    {{
      "area": "function/contract name",
      "risk_type": "reentrancy|access_control|unchecked_return|oracle_manipulation|flash_loan|price_manipulation|governance_attack|logic_error|business_logic",
      "confidence": 0.0-1.0,
      "reasoning": "why this area is risky",
      "functions": ["func1", "func2"],
      "files": ["file1.sol"]
    }}
  ]
}}

Code:
```{language}
{code}
```

Focus on: external calls, state changes, access control, token flows, price feeds.
Return ONLY valid JSON."""


def scout(code: str, language: str = "solidity") -> dict:
    """Fast exploration — identify high-risk areas."""
    prompt = SCOUT_PROMPT.format(code=code[:8000], language=language)
    result = call_model("mimo", prompt, max_tokens=2000)

    if not result["ok"]:
        return {"risk_areas": []}

    try:
        start = result["content"].find("{")
        end = result["content"].rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(result["content"][start:end])
    except Exception:
        pass
    return {"risk_areas": []}


# ─── Senior: Deep analysis ──────────────────────────────────────────

SENIOR_PROMPT = """You are an expert smart contract security auditor. Analyze this code for vulnerabilities.

Based on the scout's findings, these are high-risk areas to focus on:
{scout_findings}

For EACH vulnerability found, return:
{{
  "prediction": true,
  "vulnerabilities": [
    {{
      "title": "short title",
      "severity": "critical|high|medium|low",
      "category": "reentrancy|access_control|unchecked_return|integer_overflow|front_running|tx_origin|oracle_manipulation|flash_loan|price_manipulation|governance_attack|logic_error|business_logic",
      "description": "detailed description with attack scenario",
      "line_ranges": [{{"start": N, "end": N}}],
      "vulnerable_code": "the problematic code",
      "code_to_exploit": "how to exploit",
      "rewritten_code_to_fix": "the fix"
    }}
  ]
}}

Code:
```{language}
{code}
```

Be thorough but precise. Only report real vulnerabilities with clear attack paths.
Return ONLY valid JSON."""


def senior(code: str, scout_findings: list[dict], language: str = "solidity") -> dict:
    """Deep analysis — precise vulnerability detection."""
    scout_text = json.dumps(scout_findings, indent=2) if scout_findings else "No specific areas identified."

    prompt = SENIOR_PROMPT.format(
        code=code[:12000],
        language=language,
        scout_findings=scout_text,
    )
    result = call_model("gpt-oss-20b", prompt, max_tokens=4000)

    if not result["ok"]:
        return {"prediction": False, "vulnerabilities": [], "error": result.get("error")}

    content = result["content"]
    try:
        start = content.find("{")
        end = content.rfind("}") + 1
        if start >= 0 and end > start:
            parsed = json.loads(content[start:end])
            return parsed
    except Exception:
        pass

    return {"prediction": False, "vulnerabilities": []}


# ─── Main analysis pipeline ──────────────────────────────────────────

def analyze_code(code: str, language: str = "solidity") -> dict:
    """Full Scout/Senior analysis pipeline."""
    # Pass 1: Scout identifies high-risk areas
    scout_result = scout(code, language)
    risk_areas = scout_result.get("risk_areas", [])

    # Pass 2: Senior analyzes each risk area
    senior_result = senior(code, risk_areas, language)

    # Combine
    all_vulns = senior_result.get("vulnerabilities", [])

    return {
        "prediction": len(all_vulns) > 0,
        "vulnerabilities": all_vulns,
        "scout_areas": len(risk_areas),
        "senior_findings": len(all_vulns),
    }


def analyze_file(filepath: str) -> dict:
    """Analyze a file."""
    code = Path(filepath).read_text()
    ext = Path(filepath).suffix.lower()
    lang_map = {".sol": "solidity", ".vy": "vyper", ".rs": "rust", ".py": "python"}
    lang = lang_map.get(ext, "solidity")
    return analyze_code(code, lang)


# ─── Bitsec submission interface ─────────────────────────────────────

def predict(code: str) -> dict:
    """Drop-in replacement for bitsec.miner.predict.predict().

    Returns PredictionResponse-compatible dict.
    """
    result = analyze_code(code)

    return {
        "prediction": result["prediction"],
        "vulnerabilities": result["vulnerabilities"],
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python miner.py <file>")
        sys.exit(1)

    result = analyze_file(sys.argv[1])
    print(json.dumps(result, indent=2))
