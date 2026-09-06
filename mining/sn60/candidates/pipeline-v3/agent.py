"""BitSec Pipeline Agent v3 — Structural fix: per-entry-point analysis.

Fixes from v1/v2:
  1. Per-entry-point analysis (not per-file dedup) — biggest info-loss bug
  2. Unified FindingHypothesis schema across all phases
  3. Phase 1 produces related_files per entry point
  4. Language-specific static analysis (Solidity: Slither patterns, CosmWasm: ExecuteMsg)
  5. Stricter verification (require concrete invariant violation)
  6. Environment variables only (no hardcoded creds)

Architecture:
  Phase 0: Language-aware static analysis
  Phase 1: Protocol understanding + entry-point inventory with related_files
  Phase 2: Per-entry-point state-machine trace (one trace per function)
  Phase 3: Strict verification (require violated invariant, concrete state transition)
  Phase 4: Cross-file correlation + typed report
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

import requests

# ── Config ────────────────────────────────────────────────────────
PROXY = os.environ.get("INFERENCE_API", "http://localhost:8087")
API_KEY = os.environ.get("INFERENCE_API_KEY", "")
MODEL = os.environ.get("OPENAI_MODEL", "mimo-v2.5")
AGENT_ID = os.environ.get("AGENT_ID", "pipeline-v3")

EXCLUDE_DIRS = {"testing", "mocks", "examples", "interfaces", "script",
                "broadcast", "libraries", "node_modules", "lib", "deps", "target"}
SOLIDITY_PATTERNS = ['**/*.sol']
RUST_PATTERNS = ['**/*.rs']
COSMWASM_PATTERNS = ['**/*.rs']  # CosmWasm is Rust
ALL_PATTERNS = ['**/*.sol', '**/*.vy', '**/*.cairo', '**/*.rs', '**/*.move']

LOG_DIR = Path("/root/bitt/data/pipeline-logs")

# ── Strategy Config (CGE writes this, agent reads it) ─────────────
STRATEGY_CONFIG_PATH = Path("/root/bitt/data/active_strategy.json")


def load_strategy_config() -> dict:
    """Load strategy config if CGE wrote one. Returns empty dict if not found."""
    if STRATEGY_CONFIG_PATH.exists():
        try:
            cfg = json.loads(STRATEGY_CONFIG_PATH.read_text())
            # Age check: ignore stale configs (>5 min old)
            ts = cfg.get("timestamp", 0)
            if time.time() - ts < 300:
                return cfg
        except:
            pass
    return {}


def get_prompt(key: str, default: str) -> str:
    """Get a prompt from strategy config, falling back to hardcoded default."""
    cfg = load_strategy_config()
    prompts = cfg.get("prompts", {})
    return prompts.get(key, default)


# ── Unified Finding Schema ────────────────────────────────────────

@dataclass
class FindingHypothesis:
    """One immutable finding object carried through all phases."""
    id: str = ""
    title: str = ""
    invariant: str = ""                # what should hold
    entry_point: str = ""              # function/method name
    affected_function: str = ""        # where the bug lives
    file: str = ""
    lines: list[int] = field(default_factory=list)
    related_files: list[str] = field(default_factory=list)
    preconditions: list[str] = field(default_factory=list)
    state_before: str = ""
    action_sequence: list[str] = field(default_factory=list)
    state_after: str = ""
    violated_property: str = ""
    impact: str = ""
    category: str = ""
    severity: str = "medium"
    confidence: float = 0.5
    evidence: list[str] = field(default_factory=list)
    status: str = "hypothesis"  # hypothesis → confirmed → rejected
    verification_notes: str = ""
    trace_region: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def _finding_id(title: str, file: str, entry_point: str) -> str:
    src = f"{title}:{file}:{entry_point}"
    return hashlib.md5(src.encode()).hexdigest()[:12]


# ── LLM Call ──────────────────────────────────────────────────────

def call_llm(messages, max_tokens=8192, temperature=0.1, model=None):
    model = model or MODEL
    for attempt in range(3):
        try:
            resp = requests.post(f"{PROXY}/inference", headers={
                "x-inference-api-key": API_KEY,
                "x-agent-id": AGENT_ID,
                "x-job-run-id": f"v3-{int(time.time())}-{attempt}",
                "x-request-phase": "execution"
            }, json={
                "model": model, "messages": messages,
                "max_tokens": max_tokens, "temperature": temperature
            }, timeout=300)
            if resp.status_code == 200:
                r = resp.json()
                if "choices" in r and r["choices"]:
                    content = r["choices"][0].get("message", {}).get("content", "")
                    if content and len(content) > 10:
                        return content
        except:
            pass
        time.sleep(2)
    return ""


def parse_json_from_text(text):
    """Extract JSON from LLM text. Try array first, then object."""
    for pattern in [r'\[[\s\S]*\]', r'\{[\s\S]*\}']:
        match = re.search(pattern, text)
        if match:
            try:
                return json.loads(match.group())
            except:
                pass
    return None


# ── File Discovery ────────────────────────────────────────────────

def discover_files(source_dir):
    files = []
    for p in ALL_PATTERNS:
        files.extend(source_dir.glob(p))
    return [f for f in files if f.is_file()
            and "test" not in f.name.lower()
            and not any(part.lower() in EXCLUDE_DIRS for part in f.parts)]


def read_file(path, max_chars=50000):
    try:
        return path.read_text(encoding="utf-8")[:max_chars]
    except:
        return ""


def detect_languages(source_dir):
    exts = set()
    for f in source_dir.rglob("*"):
        if f.is_file():
            exts.add(f.suffix.lower())
    langs = []
    if any(e in exts for e in ['.sol']):
        langs.append('solidity')
    if any(e in exts for e in ['.vy']):
        langs.append('vyper')
    if any(e in exts for e in ['.cairo']):
        langs.append('cairo')
    if any(e in exts for e in ['.rs']):
        langs.append('rust')
    if any(e in exts for e in ['.move']):
        langs.append('move')
    return langs


# ══════════════════════════════════════════════════════════════════
# PHASE 0: Language-Aware Static Analysis
# ══════════════════════════════════════════════════════════════════

def phase0_static_analysis(source_dir, languages):
    """Language-aware static analysis. No generic regex on CosmWasm."""
    print("  [Phase 0] Static analysis...", flush=True)
    findings = []

    if 'solidity' in languages:
        findings.extend(_static_solidity(source_dir))
    if 'rust' in languages:
        findings.extend(_static_rust_cosmawasm(source_dir))

    print(f"    Total Phase 0: {len(findings)} findings", flush=True)
    return {"findings": findings}


def _static_solidity(source_dir):
    """Solidity-specific patterns: external calls, access control, reentrancy."""
    findings = []
    for f in discover_files(source_dir):
        if not f.suffix == '.sol':
            continue
        content = read_file(f, 30000)
        rel = str(f.relative_to(source_dir))
        lines = content.split('\n')

        for i, line in enumerate(lines):
            # External calls without return check
            if re.search(r'\.\s*(?:call|send|transfer)\s*\(', line):
                # Check if return value is checked
                has_check = False
                for j in range(max(0, i-3), min(len(lines), i+5)):
                    if 'require' in lines[j] or 'assert' in lines[j] or 'if' in lines[j]:
                        has_check = True
                        break
                if not has_check:
                    findings.append({
                        "tool": "solidity-static", "detector": "unchecked_external_call",
                        "file": rel, "line": i+1,
                        "raw_message": f"External call at line {i+1} without return check"
                    })

            # tx.origin usage
            if 'tx.origin' in line and not line.strip().startswith('//'):
                findings.append({
                    "tool": "solidity-static", "detector": "tx_origin",
                    "file": rel, "line": i+1,
                    "raw_message": f"tx.origin used at line {i+1}"
                })

    return findings


def _static_rust_cosmawasm(source_dir):
    """CosmWasm/Rust patterns: ExecuteMsg dispatch, BankMsg, storage mutations."""
    findings = []
    for f in discover_files(source_dir):
        if not f.suffix == '.rs':
            continue
        content = read_file(f, 30000)
        rel = str(f.relative_to(source_dir))

        # ExecuteMsg dispatch — entry points
        for m in re.finditer(r'ExecuteMsg::(\w+)', content):
            line = content[:m.start()].count('\n') + 1
            findings.append({
                "tool": "cosmawasm-static", "detector": "execute_entry_point",
                "file": rel, "line": line,
                "raw_message": f"ExecuteMsg variant: {m.group(1)} at line {line}"
            })

        # BankMsg sends
        for m in re.finditer(r'BankMsg::Send', content):
            line = content[:m.start()].count('\n') + 1
            findings.append({
                "tool": "cosmawasm-static", "detector": "bank_send",
                "file": rel, "line": line,
                "raw_message": f"BankMsg::Send at line {line}"
            })

        # Storage mutations (deps.storage)
        for m in re.finditer(r'(?:save|set|update)\s*\(', content):
            line = content[:m.start()].count('\n') + 1
            findings.append({
                "tool": "cosmawasm-static", "detector": "storage_mutation",
                "file": rel, "line": line,
                "raw_message": f"Storage mutation at line {line}"
            })

    return findings


# ══════════════════════════════════════════════════════════════════
# PHASE 1: Protocol Understanding + Entry-Point Inventory
# ══════════════════════════════════════════════════════════════════

PHASE1_SYSTEM = """You are a security auditor performing Phase 1 of a vulnerability audit.
Your job: UNDERSTAND THE PROTOCOL and produce a complete ENTRY-POINT INVENTORY.

