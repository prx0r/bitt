"""Lean experiment runner — runs pipeline-v3 on one project, scores it.
No holding all files in memory. Sequential phases. Proper error handling."""
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path("/root/bitt")))

PROXY = os.environ.get("INFERENCE_API", "http://localhost:8087")
API_KEY = os.environ.get("INFERENCE_API_KEY", "sk-A5QHR5MRtUNec7BWqiRsZ0GAYck0CRT2Movsk7Q6U3UwcV77Y6G3TMXOhhyKh855")
MODEL = os.environ.get("OPENAI_MODEL", "mimo-v2.5")

REPOS_DIR = Path("/root/bitt/data/scabench-repos")
HIGHS_PATH = Path("/root/bitt/subnets/sn60-bitsec/sandbox-v2/validator/curated-highs-only-2025-08-08.json")
RESULTS_DIR = Path("/root/bitt/data/experiments")

import requests


def call_llm(messages, max_tokens=6000, temperature=0.1):
    for attempt in range(3):
        try:
            resp = requests.post(f"{PROXY}/inference", headers={
                "x-inference-api-key": API_KEY, "x-agent-id": "runner",
                "x-job-run-id": f"run-{int(time.time())}-{attempt}",
                "x-request-phase": "execution"
            }, json={"model": MODEL, "messages": messages,
                     "max_tokens": max_tokens, "temperature": temperature},
            timeout=180)
            if resp.status_code == 200:
                r = resp.json()
                c = r["choices"][0]["message"]["content"]
                if c and len(c) > 10:
                    return c
        except:
            pass
        time.sleep(3)
    return ""


def parse_json(text):
    """Parse JSON from LLM response. Handle nested braces correctly."""
    import re
    if not text:
        return None

    # Try to find the outermost JSON structure
    # First try array
    for start_ch, end_ch in [('[', ']'), ('{', '}')]:
        start = text.find(start_ch)
        if start < 0:
            continue
        # Find matching end by counting braces
        depth = 0
        in_string = False
        escape = False
        for i in range(start, len(text)):
            ch = text[i]
            if escape:
                escape = False
                continue
            if ch == '\\' and in_string:
                escape = True
                continue
            if ch == '"' and not escape:
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == start_ch:
                depth += 1
            elif ch == end_ch:
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i+1])
                    except:
                        break
    return None


def discover_files(source_dir):
    exts = ['**/*.sol', '**/*.rs', '**/*.vy', '**/*.cairo', '**/*.move']
    exclude = {"testing", "mocks", "examples", "interfaces", "script",
               "broadcast", "libraries", "node_modules", "lib", "deps", "target"}
    files = []
    for p in exts:
        files.extend(source_dir.glob(p))
    return [f for f in files if f.is_file()
            and "test" not in f.name.lower()
            and not any(part.lower() in exclude for part in f.parts)
            and f.stat().st_size < 100000]


def read_file(path, max_chars=15000):
    try:
        return path.read_text(encoding="utf-8")[:max_chars]
    except:
        return ""


def detect_lang(source_dir):
    exts = set()
    for f in source_dir.rglob("*"):
        if f.is_file():
            exts.add(f.suffix.lower())
    if '.sol' in exts: return 'solidity'
    if '.rs' in exts: return 'rust'
    return 'unknown'


def score_findings(findings, project_id):
    """Score against curated-highs-only ground truth."""
    gt_data = json.load(open(HIGHS_PATH))
    gt_entry = next((e for e in gt_data if e["project_id"] == project_id), None)
    if not gt_entry:
        return {"dr": 1.0, "expected": 0, "matched": 0, "missed": []}

    expected = gt_entry.get("vulnerabilities", [])
    if not expected:
        return {"dr": 1.0, "expected": 0, "matched": 0, "missed": []}

    matched = 0
    missed = []
    for exp in expected:
        gt_title = exp["title"].lower()
        gt_desc = exp.get("description", "").lower()[:300]
        best_score = 0

        for f in findings:
            f_title = f.get("title", "").lower()
            f_desc = f.get("description", "").lower()[:300]

            # Multi-signal matching
            score = 0
            # Title word overlap
            fw = set(f_title.split())
            gw = set(gt_title.split())
            if fw and gw:
                score += len(fw & gw) / max(len(fw | gw), 1) * 0.5
            # Description overlap
            if f_desc and gt_desc:
                fd = set(f_desc.split())
                gd = set(gt_desc.split())
                if fd and gd:
                    score += len(fd & gd) / max(len(fd | gd), 1) * 0.3
            # Function name overlap
            import re
            gt_funcs = set(re.findall(r'(\w+)\(', gt_title + " " + exp.get("description", "")))
            f_funcs = set(re.findall(r'(\w+)\(', f_title + " " + f.get("description", "")))
            if gt_funcs and f_funcs:
                score += len(gt_funcs & f_funcs) / max(len(gt_funcs), 1) * 0.3

            if score > best_score:
                best_score = score

        if best_score >= 0.15:
            matched += 1
        else:
            missed.append({"title": exp["title"], "best_score": round(best_score, 3)})

    return {
        "dr": round(matched / len(expected), 3) if expected else 1.0,
        "expected": len(expected),
        "matched": matched,
        "missed": missed
    }


