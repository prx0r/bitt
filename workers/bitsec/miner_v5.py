"""Bitsec Agent v5 — Compositional security primitives from reference/.

Integrates:
  - Hound graph-driven analysis (reference/hound/)
  - Trail of Bits skills (reference/tob-skills/)
  - Cloudflare audit methodology (reference/cloudflare-audit-skill/)
  - Composable process genome from lab-interfaces/

Model routing (all free):
  Scout: CF Workers AI llama-3.3-70b (cheap, fast)
  Strategist: CF Workers AI llama-3.3-70b (strong)
  Verifier: Groq gpt-oss-20b (independent)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path("/root/bitt")))
from workers.bitsec.cloudflare_harness import call_model
from workers.bitsec.pool_knowledge import build_prompt_with_pool_knowledge, load_doctrine


# ─── Process Arms (from email A/B/C/D/E) ─────────────────────────────

PROCESS_ARMS = {
    "A": {
        "name": "moltwork-default",
        "description": "Current Scout/Strategist/Analyst pipeline",
        "use_hound_graph": False,
        "use_tob_skills": False,
        "use_cf_audit": False,
    },
    "B": {
        "name": "hound",
        "description": "Graph-driven long-horizon auditing",
        "use_hound_graph": True,
        "use_tob_skills": False,
        "use_cf_audit": False,
    },
    "C": {
        "name": "cloudflare-audit",
        "description": "Parallel hunting + independent verification",
        "use_hound_graph": False,
        "use_tob_skills": False,
        "use_cf_audit": True,
    },
    "D": {
        "name": "tob-stack",
        "description": "Trail of Bits specialist skills",
        "use_hound_graph": False,
        "use_tob_skills": True,
        "use_cf_audit": False,
    },
}


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


def scout(code: str, language: str = "solidity", arm: str = "A") -> dict:
    """Scout phase: identify high-risk areas."""
    config = PROCESS_ARMS.get(arm, PROCESS_ARMS["A"])

    # Hound variant: add graph-based reasoning
    prompt = SCOUT_PROMPT.format(code=code[:10000], language=language)
    if config["use_hound_graph"]:
        prompt = (
            "You are a security scout using graph-driven analysis.\n"
            "Map the codebase as a knowledge graph: contracts, functions, "
            "external calls, state variables, access controls.\n"
            "Identify authorization flows, value flows, and cross-contract interactions.\n\n"
            + prompt
        )

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


def strategist(scout_findings: list[dict], arm: str = "A") -> dict:
    """Strategist phase: plan investigations."""
    config = PROCESS_ARMS.get(arm, PROCESS_ARMS["A"])

    prompt = STRATEGIST_PROMPT.format(scout_findings=json.dumps(scout_findings, indent=2))

    # Cloudflare audit variant: add adversarial validation thinking
    if config["use_cf_audit"]:
        prompt = (
            "You are a security strategist using the Cloudflare audit methodology.\n"
            "Plan investigations so that the finder of each issue cannot validate their own finding.\n"
            "Each investigation should be independently verifiable.\n"
            "Multiple runs should be intentionally additive — different runs discover different regions.\n\n"
            + prompt
        )

    # Hound variant: add sweep vs intuition planning
    if config["use_hound_graph"]:
        prompt = (
            "You are a strategist using Hound's sweep/intuition modes.\n"
            "Sweep mode: broad exploration of all attack surfaces.\n"
            "Intuition mode: deep dive on highest-confidence hypotheses.\n"
            "Plan which investigations use which mode.\n\n"
            + prompt
        )

    result = call_model("mimo", prompt, max_tokens=2000)
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


def analyst(code: str, investigation: dict, language: str = "solidity",
            arm: str = "A") -> list[dict]:
    """Analyst phase: deep investigation of specific areas.

    Uses a direct prompt — pool knowledge is in doctrine, not in every prompt.
    """
    config = PROCESS_ARMS.get(arm, PROCESS_ARMS["A"])

    # Direct, simple prompt — works reliably
    prompt = f"""Audit this {language} code for security vulnerabilities.

Focus on: {investigation.get('goal', 'all vulnerability types')}
Areas: {', '.join(investigation.get('focus_areas', ['all']))}

Code:
```{language}
{code[:10000]}
```

