"""BitSec Pipeline Agent v1 — Multi-phase vulnerability detection.

Phases:
  0: Static analysis (Slither/Semgrep, no LLM)
  1: Architecture Map (LLM, whole-repo comprehension)
  2: Targeted Trace (LLM, per entry point, reasoning)
  3: Deep-Dive Verification (LLM, per candidate, full context)
  4: Cross-File Correlation & Report Assembly
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import requests

# ── Config ────────────────────────────────────────────────────────

PROXY = "http://localhost:8087"
API_KEY = "sk-A5QHR5MRtUNec7BWqiRsZ0GAYck0CRT2Movsk7Q6U3UwcV77Y6G3TMXOhhyKh855"
MODEL = "mimo-v2.5"
REASONING_MODEL = "mimo-v2.5"  # Use same model, but with more tokens

EXCLUDE_DIRS = {"testing", "mocks", "examples", "interfaces", "script", "broadcast", "libraries", "node_modules", "lib"}
CONTRACT_PATTERNS = ['**/*.sol', '**/*.vy', '**/*.cairo', '**/*.rs', '**/*.move']

LOG_DIR = Path("/root/bitt/data/pipeline-logs")


# ── LLM Call ──────────────────────────────────────────────────────

def call_llm(messages, max_tokens=8192, temperature=0.1, model=None):
    """Call LLM through proxy."""
    model = model or MODEL
    for attempt in range(3):
        try:
            resp = requests.post(f"{PROXY}/inference", headers={
                "x-inference-api-key": API_KEY,
                "x-agent-id": "pipeline-v1",
                "x-job-run-id": f"pipe-{int(time.time())}-{attempt}",
                "x-request-phase": "execution"
            }, json={
                "model": model,
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


def parse_json_from_text(text):
    """Extract JSON from LLM text response."""
    # Try array first
    match = re.search(r'\[[\s\S]*\]', text)
    if match:
        try:
            return json.loads(match.group())
        except:
            pass
    # Try object
    match = re.search(r'\{[\s\S]*\}', text)
    if match:
        try:
            return json.loads(match.group())
        except:
            pass
    return None


# ── File Discovery ────────────────────────────────────────────────

def discover_files(source_dir):
    """Discover all relevant source files."""
    files = []
    for p in CONTRACT_PATTERNS:
        files.extend(source_dir.glob(p))
    return [
        f for f in files
        if f.is_file()
        and "test" not in f.name.lower()
        and not any(part.lower() in EXCLUDE_DIRS for part in f.parts)
    ]


def read_file(path, max_chars=50000):
    """Read file with generous limit."""
    try:
        return path.read_text(encoding="utf-8")[:max_chars]
    except:
        return ""


def detect_languages(source_dir):
    """Detect project languages from file extensions."""
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
# PHASE 0: Static Analysis (No LLM)
# ══════════════════════════════════════════════════════════════════

def phase0_static_analysis(source_dir, languages):
    """Run static analysis tools. No LLM involved."""
    print("  [Phase 0] Static analysis...", flush=True)
    findings = []

    if 'solidity' in languages:
        # Try Slither
        try:
            result = subprocess.run(
                ['slither', '.', '--json', '/tmp/slither_out.json', '--quiet'],
                cwd=str(source_dir),
                capture_output=True, text=True, timeout=120
            )
            if Path('/tmp/slither_out.json').exists():
                slither_data = json.load(open('/tmp/slither_out.json'))
                for det in slither_data.get('results', {}).get('detectors', []):
                    findings.append({
                        "tool": "slither",
                        "detector": det.get('check', 'unknown'),
                        "file": det.get('elements', [{}])[0].get('source_mapping', {}).get('filename_relative', 'unknown') if det.get('elements') else 'unknown',
                        "lines": [det.get('elements', [{}])[0].get('source_mapping', {}).get('start', 0)] if det.get('elements') else [],
                        "raw_message": det.get('description', ''),
                        "confidence": "medium"
                    })
                print(f"    Slither: {len(findings)} findings", flush=True)
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            print(f"    Slither: skipped ({type(e).__name__})", flush=True)

        # Try Semgrep on Solidity
        try:
            result = subprocess.run(
                ['semgrep', '--config=p/security-audit', '--json', '--quiet', '.'],
                cwd=str(source_dir),
                capture_output=True, text=True, timeout=120
            )
            if result.stdout:
                semgrep_data = json.loads(result.stdout)
                for r in semgrep_data.get('results', []):
                    findings.append({
                        "tool": "semgrep",
                        "detector": r.get('check_id', 'unknown'),
                        "file": r.get('path', 'unknown'),
                        "lines": [r.get('start', {}).get('line', 0)],
                        "raw_message": r.get('extra', {}).get('message', ''),
                        "confidence": "medium"
                    })
                print(f"    Semgrep: {len(semgrep_data.get('results', []))} findings", flush=True)
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            print(f"    Semgrep: skipped ({type(e).__name__})", flush=True)

    # Also do simple regex-based analysis
    regex_findings = phase0_regex_analysis(source_dir)
    findings.extend(regex_findings)
    print(f"    Regex: {len(regex_findings)} patterns detected", flush=True)

    print(f"    Total Phase 0: {len(findings)} findings", flush=True)
    return {"findings": findings}


def phase0_regex_analysis(source_dir):
    """Simple regex-based pattern detection."""
    findings = []
    files = discover_files(source_dir)

    for f in files:
        content = read_file(f, 30000)
        rel = str(f.relative_to(source_dir))

        # Unchecked return values
        for m in re.finditer(r'(?:call|send|transfer)\s*\(', content):
            line = content[:m.start()].count('\n') + 1
            findings.append({
                "tool": "regex",
                "detector": "unchecked_external_call",
                "file": rel,
                "lines": [line],
                "raw_message": f"External call at line {line} — check return value",
                "confidence": "low"
            })

        # Reentrancy pattern: state change after external call
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if re.search(r'\.\s*(?:call|send|transfer)\s*\(', line):
                # Check if there's a state change after this
                for j in range(i+1, min(i+10, len(lines))):
                    if '=' in lines[j] and not lines[j].strip().startswith('//'):
                        findings.append({
                            "tool": "regex",
                            "detector": "potential_reentrancy",
                            "file": rel,
                            "lines": [i+1, j+1],
                            "raw_message": f"State change at line {j+1} after external call at line {i+1}",
                            "confidence": "low"
                        })
                        break

    return findings


# ══════════════════════════════════════════════════════════════════
# PHASE 1: Architecture Map
# ══════════════════════════════════════════════════════════════════

PHASE1_SYSTEM = """You are a code architecture mapper for a security audit pipeline. You do not
find vulnerabilities in this phase — you build a map that later phases will
use to focus their analysis. Being wrong here means later phases waste budget
looking in the wrong place, so be thorough rather than fast.

