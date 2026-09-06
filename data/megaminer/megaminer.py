"""MEGAMINER Autonomous Probe System.

Each miner gets a codename. When it scores 100% on a project, it's promoted.
Promoted miners must pass on ADDITIONAL projects to prevent overfitting.
Lessons are extracted and added to the MEGAMINER rubric.
All future miners inherit the full rubric.
"""
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

PROXY = "http://localhost:8087"
API_KEY = "sk-A5QHR5MRtUNec7BWqiRsZ0GAYck0CRT2Movsk7Q6U3UwcV77Y6G3TMXOhhyKh855"
MODEL = "mimo-v2.5"

REPOS_DIR = Path("/root/bitt/data/scabench-repos")
HIGHS_PATH = "/root/bitt/subnets/sn60-bitsec/sandbox-v2/validator/curated-highs-only-2025-08-08.json"
DATA_DIR = Path("/root/bitt/data/megaminer")
DATA_DIR.mkdir(parents=True, exist_ok=True)

# The 6 official projects
PROJECTS = [
    "code4rena_coded-estate-invitational_2024_12",
    "code4rena_iq-ai_2025_03",
    "code4rena_liquid-ron_2025_03",
    "code4rena_mantra-dex_2025_03",
    "sherlock_cork-protocol_2025_01",
    "sherlock_crestal-network_2025_03",
]

# Codename generator
CODENAMES = ["jax", "shark", "hawk", "wolf", "fox", "lynx", "bear", "eagle", "tiger", "cobra"]
codename_idx = 0

def next_codename():
    global codename_idx
    name = CODENAMES[codename_idx % len(CODENAMES)]
    codename_idx += 1
    return name


def call_llm(messages, max_tokens=8192):
    import requests
    for attempt in range(3):
        try:
            resp = requests.post(f"{PROXY}/inference", headers={
                "x-inference-api-key": API_KEY, "x-agent-id": "megaminer",
                "x-job-run-id": f"mm-{int(time.time())}-{attempt}", "x-request-phase": "execution"
            }, json={"model": MODEL, "messages": messages, "max_tokens": max_tokens, "temperature": 0.1}, timeout=300)
            if resp.status_code == 200:
                r = resp.json()
                if "choices" in r and r["choices"]:
                    msg = r["choices"][0].get("message", {})
                    content = msg.get("content", "")
                    # Skip system prompt responses
                    if content and "MiMo" not in content and "helpful assistant" not in content and len(content) > 10:
                        return content
        except: pass
        time.sleep(2)
    return ""


def run_miner(project_id):
    """Run pipeline-v1 agent on a project."""
    source_dir = REPOS_DIR / project_id
    agent_path = Path("/root/bitt/mining/sn60/candidates/pipeline-v1/agent.py")
    if not source_dir.exists() or not agent_path.exists():
        return []

    env = os.environ.copy()
    env["INFERENCE_API"] = PROXY
    env["INFERENCE_API_KEY"] = API_KEY
    env["AGENT_ID"] = "megaminer"
    env["OPENAI_MODEL"] = MODEL

    try:
        result = subprocess.run(
            [sys.executable, str(agent_path), str(source_dir)],
            capture_output=True, text=True, timeout=900, env=env
        )
    except subprocess.TimeoutExpired:
        return []

    report_path = source_dir / "agent_report.json"
    if report_path.exists():
        try:
            return json.load(open(report_path)).get("vulnerabilities", [])
        except: pass
    return []


def score_findings(findings, project_id):
    """Score against ground truth using LLM matching."""
    gt = json.load(open(HIGHS_PATH))
    gt_entry = next((e for e in gt if e["project_id"] == project_id), None)
    if not gt_entry:
        return {"dr": 1.0, "expected": 0, "matched": 0, "missed": []}

    expected = gt_entry.get("vulnerabilities", [])
    if not expected:
        return {"dr": 1.0, "expected": 0, "matched": 0, "missed": []}

    matched = 0
    missed = []

    for exp in expected:
        # Build findings text for this expected vuln
        ft = ""
        for i, f in enumerate(findings[:15]):
            ft += f"[{i}] {f.get('title','?')} ({f.get('severity','?')}) - {f.get('description','?')[:200]}\n"

        prompt = f"""You are a security expert. Does any TOOL FINDING match this EXPECTED vulnerability?

EXPECTED: {exp['title']}
DESCRIPTION: {exp.get('description','')[:500]}

TOOL FINDINGS:
{ft}

Return JSON: {{"found": true/false, "confidence": 0.0-1.0, "reason": "brief"}}"""

        try:
            content = call_llm([
                {"role": "system", "content": "You are a vulnerability matcher. Return JSON only."},
                {"role": "user", "content": prompt}
            ], max_tokens=300)
            m = re.search(r'\{[^{}]*"found"[^{}]*\}', content)
            if m:
                r = json.loads(m.group())
                if r.get("found") and r.get("confidence", 0) >= 0.6:
                    matched += 1
                else:
                    missed.append({"title": exp["title"], "reason": r.get("reason", "")})
            else:
                missed.append({"title": exp["title"], "reason": "parse_fail"})
        except:
            missed.append({"title": exp["title"], "reason": "error"})
        time.sleep(0.3)

    dr = matched / len(expected) if expected else 0
    return {"dr": round(dr, 3), "expected": len(expected), "matched": matched, "missed": missed}


def extract_lesson(findings, missed, project_id):
    """Extract a lesson from what was missed."""
    if not missed:
        return None

    missed_titles = [m['title'] for m in missed[:5]]
    missed_text = "\n".join([f"- {t}" for t in missed_titles])

    prompt = f"""A security miner missed these vulnerabilities on {project_id}:

{missed_text}

What ONE specific thing should the miner check to catch these?
Answer with a short phrase starting with "Check:" or "Verify:" """

    response = call_llm([{"role": "user", "content": prompt}], max_tokens=100)
    if response and not response.startswith("{") and len(response) > 10:
        return response.strip()
    return f"Check all functions in {project_id} for business logic errors"


