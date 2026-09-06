"""Evolution loop for Scout/Senior agent — mutates prompts, evaluates, selects."""
import json
import hashlib
import random
import re
import sys
import time
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))
from agent import call_llm, discover_files, read_file_safe, StaticAnalyzer, scout_pass, senior_pass, analyze_project

GT_PATH = "/root/bitt/subnets/sn60-bitsec/tools/scabench/datasets/curated-2025-08-18/curated-2025-08-18.json"
HIGHS_PATH = "/root/bitt/subnets/sn60-bitsec/sandbox-v2/validator/curated-highs-only-2025-08-08.json"
RESULTS_BASE = Path("/root/bitt/data/scout-senior-evolution")
TEST_PROJECTS = [
    "code4rena_superposition_2025_01",
    "code4rena_lambowin_2025_02",
]


def score_against_ground_truth(findings, project_id):
    """Score findings against ground truth using LLM matching."""
    highs_data = json.load(open(HIGHS_PATH))
    highs_entry = next((e for e in highs_data if e["project_id"] == project_id), None)

    if not highs_entry:
        gt_data = json.load(open(GT_PATH))
        gt_entry = next((e for e in gt_data if e["project_id"] == project_id), None)
        if not gt_entry:
            return {"detection_rate": 0, "expected": 0, "matched": 0}
        expected = [v for v in gt_entry["vulnerabilities"] if v.get("severity") in ("high", "critical")]
    else:
        expected = highs_entry.get("vulnerabilities", [])

    if not expected:
        return {"detection_rate": 1.0, "expected": 0, "matched": 0}

    matched = 0
    for exp in expected:
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


def evaluate_strategy(scout_prompt, senior_prompt, test_projects):
    """Evaluate a strategy pair on test projects."""
    results = []
    for pid in test_projects:
        source_dir = Path(f"/root/bitt/data/scabench-repos/{pid}")
        if not source_dir.exists():
            continue

        print(f"    [{pid}]", end=" ", flush=True)
        start = time.monotonic()
        
        # Run with custom prompts
        analyzer = StaticAnalyzer(source_dir)
        static_result = analyzer.analyze()
        static_summary = analyzer.get_summary()
        
        # Custom scout prompt
        messages = [
            {"role": "system", "content": scout_prompt},
            {"role": "user", "content": f"Analyze this project:\n{static_summary}"}
        ]
        scout_response = call_llm(messages, max_tokens=4096)
        try:
            match = re.search(r'\[[\s\S]*\]', scout_response)
            scout_findings = json.loads(match.group()) if match else []
        except:
            scout_findings = []
        
        # Custom senior prompt
        senior_findings = []
        for sf in scout_findings[:8]:
            area = sf.get("area", "unknown")
            relevant_funcs = sf.get("relevant_functions", [])
            code_context = ""
            for fid in relevant_funcs[:3]:
                code = analyzer.get_code_context(fid)
                if code:
                    code_context += f"\n--- {fid} ---\n{code}\n"
            if not code_context:
                continue
            
            messages = [
                {"role": "system", "content": senior_prompt},
                {"role": "user", "content": f"AREA: {area}\nCODE:\n{code_context}"}
            ]
            response = call_llm(messages, max_tokens=4096)
            try:
                match = re.search(r'\[[\s\S]*\]', response)
                if match:
                    senior_findings.extend(json.loads(match.group()))
            except:
                pass
        
        duration = time.monotonic() - start
        score = score_against_ground_truth(senior_findings, pid)
        
        results.append({
            "project": pid,
            "findings_count": len(senior_findings),
            "detection_rate": score["detection_rate"],
            "expected": score["expected"],
            "matched": score["matched"],
            "duration_seconds": round(duration, 1),
        })
        print(f"DR={score['detection_rate']:.0%} ({score['matched']}/{score['expected']}) {duration:.0f}s", flush=True)
    
    return results


def mutate_prompt(prompt, rng):
    """Create a mutated version of a prompt."""
    mutations = [
        "Focus on BUSINESS LOGIC errors, not just common vulnerability patterns.",
        "Look for: incorrect math, missing validations, wrong variable usage.",
        "Trace the flow of assets (tokens, ETH) through this code.",
        "Check: does this code do what the comments say it does?",
        "Look for cross-contract state synchronization issues.",
        "Focus on: slippage protection, oracle manipulation, economic invariants.",
        "Check for: reentrancy, access control, integer overflow.",
        "Compare with known DeFi vulnerability patterns.",
        "Look for: missing validations, unchecked return values, silent failures.",
        "Focus on: business rule violations, not just code patterns.",
    ]
    
    # Random mutation type
    mutation_type = rng.choice(["append", "replace_focus", "add_constraint"])
    
    if mutation_type == "append":
        return prompt + "\n\n" + rng.choice(mutations)
    elif mutation_type == "replace_focus":
        # Replace the focus section
        lines = prompt.split('\n')
        focus_start = -1
        for i, line in enumerate(lines):
            if 'Focus on:' in line or 'focus on' in line.lower():
                focus_start = i
                break
        if focus_start >= 0:
            lines[focus_start] = "Focus on: " + rng.choice(mutations).replace("Look for: ", "").replace("Check: ", "")
        return '\n'.join(lines)
    else:
        # Add constraint
        constraints = [
            "\n\nIMPORTANT: Do NOT report findings with confidence below 0.7.",
            "\n\nIMPORTANT: Only report vulnerabilities that could lead to actual fund loss.",
            "\n\nIMPORTANT: Cross-reference findings across contracts before reporting.",
            "\n\nIMPORTANT: Prioritize high-severity findings over medium/low.",
        ]
        return prompt + rng.choice(constraints)