For the codebase provided, produce a structured JSON map with:

1. entry_points: every function reachable by an external actor. For each:
   file, function name, line, what untrusted input flows in, permission level.

2. trust_boundaries: every place value/authority crosses trust levels —
   external calls, cross-contract calls, privilege checks, admin branches.
   For each: file, line, what's crossing, what should be validated.

3. value_flows: trace where value (tokens, balances, permissions, ownership)
   is created, moved, destroyed. Note order of operations.

4. call_graph_summary: for each entry point, chain of internal calls 2+ levels deep.
   Flag recursive or circular paths.

5. static_findings_context: map each static finding onto the above —
   which entry point can reach it, is it likely real or false positive.

Output ONLY valid JSON. No prose."""

def phase1_architecture_map(source_dir, project_name, static_results):
    """Phase 1: Build architecture map from full repo."""
    print("  [Phase 1] Architecture map...", flush=True)

    files = discover_files(source_dir)

    # Read all files (no truncation)
    file_contents = {}
    for f in files:
        rel = str(f.relative_to(source_dir))
        content = read_file(f, 50000)
        if content:
            file_contents[rel] = content

    # Build file tree
    file_tree = "\n".join(sorted(file_contents.keys()))

    # Batch file contents (max ~30000 chars per batch to stay in context)
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

    # Run Phase 1 on each batch, merge results
    all_arch_maps = []
    for i, batch in enumerate(batches):
        print(f"    Batch {i+1}/{len(batches)} ({len(batch)} chars)", flush=True)

        user_prompt = f"""Repository: {project_name}
Language(s): {', '.join(detect_languages(source_dir))}
Files ({len(files)} total, full contents below):

{batch}

Static analysis findings so far:
{json.dumps(static_results['findings'][:50], indent=2)}

