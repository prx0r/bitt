"""BitSec Agent v2 — Scout/Senior two-pass architecture with static analysis."""
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from pydantic import BaseModel

# Proxy config
PROXY = "http://localhost:8087"
API_KEY = "sk-A5QHR5MRtUNec7BWqiRsZ0GAYck0CRT2Movsk7Q6U3UwcV77Y6G3TMXOhhyKh855"
MODEL = "mimo-v2.5"

# File patterns
CONTRACT_PATTERNS = ['**/*.sol', '**/*.vy', '**/*.cairo', '**/*.rs']
EXCLUDE_DIRS = {"testing", "mocks", "examples", "interfaces", "script", "broadcast", "libraries"}


def call_llm(messages, max_tokens=8192, temperature=0.1):
    """Call LLM through proxy."""
    for attempt in range(3):
        try:
            resp = requests.post(f"{PROXY}/inference", headers={
                "x-inference-api-key": API_KEY,
                "x-agent-id": "agent-v2",
                "x-job-run-id": f"v2-{int(time.time())}-{attempt}",
                "x-request-phase": "execution"
            }, json={
                "model": MODEL,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature
            }, timeout=300)
            if resp.status_code == 200:
                r = resp.json()
                if "choices" in r and r["choices"]:
                    content = r["choices"][0].get("message", {}).get("content", "")
                    if content:
                        return content
        except:
            pass
        time.sleep(2)
    return ""


def discover_files(source_dir):
    """Discover contract files."""
    files = []
    for p in CONTRACT_PATTERNS:
        files.extend(source_dir.glob(p))
    return [
        f for f in files
        if f.is_file()
        and "test" not in f.name.lower()
        and not any(part.lower() in EXCLUDE_DIRS for part in f.parts)
    ]


def read_file_safe(path, max_chars=20000):
    """Read file with generous limit."""
    try:
        return path.read_text(encoding="utf-8")[:max_chars]
    except:
        return ""


# ── Static Analysis ──────────────────────────────────────────────

