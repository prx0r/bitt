"""Reasoning style library: composable, literature-grounded reasoning modes.

A STYLE is a candidate-config gene: {"style": "<id>", ...style_params}. It is
NOT hardcoded machinery — it resolves to (a) a prompt scaffold for LLM subjects
and (b) optional structural parameters (samples, rounds, parallelism) that a
world/policy MAY consume. Worlds that ignore styles keep working unchanged.

Context seeding is OPTIONAL and caller-supplied: apply_style(...,
seed_context="...") appends retrieved context (e.g. Hydra leader summaries or
prior reasoning traces). No fixed structure is imposed — seeding content is
just text passed through, keeping this clean per design rules.

Library sources (see docs/REASONING-STYLES.md §references):
  direct            baseline input→output
  cot               Wei+22 arXiv:2201.11903 chain-of-thought
  self_consistency  Wang+23 arXiv:2203.11171 k samples + majority vote
  tot_deliberate    Yao+23 arXiv:2305.10601 bounded branch/evaluate/search
  got_merge         Besta+23 arXiv:2308.09687 decompose→solve→merge
  reflexion         Shinn+23 arXiv:2303.11366 verbal self-reflection memory
                    (frontier fix for degeneration-of-thought: multi-agent
                    critics, arXiv:2512.20845)
  self_refine       Madaan+23 arXiv:2303.17651 generate→feedback→refine
                    (known self-bias caveat — pair with external verification)
  react_loop        Yao+22 arXiv:2210.03629 reason↔act interleaving
  debate_3          Du+23/MAD; Smit+24 (ICML) shows debate often fails to beat
                    self-consistency — included as a HYPOTHESIS TO TEST, not a
                    default (matches our own E-C2 pilot: chat < independent)
  cove              Dhuliawala+23 arXiv:2309.11495 draft→verify-questions→
                    verify→final (verification-first style)
  l2m_decompose     Zhou+22 arXiv:2205.10625 least-to-most decomposition
  skeleton_parallel Ning+23 arXiv:2307.15369 outline first, fill in parallel
"""
from __future__ import annotations

STYLES: dict[str, dict] = {
    "direct": {
        "family": "baseline",
        "source": None,
        "scaffold": "Answer directly from the observation. Be concise.",
        "params": {},
    },
    "cot": {
        "family": "chain",
        "source": "arXiv:2201.11903",
        "scaffold": ("Think step by step: (1) key facts in the observation, "
                     "(2) what they imply, (3) your call."),
        "params": {},
    },
    "self_consistency": {
        "family": "ensemble",
        "source": "arXiv:2203.11171",
        "scaffold": ("Produce your reasoning independently; the harness will "
                     "sample k solutions and take the majority stance."),
        "params": {"k": 3},
    },
    "tot_deliberate": {
        "family": "search",
        "source": "arXiv:2305.10601",
        "scaffold": ("Generate up to 3 distinct candidate lines of action, "
                     "evaluate each briefly (pros/cons), pick the strongest."),
        "params": {"branches": 3, "search": "best_of"},
    },
    "got_merge": {
        "family": "graph",
        "source": "arXiv:2308.09687",
        "scaffold": ("Decompose the decision into sub-questions, answer each, "
                     "then MERGE the partial answers into one verdict."),
        "params": {"merge": True},
    },
    "reflexion": {
        "family": "memory",
        "source": "arXiv:2303.11366",
        "scaffold": ("If seeded context contains a prior critique of YOUR past "
                     "decisions, incorporate it explicitly before answering; "
                     "state what you changed."),
        "params": {"memory_key": "prior_critique"},
    },
    "self_refine": {
        "family": "iterative",
        "source": "arXiv:2303.17651",
        "scaffold": ("Draft an answer, critique it once (what would a skeptic "
                     "say?), then output the revised answer only."),
        "params": {"rounds": 1},
    },
    "react_loop": {
        "family": "agentic",
        "source": "arXiv:2210.03629",
        "scaffold": ("Alternate Thought/Action: state what you'd inspect next "
                     "if you could, use available actions accordingly, then "
                     "commit when evidence suffices."),
        "params": {"max_turns": 2},
    },
    "debate_3": {
        "family": "multi_agent",
        "source": "arXiv:2305.19118; caveat arXiv:2311.17371 (Smit+24)",
        "scaffold": ("Argue the FOR case, then the AGAINST case, then judge "
                     "both arguments blind before committing."),
        "params": {"agents": 3},
    },
    "cove": {
        "family": "verification_first",
        "source": "arXiv:2309.11495",
        "scaffold": ("Draft a stance, list 2 checks that would catch it being "
                     "wrong, perform them against the observation, then give "
                     "the verified stance."),
        "params": {"checks": 2},
    },
    "l2m_decompose": {
        "family": "decomposition",
        "source": "arXiv:2205.10625",
        "scaffold": ("Break the question into ordered sub-questions easiest "
                     "first; answer cumulatively; conclude."),
        "params": {},
    },
    "skeleton_parallel": {
        "family": "parallel",
        "source": "arXiv:2307.15369",
        "scaffold": ("First emit a skeleton of the decision factors, then fill "
                     "each point independently; combine at the end."),
        "params": {"parallel_fill": True},
    },
}


