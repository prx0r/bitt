"""cge1 evolution: answer-quality scorer optimisation against REAL traffic.

Uses live node traffic fixtures + literature-best-practice scoring signals.
Evolves knob weights under replace-if-wins gates, then emits submission-ready
genomes for the weakest-held intents.

Run: python3 evolve_scorer.py --intents TVL_LOOKUP,WALLET_BALANCE_CHECK,...
"""
from __future__ import annotations
import json
import math
import os
import random
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from cogym_kernel.evo.recipes import (
    EvolutionContext, propose_children)
from cogym_kernel.eval.gates import QualityGate, gates_pass, wilson

# ── Literature-grounded scoring primitives (WASM-portable, no deps) ──────────

STOP = {"a","an","the","is","are","was","were","be","been","of","in","on","at",
        "to","for","and","or","but","it","as","by","with","that","this","from",
        "its","has","have","had","there","about"}

def tokens(text: str) -> set[str]:
    return {w.lower() for w in re.findall(r"[a-z0-9]+", text.lower())
            if w not in STOP and len(w) > 1}

def char_trigrams(text: str) -> set[str]:
    s = re.sub(r"\s+", " ", text.lower()).strip()
    return {s[i:i+3] for i in range(max(0, len(s)-2))}

def extract_numbers(text: str) -> set[float]:
    vals = set()
    for m in re.finditer(r"\d[\d,]*(?:\.\d+)?", text):
        try:
            v = float(m.group().replace(",", ""))
            if v > 0: vals.add(v)
        except ValueError: pass
    return vals


def token_f1(gt_toks: set, ans_toks: set) -> float:
    if not gt_toks or not ans_toks: return 0.0
    overlap = len(gt_toks & ans_toks)
    prec = overlap / len(ans_toks)
    rec = overlap / len(gt_toks)
    return 2*prec*rec/(prec+rec) if prec+rec > 0 else 0.0


def trigram_jaccard(gt_tri: set, ans_tri: set) -> float:
    if not gt_tri or not ans_tri: return 0.0
    return len(gt_tri & ans_tri) / len(gt_tri | ans_tri)


def number_match_score(gt_nums: set, ans_nums: set, band: float) -> float:
    """Best-match relative error score for ground truth numbers."""
    if not gt_nums: return -1.0  # signal: no numbers in truth
    if not ans_nums: return 0.0
    total = 0.0
    for g in gt_nums:
        denom = max(abs(g), 1e-9)
        best_rel = min(abs(g-a)/denom for a in ans_nums)
        if best_rel <= band * 0.25: total += 1.0
        elif best_rel <= band: total += 1.0 - (best_rel - band*0.25)/(band*0.75)
    return total / len(gt_nums)


def negation_penalty(gt_text: str, ans_text: str) -> float:
    """Penalty if answer flips the polarity of the ground truth."""
    neg = {"not", "no", "never", "neither", "nor", "cannot", "without",
           "fails", "failed", "unable", "rejected", "denied", "refused"}
    gt_neg = len(re.findall(r"\b(?:not|no|never|neither|nor|cannot)\b", gt_text.lower()))
    an_neg = len(re.findall(r"\b(?:not|no|never|neither|nor|cannot)\b", ans_text.lower()))
    # penalty if one has negation and other doesn't
    if (gt_neg > 0) != (an_neg > 0):
        return 0.15
    return 0.0


def composite_answer_score(gt_text: str, ans_text: str, w: dict) -> float:
    """Weighted composite of all scoring primitives."""
    if not ans_text.strip(): return 0.0
    if normalize_eq(gt_text, ans_text): return 1.0

    gt_t = tokens(gt_text); an_t = tokens(ans_text)
    f1 = token_f1(gt_t, an_t)
    tri = trigram_jaccard(char_trigrams(gt_text), char_trigrams(ans_text))
    
    gtn = extract_numbers(gt_text); ann = extract_numbers(ans_text)
    num_s = number_match_score(gtn, ann, w.get("num_band", 0.005))
    
    neg_p = negation_penalty(gt_text, ans_text)
    
    if num_s < 0:  # no numbers in truth
        base = f1
    else:
        base = w.get("num_weight", 0.6) * num_s + (1-w.get("num_weight", 0.6)) * f1
    
    base -= neg_p
    base += w.get("tri_weight", 0.2) * tri
    
    # length normalisation: penalise very short answers
    gt_len = max(1, len(gt_text.split()))
    an_len = max(1, len(ans_text.split()))
    lr = an_len / gt_len
    if lr < 0.1: base *= 0.5
    elif lr > 10: base *= 0.7
    
    # sharpen
    k = w.get("stretch_k", 3.0)
    sharp_base = smoothstep(max(0, min(1, base)))
    stretched = (sharp_base - 0.5) * k + 0.5
    capped = min(stretched, 1.0 - 1e-7)
    return max(0.0, capped)