def run_evolution(generations=3, pop_size=4):
    """Run evolution campaign."""
    rng = random.Random(42)
    log_dir = RESULTS_BASE / f"campaign-{int(time.time())}"
    log_dir.mkdir(parents=True, exist_ok=True)

    # Base prompts (from the working agent)
    base_scout = """You are a security Scout agent. Your job is to quickly scan smart contract code and identify high-risk areas.

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

    base_senior = """You are a security Senior agent. Your job is to deeply analyze specific high-risk areas and confirm vulnerabilities.

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

    # Initialize population with prompt variations
    strategies = []
    for i in range(pop_size):
        scout = mutate_prompt(base_scout, rng)
        senior = mutate_prompt(base_senior, rng)
        strategies.append({
            "id": f"gen0-{i}",
            "scout_prompt": scout,
            "senior_prompt": senior,
            "generation": 0,
            "fitness": 0,
        })

    best_ever = None
    best_ever_dr = 0

    for gen in range(generations):
        print(f"\n=== Generation {gen} ===", flush=True)
        gen_results = []

        for strategy in strategies:
            print(f"\n  Strategy: {strategy['id']}", flush=True)
            print(f"    Scout: {strategy['scout_prompt'][:80]}...", flush=True)

            results = evaluate_strategy(
                strategy["scout_prompt"],
                strategy["senior_prompt"],
                TEST_PROJECTS
            )

            avg_dr = sum(r["detection_rate"] for r in results) / max(len(results), 1)
            strategy["fitness"] = avg_dr

            gen_results.append({
                "strategy_id": strategy["id"],
                "generation": gen,
                "scout_prompt": strategy["scout_prompt"],
                "senior_prompt": strategy["senior_prompt"],
                "results": results,
                "avg_detection_rate": round(avg_dr, 3),
            })

            if avg_dr > best_ever_dr:
                best_ever_dr = avg_dr
                best_ever = strategy.copy()

            print(f"    AVG DR: {avg_dr:.0%}", flush=True)

        # Save generation
        (log_dir / f"gen-{gen}.json").write_text(json.dumps(gen_results, indent=2))

        # Selection: top 2 survive
        strategies.sort(key=lambda s: s["fitness"], reverse=True)
        elites = strategies[:2]

        print(f"\n  Top strategies:", flush=True)
        for e in elites:
            print(f"    {e['id']}: DR={e['fitness']:.0%}", flush=True)

        if gen < generations - 1:
            children = []
            for parent in elites:
                children.append({
                    "id": f"gen{gen+1}-{rng.randint(0,9999)}",
                    "scout_prompt": mutate_prompt(parent["scout_prompt"], rng),
                    "senior_prompt": mutate_prompt(parent["senior_prompt"], rng),
                    "generation": gen + 1,
                    "fitness": 0,
                })
            strategies = elites + children
            while len(strategies) < pop_size:
                strategies.append({
                    "id": f"gen{gen+1}-{rng.randint(0,9999)}",
                    "scout_prompt": mutate_prompt(rng.choice(elites)["scout_prompt"], rng),
                    "senior_prompt": mutate_prompt(rng.choice(elites)["senior_prompt"], rng),
                    "generation": gen + 1,
                    "fitness": 0,
                })

    # Save summary
    summary = {
        "best_strategy": best_ever["id"] if best_ever else None,
        "best_dr": best_ever_dr,
        "generations": generations,
        "log_dir": str(log_dir),
    }
    (log_dir / "summary.json").write_text(json.dumps(summary, indent=2))

    print(f"\n=== EVOLUTION COMPLETE ===", flush=True)
    print(f"Best: {best_ever['id'] if best_ever else 'none'} DR={best_ever_dr:.0%}", flush=True)
    print(f"Log: {log_dir}", flush=True)

    return summary


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--generations", type=int, default=2)
    parser.add_argument("--pop-size", type=int, default=4)
    args = parser.parse_args()
    
    run_evolution(generations=args.generations, pop_size=args.pop_size)