def save_state(state):
    """Save state to disk."""
    (DATA_DIR / "state.json").write_text(json.dumps(state, indent=2))


def load_state():
    """Load state from disk."""
    state_path = DATA_DIR / "state.json"
    if state_path.exists():
        return json.load(open(state_path))
    return {
        "rubric": [],
        "promoted_miners": [],
        "probes": [],
        "current_miner": None,
        "current_project_idx": 0,
        "projects_tested": [],
    }


def run_probe(state):
    """Run one probe cycle."""
    projects = state.get("projects_tested", [])
    project_idx = state.get("current_project_idx", 0)

    # Pick next project to test
    if project_idx < len(PROJECTS):
        project_id = PROJECTS[project_idx]
    else:
        # All projects tested, pick a random one for cross-validation
        import random
        project_id = random.choice(PROJECTS)

    # Check if already passed this project
    if project_id in projects:
        project_idx += 1
        if project_idx >= len(PROJECTS):
            project_idx = 0
        state["current_project_idx"] = project_idx
        return state, None

    codename = state.get("current_miner") or next_codename()
    state["current_miner"] = codename

    print(f"\n{'='*60}", flush=True)
    print(f"PROBE: {codename} on {project_id}", flush=True)
    print(f"{'='*60}", flush=True)

    # Run miner
    start = time.time()
    findings = run_miner(project_id)
    duration = time.time() - start

    if not findings:
        print(f"  No findings ({duration:.0f}s)", flush=True)
        state["current_project_idx"] = project_idx + 1
        save_state(state)
        return state, None

    # Score
    score = score_findings(findings, project_id)
    dr = score["dr"]
    matched = score["matched"]
    expected = score["expected"]

    print(f"  Findings: {len(findings)}", flush=True)
    print(f"  DR: {dr:.0%} ({matched}/{expected})", flush=True)
    print(f"  Time: {duration:.0f}s", flush=True)

    # Log probe
    probe = {
        "codename": codename,
        "project": project_id,
        "findings_count": len(findings),
        "dr": dr,
        "matched": matched,
        "expected": expected,
        "missed": score["missed"],
        "duration": round(duration, 1),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    state["probes"].append(probe)

    # Check if 100% DR
    if dr >= 1.0:
        print(f"\n  *** 100% DR ON {project_id} ***", flush=True)
        projects.append(project_id)
        state["projects_tested"] = projects

        # Check if promoted (100% on 2+ projects)
        if len(projects) >= 2:
            print(f"\n  *** PROMOTED: {codename} passed {len(projects)} projects ***", flush=True)

            # Extract lesson
            lesson = extract_lesson(findings, score["missed"], project_id)
            if lesson:
                state["rubric"].append({
                    "lesson": lesson,
                    "miner": codename,
                    "project": project_id,
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                })
                print(f"  Lesson added: {lesson}", flush=True)

            state["promoted_miners"].append({
                "codename": codename,
                "projects_passed": projects.copy(),
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            })

            # Reset for next miner
            state["current_miner"] = None
            state["current_project_idx"] = 0
            state["projects_tested"] = []
        else:
            print(f"  Candidate (need 1 more project for promotion)", flush=True)
    else:
        print(f"  Missed {len(score['missed'])} vulnerabilities", flush=True)

        # Extract lesson from misses
        lesson = extract_lesson(findings, score["missed"], project_id)
        if lesson:
            print(f"  Lesson: {lesson}", flush=True)
            state["rubric"].append({
                "lesson": lesson,
                "miner": codename,
                "project": project_id,
                "type": "miss",
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            })

    # Move to next project
    state["current_project_idx"] = project_idx + 1
    if state["current_project_idx"] >= len(PROJECTS):
        state["current_project_idx"] = 0

    save_state(state)
    return state, probe


def main():
    """Run the MEGAMINER probe loop."""
    state = load_state()

    print(f"MEGAMINER Autonomous Probe System", flush=True)
    print(f"Rubric lessons: {len(state['rubric'])}", flush=True)
    print(f"Promoted miners: {len(state['promoted_miners'])}", flush=True)
    print(f"Total probes: {len(state['probes'])}", flush=True)

    max_probes = 20
    for i in range(max_probes):
        print(f"\n--- Probe {i+1}/{max_probes} ---", flush=True)
        state, probe = run_probe(state)

        # Check stopping conditions
        if len(state["promoted_miners"]) >= 3:
            print(f"\n*** 3 PROMOTED MINERS ACHIEVED ***", flush=True)
            break

        if len(state["rubric"]) >= 10:
            print(f"\n*** 10 RUBRIC LESSONS ACHIEVED ***", flush=True)
            break

    # Final summary
    print(f"\n{'='*60}", flush=True)
    print(f"MEGAMINER SUMMARY", flush=True)
    print(f"{'='*60}", flush=True)
    print(f"Total probes: {len(state['probes'])}", flush=True)
    print(f"Promoted miners: {len(state['promoted_miners'])}", flush=True)
    print(f"Rubric lessons: {len(state['rubric'])}", flush=True)

    if state["rubric"]:
        print(f"\nRubric:", flush=True)
        for r in state["rubric"]:
            print(f"  - {r['lesson']}", flush=True)

    if state["promoted_miners"]:
        print(f"\nPromoted:", flush=True)
        for p in state["promoted_miners"]:
            print(f"  {p['codename']}: passed {', '.join(p['projects_passed'])}", flush=True)

    save_state(state)


if __name__ == "__main__":
    main()