You do NOT find vulnerabilities yet. You build the foundation for Phase 2.

STEP 1 — Understand the protocol:
- What does this protocol do? What problem does it solve?
- What assets/tokens does it handle?
- What are the core business rules and invariants?
- What state transitions exist?

STEP 2 — Entry-point inventory (THIS IS CRITICAL):
For EVERY function reachable by an external actor, produce an entry with:
  - function: exact function/method name
  - file: which file it's in
  - line: line number (approximate is fine)
  - related_files: ALL files that this function reads/writes state in
    (callers, callees, storage files, shared state). This is the most
    important field. If unsure, include MORE files not fewer.
  - untrusted_input: what flows in from outside
  - state_modified: what state does this function change
  - lifecycle: what part of the protocol lifecycle does this touch
  - invariants_that_must_hold: what must be true after this function runs

STEP 3 — Business logic risks:
Based on your protocol understanding, where are the highest-risk areas
for BUSINESS LOGIC errors? (slippage, rounding, fee calc, state machines,
access control, cross-contract sync)

STEP 4 — Invariant hypotheses:
For each key invariant, state: "IF [condition] THEN [invariant]"
These are what Phase 2 will test.

Output ONLY valid JSON."""


def phase1_protocol_understanding(source_dir, project_name, static_results):
    """Phase 1: Understand protocol + produce entry-point inventory with related_files."""
    print("  [Phase 1] Protocol understanding + entry-point inventory...", flush=True)

    files = discover_files(source_dir)
    file_contents = {}
    for f in files:
        rel = str(f.relative_to(source_dir))
        content = read_file(f, 50000)
        if content:
            file_contents[rel] = content

    # Build complete file tree for context
    file_tree = "\n".join(sorted(file_contents.keys()))

    # Batch file contents
    batches = []
    current_batch = ""
    current_size = 0
    for rel, content in file_contents.items():
        entry = f"\n--- {rel} ---\n{content}\n"
        if current_size + len(entry) > 25000:
            batches.append(current_batch)
            current_batch = ""
            current_size = 0
        current_batch += entry
        current_size += len(entry)
    if current_batch:
        batches.append(current_batch)

    all_arch_maps = []
    for i, batch in enumerate(batches):
        print(f"    Batch {i+1}/{len(batches)} ({len(batch)} chars)", flush=True)

        user_prompt = f"""Repository: {project_name}