Produce the architecture map JSON now."""

        response = call_llm([
            {"role": "system", "content": PHASE1_SYSTEM},
            {"role": "user", "content": user_prompt}
        ], max_tokens=8192, temperature=0.1)

        arch_map = parse_json_from_text(response)
        if arch_map:
            all_arch_maps.append(arch_map)

    # Merge architecture maps
    merged = merge_arch_maps(all_arch_maps)
    print(f"    Entry points: {len(merged.get('entry_points', []))}", flush=True)
    print(f"    Trust boundaries: {len(merged.get('trust_boundaries', []))}", flush=True)
    print(f"    Value flows: {len(merged.get('value_flows', []))}", flush=True)

    return merged


def merge_arch_maps(maps):
    """Merge multiple architecture maps into one."""
    if not maps:
        return {"entry_points": [], "trust_boundaries": [], "value_flows": [], "call_graph_summary": {}, "static_findings_context": []}

    merged = {
        "entry_points": [],
        "trust_boundaries": [],
        "value_flows": [],
        "call_graph_summary": {},
        "static_findings_context": []
    }

    for m in maps:
        if isinstance(m, dict):
            for key in merged:
                if key in m:
                    val = m[key]
                    if isinstance(val, list) and isinstance(merged[key], list):
                        for item in val:
                            if isinstance(item, dict):
                                merged[key].append(item)
                            elif isinstance(item, str):
                                merged[key].append({"raw": item})
                    elif isinstance(val, dict) and isinstance(merged[key], dict):
                        merged[key].update(val)
                    elif isinstance(val, str) and isinstance(merged[key], list):
                        merged[key].append({"raw": val})

    return merged


# ══════════════════════════════════════════════════════════════════
# PHASE 2: Targeted Trace
# ══════════════════════════════════════════════════════════════════

PHASE2_SYSTEM = """You are a vulnerability researcher doing targeted analysis on ONE region of
a codebase at a time. You have already been given the architecture context —
do not re-derive it, use it.

Your job: for the specific entry point / trust boundary given, trace what an
adversarial caller can do, step by step, and identify every point where:

- A check is missing, wrong, or bypassable
- State changes happen in the wrong order relative to external calls
- An invariant can be broken
- Arithmetic can overflow/underflow/truncate/round exploitably
- Business logic assumptions don't match what the code enforces

For each hypothesis, write out the actual attack sequence as concrete steps.
If you cannot construct a concrete sequence, lower your confidence.

Bias toward reporting a candidate over staying silent. Phase 3 will verify.

Output ONLY valid JSON: a list of candidates with file, lines, category,
attack_sequence, confidence, and reasoning."""


def phase2_targeted_trace(source_dir, arch_map, static_results, project_name):
    """Phase 2: Trace each entry point / trust boundary."""
    print("  [Phase 2] Targeted trace...", flush=True)

    regions = []
    # Add entry points as regions
    for ep in arch_map.get("entry_points", []):
        if isinstance(ep, dict):
            regions.append(ep)
    # Add trust boundaries as regions
    for tb in arch_map.get("trust_boundaries", []):
        if isinstance(tb, dict):
            regions.append(tb)

    # If no regions from arch map, use files as regions
    if not regions:
        files = discover_files(source_dir)
        for f in files[:20]:
            regions.append({
                "area": f.name,
                "file": str(f.relative_to(source_dir)),
                "risk_type": "general"
            })

    # Prioritize implementation files over interfaces
    def region_priority(r):
        file_path = r.get("file", r.get("relevant_files", [""])[0] if r.get("relevant_files") else "")
        if "interface" in file_path.lower() or file_path.startswith("I"):
            return 2  # Interfaces last
        if ".sol" in file_path or ".vy" in file_path or ".cairo" in file_path:
            return 0  # Implementation first
        return 1

    regions.sort(key=region_priority)

    # Deduplicate by file path
    seen_files = set()
    deduped = []
    for r in regions:
        f = r.get("file", "")
        if f and f not in seen_files:
            seen_files.add(f)
            deduped.append(r)
    regions = deduped

    print(f"    Analyzing {len(regions)} regions", flush=True)

    all_candidates = []
    for i, region in enumerate(regions[:15]):  # Cap at 15 regions
        region_name = region.get("area", region.get("function", region.get("file", f"region_{i}")))
        print(f"    [{i+1}/{min(len(regions),15)}] {region_name}", flush=True)

        # Gather region files
        region_files = {}
        relevant_files = region.get("relevant_files", [])
        if not relevant_files and "file" in region:
            relevant_files = [region["file"]]

        for f_path in relevant_files[:5]:
            full_path = source_dir / f_path
            if full_path.exists():
                region_files[f_path] = read_file(full_path, 30000)

        if not region_files:
            continue

        # Build context
        files_text = ""
        for fp, content in region_files.items():
            files_text += f"\n--- {fp} ---\n{content[:8000]}\n"

        # Filter static findings for this region
        region_findings = []
        for sf in static_results.get("findings", []):
            if any(sf.get("file", "") in fp for fp in region_files):
                region_findings.append(sf)

        user_prompt = f"""Architecture map (context already established):
{json.dumps(arch_map, indent=2)[:3000]}