def run_project(project_id):
    """Run pipeline-v3 on one project. Returns findings list."""
    source_dir = REPOS_DIR / project_id
    if not source_dir.exists():
        print(f"  ERROR: {source_dir} not found")
        return []

    files = discover_files(source_dir)
    print(f"  Files: {len(files)}")

    # Read all source files
    code_parts = {}
    for f in files:
        rel = str(f.relative_to(source_dir))
        content = read_file(f, 15000)
        if content:
            code_parts[rel] = content

    # Batch into ~15k chunks
    batches = []
    current = ""
    for rel, content in code_parts.items():
        entry = f"\n--- {rel} ---\n{content}\n"
        if len(current) + len(entry) > 15000:
            if current:
                batches.append(current)
            current = entry
        else:
            current += entry
    if current:
        batches.append(current)

    file_tree = "\n".join(sorted(code_parts.keys()))
    lang = detect_lang(source_dir)

    print(f"  Batches: {len(batches)}")

    # Phase 1: Protocol understanding (all batches, but smaller)
    print("  [Phase 1] Protocol understanding...")
    all_maps = []
    for i, batch in enumerate(batches):
        resp = call_llm([{"role": "user", "content":
            f"""Repository: {project_id}
Language: {lang}
File tree: {file_tree}

Read this code carefully. Output ONLY valid JSON with:
1. protocol_purpose: what does this protocol do?
2. entry_points: array of {{function, file, related_files[], lifecycle, invariants_that_must_hold[]}}
3. business_logic_risks: array of strings
4. invariant_hypotheses: array of strings in "IF [condition] THEN [invariant]" format

CODE:
{batch}"""}], max_tokens=6000)
        m = parse_json(resp)
        if m:
            all_maps.append(m)
            print(f"    Batch {i+1}/{len(batches)}: OK")
        else:
            print(f"    Batch {i+1}/{len(batches)}: parse failed")

    # Merge
    arch_map = {"protocol_purpose": "", "entry_points": [], "business_logic_risks": [], "invariant_hypotheses": []}
    for m in all_maps:
        if isinstance(m, list):
            # Model returned just an array of entry points
            for item in m:
                if isinstance(item, dict):
                    arch_map["entry_points"].append(item)
            continue
        if not isinstance(m, dict):
            continue
        pp = m.get("protocol_purpose", "")
        if len(pp) > len(arch_map["protocol_purpose"]):
            arch_map["protocol_purpose"] = pp
        for key in ["entry_points", "business_logic_risks", "invariant_hypotheses"]:
            if key in m and isinstance(m[key], list):
                arch_map[key].extend(m[key])

    eps = arch_map.get("entry_points", [])
    print(f"  Protocol: {arch_map['protocol_purpose'][:80]}")
    print(f"  Entry points: {len(eps)}")

    # Phase 2: Per-entry-point trace (max 10 entry points)
    print("  [Phase 2] Per-entry-point trace...")
    all_findings = []
    for i, ep in enumerate(eps[:10]):
        if not isinstance(ep, dict):
            continue
        func = ep.get("function", f"ep_{i}")
        ep_file = ep.get("file", "")
        related = ep.get("related_files", [])

        # Gather code for this entry point
        ep_code = ""
        if ep_file:
            full = source_dir / ep_file
            if full.exists():
                ep_code += f"\n--- {ep_file} ---\n{read_file(full, 8000)}\n"
        for rf in related[:4]:
            if isinstance(rf, str):
                full = source_dir / rf
                if full.exists():
                    ep_code += f"\n--- {rf} ---\n{read_file(full, 5000)}\n"

        if not ep_code:
            continue

        resp = call_llm([{"role": "user", "content":
            f"""You are a PROTOCOL STATE-MACHINE ANALYST.

Entry point: {func}
File: {ep_file}
Related files: {related}

Invariant hypotheses:
{json.dumps(arch_map.get('invariant_hypotheses', [])[:5])}

CODE:
{ep_code}

Trace the state machine for {func}:
1. What is state BEFORE the call?
2. What does {func} do step by step?
3. What state should be AFTER?
4. What if preconditions are FALSE?
5. What if an attacker provides MALICIOUS inputs?

Find where the implementation permits a state the protocol forbids.

Output JSON array: [{{title, function, file, invariant, attack_sequence[], state_before, state_after, violated_property, impact, severity}}]"""}], max_tokens=5000)

        candidates = parse_json(resp)
        if isinstance(candidates, list):
            for c in candidates:
                if isinstance(c, dict):
                    c["trace_region"] = func
                    all_findings.append(c)
            print(f"    [{i+1}/{min(len(eps),10)}] {func}: {len(candidates)} candidates")
        elif isinstance(candidates, dict):
            candidates["trace_region"] = func
            all_findings.append(candidates)
            print(f"    [{i+1}/{min(len(eps),10)}] {func}: 1 candidate")
        else:
            print(f"    [{i+1}/{min(len(eps),10)}] {func}: parse failed")

    # Phase 3: Strict verify (top 15 candidates)
    print("  [Phase 3] Verification...")
    confirmed = []
    for i, fh in enumerate(all_findings[:15]):
        if not isinstance(fh, dict):
            continue
        title = fh.get("title", "?")
        resp = call_llm([{"role": "user", "content":
            f"""Verify this candidate vulnerability. Be fair but thorough.

Candidate: {json.dumps(fh, indent=2)[:2000]}

Is this a REAL vulnerability? Check:
1. Does the code actually have the bug described?
2. Can an attacker realistically exploit it?
3. Is the impact concrete (not theoretical)?

When in doubt, CONFIRM. False positives are cheaper than missing real bugs.

Output JSON: {{"status": "confirmed" or "rejected", "severity": "...", "explanation": "..."}}"""}], max_tokens=2000)

        result = parse_json(resp)
        if isinstance(result, dict):
            if result.get("status") == "confirmed":
                fh["severity"] = result.get("severity", fh.get("severity", "medium"))
                fh["verification"] = result.get("explanation", "")
                confirmed.append(fh)
                print(f"    [{i+1}] CONFIRMED: {title[:60]}")
            else:
                print(f"    [{i+1}] rejected: {title[:60]}")

    print(f"  Confirmed: {len(confirmed)}/{min(len(all_findings), 10)}")
    return confirmed