class StaticAnalyzer:
    """Regex-based static analysis that pre-filters risky patterns."""

    def __init__(self, source_dir):
        self.source_dir = source_dir
        self.contracts = {}  # name -> {file, functions, state_vars, external_calls}
        self.call_graph = {}  # function -> set of callees
        self.risky_patterns = []

    def analyze(self):
        """Run static analysis on all files."""
        files = discover_files(self.source_dir)

        for f in files:
            content = read_file_safe(f, 30000)
            rel = str(f.relative_to(self.source_dir))
            self._parse_file(rel, content)

        self._find_risky_patterns()
        return {
            "contracts": self.contracts,
            "call_graph": self.call_graph,
            "risky_patterns": self.risky_patterns,
            "file_count": len(files),
            "contract_count": len(self.contracts),
        }

    def _parse_file(self, rel_path, content):
        """Extract contracts, functions, state vars from Solidity-like code."""
        # Find contract/interface/library definitions
        contract_matches = re.finditer(
            r'(?:contract|interface|library|module)\s+(\w+)(?:\s+is\s+([^{]+))?\s*\{',
            content
        )

        for m in contract_matches:
            name = m.group(1)
            parents = [p.strip() for p in (m.group(2) or "").split(",") if p.strip()]

            # Extract functions within this contract
            body_start = m.end()
            # Find matching closing brace (simple heuristic)
            depth = 1
            pos = body_start
            while pos < len(content) and depth > 0:
                if content[pos] == '{':
                    depth += 1
                elif content[pos] == '}':
                    depth -= 1
                pos += 1
            body = content[body_start:pos]

            functions = []
            for fm in re.finditer(r'function\s+(\w+)\s*\(([^)]*)\)\s*(\w+)?', body):
                func_name = fm.group(1)
                params = fm.group(2)
                visibility = fm.group(3) or "internal"
                functions.append({
                    "name": func_name,
                    "params": params,
                    "visibility": visibility,
                })

            # Extract state variables
            state_vars = re.findall(
                r'(?:mapping|uint\d*|int\d*|address|bool|string|bytes\d*|address)\s+(?:public\s+|private\s+|internal\s+)?(\w+)',
                body
            )

            # Extract external calls
            external_calls = re.findall(
                r'(?:I[A-Z]\w+|[A-Z]\w+)\s*\.\s*\w+\s*\(',
                body
            )

            self.contracts[name] = {
                "file": rel_path,
                "parents": parents,
                "functions": functions,
                "state_vars": state_vars,
                "external_calls": external_calls,
                "body_preview": body[:2000],
            }

            # Build call graph
            for func in functions:
                caller = f"{name}.{func['name']}"
                callees = set()
                # Find calls to other contracts
                for ec in external_calls:
                    callee_name = ec.split('.')[0]
                    if callee_name != name:
                        callees.add(callee_name)
                self.call_graph[caller] = callees

    def _find_risky_patterns(self):
        """Identify high-risk patterns from static analysis."""
        for name, info in self.contracts.items():
            for func in info["functions"]:
                func_id = f"{name}.{func['name']}"

                # Public functions without access control modifiers
                if func["visibility"] in ("public", "external"):
                    # Check if body has modifier-like patterns
                    has_modifier = any(
                        mod in func.get("params", "").lower()
                        for mod in ["onlyowner", "onlyadmin", "require(msg.sender"]
                    )
                    if not has_modifier:
                        self.risky_patterns.append({
                            "pattern": "public_no_access_control",
                            "function": func_id,
                            "file": info["file"],
                            "description": f"Public function {func['name']} may lack access control",
                        })

                # State writes followed by external calls (reentrancy)
                body = info.get("body_preview", "")
                if func["name"] in body:
                    # Simple heuristic: function body has both state write and external call
                    has_state_write = "=" in body and not body.strip().startswith("//")
                    has_external_call = bool(re.search(r'\.\s*\w+\s*\(', body))
                    if has_state_write and has_external_call:
                        self.risky_patterns.append({
                            "pattern": "reentrancy_candidate",
                            "function": func_id,
                            "file": info["file"],
                            "description": f"Function {func['name']} may have state write + external call pattern",
                        })

    def get_summary(self, max_contracts=10, max_functions_per=5):
        """Get compact summary for Scout pass."""
        summary = f"Static Analysis: {len(self.contracts)} contracts, {len(self.risky_patterns)} risky patterns\n\n"

        for i, (name, info) in enumerate(list(self.contracts.items())[:max_contracts]):
            summary += f"Contract: {name} ({info['file']})\n"
            summary += f"  Parents: {info['parents']}\n"
            funcs = info["functions"][:max_functions_per]
            summary += f"  Functions: {', '.join(f['name'] + '(' + f['visibility'] + ')' for f in funcs)}\n"
            if len(info["functions"]) > max_functions_per:
                summary += f"  ... +{len(info['functions']) - max_functions_per} more\n"
            summary += f"  State vars: {', '.join(info['state_vars'][:5])}\n"
            summary += f"  External calls: {', '.join(info['external_calls'][:5])}\n\n"

        if self.risky_patterns:
            summary += f"Risky Patterns Detected ({len(self.risky_patterns)} total):\n"
            for p in self.risky_patterns[:15]:
                summary += f"  [{p['pattern']}] {p['function']}: {p['description']}\n"

        return summary

    def get_code_context(self, function_id, max_lines=50):
        """Get code for a specific function."""
        parts = function_id.split('.')
        if len(parts) != 2:
            return ""
        contract_name, func_name = parts

        if contract_name not in self.contracts:
            return ""

        info = self.contracts[contract_name]
        file_path = self.source_dir / info["file"]
        content = read_file_safe(file_path, 50000)

        # Find the function in the file
        pattern = rf'function\s+{re.escape(func_name)}\s*\('
        match = re.search(pattern, content)
        if not match:
            return ""

        # Extract function body
        start = match.start()
        depth = 0
        pos = match.end()
        found_first = False
        while pos < len(content):
            if content[pos] == '{':
                depth += 1
                found_first = True
            elif content[pos] == '}':
                if found_first and depth == 0:
                    break
                depth -= 1
            pos += 1

        func_code = content[start:pos+1]
        # Limit lines
        lines = func_code.split('\n')[:max_lines]
        return '\n'.join(lines)