Language(s): {', '.join(detect_languages(source_dir))}

COMPLETE FILE TREE (all {len(files)} files):
{file_tree}

BATCH CONTENTS ({i+1}/{len(batches)}):
{batch}

Static analysis findings:
{json.dumps(static_results['findings'][:30], indent=2)}

STEP 1: Understand the protocol.
STEP 2: Inventory EVERY entry point with related_files.
STEP 3: Identify business logic risks.
STEP 4: State invariant hypotheses.

Output ONLY valid JSON."""

        response = call_llm([
            {"role": "system", "content": get_prompt("phase1", PHASE1_SYSTEM)},
            {"role": "user", "content": user_prompt}
        ], max_tokens=8192, temperature=0.1)

        arch_map = parse_json_from_text(response)
        if arch_map:
            all_arch_maps.append(arch_map)

    merged = _merge_arch_maps(all_arch_maps)
    print(f"    Protocol: {merged.get('protocol_purpose', 'unknown')[:80]}", flush=True)
    print(f"    Entry points: {len(merged.get('entry_points', []))}", flush=True)
    print(f"    Business logic risks: {len(merged.get('business_logic_risks', []))}", flush=True)
    print(f"    Invariant hypotheses: {len(merged.get('invariant_hypotheses', []))}", flush=True)

    return merged


def _merge_arch_maps(maps):
    merged = {
        "protocol_purpose": "",
        "entry_points": [],
        "trust_boundaries": [],
        "value_flows": [],
        "business_logic_risks": [],
        "invariant_hypotheses": [],
    }
    for m in maps:
        if not isinstance(m, dict):
            continue
        pp = m.get("protocol_purpose", "")
        if len(pp) > len(merged["protocol_purpose"]):
            merged["protocol_purpose"] = pp
        for key in merged:
            if key == "protocol_purpose":
                continue
            if key in m:
                val = m[key]
                if isinstance(val, list) and isinstance(merged[key], list):
                    for item in val:
                        if isinstance(item, dict):
                            merged[key].append(item)
                        elif isinstance(item, str):
                            merged[key].append({"raw": item})
    return merged


# ══════════════════════════════════════════════════════════════════
# PHASE 2: Per-Entry-Point State-Machine Trace
# ══════════════════════════════════════════════════════════════════

PHASE2_SYSTEM = """You are a vulnerability researcher doing PROTOCOL STATE-MACHINE analysis.
You analyze ONE entry point at a time. Do NOT analyze entire files.