Region under analysis: {region_name}
Full file contents for this region:
{files_text}

Relevant static findings:
{json.dumps(region_findings[:10], indent=2)}

Trace this region now."""

        response = call_llm([
            {"role": "system", "content": PHASE2_SYSTEM},
            {"role": "user", "content": user_prompt}
        ], max_tokens=8192, temperature=0.1)

        candidates = parse_json_from_text(response)
        if isinstance(candidates, list):
            for c in candidates:
                if isinstance(c, dict):
                    c["trace_region"] = region_name
                    all_candidates.append(c)
        elif isinstance(candidates, dict):
            # Try various keys
            for key in ["candidates", "findings", "vulnerabilities", "hypotheses"]:
                if key in candidates and isinstance(candidates[key], list):
                    for c in candidates[key]:
                        if isinstance(c, dict):
                            c["trace_region"] = region_name
                            all_candidates.append(c)
                    break
            else:
                # If no list found, treat the dict itself as a single candidate
                candidates["trace_region"] = region_name
                all_candidates.append(candidates)

        time.sleep(0.5)

    print(f"    Total candidates: {len(all_candidates)}", flush=True)
    return all_candidates


# ══════════════════════════════════════════════════════════════════
# PHASE 3: Deep-Dive Verification
# ══════════════════════════════════════════════════════════════════

PHASE3_SYSTEM = """You are verifying a single candidate vulnerability. Be fair, not overly skeptical.

Your job:
1. Read the candidate and the full code context.
2. Determine if the vulnerability is PLAUSIBLE — could it theoretically be exploited?
3. If yes, CONFIRM it. Assign severity based on potential impact.
4. If no, REJECT with the specific guard/check that prevents it.

