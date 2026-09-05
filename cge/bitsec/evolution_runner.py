"""BitSec Evolution Runner — mutates strategies, evaluates on ScaBench, logs results."""
import json
import os
import random
import re
import sys
import time
import hashlib
import requests
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

# Proxy config
PROXY = "http://localhost:8087"
API_KEY = "sk-A5QHR5MRtUNec7BWqiRsZ0GAYck0CRT2Movsk7Q6U3UwcV77Y6G3TMXOhhyKh855"
MODEL = "mimo-v2.5"

# Data paths
GT_PATH = "/root/bitt/subnets/sn60-bitsec/tools/scabench/datasets/curated-2025-08-18/curated-2025-08-18.json"
RESULTS_BASE = Path("/root/bitt/data/evolution")

# Test projects (2 for speed)
TEST_PROJECTS = [
    "code4rena_superposition_2025_01",
    "code4rena_lambowin_2025_02",
]


@dataclass
class Strategy:
    """A mutation of the analysis approach."""
    id: str
    system_prompt: str
    max_tokens: int
    turns_per_file: int
    seed_with_list: bool
    seed_with_content: bool
    content_truncate: int
    architecture_first: bool
    priority_order: str  # "random", "size", "risk"
    report_early: bool
    # Metadata
    generation: int = 0
    parent_id: str = ""
    fitness: float = 0.0


