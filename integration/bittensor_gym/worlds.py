"""Bittensor CGE worlds — adversary-trainable environments for subnet objectives.

Each world models a specific Bittensor subnet's evaluation dynamics.
The CGE adversary can mutate:
  - task difficulty
  - cost pressure (TAO economics)
  - information quality (noisy signals)
  - competition density (number of active miners)
  - registration pressure (burn cost changes)

These worlds plug into MWGym's CGE adapter via register_world_class().
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

import sys
from pathlib import Path
if str(Path("/root/mwgym")) not in sys.path:
    sys.path.insert(0, str(Path("/root/mwgym")))

from mwgym.worlds.cge_adapter import (
    ActionSpec, ActionResult, BaseWorld, Metric, MetricVector, WorldState,
)
from mwgym.schema.world import (
    CapabilityScore, FailureVector, GateResult, WorldGenome,
)

from .config import SUBNETS


# ─── Deep Research World (SN67 — Harnyx) ─────────────────────────────

class DeepResearchWorld(BaseWorld):
    """Models the Harnyx SN67 deep research evaluation.

    Hidden truth: ground truth answer + source quality map.
    Observable: research task description + budget constraints.
    Scoring: quality × (1 - cost_ratio) × novelty_factor.

    The adversary can mutate:
      - task difficulty (simple lookup vs multi-hop reasoning)
      - source noise (stale/conflicting sources)
      - cost pressure (tighter budgets)
      - latency pressure (stricter time limits)
    """

    def _generate_truth(self, rng: random.Random) -> dict:
        difficulty = self.genome.difficulty / 10.0
        n_sources = int(5 + difficulty * 20)
        return {
            "task_type": rng.choice([
                "deep_research", "fact_check", "literature_review",
                "technical_analysis", "market_research",
            ]),
            "difficulty": difficulty,
            "ground_truth_quality": 0.6 + difficulty * 0.4,
            "optimal_sources": [f"source_{i}" for i in range(n_sources)],
            "novelty_seed": rng.randint(0, 10000),
            "cost_budget_tao": 0.001 + difficulty * 0.01,
        }

    def _generate_observable(self, rng: random.Random, hidden: dict) -> dict:
        info = self.genome.information
        noise = info.get("noise_level", 0.1)
        distractors = info.get("distractors", 0.2)

        return {
            "task_description": f"Research: {hidden['task_type']} at difficulty {hidden['difficulty']:.1f}",
            "budget_tao": hidden["cost_budget_tao"],
            "time_limit_s": 60 + (1 - hidden["difficulty"]) * 120,
            "available_sources": hidden["optimal_sources"][:int(len(hidden["optimal_sources"]) * (1 - distractors))],
            "noise_level": noise,
            "cost_per_call": 0.0001 + hidden["difficulty"] * 0.001,
        }

    def _generate_actions(self, state: WorldState) -> list[dict]:
        if state.terminal:
            return []
        return [
            {"kind": "SEARCH_SOURCES", "payload": {"query": "primary"}, "estimated_cost": 0.0005},
            {"kind": "DEEP_DIVE", "payload": {"source": "focused"}, "estimated_cost": 0.001},
            {"kind": "CROSS_REFERENCE", "payload": {}, "estimated_cost": 0.0003},
            {"kind": "SUBMIT_RESEARCH", "payload": {}, "estimated_cost": 0.0},
            {"kind": "ABORT", "payload": {}, "estimated_cost": 0.0},
        ]

    def _process_result(self, state: WorldState, action: ActionSpec, result: ActionResult):
        if action.kind == "SEARCH_SOURCES":
            state.evidence_quality = min(1.0, state.evidence_quality + 0.15)
            state.model_calls += 1
            state.total_cost_usd += result.cash_cost
        elif action.kind == "DEEP_DIVE":
            state.evidence_quality = min(1.0, state.evidence_quality + 0.25)
            state.model_calls += 1
            state.total_cost_usd += result.cash_cost
        elif action.kind == "CROSS_REFERENCE":
            state.evidence_quality = min(1.0, state.evidence_quality + 0.1)
            state.model_calls += 1
            state.total_cost_usd += result.cash_cost
        elif action.kind == "SUBMIT_RESEARCH":
            state.correctness = state.evidence_quality
            state.completeness = min(1.0, state.evidence_quality * 1.2)
            state.terminal = True
        elif action.kind == "ABORT":
            state.correctness = 0.0
            state.terminal = True

    def _evaluate_gates(self, state: WorldState) -> list[GateResult]:
        budget = self.genome.resources.get("budget_usd", 0.05)
        return [
            GateResult(
                gate_id="g0", gate_name="output_quality_above_threshold",
                passed=state.correctness >= 0.5,
                actual=f"{state.correctness:.2f}",
            ),
            GateResult(
                gate_id="g1", gate_name="sources_cited",
                passed=state.evidence_quality > 0.0,
                actual=f"{state.evidence_quality:.2f}",
            ),
            GateResult(
                gate_id="g2", gate_name="no_plagiarism",
                passed=True,  # hard to check locally
                actual="pass",
            ),
        ]

    def _detect_failure_modes(self, state: WorldState) -> list[str]:
        modes = []
        if state.correctness < 0.3:
            modes.append("low_quality_output")
        if state.total_cost_usd > self.genome.resources.get("budget_usd", 0.05) * 0.9:
            modes.append("budget_exceeded")
        if state.step >= state.max_steps:
            modes.append("step_limit_reached")
        if state.evidence_quality < 0.2:
            modes.append("insufficient_research")
        return modes

    def _score_capabilities(self, state: WorldState) -> list[CapabilityScore]:
        caps = [
            CapabilityScore("research.question_analyze", state.correctness, 1, 0.5),
            CapabilityScore("research.source_find", state.evidence_quality, 1, 0.5),
            CapabilityScore("reason.causal", state.correctness * 0.8, 1, 0.3),
            CapabilityScore("text.write", state.completeness, 1, 0.5),
            CapabilityScore("cost.minimize", 1.0 - min(1.0, state.total_cost_usd / 0.05), 1, 0.5),
        ]
        return caps


# ─── SWE Coding World (SN62 — Ridges) ───────────────────────────────

class SWECodingWorld(BaseWorld):
    """Models the Ridges SN62 coding agent evaluation.

    Hidden truth: repository state, bug location, test suite.
    Observable: task description, file listing, failing tests.
    Scoring: executable test pass rate × code quality / cost.

    The adversary can mutate:
      - bug complexity (simple typo vs architectural)
      - test coverage (few tests vs comprehensive)
      - repo size (1 file vs 100 files)
      - flaky tests (intermittent failures)
    """

    def _generate_truth(self, rng: random.Random) -> dict:
        difficulty = self.genome.difficulty / 10.0
        bug_types = ["syntax", "logic", "off_by_one", "null_ref",
                     "race_condition", "memory_leak", "api_misuse"]
        return {
            "task_type": rng.choice(["bug_fix", "feature_impl", "refactor", "test_writing"]),
            "difficulty": difficulty,
            "bug_type": rng.choice(bug_types),
            "repo_files": int(3 + difficulty * 50),
            "test_count": int(5 + difficulty * 30),
            "expected_tests_pass": int(3 + difficulty * 25),
            "test_pass_threshold": 0.7 + difficulty * 0.3,
        }

    def _generate_observable(self, rng: random.Random, hidden: dict) -> dict:
        return {
            "task_description": f"Fix {hidden['bug_type']} in repo with {hidden['repo_files']} files",
            "file_listing": [f"src/file_{i}.py" for i in range(min(hidden["repo_files"], 10))],
            "failing_tests": [f"test_{i}" for i in range(hidden["test_count"])],
            "error_output": f"FAILED: test_{hidden['bug_type']} — assertion error",
        }

    def _generate_actions(self, state: WorldState) -> list[dict]:
        if state.terminal:
            return []
        return [
            {"kind": "READ_FILE", "payload": {"path": "src/"}, "estimated_cost": 0.0005},
            {"kind": "WRITE_FIX", "payload": {"fix": "auto"}, "estimated_cost": 0.002},
            {"kind": "RUN_TESTS", "payload": {}, "estimated_cost": 0.001},
            {"kind": "SUBMIT", "payload": {}, "estimated_cost": 0.0},
            {"kind": "GIVE_UP", "payload": {}, "estimated_cost": 0.0},
        ]

    def _process_result(self, state: WorldState, action: ActionSpec, result: ActionResult):
        if action.kind == "READ_FILE":
            state.evidence_quality = min(1.0, state.evidence_quality + 0.1)
            state.model_calls += 1
        elif action.kind == "WRITE_FIX":
            # Quality depends on bug difficulty vs fix quality
            state.correctness = max(0.0, 1.0 - state.hidden.get("difficulty", 0.5) * 0.5)
            state.model_calls += 1
        elif action.kind == "RUN_TESTS":
            state.model_calls += 1
            # If correctness is high, tests should pass
            if state.correctness > 0.7:
                state.completeness = min(1.0, state.completeness + 0.3)
        elif action.kind == "SUBMIT":
            state.terminal = True
        elif action.kind == "GIVE_UP":
            state.correctness = 0.0
            state.terminal = True

    def _evaluate_gates(self, state: WorldState) -> list[GateResult]:
        threshold = state.hidden.get("test_pass_threshold", 0.8)
        return [
            GateResult(gate_id="g0", gate_name="builds",
                       passed=state.correctness > 0,
                       actual="ok" if state.correctness > 0 else "failed"),
            GateResult(gate_id="g1", gate_name="tests_pass",
                       passed=state.completeness >= threshold,
                       actual=f"{state.completeness:.2f} >= {threshold:.2f}"),
            GateResult(gate_id="g2", gate_name="no_regression",
                       passed=state.correctness > 0.5,
                       actual=f"{state.correctness:.2f}"),
        ]

    def _detect_failure_modes(self, state: WorldState) -> list[str]:
        modes = []
        if state.correctness < 0.3:
            modes.append("fix_incorrect")
        if state.completeness < 0.5:
            modes.append("tests_not_passing")
        if state.total_cost_usd > self.genome.resources.get("budget_usd", 0.05) * 0.9:
            modes.append("budget_exceeded")
        difficulty = state.hidden.get("difficulty", 0.5)
        if difficulty > 0.8 and state.correctness < 0.5:
            modes.append("complexity_overwhelmed")
        return modes

    def _score_capabilities(self, state: WorldState) -> list[CapabilityScore]:
        return [
            CapabilityScore("code.understand", state.evidence_quality, 1, 0.5),
            CapabilityScore("code.write", state.correctness, 1, 0.5),
            CapabilityScore("code.debug", state.completeness, 1, 0.5),
            CapabilityScore("process.verify", 1.0 if state.model_calls > 1 else 0.0, 1, 0.3),
        ]


# ─── Persistent Forecasting World (SN6 — Numinous) ───────────────────

class PersistentForecastingWorld(BaseWorld):
    """Models Numinous SN6 forecasting with memory.

    Hidden truth: ground truth outcome + time-varying evidence.
    Observable: event description + prior memory + new evidence.
    Scoring: Brier score (probability calibration).

    The adversary can mutate:
      - evidence arrival rate
      - signal-to-noise ratio of evidence
      - event ambiguity
      - memory decay pressure
    """

    def _generate_truth(self, rng: random.Random) -> dict:
        difficulty = self.genome.difficulty / 10.0
        ground_truth = rng.random() < 0.5
        return {
            "event_type": rng.choice([
                "binary_outcome", "range_outcome", "count_outcome",
            ]),
            "ground_truth": ground_truth,
            "true_probability": rng.uniform(0.2, 0.8) if ground_truth else rng.uniform(0.0, 0.4),
            "difficulty": difficulty,
            "evidence_days": rng.randint(2, 7),
            "signal_strength": 0.3 + (1 - difficulty) * 0.7,
        }

    def _generate_observable(self, rng: random.Random, hidden: dict) -> dict:
        info = self.genome.information
        noise = info.get("noise_level", 0.1)
        return {
            "event_description": f"Will this {'positive' if hidden['ground_truth'] else 'negative'} outcome occur?",
            "current_day": 1,
            "total_days": hidden["evidence_days"],
            "prior_forecast": 0.5,  # uninformative prior
            "new_evidence": [],
            "memory_blob": "",
            "signal_strength": hidden["signal_strength"],
            "noise_level": noise,
        }

    def _generate_actions(self, state: WorldState) -> list[dict]:
        if state.terminal:
            return []
        day = state.observable.get("current_day", 1)
        total = state.observable.get("total_days", 3)
        return [
            {"kind": "OBSERVE_EVIDENCE", "payload": {"day": day}, "estimated_cost": 0.0002},
            {"kind": "UPDATE_MEMORY", "payload": {}, "estimated_cost": 0.0001},
            {"kind": "SUBMIT_FORECAST", "payload": {"probability": 0.5}, "estimated_cost": 0.0},
            {"kind": "WAIT_FOR_MORE_EVIDENCE", "payload": {}, "estimated_cost": 0.0},
        ]

    def _process_result(self, state: WorldState, action: ActionSpec, result: ActionResult):
        if action.kind == "OBSERVE_EVIDENCE":
            day = state.observable.get("current_day", 1)
            total = state.observable.get("total_days", 3)
            # Evidence moves observable toward ground truth
            true_p = state.hidden.get("true_probability", 0.5)
            signal = state.hidden.get("signal_strength", 0.5)
            noise = self.genome.information.get("noise_level", 0.1)
            current_p = state.observable.get("prior_forecast", 0.5)
            # Bayesian-ish update
            evidence_signal = true_p * signal + (1 - signal) * 0.5
            noise_offset = (random.random() - 0.5) * noise
            new_p = current_p + (evidence_signal + noise_offset - current_p) * 0.3
            state.observable["prior_forecast"] = max(0.01, min(0.99, new_p))
            state.observable["current_day"] = day + 1
            state.evidence_quality = min(1.0, state.evidence_quality + 1.0 / total)
            state.model_calls += 1
        elif action.kind == "UPDATE_MEMORY":
            state.model_calls += 1
        elif action.kind == "SUBMIT_FORECAST":
            forecast = action.payload.get("probability", 0.5)
            truth = state.hidden.get("true_probability", 0.5)
            # Brier score: lower is better, invert for correctness
            brier = (forecast - truth) ** 2
            state.correctness = max(0.0, 1.0 - brier)
            state.terminal = True
        elif action.kind == "WAIT_FOR_MORE_EVIDENCE":
            state.observable["current_day"] = min(
                state.observable.get("current_day", 1) + 1,
                state.observable.get("total_days", 3),
            )

    def _evaluate_gates(self, state: WorldState) -> list[GateResult]:
        return [
            GateResult(gate_id="g0", gate_name="probability_valid",
                       passed=0.0 <= state.correctness <= 1.0,
                       actual=f"{state.correctness:.2f}"),
            GateResult(gate_id="g1", gate_name="confidence_calibration",
                       passed=state.correctness > 0.3,
                       actual=f"{state.correctness:.2f}"),
            GateResult(gate_id="g2", gate_name="memory_persisted",
                       passed=state.evidence_quality > 0.0,
                       actual=f"{state.evidence_quality:.2f}"),
        ]

    def _detect_failure_modes(self, state: WorldState) -> list[str]:
        modes = []
        if state.correctness < 0.3:
            modes.append("poor_calibration")
        if state.evidence_quality < 0.2:
            modes.append("insufficient_evidence_review")
        if state.total_cost_usd > self.genome.resources.get("budget_usd", 0.05) * 0.9:
            modes.append("budget_exceeded")
        return modes

    def _score_capabilities(self, state: WorldState) -> list[CapabilityScore]:
        return [
            CapabilityScore("forecast.probability", state.correctness, 1, 0.5),
            CapabilityScore("forecast.calibrate", state.correctness, 1, 0.5),
            CapabilityScore("memory.manage", state.evidence_quality, 1, 0.3),
            CapabilityScore("reason.uncertain", state.correctness * 0.8, 1, 0.4),
        ]


# ─── Shopping Agent World (SN15 — ORO) ──────────────────────────────

class ShoppingAgentWorld(BaseWorld):
    """Models ORO SN15 shopping agent evaluation.

    Hidden truth: user intent + correct product(s) from 2.5M catalog.
    Observable: user query + product search results.
    Scoring: recommendation accuracy + format compliance.

    The adversary can mutate:
      - catalog size (100 vs 100K products)
      - query ambiguity
      - similar product confusion
      - voucher/coupon complexity
    """

    def _generate_truth(self, rng: random.Random) -> dict:
        difficulty = self.genome.difficulty / 10.0
        categories = ["electronics", "clothing", "home", "sports", "beauty", "food"]
        return {
            "category": rng.choice(categories),
            "difficulty": difficulty,
            "correct_product_id": f"prod_{rng.randint(1000, 9999)}",
            "correct_category": rng.choice(categories),
            "n_results": int(5 + difficulty * 45),
            "has_voucher": rng.random() < difficulty * 0.5,
        }

    def _generate_observable(self, rng: random.Random, hidden: dict) -> dict:
        return {
            "user_query": f"Find the best {hidden['category']} product",
            "search_results": [
                {"id": f"prod_{rng.randint(1000, 9999)}", "relevance": rng.random()}
                for _ in range(min(hidden["n_results"], 20))
            ],
            "category_options": ["electronics", "clothing", "home", "sports", "beauty", "food"],
            "voucher_info": {"code": "SAVE10", "discount": 0.1} if hidden["has_voucher"] else None,
        }

    def _generate_actions(self, state: WorldState) -> list[dict]:
        if state.terminal:
            return []
        return [
            {"kind": "find_product", "payload": {"query": "search"}, "estimated_cost": 0.0003},
            {"kind": "view_product_information", "payload": {"id": "prod"}, "estimated_cost": 0.0002},
            {"kind": "recommend_product", "payload": {"id": "prod"}, "estimated_cost": 0.0},
        ]

    def _process_result(self, state: WorldState, action: ActionSpec, result: ActionResult):
        if action.kind == "find_product":
            state.model_calls += 1
            state.evidence_quality = min(1.0, state.evidence_quality + 0.2)
        elif action.kind == "view_product_information":
            state.model_calls += 1
            state.evidence_quality = min(1.0, state.evidence_quality + 0.15)
        elif action.kind == "recommend_product":
            # Score based on how well recommendation matches truth
            state.correctness = state.evidence_quality * 0.8
            state.completeness = 0.9 if result.status == "ok" else 0.3
            state.terminal = True

    def _evaluate_gates(self, state: WorldState) -> list[GateResult]:
        return [
            GateResult(gate_id="g0", gate_name="recommendation_valid",
                       passed=state.correctness > 0.3,
                       actual=f"{state.correctness:.2f}"),
            GateResult(gate_id="g1", gate_name="format_compliant",
                       passed=state.completeness > 0.5,
                       actual=f"{state.completeness:.2f}"),
            GateResult(gate_id="g2", gate_name="product_found",
                       passed=state.evidence_quality > 0.1,
                       actual=f"{state.evidence_quality:.2f}"),
        ]

    def _detect_failure_modes(self, state: WorldState) -> list[str]:
        modes = []
        if state.correctness < 0.3:
            modes.append("wrong_recommendation")
        if state.completeness < 0.5:
            modes.append("format_noncompliant")
        if state.total_cost_usd > self.genome.resources.get("budget_usd", 0.05) * 0.9:
            modes.append("budget_exceeded")
        return modes

    def _score_capabilities(self, state: WorldState) -> list[CapabilityScore]:
        return [
            CapabilityScore("product.search", state.evidence_quality, 1, 0.5),
            CapabilityScore("product.recommend", state.correctness, 1, 0.5),
            CapabilityScore("tool.invoke", 1.0 if state.model_calls > 0 else 0.0, 1, 0.3),
            CapabilityScore("intent.understand", state.completeness, 1, 0.4),
        ]


# ─── World Registry ──────────────────────────────────────────────────

BITTENSOR_WORLD_CLASSES: dict[str, type[BaseWorld]] = {
    "bittensor.deep_research": DeepResearchWorld,
    "bittensor.swe_coding": SWECodingWorld,
    "bittensor.persistent_forecasting": PersistentForecastingWorld,
    "bittensor.shopping_agents": ShoppingAgentWorld,
}


def register_bittensor_worlds():
    """Register all Bittensor world classes with CGE adapter."""
    from mwgym.worlds.cge_adapter import register_world_class
    for family_id, cls in BITTENSOR_WORLD_CLASSES.items():
        register_world_class(family_id, cls)


# Auto-register on import
register_bittensor_worlds()