For the entry point given:
1. What is the INTENDED state transition? (state_before → action → state_after)
2. What invariants must hold during/after this transition?
3. What preconditions must be true for correct behavior?
4. What happens if preconditions are FALSE?
5. What happens if an attacker provides MALICIOUS inputs?

Think like a protocol designer, not a pattern matcher.

CONCRETE ATTACK FORMAT:
For each hypothesis, produce:
- title: specific, descriptive (NOT "Unknown vulnerability")
- invariant: "IF [precondition] THEN [invariant that should hold]"
- attack_sequence: step-by-step how an attacker exploits this
- state_before: normal state before attack
- state_after: compromised state after attack
- violated_property: which invariant is broken
- impact: concrete loss/damage
- severity: critical/high/medium/low

If you cannot construct a concrete attack, LOWER your confidence.
Bias toward reporting over silence — Phase 3 will verify.

Output ONLY valid JSON: list of FindingHypothesis objects."""


def phase2_per_entry_point_trace(source_dir, arch_map, static_results, project_name):
    """Phase 2: Trace EACH entry point independently. No file-level dedup."""
    print("  [Phase 2] Per-entry-point state-machine trace...", flush=True)

    entry_points = arch_map.get("entry_points", [])
    if not entry_points:
        # Fallback: use all files
        files = discover_files(source_dir)
        entry_points = [{"function": f.name, "file": str(f.relative_to(source_dir)),
                         "related_files": []} for f in files[:20]]

    print(f"    Tracing {len(entry_points)} entry points independently", flush=True)

    protocol_context = json.dumps({
        "protocol_purpose": arch_map.get("protocol_purpose", ""),
        "invariant_hypotheses": arch_map.get("invariant_hypotheses", [])[:10],
        "business_logic_risks": arch_map.get("business_logic_risks", [])[:10],
    }, indent=2)[:4000]

    all_findings: list[FindingHypothesis] = []

    for i, ep in enumerate(entry_points):
        if not isinstance(ep, dict):
            continue

        func_name = ep.get("function", ep.get("name", f"entry_{i}"))
        ep_file = ep.get("file", "")
        related = ep.get("related_files", [])

        print(f"    [{i+1}/{len(entry_points)}] {func_name} ({ep_file})", flush=True)

        # Gather code: entry point file + all related files
        code_parts = {}
        # Primary file
        if ep_file:
            full = source_dir / ep_file
            if full.exists():
                code_parts[ep_file] = read_file(full, 20000)

        # Related files (critical for cross-file bugs)
        for rf in related[:8]:
            if isinstance(rf, str) and rf not in code_parts:
                full = source_dir / rf
                if full.exists():
                    code_parts[rf] = read_file(full, 15000)

        if not code_parts:
            continue

        code_text = ""
        for fp, content in code_parts.items():
            code_text += f"\n--- {fp} ---\n{content[:8000]}\n"

        # Static findings for this entry point's files
        ep_findings = [sf for sf in static_results.get("findings", [])
                       if any(sf.get("file", "") in fp for fp in code_parts)]

        user_prompt = f"""PROTOCOL CONTEXT:
{protocol_context}