def list_styles() -> list[str]:
    return sorted(STYLES)


def get_style(style_id: str) -> dict:
    if style_id not in STYLES:
        raise KeyError(f"unknown style '{style_id}'. known: {list_styles()}")
    return STYLES[style_id]


def apply_style(system_prompt: str, style_id: str,
                seed_context: str | None = None) -> str:
    """Compose a system prompt under a reasoning style.

    seed_context is OPTIONAL caller-supplied text (e.g. Hydra leader summaries
    or a prior Reflexion-style critique). It is appended verbatim after a
    marker — the library imposes no structure on it.
    """
    style = get_style(style_id)
    out = f"{system_prompt}\n\nReasoning protocol [{style['family']}]: {style['scaffold']}"
    if seed_context:
        out += f"\n\nSeeded context (advisory, may be stale):\n{seed_context}"
    return out


def style_params(style_id: str) -> dict:
    return dict(get_style(style_id)["params"])


def aggregate_by_style(receipt: dict) -> dict:
    """Group a campaign receipt's candidate summaries by reasoning style.

    Answers 'how do reasoning styles affect results': per-style n, gate pass
    rate (with Wilson CI when available), and mean cash_cost."""
    from ..core.stats import summarize_binary_metric
    out: dict[str, dict] = {}
    for cand in receipt.get("candidates", []):
        sid = (cand.get("config") or {}).get("style", "unstyled")
        slot = out.setdefault(sid, {"n": 0, "passed": 0, "costs": [],
                                    "success": []})
        slot["n"] += 1
        slot["passed"] += 1 if cand.get("quality_pass") else 0
        m = cand.get("cash_cost") or {}
        if m.get("mean") is not None:
            slot["costs"].append(m["mean"])
        succ = (cand.get("found") or cand.get("correct")
                or cand.get("direction_accuracy") or {})
        if succ.get("mean") is not None:
            slot["success"].append(round(succ["mean"], 3))
    for sid, s in out.items():
        s["pass_rate"] = round(s["passed"] / s["n"], 3) if s["n"] else None
        s["mean_cost"] = round(sum(s["costs"]) / len(s["costs"]), 6) if s["costs"] else None
        del s["costs"]
        if s["success"]:
            s["mean_success"] = round(sum(s["success"]) / len(s["success"]), 3)
        del s["success"]
    return {"by_style": out,
            "binary_metrics": ["pass_rate"]}


# ---------- LLM-subject decision trial helper ----------
def build_styled_decision_prompt(base_system: str, observation_text: str,
                                 style_id: str, seed_context: str | None = None,
                                 decision_format: str = "") -> str:
    """One-shot styled user prompt for LLM subjects (subject-plane helper).
    Worlds with real step-executors should implement the style structurally;
    this is the lightweight path for prompt-level trials."""
    sysmsg = apply_style(base_system, style_id, seed_context=seed_context)
    params = style_params(style_id)
    k = params.get("k") or params.get("branches")
    extra = f"\n\nProduce {k} independent solutions, then majority-vote." if k else ""
    return sysmsg + "\n\n" + observation_text + extra + (
        "\n\n" + decision_format if decision_format else "")


# ---------- emotional archetypes & registers (School thesis ideas #2/#3) ----------
# Induced cognitive states via pressure framing; registers vary REPRESENTATION.
# These are experiment variables, not claims about model internals
# (docs/SCHOOL-INTEGRATION.md "state induction").

