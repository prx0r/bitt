"""Bitsec Agent v4 — Hound-inspired Scout/Strategist with CF/Groq.

Patterns from hound/analysis/:
  Scout: autonomous exploration, builds knowledge graph
  Strategist: plans investigations, prioritizes by confidence
  GraphStore: findings as graph nodes with relationships
  HypothesisItemJSON: structured vulnerability output

Models (all free):
  Scout: CF Workers AI (llama-3.3-70b)
  Strategist: Groq (qwen3.6-27b reasoning)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path("/root/bitt")))
from workers.bitsec.cloudflare_harness import call_model


# ─── Scout: autonomous exploration ───────────────────────────────────

SCOUT_PROMPT = """You are a security scout analyzing a smart contract codebase.
Your job: identify HIGH-RISK areas that need deep investigation.

For each area, return JSON:
{{
  "investigations": [
    {{
      "goal": "specific security question to investigate",
      "focus_areas": ["function_name", "contract_name"],
      "priority": 1-10,
      "reasoning": "why this area is suspicious",
      "category": "aspect"
    }}
  ]
}}

Focus on:
- External calls (msg.sender.call, transfer, send)
- State changes after external calls
- Access control (who can call what)
- Token flows (who sends/receives tokens)
- Price oracle dependencies
- Flash loan attack surfaces
- Governance mechanisms
- Upgrade patterns

Code to analyze:
```{language}
{code}
```

Return ONLY valid JSON. Be specific — name exact functions and contracts."""


def scout(code: str, language: str = "solidity") -> dict:
    """Scout phase: identify high-risk areas."""
    prompt = SCOUT_PROMPT.format(code=code[:10000], language=language)
    result = call_model("mimo", prompt, max_tokens=3000)

    if not result["ok"]:
        return {"investigations": []}

    try:
        start = result["content"].find("{")
        end = result["content"].rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(result["content"][start:end])
    except Exception:
        pass
    return {"investigations": []}


# ─── Strategist: plan investigations ─────────────────────────────────

STRATEGIST_PROMPT = """You are a security strategist. Based on the scout's findings, create an investigation plan.

Scout findings:
{scout_findings}

For each investigation, determine:
{{
  "investigations": [
    {{
      "goal": "what to investigate",
      "focus_areas": ["specific code locations"],
      "priority": 1-10,
      "reasoning": "why this matters",
      "category": "aspect | suspicion",
      "expected_impact": "high | medium | low"
    }}
  ]
}}

Prioritize by:
1. Potential financial impact (high > medium > low)
2. Ease of exploitation (external calls > logic bugs)
3. Confidence based on code patterns observed

Return ONLY valid JSON."""


def strategist(scout_findings: list[dict]) -> dict:
    """Strategist phase: plan investigations."""
    prompt = STRATEGIST_PROMPT.format(scout_findings=json.dumps(scout_findings, indent=2))
    result = call_model("gpt-oss-20b", prompt, max_tokens=2000)

    if not result["ok"]:
        return {"investigations": scout_findings}

    try:
        start = result["content"].find("{")
        end = result["content"].rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(result["content"][start:end])
    except Exception:
        pass
    return {"investigations": scout_findings}


# ─── Analyst: deep vulnerability detection ───────────────────────────

ANALYST_PROMPT = """You are a senior security auditor. Investigate this specific security concern.

Investigation goal: {goal}
Focus areas: {focus_areas}
Code context:
```{language}
{code}
```

Based on your investigation, identify ALL vulnerabilities related to this concern.
For each finding return:
{{
  "title": "concise vulnerability title",
  "severity": "critical|high|medium|low",
  "category": "reentrancy|access_control|unchecked_return|oracle_manipulation|flash_loan|price_manipulation|governance|logic_error|business_logic",
  "description": "detailed explanation with attack scenario",
  "line_ranges": [{{"start": N, "end": N}}],
  "confidence": 0.0-1.0,
  "affected_code": "the problematic code snippet"
}}

Return ONLY valid JSON array of findings."""


def analyst(code: str, investigation: dict, language: str = "solidity") -> list[dict]:
    """Analyst phase: deep investigation of specific areas."""
    prompt = ANALYST_PROMPT.format(
        goal=investigation.get("goal", ""),
        focus_areas=", ".join(investigation.get("focus_areas", [])),
        code=code[:8000],
        language=language,
    )
    result = call_model("gpt-oss-20b", prompt, max_tokens=3000)

    if not result["ok"]:
        return []

    try:
        start = result["content"].find("[")
        end = result["content"].rfind("]") + 1
        if start >= 0 and end > start:
            return json.loads(result["content"][start:end])
    except Exception:
        pass
    return []


# ─── Main pipeline ───────────────────────────────────────────────────

def analyze_code(code: str, language: str = "solidity") -> dict:
    """Full Scout/Strategist/Analyst pipeline."""
    # Phase 1: Scout explores
    scout_result = scout(code, language)
    investigations = scout_result.get("investigations", [])

    # Phase 2: Strategist plans
    if investigations:
        strategy = strategist(investigations)
        planned = strategy.get("investigations", investigations)
    else:
        planned = [{"goal": "general vulnerability scan", "focus_areas": ["all"], "priority": 5}]

    # Phase 3: Analyst investigates each area
    all_findings = []
    for inv in planned[:5]:  # Top 5 investigations
        findings = analyst(code, inv, language)
        all_findings.extend(findings)

    # Deduplicate
    seen_titles = set()
    unique = []
    for f in all_findings:
        title = f.get("title", "").lower()
        if title not in seen_titles:
            seen_titles.add(title)
            unique.append(f)

    return {
        "prediction": len(unique) > 0,
        "vulnerabilities": unique,
        "scout_areas": len(investigations),
        "strategist_plans": len(planned),
        "analyst_findings": len(unique),
    }


def predict(code: str) -> dict:
    """Drop-in for bitsec.miner.predict."""
    return analyze_code(code)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python miner_v4.py <file>")
        sys.exit(1)
    result = analyze_code(Path(sys.argv[1]).read_text())
    print(json.dumps(result, indent=2))