ENTRY POINT TO ANALYZE:
  Function: {func_name}
  File: {ep_file}
  Related files: {related}
  Lifecycle: {ep.get('lifecycle', 'unknown')}
  Invariants that must hold: {ep.get('invariants_that_must_hold', [])}

CODE:
{code_text}

Relevant static findings:
{json.dumps(ep_findings[:5], indent=2)}

TRACE THIS ENTRY POINT'S STATE MACHINE.
Find where the implementation violates its own protocol rules.
Produce concrete attack hypotheses."""

        response = call_llm([
            {"role": "system", "content": get_prompt("phase2", PHASE2_SYSTEM)},
            {"role": "user", "content": user_prompt}
        ], max_tokens=8192, temperature=0.1)

        candidates = parse_json_from_text(response)
        if isinstance(candidates, list):
            for c in candidates:
                if isinstance(c, dict):
                    fh = _dict_to_finding(c, ep_file, func_name, related)
                    all_findings.append(fh)
        elif isinstance(candidates, dict):
            for key in ["candidates", "findings", "vulnerabilities", "hypotheses"]:
                if key in candidates and isinstance(candidates[key], list):
                    for c in candidates[key]:
                        if isinstance(c, dict):
                            fh = _dict_to_finding(c, ep_file, func_name, related)
                            all_findings.append(fh)
                    break

        time.sleep(0.5)

    print(f"    Total hypotheses: {len(all_findings)}", flush=True)
    return all_findings


def _dict_to_finding(d: dict, ep_file: str, func_name: str, related: list) -> FindingHypothesis:
    """Convert raw LLM dict to typed FindingHypothesis."""
    title = d.get("title", "")
    if not title or title.lower() == "unknown vulnerability":
        title = f"Potential issue in {func_name}"

    return FindingHypothesis(
        id=_finding_id(title, ep_file, func_name),
        title=title,
        invariant=d.get("invariant", ""),
        entry_point=func_name,
        affected_function=d.get("affected_function", d.get("function", func_name)),
        file=d.get("file", ep_file),
        lines=d.get("lines", []),
        related_files=d.get("related_files", related),
        preconditions=d.get("preconditions", []),
        state_before=d.get("state_before", ""),
        action_sequence=d.get("action_sequence", d.get("attack_sequence", [])),
        state_after=d.get("state_after", ""),
        violated_property=d.get("violated_property", ""),
        impact=d.get("impact", d.get("description", "")),
        category=d.get("category", d.get("risk_type", "other")),
        severity=d.get("severity", "medium"),
        confidence=d.get("confidence", 0.5),
        evidence=d.get("evidence", []),
        trace_region=func_name,
    )


# ══════════════════════════════════════════════════════════════════
# PHASE 3: Strict Verification
# ══════════════════════════════════════════════════════════════════

PHASE3_SYSTEM = """You are verifying a candidate vulnerability. Be STRICT, not permissive.