# ── Scout Pass ────────────────────────────────────────────────────

SCOUT_SYSTEM_PROMPT = """You are a security Scout agent. Your job is to quickly scan smart contract code and identify high-risk areas.

Focus on:
1. Access Control: Public functions without proper modifiers
2. Accounting: Functions that update balances/rewards/state
3. Reentrancy: External calls after state changes
4. Upgradeability: Critical admin functions, proxy patterns
5. Asset Transfers: Functions moving tokens/ETH
6. Cross-contract interactions: State synchronization issues
7. Business logic: Invariants that could be violated

Return your findings as a JSON array with this structure:
[
  {
    "area": "descriptive name of the risk area",
    "risk_type": "access_control|reentrancy|logic_error|cross_contract|math_error|other",
    "confidence": 0.0-1.0,
    "reasoning": "why this is high risk",
    "relevant_functions": ["Contract.function1", "Contract.function2"],
    "relevant_files": ["path/to/file.sol"]
  }
]

Focus on the 5-10 MOST risky areas. Quality over quantity."""


def scout_pass(source_dir, static_summary, project_name):
    """Scout pass: identify high-risk areas from static analysis summary."""
    messages = [
        {"role": "system", "content": SCOUT_SYSTEM_PROMPT},
        {"role": "user", "content": f"""Analyze this smart contract project and identify high-risk security areas.

PROJECT: {project_name}

{static_summary}

Identify the 5-10 most critical areas that need deep analysis. For each area, specify which functions and files are relevant.

Return ONLY a JSON array of findings."""}
    ]

    response = call_llm(messages, max_tokens=4096)

    # Parse JSON
    try:
        match = re.search(r'\[[\s\S]*\]', response)
        if match:
            return json.loads(match.group())
    except:
        pass

    # Fallback: try to extract from text
    try:
        match = re.search(r'\{[\s\S]*\}', response)
        if match:
            data = json.loads(match.group())
            if "findings" in data:
                return data["findings"]
    except:
        pass

    return []


# ── Senior Pass ───────────────────────────────────────────────────

SENIOR_SYSTEM_PROMPT = """You are a security Senior agent. Your job is to deeply analyze specific high-risk areas and confirm vulnerabilities.

For each area, you must:
1. Read the actual code carefully
2. Trace the call graph to understand the full flow
3. Identify the specific vulnerability
4. Provide a detailed explanation with exact function names
5. Rate severity (critical/high/medium/low)

Return findings as a JSON array:
[
  {
    "title": "Specific vulnerability title",
    "description": "Detailed explanation of the vulnerability",
    "vulnerability_type": "reentrancy|access_control|logic_error|math_error|cross_contract|other",
    "severity": "critical|high|medium|low",
    "confidence": 0.0-1.0,
    "location": "ContractName.functionName()",
    "file": "path/to/file.sol"
  }
]

Be specific. Name exact functions. Explain the root cause and impact."""


