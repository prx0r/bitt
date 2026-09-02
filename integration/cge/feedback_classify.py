"""feedback_classify.py — Rejection taxonomy + mutation prescription.

The CORE feedback mechanic: maps free-text node rejection reasons to
structured rejection classes, then prescribes targeted knob mutations
for each class. This is how learning from failure works.

Rejection classes (from NETWORK-INTEL.md):
  ordering           — good answer ranked below bad answer
  separation         — margin too low vs champion
  weak_discrimination — margin exists but not enough
  selfmatch          — scorer didn't recognize correct answer
  hash_mismatch      — WASM binary hash doesn't match registration
  structural         — binary fails basic validity checks
  real_traffic       — disagreement on live (non-synthetic) cases
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field


@dataclass
class RejectionReport:
    """Structured rejection analysis from node feedback text."""
    raw_text: str
    rejection_class: str  # ordering | separation | weak_discrimination | ...
    confidence: float     # 0.0-1.0 how sure we are about classification
    metrics: dict = field(default_factory=dict)  # extracted numeric metrics
    mutation_recipe: dict = field(default_factory=dict)  # {knob: [candidates]}
    rationale: str = ""   # human-readable explanation


# ── Rejection classifiers (ordered by specificity) ──────────────────────────

_CLASSIFIERS = [
    {
        "class": "ordering",
        "patterns": [
            r"ordered.*good.*below.*bad",
            r"ranked.*good.*answer.*above.*bad",
            r"ordering.*(\d+)\s*of\s*(\d+)",
            r"fewer fixture cases",
            r"good answer above bad one on fewer",
        ],
        "metrics_extract": [
            (r"(\d+)\s*of\s*(\d+)", "ordering_correct", "ordering_total"),
        ],
    },
    {
        "class": "separation",
        "patterns": [
            r"separation",
            r"separate.*good.*bad.*clearly",
            r"average margin.*(\d+\.?\d*)\s*vs.*champion.*(\d+\.?\d*)",
            r"margin.*too low",
        ],
        "metrics_extract": [
            (r"average margin\s*([\d.]+)\s*vs\s*champion\s*([\d.]+)", "our_margin", "champ_margin"),
            (r"your average margin\s*([\d.]+)", "our_margin"),
        ],
    },
    {
        "class": "weak_discrimination",
        "patterns": [
            r"weak.*discrimination",
            r"discrimination.*weak",
            r"margin.*narrow",
        ],
        "metrics_extract": [],
    },
    {
        "class": "selfmatch",
        "patterns": [
            r"self.?match",
            r"recognise.*known.?correct",
            r"self.*score.*low",
        ],
        "metrics_extract": [],
    },
    {
        "class": "hash_mismatch",
        "patterns": [
            r"hash.*mismatch",
            r"hash.*doesn.?t match",
            r"keccak.*mismatch",
        ],
        "metrics_extract": [],
    },
    {
        "class": "structural",
        "patterns": [
            r"structural",
            r"binary.*fail",
            r"invalid.*wasm",
            r"missing.*export",
            r"TELEGRAPH_INTENT",
        ],
        "metrics_extract": [],
    },
    {
        "class": "real_traffic",
        "patterns": [
            r"real.?traffic",
            r"live.*intent",
            r"disagreement.*live",
        ],
        "metrics_extract": [],
    },
]

# ── Mutation prescriptions per rejection class ──────────────────────────────
# These encode domain knowledge about WHAT to change when the node rejects
# for a specific reason. Each knob maps to a list of candidate values.

MUTATION_RECIPES = {
    "ordering": {
        "high_priority": {
            "M_ORDER": [0.70, 0.80, 0.85, 0.90, 0.95],
            "M_CONTRA": [0.20, 0.25, 0.30, 0.40],
            "M_TWO_FACED": [0.20, 0.25, 0.30, 0.40],
            "STEP_T": [0.20, 0.25, 0.30],
            "STEP_B": [0.001, 0.002, 0.004],
        },
        "low_priority": {
            "W_GRAM3": [0.50, 0.60, 0.70],
            "F_BETA2": [0.20, 0.25, 0.30],
            "POST_ITERS": [1, 2, 3],
        },
        "rationale": "Ordering failures mean the scorer can't tell good from bad. "
                     "Tighten ordering penalties (M_ORDER, M_CONTRA) and lower the "
                     "binary gate threshold (STEP_T).",
    },
    "separation": {
        "high_priority": {
            "STEP_T": [0.25, 0.30, 0.35],
            "SHARPEN": [0.3, 0.5, 0.7],
            "M_NUM_MATCH": [0.3, 0.4, 0.5, 0.6],
            "M_ENTITY_FIGURE": [0.7, 0.8, 0.9],
        },
        "low_priority": {
            "POST_ITERS": [2, 3, 4],
            "POST_FRAC": [0.1, 0.2, 0.3],
            "SIGK": [15.0, 20.0, 25.0],
        },
        "rationale": "Separation failures mean the scorer is right but not confident "
                     "enough. Sharpen contrast (STEP_T, SHARPEN) and boost match "
                     "signals (M_NUM_MATCH, M_ENTITY_FIGURE).",
    },
    "weak_discrimination": {
        "high_priority": {
            "STEP_T": [0.25, 0.30, 0.35],
            "SHARPEN": [0.3, 0.5, 0.7],
            "M_NUM_WRONG": [0.15, 0.20, 0.30],
            "M_NUM_MISS_BASE": [0.85, 0.90, 0.95],
        },
        "low_priority": {
            "SIGK": [15.0, 20.0, 25.0],
            "SIGC": [0.40, 0.45, 0.50],
        },
        "rationale": "Weak discrimination: margin exists but isn't enough to beat "
                     "champion. Need stronger penalties for wrong answers.",
    },
    "selfmatch": {
        "high_priority": {},
        "low_priority": {},
        "rationale": "Self-match failure is a structural bug, not a knob issue. "
                     "Check that normalize_eq works correctly.",
    },
    "hash_mismatch": {
        "high_priority": {},
        "low_priority": {},
        "rationale": "Hash mismatch is an infrastructure issue (R2 caching, keccak "
                     "computation). Not a genome problem.",
    },
    "structural": {
        "high_priority": {},
        "low_priority": {},
        "rationale": "Structural failure means the WASM binary is broken. Check "
                     "TELEGRAPH_INTENT export, allocator, and compilation.",
    },
    "real_traffic": {
        "high_priority": {
            "W_QA": [0.2, 0.3, 0.4, 0.5],
            "NOGT_Q": [0.5, 1.0],
            "B_AGREE": [0.05, 0.10, 0.15],
        },
        "low_priority": {
            "TIE_SRC": [0.02, 0.05, 0.10],
            "EXACT_TIE": [0.02, 0.05, 0.10],
        },
        "rationale": "Real-traffic disagreement means synthetic benchmarks don't "
                     "match live distribution. Increase QA weight and agreement bonus.",
    },
}


def classify_rejection(text: str) -> RejectionReport:
    """Classify free-text rejection reason into structured report.

    Args:
        text: The node's rejection reason string.

    Returns:
        RejectionReport with class, confidence, extracted metrics, and
        mutation recipe for the appropriate knobs.
    """
    text_lower = text.lower().strip()
    if not text_lower:
        return RejectionReport(
            raw_text=text, rejection_class="unknown", confidence=0.0,
            rationale="Empty rejection text.",
        )

    best_class = "unknown"
    best_confidence = 0.0

    for classifier in _CLASSIFIERS:
        matches = 0
        for pattern in classifier["patterns"]:
            if re.search(pattern, text_lower):
                matches += 1
        confidence = matches / len(classifier["patterns"]) if classifier["patterns"] else 0.0
        if confidence > best_confidence:
            best_confidence = confidence
            best_class = classifier["class"]

    # Extract numeric metrics
    metrics = {}
    for classifier in _CLASSIFIERS:
        if classifier["class"] != best_class:
            continue
        for pattern, *keys in classifier["metrics_extract"]:
            m = re.search(pattern, text_lower)
            if m:
                for i, key in enumerate(keys):
                    val = m.group(i + 1)
                    try:
                        metrics[key] = float(val)
                    except ValueError:
                        metrics[key] = val

    # Get mutation recipe
    recipe = MUTATION_RECIPES.get(best_class, {})
    high = recipe.get("high_priority", {})
    low = recipe.get("low_priority", {})

    # Merge into single mutation dict
    mutations = {}
    mutations.update(high)
    mutations.update(low)

    return RejectionReport(
        raw_text=text,
        rejection_class=best_class,
        confidence=best_confidence,
        metrics=metrics,
        mutation_recipe=mutations,
        rationale=recipe.get("rationale", f"Classified as {best_class}."),
    )


def prescribe_mutations(report: RejectionReport, current_genome: dict,
                        search_space: dict, rng=None) -> list[dict]:
    """Generate candidate genomes based on rejection feedback.

    Args:
        report: The rejection report from classify_rejection()
        current_genome: The genome that was rejected
        search_space: The full knob search space {knob: [candidates]}
        rng: Random state (optional)

    Returns:
        List of candidate genome dicts to try next.
    """
    import random
    rng = rng or random.Random()

    candidates = []
    recipe = report.mutation_recipe

    if not recipe:
        # No targeted mutations — do random search
        for _ in range(3):
            c = dict(current_genome)
            for k in list(search_space.keys()):
                if rng.random() < 0.3:
                    c[k] = rng.choice(search_space[k])
            candidates.append(c)
        return candidates

    # Strategy 1: mutate only high-priority knobs
    high = {k: v for k, v in recipe.items()
            if k in MUTATION_RECIPES.get(report.rejection_class, {}).get("high_priority", {})}
    if high:
        for _ in range(2):
            c = dict(current_genome)
            for k, vals in high.items():
                if k in c:
                    c[k] = rng.choice(vals)
            candidates.append(c)

    # Strategy 2: mutate high + one random low
    low = {k: v for k, v in recipe.items()
           if k not in high}
    if high and low:
        c = dict(current_genome)
        for k, vals in high.items():
            if k in c:
                c[k] = rng.choice(vals)
        # Pick one random low-priority knob
        low_k = rng.choice(list(low.keys()))
        if low_k in c:
            c[low_k] = rng.choice(low[low_k])
        candidates.append(c)

    # Strategy 3: broader exploration — mutate all recipe knobs + 20% of search space
    c = dict(current_genome)
    for k, vals in recipe.items():
        if k in c:
            c[k] = rng.choice(vals)
    for k in list(search_space.keys()):
        if k not in recipe and rng.random() < 0.2:
            c[k] = rng.choice(search_space[k])
    candidates.append(c)

    return candidates