VERIFICATION REQUIREMENTS — ALL must be met to confirm:
1. CONCRETE INVARIANT VIOLATION: What specific invariant is broken?
2. EXACT AFFECTED CODE: Which function/line has the bug?
3. REALISTIC PRECONDITIONS: Under what conditions is this exploitable?
4. COHERENT STATE TRANSITION: What is state_before → state_after?
5. CONCRETE IMPACT: What does the attacker gain?

If ANY of the above is missing or speculative, REJECT.
False negatives are acceptable. Speculative findings are NOT.

Severity guide:
- Critical: direct theft/loss, arbitrary code execution
- High: conditional loss, privilege escalation, permanent DoS
- Medium: griefing, edge-case loss
- Low: best practice violations

Output ONLY valid JSON:
{{
  "status": "confirmed" or "rejected",
  "severity": "critical/high/medium/low",
  "violated_invariant": "what invariant is broken",
  "concrete_impact": "what the attacker gains",
  "explanation": "why confirmed or rejected"
}}"""


def phase3_strict_verify(source_dir, findings: list[FindingHypothesis], arch_map):
    """Phase 3: Strict verification. Require concrete invariant violation."""
    print("  [Phase 3] Strict verification...", flush=True)

    verified = []
    for i, fh in enumerate(findings):
        print(f"    [{i+1}/{len(findings)}] {fh.title[:60]}", flush=True)

        # Gather code context
        context_files = {}
        if fh.file:
            full = source_dir / fh.file
            if full.exists():
                context_files[fh.file] = read_file(full, 20000)

        for rf in fh.related_files[:5]:
            if isinstance(rf, str) and rf not in context_files:
                full = source_dir / rf
                if full.exists():
                    context_files[rf] = read_file(full, 10000)

        code_text = ""
        for fp, content in context_files.items():
            code_text += f"\n--- {fp} ---\n{content[:8000]}\n"

        user_prompt = f"""CANDIDATE TO VERIFY:
{json.dumps(fh.to_dict(), indent=2)[:3000]}

FULL CODE CONTEXT:
{code_text}

VERIFY STRICTLY:
- Is there a concrete invariant violation?
- Is the affected code exact (not speculative)?
- Are the preconditions realistic?
- Is the state transition coherent?
- Is the impact concrete?

REJECT if any requirement is missing."""

        response = call_llm([
            {"role": "system", "content": get_prompt("phase3", PHASE3_SYSTEM)},
            {"role": "user", "content": user_prompt}
        ], max_tokens=4096, temperature=0.1)

        result = parse_json_from_text(response)
        if isinstance(result, dict):
            if result.get("status") == "confirmed":
                fh.status = "confirmed"
                fh.severity = result.get("severity", fh.severity)
                fh.verification_notes = result.get("explanation", "")
                fh.violated_property = result.get("violated_invariant", fh.violated_property)
                fh.impact = result.get("concrete_impact", fh.impact)
                verified.append(fh)
            else:
                fh.status = "rejected"
                fh.verification_notes = result.get("explanation", "")

        time.sleep(0.3)

    confirmed = [f for f in verified if f.status == "confirmed"]
    print(f"    Confirmed: {len(confirmed)}/{len(findings)}", flush=True)
    return confirmed


# ══════════════════════════════════════════════════════════════════
# PHASE 4: Cross-File Correlation + Typed Report
# ══════════════════════════════════════════════════════════════════

PHASE4_SYSTEM = """You are a security report assembler. Check if combining confirmed
findings creates additional exploit paths. Report only concrete combinations.