def senior_pass(source_dir, scout_findings, static_analyzer, project_name):
    """Senior pass: deep analysis of each Scout finding."""
    all_findings = []

    for i, scout_finding in enumerate(scout_findings):
        area = scout_finding.get("area", "unknown")
        risk_type = scout_finding.get("risk_type", "other")
        relevant_funcs = scout_finding.get("relevant_functions", [])
        relevant_files = scout_finding.get("relevant_files", [])

        print(f"    [{i+1}/{len(scout_findings)}] {area}", flush=True)

        # Build code context
        code_context = ""
        for func_id in relevant_funcs[:3]:
            code = static_analyzer.get_code_context(func_id)
            if code:
                code_context += f"\n--- {func_id} ---\n{code}\n"

        # If no specific functions, read relevant files
        if not code_context:
            for f_path in relevant_files[:2]:
                full_path = source_dir / f_path
                if full_path.exists():
                    content = read_file_safe(full_path, 8000)
                    code_context += f"\n--- {f_path} ---\n{content}\n"

        if not code_context:
            continue

        # Get call graph context
        call_context = ""
        for func_id in relevant_funcs:
            if func_id in static_analyzer.call_graph:
                callees = static_analyzer.call_graph[func_id]
                if callees:
                    call_context += f"{func_id} calls: {', '.join(callees)}\n"

        prompt = f"""Analyze this high-risk area in detail.

PROJECT: {project_name}
AREA: {area}
RISK TYPE: {risk_type}
SCOUT REASONING: {scout_finding.get('reasoning', 'N/A')}

CODE:
{code_context}

CALL GRAPH:
{call_context if call_context else 'No cross-contract calls detected'}

Does this code contain a real, exploitable vulnerability? Be specific about:
- The exact function and line
- The root cause
- The impact
- How it could be exploited

Return ONLY a JSON array of findings (empty array if no vulnerability confirmed)."""

        messages = [
            {"role": "system", "content": SENIOR_SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ]

        response = call_llm(messages, max_tokens=4096)

        try:
            match = re.search(r'\[[\s\S]*\]', response)
            if match:
                findings = json.loads(match.group())
                for f in findings:
                    f["scout_area"] = area
                    f["scout_risk_type"] = risk_type
                all_findings.extend(findings)
        except:
            pass

        time.sleep(0.5)

    return all_findings


# ── Main Agent ────────────────────────────────────────────────────

def analyze_project(source_dir, project_name):
    """Full two-pass analysis."""
    print(f"  Phase 0: Static analysis...", flush=True)
    analyzer = StaticAnalyzer(source_dir)
    static_result = analyzer.analyze()
    static_summary = analyzer.get_summary()

    print(f"  Phase 1: Scout pass...", flush=True)
    scout_findings = scout_pass(source_dir, static_summary, project_name)
    print(f"    Found {len(scout_findings)} high-risk areas", flush=True)

    print(f"  Phase 2: Senior pass...", flush=True)
    senior_findings = senior_pass(source_dir, scout_findings, analyzer, project_name)
    print(f"    Found {len(senior_findings)} confirmed findings", flush=True)

    # Normalize severities
    severity_map = {
        "p0": "critical", "p1": "high", "p2": "medium", "p3": "low",
        "critical": "critical", "high": "high", "medium": "medium", "low": "low",
        "informational": "low", "info": "low", "none": "low",
    }
    for f in senior_findings:
        sev = f.get("severity", "medium").lower()
        f["severity"] = severity_map.get(sev, "medium")
        f["reported_by_model"] = MODEL

    # Deduplicate
    seen = set()
    unique = []
    for f in senior_findings:
        key = f.get("title", "") + f.get("location", "")
        h = hashlib.md5(key.encode()).hexdigest()[:16]
        if h not in seen:
            seen.add(h)
            unique.append(f)

    return unique, static_result


def agent_main(project_dir="/app/project_code", inference_api=None):
    """Entry point — matches official BitSec format."""
    source_dir = Path(project_dir)
    project_name = source_dir.name

    if not source_dir.exists():
        print(f"Error: {project_dir} not found")
        sys.exit(1)

    findings, static_result = analyze_project(source_dir, project_name)

    output = {
        "project": project_name,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "files_analyzed": static_result.get("file_count", 0),
        "files_skipped": 0,
        "total_vulnerabilities": len(findings),
        "vulnerabilities": findings,
        "token_usage": {"total_input": 0, "total_output": 0},
    }

    # Save report
    output_file = source_dir / "agent_report.json"
    with open(output_file, 'w') as f:
        json.dump(output, f, indent=2)

    print(f"\nAnalysis complete: {len(findings)} vulnerabilities")
    return output


if __name__ == "__main__":
    project_dir = sys.argv[1] if len(sys.argv) > 1 else "/app/project_code"
    agent_main(project_dir)