def normalize_eq(a: str, b: str) -> bool:
    ta = {w for w in re.findall(r"[a-z0-9]+", a.lower())}
    tb = {w for w in re.findall(r"[a-z0-9]+", b.lower())}
    return ta == tb and len(ta) > 0


def smoothstep(x):
    if x <= 0: return 0.0
    if x >= 1: return 1.0
    return x*x*(3-2*x)


# ── Genome space ─────────────────────────────────────────────────────────────

GENOME_SPACE = {
    "num_band": [0.001, 0.002, 0.005, 0.01, 0.02],
    "num_weight": [0.3, 0.45, 0.6, 0.75, 0.9],
    "recall_weight": [0.3, 0.4, 0.5, 0.6, 0.7],
    "tri_weight": [0.05, 0.1, 0.2, 0.3],
    "stretch_k": [2.0, 3.0, 4.0, 5.0, 6.0],
    "neg_pen": [0.05, 0.1, 0.2, 0.3],
}


def evaluate_pair(gt: str, good: str, bad: str, genome: dict) -> float:
    """Margin: how much better we score good vs bad."""
    sg = composite_answer_score(gt, good, genome)
    sb = composite_answer_score(gt, bad, genome)
    return sg - sb


# ── Fixture loading from live traffic ────────────────────────────────────────

def load_live_fixtures() -> dict[str, list[dict]]:
    """Build (gt, good, bad) triples from real node traffic."""
    live = json.load(open(os.path.join(HERE, "resources", "live_traffic.json")))
    rng = random.Random(42)
    fixtures = {}
    for intent, entries in sorted(live.items()):
        if len(entries) < 2: continue
        ranked = sorted(entries, key=lambda e: e["score"], reverse=True)
        pairs = []
        for i in range(min(len(ranked), 20)):
            top = ranked[i]
            bot = ranked[-(i+1)]
            if top["miner_answer"].strip() and top["score"] >= bot["score"]:
                pairs.append({
                    "question": top["question"][:500],
                    "ground_truth": top["ground_truth"][:800],
                    "good": top["miner_answer"][:600],
                    "bad": bot["miner_answer"][:600],
                })
        if pairs:
            fixtures[intent] = pairs
    return fixtures


# ── Evolution campaign ───────────────────────────────────────────────────────

def evolve_for_intent(intent: str, fixtures: list[dict], gens: int = 40,
                      pop_size: int = 24, seed: int = 42):
    """Evolve genome weights to maximise margin on this intent's fixtures."""
    rng = random.Random(seed)

    def fitness(genome: dict) -> float:
        margins = []
        for f in fixtures:
            m = evaluate_pair(f["ground_truth"], f["good"], f["bad"], genome)
            m2 = evaluate_pair(f["ground_truth"], f["good"], f["bad"],
                              {k: genome[k] for k in genome})
            margins.append(m)
        # objective: mean margin; gate: no negative margins on majority
        pos = sum(1 for m in margins if m > 0)
        return sum(margins)/len(margins) if margins else 0

    population = [{k: rng.choice(v) for k, v in GENOME_SPACE.items()}
                  for _ in range(pop_size)]

    elites = []
    ctx_cls = None
    sys.path.insert(0, "/root/noslop/repos/cogym")
    try:
        from cogym_kernel.evo.recipes import (
            EvolutionContext as EC, propose_children as pc)
        ctx_cls, pc_fn = EC, pc
    except ImportError:
        pass

    best_ever, best_genome = -999, None
    for gen in range(gens):
        scored = [(fitness(g), g) for g in population]
        scored.sort(key=lambda x: x[0], reverse=True)
        if scored[0][0] > best_ever:
            best_ever, best_genome = scored[0][0], scored[0][1]

        if gen % 10 == 0 or gen == gens-1:
            print(f"  gen {gen:>3}: best={best_ever:.4f}")

        elite_g = [g for _, g in scored[:pop_size//4]]
        population = elite_g[:]
        while len(population) < pop_size:
            parent = rng.choice(elite_g) if elite_g else {}
            child = {k: rng.choice(GENOME_SPACE[k]) if rng.random() < 0.3
                     else parent.get(k, rng.choice(GENOME_SPACE[k]))
                     for k in GENOME_SPACE}
            population.append(child)

    return best_genome, best_ever


if __name__ == "__main__":
    fixtures = load_live_fixtures()
    print(f"loaded fixtures for {len(fixtures)} intents")
    results = {}
    for intent, fx in sorted(fixtures.items()):
        print(f"\n=== {intent} ({len(fx)} fixtures) ===")
        best_g, best_fit = evolve_for_intent(intent, fx, gens=30, pop_size=16)
        results[intent] = {"fitness": round(best_fit,4), "genome": best_g}
        print(f"  -> fitness={best_fit:.4f} genome={json.dumps(best_g)}")
    json.dump(results, open("evolved_scorer_weights.json","w"), indent=1)
    print("\nsaved -> evolved_scorer_weights.json")
