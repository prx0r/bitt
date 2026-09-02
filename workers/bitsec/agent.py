"""Bitsec Agent v1 — self-contained vulnerability detector.

Does not import bitsec package (incompatible with v11 SDK).
Implements the same protocol types locally.

Usage:
  python workers/bitsec/agent.py <file>
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from typing import List, Optional


# ─── Protocol types (self-contained) ─────────────────────────────

@dataclass
class LineRange:
    start: int
    end: int

@dataclass
class Vulnerability:
    title: str
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW
    line_ranges: List[LineRange] = field(default_factory=list)
    category: str = "general"
    description: str = ""
    vulnerable_code: str = ""
    code_to_exploit: str = ""
    rewritten_code_to_fix_vulnerability: str = ""

@dataclass
class PredictionResponse:
    prediction: bool = False
    vulnerabilities: List[Vulnerability] = field(default_factory=list)


# ─── Enhanced prompt ──────────────────────────────────────────────

ANALYSIS_PROMPT = """You are an expert security auditor. Analyze this code for vulnerabilities.

For each vulnerability:
1. Title (concise)
2. Severity: CRITICAL/HIGH/MEDIUM/LOW
3. Line ranges
4. Category: reentrancy/access_control/unchecked_return/general
5. Description + financial impact
6. Vulnerable code snippet
7. Exploit code
8. Fix

Code:
```{language}
{code}
```

Return JSON: {{"prediction": true/false, "vulnerabilities": [...]}}
If clean, return {{"prediction": false, "vulnerabilities": []}}
"""


# ─── Structural analysis ──────────────────────────────────────────

def analyze_structural(code: str) -> list[dict]:
    """Pattern-based vulnerability detection."""
    findings = []
    lines = code.split('\n')

    patterns = [
        (r'\.call\{.*value.*\}\(|\.transfer\(|\.send\(',
         "Reentrancy Risk", "HIGH", "reentrancy"),
        (r'selfdestruct\(|suicide\(',
         "Selfdestruct", "HIGH", "access_control"),
        (r'tx\.origin',
         "tx.origin Auth", "MEDIUM", "access_control"),
        (r'\.call\(|\.delegatecall\(|\.staticcall\(',
         "Unchecked External Call", "MEDIUM", "unchecked_return"),
        (r'block\.timestamp',
         "Timestamp Dependence", "LOW", "general"),
        (r'block\.number',
         "Block Number Dependence", "LOW", "general"),
    ]

    for line_num, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith('//') or stripped.startswith('/*') or stripped.startswith('*'):
            continue
        for pattern, name, severity, category in patterns:
            if re.search(pattern, line):
                findings.append({
                    "line": line_num,
                    "name": name,
                    "severity": severity,
                    "category": category,
                    "code": stripped,
                })

    return findings


# ─── LLM analysis ─────────────────────────────────────────────────

def analyze_llm(code: str, language: str = "solidity") -> list[dict]:
    """LLM-based deep analysis."""
    try:
        import os
        api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("CHUTES_API_KEY")
        if not api_key:
            return []

        import http.client, ssl, json as _json
        ctx = ssl.create_default_context()

        prompt = ANALYSIS_PROMPT.format(code=code, language=language)
        payload = _json.dumps({
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 4000,
            "temperature": 0.1,
        })

        conn = http.client.HTTPSConnection("api.openai.com", context=ctx, timeout=60)
        conn.request("POST", "/v1/chat/completions", body=payload, headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        })
        resp = conn.getresponse()
        body = _json.loads(resp.read().decode())
        conn.close()

        content = body["choices"][0]["message"]["content"]

        # Parse JSON from response
        start = content.find("{")
        end = content.rfind("}") + 1
        if start >= 0 and end > start:
            result = _json.loads(content[start:end])
            vulns = result.get("vulnerabilities", [])
            return vulns

    except Exception:
        pass
    return []


# ─── Main analysis ────────────────────────────────────────────────

def analyze(code: str, language: str = "solidity") -> PredictionResponse:
    """Multi-pass vulnerability detection."""
    # Pass 1: Structural
    structural = analyze_structural(code)

    # Pass 2: LLM (if available)
    llm_findings = analyze_llm(code, language)

    # Combine
    all_findings = []

    for f in structural:
        all_findings.append(Vulnerability(
            title=f["name"],
            severity=f["severity"],
            line_ranges=[LineRange(start=f["line"], end=f["line"])],
            category=f["category"],
            description=f"Pattern detection: {f['name']} at line {f['line']}",
            vulnerable_code=f["code"],
            code_to_exploit="// Depends on context",
            rewritten_code_to_fix_vulnerability="// Depends on context",
        ))

    for f in llm_findings:
        line_ranges = []
        for lr in f.get("line_ranges", []):
            if isinstance(lr, dict):
                line_ranges.append(LineRange(start=lr.get("start", 1), end=lr.get("end", lr.get("start", 1))))
        all_findings.append(Vulnerability(
            title=f.get("title", "LLM Finding"),
            severity=f.get("severity", "MEDIUM"),
            line_ranges=line_ranges,
            category=f.get("category", "general"),
            description=f.get("description", ""),
            vulnerable_code=f.get("vulnerable_code", ""),
            code_to_exploit=f.get("code_to_exploit", ""),
            rewritten_code_to_fix_vulnerability=f.get("rewritten_code_to_fix_vulnerability", ""),
        ))

    # Deduplicate by title + line
    seen = set()
    unique = []
    for v in all_findings:
        key = (v.title.lower(), v.line_ranges[0].start if v.line_ranges else 0)
        if key not in seen:
            seen.add(key)
            unique.append(v)

    # Sort by severity
    severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    unique.sort(key=lambda v: severity_order.get(v.severity, 4))

    return PredictionResponse(
        prediction=len(unique) > 0,
        vulnerabilities=unique,
    )


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python agent.py <file>")
        sys.exit(1)

    filepath = sys.argv[1]
    with open(filepath) as f:
        code = f.read()

    # Detect language from extension
    ext = Path(filepath).suffix.lower()
    lang_map = {".sol": "solidity", ".rs": "rust", ".py": "python", ".js": "javascript", ".ts": "typescript"}
    lang = lang_map.get(ext, "solidity")

    result = analyze(code, lang)

    print(f"\n{'='*60}")
    print(f"Prediction: {result.prediction}")
    print(f"Vulnerabilities: {len(result.vulnerabilities)}")
    print(f"{'='*60}")

    for i, v in enumerate(result.vulnerabilities, 1):
        print(f"\n[{v.severity}] {v.title}")
        print(f"  Category: {v.category}")
        if v.line_ranges:
            print(f"  Lines: {v.line_ranges[0].start}-{v.line_ranges[0].end}")
        print(f"  {v.description[:200]}")
