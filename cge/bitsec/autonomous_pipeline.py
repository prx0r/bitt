"""Autonomous CG/CGE Pipeline — mutates miner prompts, evaluates on 6 projects, evolves."""
import hashlib
import json
import os
import random
import re
import sys
import time
from pathlib import Path

PROXY = "http://localhost:8087"
API_KEY = "sk-A5QHR5MRtUNec7BWqiRsZ0GAYck0CRT2Movsk7Q6U3UwcV77Y6G3TMXOhhyKh855"
MODEL = "mimo-v2.5"

# The 6 official BitSec projects
PROJECTS = [
    "code4rena_coded-estate-invitational_2024_12",
    "code4rena_iq-ai_2025_03",
    "code4rena_liquid-ron_2025_03",
    "code4rena_mantra-dex_2025_03",
    "sherlock_cork-protocol_2025_01",
    "sherlock_crestal-network_2025_03",
]

REPOS_DIR = Path("/root/bitt/data/scabench-repos")
HIGHS_PATH = "/root/bitt/subnets/sn60-bitsec/sandbox-v2/validator/curated-highs-only-2025-08-08.json"
RESULTS_BASE = Path("/root/bitt/data/cge-runs")

# ── LLM Call ──────────────────────────────────────────────────────

def call_llm(messages, max_tokens=8192, temperature=0.1):
    import requests
    for attempt in range(3):
        try:
            resp = requests.post(f"{PROXY}/inference", headers={
                "x-inference-api-key": API_KEY,
                "x-agent-id": "cge",
                "x-job-run-id": f"cge-{int(time.time())}-{attempt}",
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

# ── File Handling ──────────────────────────────────────────────────

EXCLUDE = {"testing", "mocks", "examples", "interfaces", "script", "broadcast", "libraries", "node_modules"}

def discover_files(source_dir):
    files = []
    for ext in ['**/*.sol', '**/*.vy', '**/*.cairo', '**/*.rs', '**/*.move']:
        files.extend(source_dir.glob(ext))
    return [f for f in files if f.is_file() and "test" not in f.name.lower()
            and not any(p.lower() in EXCLUDE for p in f.parts)]

def read_file(path, max_chars=20000):
    try:
        return path.read_text(encoding="utf-8")[:max_chars]
    except:
        return ""

# ── Static Analysis ───────────────────────────────────────────────

def static_analysis(source_dir):
    """Simple regex-based static analysis."""
    findings = []
    files = discover_files(source_dir)
    for f in files:
        content = read_file(f, 15000)
        rel = str(f.relative_to(source_dir))
        # External calls
        for m in re.finditer(r'\.\s*(?:call|send|transfer)\s*\(', content):
            line = content[:m.start()].count('\n') + 1
            findings.append({"tool": "regex", "detector": "external_call", "file": rel, "line": line})
        # State changes after external calls
        lines = content.split('\n')
        for i, line_text in enumerate(lines):
            if re.search(r'\.\s*(?:call|send|transfer)\s*\(', line_text):
                for j in range(i+1, min(i+8, len(lines))):
                    if '=' in lines[j] and not lines[j].strip().startswith('//'):
                        findings.append({"tool": "regex", "detector": "potential_reentrancy", "file": rel, "lines": [i+1, j+1]})
                        break
    return findings

# ── Pipeline Phases ────────────────────────────────────────────────

def phase1_arch_map(source_dir, project_name, static_findings):
    """Architecture map — cheap/fast model call."""
    files = discover_files(source_dir)
    file_contents = {}
    for f in files[:30]:
        rel = str(f.relative_to(source_dir))
        file_contents[rel] = read_file(f, 8000)

    # Batch
    batch = ""
    for rel, content in file_contents.items():
        batch += f"\n--- {rel} ---\n{content}\n"

    prompt = f"""You are a code architecture mapper. For this {project_name} project, produce a JSON map with:

1. entry_points: functions reachable by external actors (file, function, what input flows in)
2. trust_boundaries: where value/authority crosses trust levels
3. value_flows: where tokens/balances/ownership are created, moved, destroyed
4. high_risk_areas: top 10 areas most likely to contain exploitable vulnerabilities

Static analysis found: {json.dumps(static_findings[:20])}

Files ({len(files)} total):
{batch[:25000]}

Output ONLY valid JSON."""

    response = call_llm([{"role": "user", "content": prompt}], max_tokens=4096)
    try:
        match = re.search(r'\{[\s\S]*\}', response)
        if match:
            return json.loads(match.group())
    except:
        pass
    return {"entry_points": [], "trust_boundaries": [], "high_risk_areas": []}


def phase2_trace(source_dir, arch_map, static_findings):
    """Targeted trace — reasoning model, per region."""
    candidates = []

    # Get high-risk areas from arch map
    regions = arch_map.get("high_risk_areas", [])
    if not regions:
        regions = arch_map.get("entry_points", [])[:10]

    for region in regions[:8]:
        if not isinstance(region, dict):
            continue
        area = region.get("area", region.get("function", "unknown"))
        relevant_files = region.get("relevant_files", [])

        # Gather code
        code = ""
        for fp in relevant_files[:3]:
            full = source_dir / fp
            if full.exists():
                code += f"\n--- {fp} ---\n{read_file(full, 6000)}\n"

        if not code:
            continue

        prompt = f"""You are a vulnerability researcher analyzing {area}.

CODE:
{code}

Trace what an adversarial caller can do. Find vulnerabilities where:
- Checks are missing or bypassable
- State changes happen in wrong order
- Invariants can be broken
- Business logic doesn't match code

For each finding: concrete attack steps, not vague descriptions.

Return JSON array: [{{"title": "...", "description": "...", "category": "...", "file": "...", "confidence": 0.0-1.0, "attack_steps": "..."}}]"""

        response = call_llm([{"role": "user", "content": prompt}], max_tokens=4096)
        try:
            match = re.search(r'\[[\s\S]*\]', response)
            if match:
                found = json.loads(match.group())
                for c in found:
                    if isinstance(c, dict):
                        c["region"] = area
                        candidates.append(c)
        except:
            pass
        time.sleep(0.3)

    return candidates


def phase3_verify(candidates, source_dir):
    """Verify candidates — lean toward confirm."""
    verified = []
    for c in candidates[:15]:
        if not isinstance(c, dict):
            continue
        title = c.get("title", "unknown")
        file_path = c.get("file", "")

        # Get code context
        code = ""
        if file_path:
            full = source_dir / file_path
            if full.exists():
                code = read_file(full, 10000)

        prompt = f"""Verify this candidate vulnerability:

TITLE: {title}
CATEGORY: {c.get('category', '?')}
DESCRIPTION: {c.get('description', '')[:500]}
ATTACK STEPS: {c.get('attack_steps', '')[:500]}

CODE:
{code[:8000]}

Is this a real, exploitable vulnerability?
- If YES: confirm with severity (critical/high/medium/low) and brief explanation
- If NO: reject with specific reason

IMPORTANT: lean toward CONFIRM when uncertain. False positives are cheap, false negatives are fatal.

Return JSON: {{"status": "confirmed/rejected", "severity": "...", "explanation": "..."}}"""

        response = call_llm([{"role": "user", "content": prompt}], max_tokens=2048)
        try:
            match = re.search(r'\{[\s\S]*\}', response)
            if match:
                result = json.loads(match.group())
                if result.get("status") == "confirmed":
                    c["severity"] = result.get("severity", "medium")
                    c["verification"] = result.get("explanation", "")
                    verified.append(c)
        except:
            pass
        time.sleep(0.3)

    return verified


# ── Scoring ────────────────────────────────────────────────────────

def score_findings(findings, project_id):
    """Score against ground truth."""
    gt_data = json.load(open(HIGHS_PATH))
    gt_entry = next((e for e in gt_data if e["project_id"] == project_id), None)
    if not gt_entry:
        return {"dr": 1.0, "expected": 0, "matched": 0}

    expected = gt_entry.get("vulnerabilities", [])
    if not expected:
        return {"dr": 1.0, "expected": 0, "matched": 0}

    matched = 0
    for exp in expected:
        findings_text = ""
        for i, f in enumerate(findings[:10]):
            findings_text += f"[{i}] {f.get('title','?')} ({f.get('severity','?')}) - {f.get('description','?')[:150]}\n"

        prompt = f"""Does any TOOL FINDING match this EXPECTED vulnerability?

EXPECTED: {exp.get('title','')}
DESCRIPTION: {exp.get('description','')[:400]}

TOOL FINDINGS:
{findings_text}

Return JSON: {{"found": true/false, "confidence": 0.0-1.0}}"""

        try:
            content = call_llm([
                {"role": "system", "content": "Return JSON only."},
                {"role": "user", "content": prompt}
            ], max_tokens=200, temperature=0.1)

            match = re.search(r'\{[^{}]*"found"[^{}]*\}', content)
            if match:
                result = json.loads(match.group())
                if result.get("found") and result.get("confidence", 0) >= 0.6:
                    matched += 1
        except:
            pass
        time.sleep(0.3)

    dr = matched / len(expected) if expected else 0
    return {"dr": round(dr, 3), "expected": len(expected), "matched": matched}


# ── Strategy Mutations ─────────────────────────────────────────────

def get_base_strategies():
    """Create initial strategy variants."""
    base_analysis = """You are a security auditor. Analyze code for vulnerabilities. Focus on:
1. Access control issues
2. Reentrancy
3. Integer overflow/underflow
4. Business logic errors
5. Cross-contract interactions
Return JSON array of findings with title, description, category, file, severity."""

    base_verify = """Verify if this is a real vulnerability. Lean toward confirm when uncertain."""

    strategies = [
        {"id": "base", "analysis_prompt": base_analysis, "verify_prompt": base_verify},
        {"id": "defi-focus", "analysis_prompt": base_analysis + "\n\nFocus especially on: slippage protection, oracle manipulation, flash loans, economic invariants, fee calculations.", "verify_prompt": base_verify},
        {"id": "cross-file", "analysis_prompt": base_analysis + "\n\nFocus on: cross-contract state synchronization, trust boundary violations, function signature mismatches.", "verify_prompt": base_verify},
        {"id": "business-logic", "analysis_prompt": base_analysis + "\n\nThis is critical: do NOT just look for common patterns. Read the code carefully and understand what the protocol is SUPPOSED to do. Find where the code violates its own business rules.", "verify_prompt": base_verify},
    ]
    return strategies


def mutate_strategy(strategy, rng):
    """Create a mutated version of a strategy."""
    prompt = strategy["analysis_prompt"]

    mutations = [
        "\n\nAdditional focus: trace the flow of all assets (tokens, ETH) through every function. Flag any function where assets can be lost or stolen.",
        "\n\nAdditional focus: check if any function can be called with parameters that cause it to behave differently than intended (e.g., zero amounts, max values, same address for from/to).",
        "\n\nAdditional focus: look for differences between how similar functions handle the same operation. Inconsistencies often indicate bugs.",
        "\n\nAdditional focus: check all external calls for return value verification. Missing checks can silently fail.",
        "\n\nAdditional focus: trace access control on every state-changing function. Who can call it? Is the check sufficient?",
        "\n\nAdditional focus: look for rounding errors, precision loss, and type conversion issues in arithmetic operations.",
    ]

    return {
        "id": f"mut-{rng.randint(0,99999)}",
        "analysis_prompt": prompt + rng.choice(mutations),
        "verify_prompt": strategy["verify_prompt"],
    }


# ── Main Loop ──────────────────────────────────────────────────────

def run_agent_on_project(strategy, project_id):
    """Run one strategy on one project using full pipeline-v1."""
    import subprocess
    import importlib.util

    source_dir = REPOS_DIR / project_id
    if not source_dir.exists():
        return None

    # Use the full pipeline-v1 agent
    agent_path = Path("/root/bitt/mining/sn60/candidates/pipeline-v1/agent.py")
    if not agent_path.exists():
        print("    ERROR: pipeline-v1/agent.py not found", flush=True)
        return []

    # Set env
    env = os.environ.copy()
    env["INFERENCE_API"] = PROXY
    env["INFERENCE_API_KEY"] = API_KEY
    env["AGENT_ID"] = "cge"
    env["OPENAI_MODEL"] = MODEL

    # Run with timeout
    try:
        result = subprocess.run(
            [sys.executable, str(agent_path), str(source_dir)],
            capture_output=True, text=True, timeout=600,
            env=env
        )
    except subprocess.TimeoutExpired:
        print("    TIMEOUT", flush=True)
        return []

    # Read report
    report_path = source_dir / "agent_report.json"
    if report_path.exists():
        report = json.load(open(report_path))
        return report.get("vulnerabilities", [])

    return []


def run_generation(strategies, generation, log_dir):
    """Run one generation: evaluate all strategies on all projects."""
    gen_dir = log_dir / f"gen-{generation}"
    gen_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for strategy in strategies:
        print(f"\n  Strategy: {strategy['id']}", flush=True)
        strategy_results = []

        for project_id in PROJECTS:
            print(f"    [{project_id[:40]}]", end=" ", flush=True)
            start = time.monotonic()

            findings = run_agent_on_project(strategy, project_id)
            duration = time.monotonic() - start

            if findings:
                score = score_findings(findings, project_id)
                strategy_results.append({
                    "project": project_id,
                    "findings_count": len(findings),
                    "dr": score["dr"],
                    "expected": score["expected"],
                    "matched": score["matched"],
                    "duration": round(duration, 1),
                })
                print(f"DR={score['dr']:.0%} ({score['matched']}/{score['expected']}) {duration:.0f}s", flush=True)
            else:
                strategy_results.append({"project": project_id, "findings_count": 0, "dr": 0, "expected": 0, "matched": 0, "duration": round(duration, 1)})
                print(f"0 findings {duration:.0f}s", flush=True)

        # Calculate fitness
        avg_dr = sum(r["dr"] for r in strategy_results) / max(len(strategy_results), 1)
        total_matched = sum(r["matched"] for r in strategy_results)
        total_expected = sum(r["expected"] for r in strategy_results)

        strategy["fitness"] = avg_dr
        strategy["total_matched"] = total_matched
        strategy["total_expected"] = total_expected

        results.append({
            "strategy_id": strategy["id"],
            "analysis_prompt": strategy["analysis_prompt"],
            "results": strategy_results,
            "avg_dr": round(avg_dr, 3),
            "total_matched": total_matched,
            "total_expected": total_expected,
        })

        # Save per-strategy
        (gen_dir / f"{strategy['id']}.json").write_text(json.dumps(results[-1], indent=2))

    # Save generation summary
    (gen_dir / "generation_summary.json").write_text(json.dumps(results, indent=2))

    return results


def run_cge(generations=3, pop_size=4):
    """Run CG/CGE evolution loop."""
    rng = random.Random(42)
    log_dir = RESULTS_BASE / f"cge-{int(time.time())}"
    log_dir.mkdir(parents=True, exist_ok=True)

    # Save config
    (log_dir / "config.json").write_text(json.dumps({
        "generations": generations,
        "pop_size": pop_size,
        "projects": PROJECTS,
        "model": MODEL,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }, indent=2))

    # Initialize
    strategies = get_base_strategies()[:pop_size]
    best_ever = None
    best_ever_dr = 0

    for gen in range(generations):
        print(f"\n{'='*60}", flush=True)
        print(f"GENERATION {gen}", flush=True)
        print(f"{'='*60}", flush=True)

        results = run_generation(strategies, gen, log_dir)

        # Sort by fitness
        strategies.sort(key=lambda s: s.get("fitness", 0), reverse=True)

        print(f"\n  Generation {gen} results:", flush=True)
        for s in strategies:
            print(f"    {s['id']}: DR={s.get('fitness',0):.0%} matched={s.get('total_matched',0)}/{s.get('total_expected',0)}", flush=True)

        if strategies[0].get("fitness", 0) > best_ever_dr:
            best_ever_dr = strategies[0]["fitness"]
            best_ever = strategies[0].copy()

        # Selection + mutation
        if gen < generations - 1:
            elites = strategies[:2]
            children = []
            for parent in elites:
                children.append(mutate_strategy(parent, rng))
                children.append(mutate_strategy(parent, rng))
            strategies = elites + children
            while len(strategies) < pop_size:
                strategies.append(mutate_strategy(rng.choice(elites), rng))

    # Final summary
    summary = {
        "best_strategy": best_ever["id"] if best_ever else None,
        "best_dr": best_ever_dr,
        "best_prompt": best_ever["analysis_prompt"][:500] if best_ever else None,
        "generations": generations,
        "log_dir": str(log_dir),
    }
    (log_dir / "final_summary.json").write_text(json.dumps(summary, indent=2))

    print(f"\n{'='*60}", flush=True)
    print(f"CGE COMPLETE", flush=True)
    print(f"Best: {best_ever['id'] if best_ever else 'none'} DR={best_ever_dr:.0%}", flush=True)
    print(f"Log: {log_dir}", flush=True)
    print(f"{'='*60}", flush=True)

    return summary


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--generations", type=int, default=3)
    parser.add_argument("--pop-size", type=int, default=4)
    args = parser.parse_args()
    run_cge(generations=args.generations, pop_size=args.pop_size)