Output ONLY valid JSON: list of additional FindingHypothesis objects, or empty list."""


def phase4_correlate_and_report(confirmed: list[FindingHypothesis], arch_map, project_name):
    """Phase 4: Correlate findings, build typed report."""
    print("  [Phase 4] Cross-file correlation...", flush=True)

    # Check for combinations
    if len(confirmed) >= 2:
        findings_json = json.dumps([f.to_dict() for f in confirmed], indent=2)[:5000]
        user_prompt = f"""Confirmed findings:
{findings_json}

Protocol purpose: {arch_map.get('protocol_purpose', 'unknown')}

Do any two findings combine into a more severe exploit? Report only concrete combinations."""

        response = call_llm([
            {"role": "system", "content": get_prompt("phase4", PHASE4_SYSTEM)},
            {"role": "user", "content": user_prompt}
        ], max_tokens=2048, temperature=0.1)

        extra = parse_json_from_text(response)
        if isinstance(extra, list):
            for c in extra:
                if isinstance(c, dict):
                    fh = _dict_to_finding(c, "", "", [])
                    fh.status = "confirmed"
                    confirmed.append(fh)

    # Build submission-format report
    vulnerabilities = []
    for fh in confirmed:
        vuln = {
            "title": fh.title,
            "description": fh.impact or fh.invariant,
            "vulnerability_type": fh.category,
            "severity": fh.severity,
            "confidence": fh.confidence,
            "location": fh.file,
            "file": fh.file,
            "reported_by_model": MODEL,
        }
        vulnerabilities.append(vuln)

    report = {
        "project": project_name,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "files_analyzed": 0,
        "files_skipped": 0,
        "total_vulnerabilities": len(vulnerabilities),
        "vulnerabilities": vulnerabilities,
        "token_usage": {"total_input": 0, "total_output": 0},
    }

    print(f"    Final report: {len(vulnerabilities)} vulnerabilities", flush=True)
    return report


# ══════════════════════════════════════════════════════════════════
# MAIN PIPELINE
# ══════════════════════════════════════════════════════════════════

def run_pipeline(source_dir, project_name, log_dir=None):
    start_time = time.monotonic()

    if log_dir:
        log_dir.mkdir(parents=True, exist_ok=True)

    languages = detect_languages(source_dir)
    static_results = phase0_static_analysis(source_dir, languages)
    if log_dir:
        (log_dir / "phase0_static.json").write_text(json.dumps(static_results, indent=2))

    arch_map = phase1_protocol_understanding(source_dir, project_name, static_results)
    if log_dir:
        (log_dir / "phase1_arch.json").write_text(json.dumps(arch_map, indent=2))

    findings = phase2_per_entry_point_trace(source_dir, arch_map, static_results, project_name)
    if log_dir:
        (log_dir / "phase2_findings.json").write_text(
            json.dumps([f.to_dict() for f in findings], indent=2))

    confirmed = phase3_strict_verify(source_dir, findings, arch_map)
    if log_dir:
        (log_dir / "phase3_verified.json").write_text(
            json.dumps([f.to_dict() for f in confirmed], indent=2))

    report = phase4_correlate_and_report(confirmed, arch_map, project_name)

    report["files_analyzed"] = len(discover_files(source_dir))
    duration = time.monotonic() - start_time
    report["duration_seconds"] = round(duration, 1)

    if log_dir:
        (log_dir / "final_report.json").write_text(json.dumps(report, indent=2))

    output_file = source_dir / "agent_report.json"
    with open(output_file, 'w') as f:
        json.dump(report, f, indent=2)

    print(f"\n  Pipeline v3 complete: {report['total_vulnerabilities']} vulnerabilities in {duration:.0f}s", flush=True)
    return report


def agent_main(project_dir="/app/project_code", inference_api=None):
    source_dir = Path(project_dir)
    project_name = source_dir.name
    if not source_dir.exists():
        print(f"Error: {project_dir} not found")
        sys.exit(1)
    log_dir = LOG_DIR / project_name / time.strftime("%Y%m%d-%H%M%S")
    report = run_pipeline(source_dir, project_name, log_dir)
    return report


if __name__ == "__main__":
    project_dir = sys.argv[1] if len(sys.argv) > 1 else "/app/project_code"
    agent_main(project_dir)