def call_llm(messages, max_tokens=8192, temperature=0.1):
    """Call LLM through proxy."""
    for attempt in range(3):
        try:
            resp = requests.post(f"{PROXY}/inference", headers={
                "x-inference-api-key": API_KEY,
                "x-agent-id": "evolution",
                "x-job-run-id": f"evo-{int(time.time())}-{attempt}",
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
        except Exception as e:
            pass
        time.sleep(2)
    return ""


def discover_files(source_dir):
    """Discover contract files."""
    patterns = ['**/*.sol', '**/*.vy', '**/*.cairo', '**/*.rs', '**/*.move']
    exclude = {"testing", "mocks", "examples", "interfaces", "script", "broadcast", "libraries"}
    files = []
    for p in patterns:
        files.extend(source_dir.glob(p))
    return [
        f for f in files
        if f.is_file()
        and "test" not in f.name.lower()
        and not any(part.lower() in exclude for part in f.parts)
    ]


def analyze_project(source_dir, project_name, strategy):
    """Run one strategy on one project. Returns findings list."""
    files = discover_files(source_dir)
    if not files:
        return []

    # Priority ordering
    if strategy.priority_order == "size":
        files.sort(key=lambda f: f.stat().st_size, reverse=True)
    elif strategy.priority_order == "random":
        import random
        random.shuffle(files)

    all_findings = []
    deadline = time.monotonic() + 300  # 5 min total

    for file_path in files:
        if time.monotonic() >= deadline:
            break

        rel_path = str(file_path.relative_to(source_dir))

        # Build messages
        messages = [
            {"role": "system", "content": strategy.system_prompt},
            {"role": "user", "content": f"Analyze {rel_path} for vulnerabilities"}
        ]

        # Seed: file list
        if strategy.seed_with_list:
            root = source_dir.resolve()
            file_list = []
            for item in sorted(source_dir.iterdir()):
                r = str(item.resolve().relative_to(root))
                file_list.append(r + ("/" if item.is_dir() else ""))
            list_content = json.dumps({"files": file_list[:50]})
            messages.append({"role": "assistant", "tool_calls": [{"id": "seed-list", "type": "function", "function": {"name": "list_files", "arguments": json.dumps({"directory": "."})}}]})
            messages.append({"role": "tool", "tool_call_id": "seed-list", "content": list_content})

        # Seed: file content
        if strategy.seed_with_content:
            try:
                content = file_path.read_text(encoding="utf-8")[:strategy.content_truncate]
            except:
                content = ""
            messages.append({"role": "assistant", "tool_calls": [{"id": "seed-read", "type": "function", "function": {"name": "read_file", "arguments": json.dumps({"file_path": rel_path})}}]})
            messages.append({"role": "tool", "tool_call_id": "seed-read", "content": content})

        # Tool loop
        tools = [
            {"type": "function", "function": {"name": "list_files", "parameters": {"type": "object", "properties": {"directory": {"type": "string"}}, "required": ["directory"]}}},
            {"type": "function", "function": {"name": "read_file", "parameters": {"type": "object", "properties": {"file_path": {"type": "string"}}, "required": ["file_path"]}}},
            {"type": "function", "function": {"name": "report_vulnerabilities", "parameters": {"type": "object", "properties": {"vulnerabilities": {"type": "array", "items": {"type": "object", "properties": {"title": {"type": "string"}, "description": {"type": "string"}, "vulnerability_type": {"type": "string"}, "severity": {"type": "string"}, "confidence": {"type": "number"}, "location": {"type": "string"}, "file": {"type": "string"}}, "required": ["title", "description", "vulnerability_type", "severity", "confidence", "location", "file"]}}}, "required": ["vulnerabilities"]}}}
        ]

        file_findings = []
        for turn in range(strategy.turns_per_file):
            if time.monotonic() >= deadline:
                break

            response_text = call_llm(messages, max_tokens=strategy.max_tokens)
            if not response_text:
                break

            # Try to parse as JSON with tool calls
            try:
                # Check if it's a tool call
                if "report_vulnerabilities" in response_text:
                    match = re.search(r'"vulnerabilities"\s*:\s*\[([\s\S]*?)\]', response_text)
                    if match:
                        vulns = json.loads("[" + match.group(1) + "]")
                        for v in vulns:
                            v["file"] = rel_path
                            v["reported_by_model"] = MODEL
                        file_findings.extend(vulns)
                        break
                    # Try content fallback
                    vuln_match = re.search(r'\{[\s\S]*"vulnerabilities"[\s\S]*\}', response_text)
                    if vuln_match:
                        data = json.loads(vuln_match.group())
                        if "vulnerabilities" in data:
                            for v in data["vulnerabilities"]:
                                v["file"] = rel_path
                                v["reported_by_model"] = MODEL
                            file_findings.extend(data["vulnerabilities"])
                            break
            except:
                pass

            # Content fallback: parse vulns from text
            try:
                vuln_match = re.search(r'\{[\s\S]*"vulnerabilities"[\s\S]*\}', response_text)
                if vuln_match:
                    data = json.loads(vuln_match.group())
                    if "vulnerabilities" in data:
                        for v in data["vulnerabilities"]:
                            v["file"] = rel_path
                            v["reported_by_model"] = MODEL
                        file_findings.extend(data["vulnerabilities"])
                        break
            except:
                pass

            # Try individual vuln extraction
            vulns_raw = re.findall(r'\{[^{}]*"title"\s*:\s*"[^"]*"[^{}]*\}', response_text)
            for v_str in vulns_raw:
                try:
                    v = json.loads(v_str)
                    v["file"] = rel_path
                    v["reported_by_model"] = MODEL
                    for field in ["title", "description", "vulnerability_type", "severity", "confidence", "location"]:
                        if field not in v:
                            v[field] = "unknown" if field != "confidence" else 0.5
                    file_findings.append(v)
                except:
                    pass

        all_findings.extend(file_findings)

    # Deduplicate
    seen = set()
    unique = []
    for f in all_findings:
        key = f.get("title", "") + f.get("file", "")
        h = hashlib.md5(key.encode()).hexdigest()[:16]
        if h not in seen:
            seen.add(h)
            unique.append(f)

    return unique


def score_against_ground_truth(findings, project_id):
    """Score findings against ground truth using LLM matching."""
    gt_data = json.load(open(GT_PATH))
    gt_entry = next((e for e in gt_data if e["project_id"] == project_id), None)
    if not gt_entry:
        return {"detection_rate": 0, "expected": 0, "matched": 0}

    # Use highs-only for production scoring
    highs_path = "/root/bitt/subnets/sn60-bitsec/sandbox-v2/validator/curated-highs-only-2025-08-08.json"
    highs_data = json.load(open(highs_path))
    highs_entry = next((e for e in highs_data if e["project_id"] == project_id), None)

    if highs_entry:
        expected = highs_entry.get("vulnerabilities", [])
    else:
        expected = [v for v in gt_entry["vulnerabilities"] if v.get("severity") in ("high", "critical")]

    if not expected:
        return {"detection_rate": 1.0, "expected": 0, "matched": 0}

    matched = 0
    for exp in expected:
        # Quick semantic check using LLM
        findings_text = ""
        for i, f in enumerate(findings[:15]):
            findings_text += f"[{i}] {f.get('title','?')} ({f.get('severity','?')}) - {f.get('description','?')[:150]}\n"

        prompt = f"""Does any TOOL FINDING match this EXPECTED vulnerability?

EXPECTED: {exp.get('title','')}
DESCRIPTION: {exp.get('description','')[:400]}
SEVERITY: {exp.get('severity','')}

TOOL FINDINGS:
{findings_text}

Return JSON: {{"found": true/false, "confidence": 0.0-1.0}}"""

        try:
            content = call_llm([
                {"role": "system", "content": "You are a vulnerability matcher. Return JSON only."},
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
    return {"detection_rate": round(dr, 3), "expected": len(expected), "matched": matched}


def run_evaluation(strategy, project_ids):
    """Evaluate a strategy across projects."""
    results = []
    for pid in project_ids:
        source_dir = Path(f"/root/bitt/data/scabench-repos/{pid}")
        if not source_dir.exists():
            continue

        print(f"    [{pid}]", end=" ", flush=True)
        start = time.monotonic()
        findings = analyze_project(source_dir, pid, strategy)
        duration = time.monotonic() - start

        score = score_against_ground_truth(findings, pid)

        result = {
            "project": pid,
            "findings_count": len(findings),
            "detection_rate": score["detection_rate"],
            "expected": score["expected"],
            "matched": score["matched"],
            "duration_seconds": round(duration, 1),
            "high_findings": sum(1 for f in findings if f.get("severity") in ("high", "critical")),
        }
        results.append(result)
        print(f"DR={score['detection_rate']:.0%} ({score['matched']}/{score['expected']}) {duration:.0f}s", flush=True)

    return results


def create_initial_population():
    """Create diverse starting strategies."""
    prompts = {
        "generic": "You are a senior smart contract security auditor. Analyze code for security vulnerabilities. Report findings using report_vulnerabilities tool.",
        "cot": "You are a senior smart contract security auditor. Think step-by-step: 1) What does this code do? 2) What could go wrong? 3) Where specifically? 4) What's the impact? Report findings using report_vulnerabilities tool.",
        "invariant": "You are a security auditor. For each function, identify: 1) What invariants must hold? 2) What conditions could violate them? 3) What would be the impact? Focus on business logic errors, not just common patterns. Report using report_vulnerabilities tool.",
        "cross_file": "You are a security auditor. Analyze this file in context of the whole project. Focus on: cross-contract calls, state synchronization, access control between contracts, and data flow across boundaries. Report using report_vulnerabilities tool.",
        "defi": "You are a DeFi security specialist. Focus on: slippage protection, oracle manipulation, flash loan attacks, liquidity math, fee calculations, and economic invariant violations. Report using report_vulnerabilities tool.",
        "architect": "You are a security architect. Before analyzing code, map the architecture: what contracts exist, how they interact, what are the trust boundaries. Then analyze each high-risk interaction for vulnerabilities. Report using report_vulnerabilities tool.",
    }

    strategies = []
    for i, (name, prompt) in enumerate(prompts.items()):
        strategies.append(Strategy(
            id=f"gen0-{i}",
            system_prompt=prompt,
            max_tokens=8192,
            turns_per_file=3,
            seed_with_list=True,
            seed_with_content=True,
            content_truncate=8000,
            architecture_first=(name == "architect"),
            priority_order="random",
            report_early=False,
            generation=0,
        ))

    return strategies


def mutate(parent, rng):
    """Create a mutated child strategy."""
    child = Strategy(
        id=f"gen{parent.generation+1}-{rng.randint(0,9999)}",
        system_prompt=parent.system_prompt,
        max_tokens=parent.max_tokens,
        turns_per_file=parent.turns_per_file,
        seed_with_list=parent.seed_with_list,
        seed_with_content=parent.seed_with_content,
        content_truncate=parent.content_truncate,
        architecture_first=parent.architecture_first,
        priority_order=parent.priority_order,
        report_early=parent.report_early,
        generation=parent.generation + 1,
        parent_id=parent.id,
    )

    # Mutate one random parameter
    mutation = rng.choice(["prompt", "tokens", "turns", "seed", "truncate", "priority", "arch"])

    if mutation == "prompt":
        # Small prompt variation
        additions = [
            "\n\nPay special attention to: integer overflow, unchecked return values, reentrancy.",
            "\n\nFocus on BUSINESS LOGIC errors, not just common vulnerability patterns.",
            "\n\nLook for: incorrect math, missing validations, wrong variable usage.",
            "\n\nCheck: does this code do what the comments say it does?",
            "\n\nCompare with known vulnerability patterns in similar protocols.",
            "\n\nTrace the flow of assets (tokens, ETH) through this code.",
        ]
        child.system_prompt = parent.system_prompt + rng.choice(additions)
    elif mutation == "tokens":
        child.max_tokens = rng.choice([4096, 8192, 12288, 16384])
    elif mutation == "turns":
        child.turns_per_file = rng.choice([2, 3, 4, 5])
    elif mutation == "seed":
        child.seed_with_list = rng.choice([True, False])
        child.seed_with_content = rng.choice([True, False])
    elif mutation == "truncate":
        child.content_truncate = rng.choice([4000, 6000, 8000, 12000, 20000])
    elif mutation == "priority":
        child.priority_order = rng.choice(["random", "size", "risk"])
    elif mutation == "arch":
        child.architecture_first = not parent.architecture_first

    return child


def run_evolution(generations=3, pop_size=6, test_projects=None):
    """Run evolution campaign."""
    if test_projects is None:
        test_projects = TEST_PROJECTS

    rng = random.Random(42)
    log_dir = RESULTS_BASE / f"campaign-{int(time.time())}"
    log_dir.mkdir(parents=True, exist_ok=True)

    # Save reference
    (log_dir / "config.json").write_text(json.dumps({
        "generations": generations,
        "pop_size": pop_size,
        "test_projects": test_projects,
        "model": MODEL,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }, indent=2))

    # Initialize population
    population = create_initial_population()[:pop_size]

    best_ever = None
    best_ever_dr = 0

    for gen in range(generations):
        print(f"\n=== Generation {gen} ===", flush=True)
        gen_results = []

        for strategy in population:
            print(f"\n  Strategy: {strategy.id}", flush=True)
            print(f"    Prompt: {strategy.system_prompt[:80]}...", flush=True)
            print(f"    Tokens: {strategy.max_tokens}, Turns: {strategy.turns_per_file}", flush=True)

            results = run_evaluation(strategy, test_projects)
            avg_dr = sum(r["detection_rate"] for r in results) / max(len(results), 1)
            strategy.fitness = avg_dr

            gen_results.append({
                "strategy_id": strategy.id,
                "generation": gen,
                "params": {
                    "system_prompt": strategy.system_prompt,
                    "max_tokens": strategy.max_tokens,
                    "turns_per_file": strategy.turns_per_file,
                    "seed_with_list": strategy.seed_with_list,
                    "seed_with_content": strategy.seed_with_content,
                    "content_truncate": strategy.content_truncate,
                    "architecture_first": strategy.architecture_first,
                    "priority_order": strategy.priority_order,
                },
                "results": results,
                "avg_detection_rate": round(avg_dr, 3),
                "fitness": round(avg_dr, 3),
            })

            if avg_dr > best_ever_dr:
                best_ever_dr = avg_dr
                best_ever = strategy

            print(f"    AVG DR: {avg_dr:.0%}", flush=True)

        # Save generation results
        gen_file = log_dir / f"gen-{gen}.json"
        gen_file.write_text(json.dumps(gen_results, indent=2))

        # Selection: top 2 survive
        population.sort(key=lambda s: s.fitness, reverse=True)
        elites = population[:2]

        print(f"\n  Top strategies:", flush=True)
        for e in elites:
            print(f"    {e.id}: DR={e.fitness:.0%}", flush=True)

        if gen < generations - 1:
            # Create children
            children = []
            for parent in elites:
                children.append(mutate(parent, rng))
                children.append(mutate(parent, rng))
            population = elites + children
            # Fill remaining slots
            while len(population) < pop_size:
                population.append(mutate(rng.choice(elites), rng))

    # Save summary
    summary = {
        "best_strategy": best_ever.id if best_ever else None,
        "best_dr": best_ever_dr,
        "generations": generations,
        "total_evaluations": generations * pop_size,
        "log_dir": str(log_dir),
    }
    (log_dir / "summary.json").write_text(json.dumps(summary, indent=2))

    print(f"\n=== EVOLUTION COMPLETE ===", flush=True)
    print(f"Best: {best_ever.id if best_ever else 'none'} DR={best_ever_dr:.0%}", flush=True)
    print(f"Log: {log_dir}", flush=True)

    return summary


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--generations", type=int, default=3)
    parser.add_argument("--pop-size", type=int, default=6)
    parser.add_argument("--projects", nargs="+", default=None)
    args = parser.parse_args()

    run_evolution(
        generations=args.generations,
        pop_size=args.pop_size,
        test_projects=args.projects,
    )