IMPORTANT RULES:
- You are NOT writing a court brief. You do NOT need a complete exploit PoC to confirm.
- A vulnerability is CONFIRMED if: the code has the pattern described, no obvious guard prevents it, and exploitation is theoretically possible.
- Do NOT reject findings just because they seem "unlikely in practice" — if the code lacks the check, confirm it.
- When uncertain between confirm/reject, lean toward CONFIRM. Phase 3 should have high recall, not high precision. False positives are cheap; false negatives are fatal.
- Match severity to the concrete impact described. If unsure, default to the LOWER severity (don't inflate).

Severity guide:
- Critical: direct theft/loss, arbitrary code execution
- High: conditional loss, privilege escalation, permanent DoS
- Medium: griefing, edge-case loss, informational with security implications
- Low: best practice violations, gas optimization, minor issues

Output ONLY valid JSON: status (confirmed/rejected), severity (if confirmed),
exploit_description (how it could be exploited, or why it can't), file, lines."""


def phase3_verify_candidates(source_dir, candidates, arch_map):
    """Phase 3: Verify each candidate with full context."""
    print("  [Phase 3] Verifying candidates...", flush=True)

    verified = []
    for i, candidate in enumerate(candidates[:20]):  # Cap at 20
        title = candidate.get("title", candidate.get("area", f"candidate_{i}"))
        print(f"    [{i+1}/{min(len(candidates),20)}] {title}", flush=True)

        # Gather full context: candidate file + callers/callees
        candidate_file = candidate.get("file", "")
        context_files = {}

        if candidate_file:
            full_path = source_dir / candidate_file
            if full_path.exists():
                context_files[candidate_file] = read_file(full_path, 30000)

        # Add callers/callees from arch map
        for ep in arch_map.get("entry_points", []):
            if isinstance(ep, dict):
                for f in ep.get("relevant_files", []):
                    if f not in context_files:
                        full_path = source_dir / f
                        if full_path.exists():
                            context_files[f] = read_file(full_path, 15000)

        # Build context
        files_text = ""
        for fp, content in context_files.items():
            files_text += f"\n--- {fp} ---\n{content[:10000]}\n"

        user_prompt = f"""Candidate to verify:
{json.dumps(candidate, indent=2)[:2000]}

Full contents of relevant files:
{files_text}

Verify this candidate now."""

        response = call_llm([
            {"role": "system", "content": PHASE3_SYSTEM},
            {"role": "user", "content": user_prompt}
        ], max_tokens=4096, temperature=0.1)

        result = parse_json_from_text(response)
        if isinstance(result, dict):
            result["candidate_original"] = candidate
            verified.append(result)

        time.sleep(0.3)

    confirmed = [v for v in verified if v.get("status") == "confirmed"]
    print(f"    Confirmed: {len(confirmed)}/{len(verified)}", flush=True)
    return confirmed


# ══════════════════════════════════════════════════════════════════
# PHASE 4: Cross-File Correlation & Report
# ══════════════════════════════════════════════════════════════════

PHASE4_SYSTEM = """You are a security report assembler. Check if combining confirmed
findings creates additional exploit paths. Report only concrete combinations.

Output ONLY valid JSON: list of additional findings, or empty list."""


def phase4_correlate_and_report(confirmed, arch_map, project_name):
    """Phase 4: Correlate findings, build final report."""
    print("  [Phase 4] Cross-file correlation...", flush=True)

    # Check for combinations
    if len(confirmed) >= 2:
        user_prompt = f"""Confirmed findings so far:
{json.dumps(confirmed, indent=2)[:5000]}

Value flow map:
{json.dumps(arch_map.get('value_flows', []), indent=2)[:3000]}

Do any two findings combine into a more severe exploit? Report only concrete combinations."""

        response = call_llm([
            {"role": "system", "content": PHASE4_SYSTEM},
            {"role": "user", "content": user_prompt}
        ], max_tokens=2048, temperature=0.1)

        extra = parse_json_from_text(response)
        if isinstance(extra, list):
            confirmed.extend(extra)

    # Build submission-format report
    vulnerabilities = []
    for v in confirmed:
        if not isinstance(v, dict):
            continue
        vuln = {
            "title": v.get("title", v.get("area", "Unknown vulnerability")),
            "description": v.get("exploit_scenario", v.get("description", v.get("reasoning", ""))),
            "vulnerability_type": v.get("category", v.get("risk_type", "other")),
            "severity": v.get("severity", "medium"),
            "confidence": v.get("confidence", 0.7),
            "location": v.get("location", v.get("file", "")),
            "file": v.get("file", ""),
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
    """Run the full 5-phase pipeline."""
    start_time = time.monotonic()

    # Setup logging
    if log_dir:
        log_dir.mkdir(parents=True, exist_ok=True)

    # Phase 0
    languages = detect_languages(source_dir)
    static_results = phase0_static_analysis(source_dir, languages)
    if log_dir:
        (log_dir / "phase0_static.json").write_text(json.dumps(static_results, indent=2))

    # Phase 1
    arch_map = phase1_architecture_map(source_dir, project_name, static_results)
    if log_dir:
        (log_dir / "phase1_arch.json").write_text(json.dumps(arch_map, indent=2))

    # Phase 2
    candidates = phase2_targeted_trace(source_dir, arch_map, static_results, project_name)
    if log_dir:
        (log_dir / "phase2_candidates.json").write_text(json.dumps(candidates, indent=2))

    # Phase 3
    confirmed = phase3_verify_candidates(source_dir, candidates, arch_map)
    if log_dir:
        (log_dir / "phase3_verified.json").write_text(json.dumps(confirmed, indent=2))

    # Phase 4
    report = phase4_correlate_and_report(confirmed, arch_map, project_name)

    # Add file count
    report["files_analyzed"] = len(discover_files(source_dir))

    duration = time.monotonic() - start_time
    report["duration_seconds"] = round(duration, 1)

    if log_dir:
        (log_dir / "final_report.json").write_text(json.dumps(report, indent=2))

    # Save report to project directory
    output_file = source_dir / "agent_report.json"
    with open(output_file, 'w') as f:
        json.dump(report, f, indent=2)

    print(f"\n  Pipeline complete: {report['total_vulnerabilities']} vulnerabilities in {duration:.0f}s", flush=True)
    return report


def agent_main(project_dir="/app/project_code", inference_api=None):
    """Entry point — matches official BitSec format."""
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