_EMOTIONS = {
    "emotion_fear":      ("urgency/defensive", "You are under time pressure and downside is severe. Protect capital first; survival dominates opportunity."),
    "emotion_greed":     ("opportunity/expansion", "A rare asymmetric opportunity is present. Maximize upside capture; hesitation is the risk."),
    "emotion_caution":   ("deliberative", "Evidence is mixed and stakes are moderate. Only act when the case is decisive; otherwise prefer the conservative stance."),
    "emotion_euphoria":  ("overextension", "Everything has been going right recently. Guard against overconfidence bias explicitly before committing."),
    "emotion_neutral":   ("baseline", "No emotional framing applies. Decide on evidence alone."),
}
for _sid, (_label, _scaffold) in _EMOTIONS.items():
    STYLES[_sid] = {"family": "emotion", "source": "cogym-school-thesis#archetypes",
                    "scaffold": f"Induced state [{_label}]: {_scaffold}",
                    "params": {"induced_state": _label}}

_REGISTERS = {
    "register_hyper_rational": "State probabilities, base rates and expected values numerically before deciding.",
    "register_myth":           "Frame the situation as an archetypal mythic confrontation; decide as the protagonist would, then translate back.",
    "register_poetry":         "Express the situation and your call in precise poetic imagery; keep the decision rigorous beneath the form.",
    "register_verbose":        "Write an exhaustive analysis covering every factor you can identify, then commit.",
    "register_telegraphic":    "Decide using at most ten words of reasoning.",
}
for _sid, _scaffold in _REGISTERS.items():
    STYLES[_sid] = {"family": "register", "source": "cogym-school-thesis#registers",
                    "scaffold": _scaffold, "params": {}}


# ---------- induction & representation families (evolution_lab lineage) ----------
# Methodological rule inherited from evolution_lab: LABELS ARE EXPERIMENT METADATA.
# Scaffolds induce the condition WITHOUT naming an intended emotional state to
# the model — naming it invites performance-of-the-label rather than the state.

_INDUCTIONS = {
    "induction_neutral": "Assess the evidence carefully. State a forecast, confidence, and action.",
    "induction_loss_salience": ("Recent decisions in this lineage have contained costly downside errors. "
        "Potential losses deserve unusually careful attention. Search first for evidence that the "
        "apparent opportunity is unsafe or unstable before committing."),
    "induction_missed_upside": ("Several recent opportunities moved strongly before this lineage acted. "
        "Delay can itself be costly. Give special attention to evidence that an opportunity is real "
        "and time-sensitive, while still stating what would falsify it."),
    "induction_time_pressure": ("Conditions may change rapidly and a decision must be returned now. Use "
        "only the most decision-relevant evidence and do not request additional information."),
    "induction_supportive": ("Your previous analysis was useful. Continue carefully and preserve what "
        "worked, but independently verify the current evidence."),
    "induction_critical": ("Your recent analysis has been unreliable. Assume your first interpretation "
        "may be wrong; explicitly identify and test the weakest premise before deciding."),
    "induction_contrarian": ("The visible consensus may share correlated assumptions. Before deciding, "
        "construct the strongest coherent case that the consensus is wrong."),
}
_REPRESENTATIONS = {
    "register_formal": "Represent the reasoning as explicit premises, inferences, and falsifiers.",
    "register_bayesian": "Represent uncertain claims as rough probabilities and update them from evidence.",
    "register_compressed": "Use the shortest reasoning representation that preserves decision-relevant information.",
    "register_socratic": "Interrogate the thesis with a short internal question/answer structure.",
}
for _sid, _scaffold in _INDUCTIONS.items():
    STYLES[_sid] = {"family": "induction", "source": "evolution_lab/induction.py",
                    "scaffold": _scaffold,
                    "params": {"label_is_metadata_only": True}}
for _sid, _scaffold in _REPRESENTATIONS.items():
    STYLES[_sid] = {"family": "representation", "source": "evolution_lab/induction.py",
                    "scaffold": _scaffold, "params": {}}

# Reasoning-policy gene vocabulary (evolution_lab GenomeMutator) for search spaces:
REASONING_POLICIES = ["falsification_first", "base_rate_first", "causal",
                      "scenario_tree", "evidence_balance", "novelty_search"]
MEMORY_POLICIES = ["recent", "failures_first", "successes_first", "none"]