List every vulnerability. JSON array:
[{{"title": "...", "severity": "critical|high|medium|low", "category": "...", "description": "..."}}]"""

    # Arm-specific methodology prefix (short, doesn't overwhelm)
    if config["use_hound_graph"]:
        prompt = "Mode: graph-driven analysis. Map authorization flows and value flows.\n\n" + prompt
    elif config["use_cf_audit"]:
        prompt = "Mode: independent verification. Each finding must be reproducible.\n\n" + prompt
    elif config["use_tob_skills"]:
        prompt = "Mode: entry-point analysis + data flow tracing + false positive check.\n\n" + prompt

    # Trail of Bits variant: add entry-point analysis + FP checking
    if config["use_tob_skills"]:
        prompt = (
            "You are a senior security auditor using Trail of Bits methodology.\n"
            "1. ENTRY POINT ANALYSIS: Identify all external entry points (public/external functions)\n"
            "2. DATA FLOW: Trace data from entry points through state changes\n"
            "3. ACCESS CONTROL: Verify authorization at each state change\n"
            "4. FALSE POSITIVE CHECK: For each finding, verify it's actually exploitable\n"
            "5. SEVERITY: Rate based on actual impact, not theoretical risk\n\n"
            + prompt
        )

    # Cloudflare variant: add independent verification thinking
    if config["use_cf_audit"]:
        prompt = (
            "You are a security auditor using Cloudflare's audit methodology.\n"
            "Your findings will be independently verified by another auditor.\n"
            "Focus on reproducible, verifiable findings with concrete evidence.\n"
            "Do NOT report theoretical risks — only issues you can demonstrate.\n\n"
            + prompt
        )

    result = call_model("mimo", prompt, max_tokens=3000)
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


# ─── Verifier: independent validation ────────────────────────────────

VERIFIER_PROMPT = """You are an independent security verifier. Another auditor has submitted these findings.
Your job: verify each finding is real and not a false positive.

Submitted findings:
{findings}

For each finding, determine:
{{
  "verifications": [
    {{
      "finding_index": 0,
      "verified": true/false,
      "reason": "why verified or false positive",
      "severity_adjustment": "keep|upgrade|downgrade",
      "actual_severity": "critical|high|medium|low"
    }}
  ]
}}

Be strict. Only verify findings you can confirm from the code.
Return ONLY valid JSON."""


def verifier(code: str, findings: list[dict], language: str = "solidity") -> list[dict]:
    """Verifier phase: independent validation of findings."""
    if not findings:
        return []

    prompt = VERIFIER_PROMPT.format(
        findings=json.dumps(findings, indent=2)[:6000],
    )
    result = call_model("mimo", prompt, max_tokens=2000)

    if not result["ok"]:
        return findings  # Return unverified if verifier fails

    try:
        start = result["content"].find("{")
        end = result["content"].rfind("}") + 1
        if start >= 0 and end > start:
            verifications = json.loads(result["content"][start:end])
            verified = []
            for i, f in enumerate(findings):
                v = verifications.get("verifications", [])[i] if i < len(verifications.get("verifications", [])) else {}
                if v.get("verified", True):
                    if v.get("severity_adjustment") == "downgrade":
                        f["severity"] = v.get("actual_severity", f["severity"])
                    verified.append(f)
            return verified
    except Exception:
        pass
    return findings


# ─── Main pipeline ───────────────────────────────────────────────────

def analyze_code(code: str, language: str = "solidity", arm: str = "A") -> dict:
    """Full Scout/Strategist/Analyst/Verifier pipeline with process arms."""
    # Phase 1: Scout explores
    scout_result = scout(code, language, arm)
    investigations = scout_result.get("investigations", [])

    # Phase 2: Strategist plans
    if investigations:
        strategy = strategist(investigations, arm)
        planned = strategy.get("investigations", investigations)
    else:
        planned = [{"goal": "general vulnerability scan", "focus_areas": ["all"], "priority": 5}]

    # Phase 3: Analyst investigates each area
    all_findings = []
    for inv in planned[:5]:  # Top 5 investigations
        findings = analyst(code, inv, language, arm)
        all_findings.extend(findings)

    # Phase 4: Verifier validates (always runs, independent of arm)
    verified = verifier(code, all_findings, language)

    # Deduplicate
    seen_titles = set()
    unique = []
    for f in verified:
        title = f.get("title", "").lower()
        if title not in seen_titles:
            seen_titles.add(title)
            unique.append(f)

    return {
        "prediction": len(unique) > 0,
        "vulnerabilities": unique,
        "process_arm": arm,
        "process_name": PROCESS_ARMS.get(arm, {}).get("name", "unknown"),
        "scout_areas": len(investigations),
        "strategist_plans": len(planned),
        "analyst_findings": len(all_findings),
        "verified_findings": len(unique),
    }


def predict(code: str, arm: str = "A") -> dict:
    """Drop-in for bitsec.miner.predict."""
    return analyze_code(code, arm=arm)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Bitsec Agent v5")
    parser.add_argument("file", help="Source file to analyze")
    parser.add_argument("--arm", choices=["A", "B", "C", "D"], default="A",
                        help="Process arm (A=default, B=hound, C=cloudflare, D=tob)")
    args = parser.parse_args()

    result = analyze_code(Path(args.file).read_text(), arm=args.arm)
    print(json.dumps(result, indent=2))