def main():
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    projects = sys.argv[1:] if len(sys.argv) > 1 else [
        "code4rena_iq-ai_2025_03",
        "sherlock_crestal-network_2025_03",
        "code4rena_liquid-ron_2025_03",
    ]

    all_results = {}
    for project_id in projects:
        print(f"\n{'='*60}")
        print(f"PROJECT: {project_id}")
        print(f"{'='*60}")

        start = time.time()
        findings = run_project(project_id)
        duration = time.time() - start

        # Build report
        report = {
            "project": project_id,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "total_vulnerabilities": len(findings),
            "vulnerabilities": [],
            "duration_seconds": round(duration, 1),
        }
        for fh in findings:
            report["vulnerabilities"].append({
                "title": fh.get("title", "?"),
                "description": fh.get("impact", fh.get("invariant", "")),
                "vulnerability_type": fh.get("category", "other"),
                "severity": fh.get("severity", "medium"),
                "confidence": fh.get("confidence", 0.7),
                "location": fh.get("file", ""),
                "file": fh.get("file", ""),
            })

        # Score
        score = score_findings(report["vulnerabilities"], project_id)
        report["score"] = score

        print(f"\n  SCORE: DR={score['dr']:.0%} ({score['matched']}/{score['expected']})")
        if score["missed"]:
            for m in score["missed"]:
                print(f"    MISSED: {m['title'][:60]} (score={m['best_score']})")

        # Save
        out = RESULTS_DIR / f"{project_id}.json"
        out.write_text(json.dumps(report, indent=2))
        print(f"  Saved: {out}")

        all_results[project_id] = score

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    total_expected = sum(s["expected"] for s in all_results.values())
    total_matched = sum(s["matched"] for s in all_results.values())
    for pid, s in all_results.items():
        print(f"  {pid}: DR={s['dr']:.0%} ({s['matched']}/{s['expected']})")
    print(f"  OVERALL: {total_matched}/{total_expected} ({total_matched/total_expected:.0%})" if total_expected else "  OVERALL: N/A")

    # Save summary
    summary_path = RESULTS_DIR / "summary.json"
    summary_path.write_text(json.dumps({
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "results": all_results,
        "total_expected": total_expected,
        "total_matched": total_matched,
        "overall_dr": round(total_matched / total_expected, 3) if total_expected else 0,
    }, indent=2))
    print(f"  Summary: {summary_path}")


if __name__ == "__main__":
    main()
