"""Difficulty model + LabValue calculator.

Difficulty: empirical measure of how hard it is to earn rewards.
LabValue: how useful a subnet is as a training environment regardless of payout.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DifficultyBreakdown:
    """Component scores for difficulty calculation (all 0-1)."""
    competitive_depth: float = 0.0      # how many active miners
    score_gap_to_paid: float = 0.0      # gap between our score and paid threshold
    reward_concentration: float = 0.0   # HHI-based
    domain_specialization: float = 0.0  # how specialized the task is
    compute_barrier: float = 0.0        # hardware requirements
    entry_risk: float = 0.0            # cost to register + lost burn
    feedback_latency: float = 0.0      # how slow feedback is
    benchmark_uncertainty: float = 0.0  # how unclear the scoring is
    protocol_instability: float = 0.0   # how often rules change


@dataclass
class LabValueBreakdown:
    """Component scores for lab value calculation (all 0-1)."""
    verifier_strength: float = 0.0       # how good the evaluator is
    replayability: float = 0.0           # how easy to replay locally
    iteration_frequency: float = 0.0    # how often new tasks arrive
    feedback_richness: float = 0.0      # how much info per episode
    skill_transferability: float = 0.0  # how useful learned skills are elsewhere
    artifact_reusability: float = 0.0   # how reusable the artifacts are
    curriculum_generatability: float = 0.0  # how easy to make curricula
    economic_reality: float = 0.0       # how real the economic signal is


def calculate_difficulty(
    netuid: int,
    emitting_miners: int | None = None,
    registered_neurons: int | None = None,
    score_gap_to_paid: float = 0.5,    # from sealed eval (0 = already paid, 1 = very far)
    hhi: float = 0.0,
    gpu_required: bool = False,
    min_vram_gb: float = 0.0,
    registration_burn_tao: float = 0.0,
    feedback_latency_hours: float = 1.0,
    local_eval: bool = True,
    protocol_version: str | None = None,
) -> tuple[float, DifficultyBreakdown]:
    """Calculate empirical difficulty score (0-1, higher = harder).

    Returns (difficulty_score, breakdown).
    """
    bd = DifficultyBreakdown()

    # Competitive depth: more miners = harder
    n_miners = emitting_miners or registered_neurons or 256
    bd.competitive_depth = min(1.0, n_miners / 256.0)

    # Score gap: how far from paid
    bd.score_gap_to_paid = max(0.0, min(1.0, score_gap_to_paid))

    # Reward concentration: higher HHI = more concentrated = harder to break in
    bd.reward_concentration = min(1.0, hhi * 3)  # HHI range ~0.01-0.33

    # Domain specialization: some tasks are more specialized
    specialization_map = {
        118: 0.5,   # memory/tool judgment — moderate
        62: 0.4,    # coding — transferable
        6: 0.6,     # forecasting — specialized
        15: 0.3,    # shopping — moderate
        67: 0.5,    # research — moderate
        107: 0.9,   # genomics — very specialized
        56: 0.7,    # automl — specialized
        61: 0.8,    # security — specialized
        114: 0.6,   # compression — specialized
        120: 0.9,   # model optimization — very specialized
        97: 0.9,    # model distillation — very specialized
        1: 0.5,     # research routing — moderate
    }
    bd.domain_specialization = specialization_map.get(netuid, 0.5)

    # Compute barrier
    if gpu_required:
        bd.compute_barrier = min(1.0, min_vram_gb / 80.0)  # normalize to A100
    else:
        bd.compute_barrier = 0.1

    # Entry risk: higher burn = higher risk
    bd.entry_risk = min(1.0, registration_burn_tao / 2.0)  # 2 TAO = max risk

    # Feedback latency
    bd.feedback_latency = min(1.0, feedback_latency_hours / 24.0)

    # Benchmark uncertainty
    bd.benchmark_uncertainty = 0.3 if local_eval else 0.7

    # Protocol instability (placeholder — needs history)
    bd.protocol_instability = 0.3

    # Weighted sum
    difficulty = (
        0.20 * bd.competitive_depth
        + 0.20 * bd.score_gap_to_paid
        + 0.15 * bd.reward_concentration
        + 0.10 * bd.domain_specialization
        + 0.10 * bd.compute_barrier
        + 0.10 * bd.entry_risk
        + 0.05 * bd.feedback_latency
        + 0.05 * bd.benchmark_uncertainty
        + 0.05 * bd.protocol_instability
    )

    return difficulty, bd


def calculate_lab_value(
    netuid: int,
    local_eval_available: bool = False,
    deterministic_verifier: bool = False,
    fresh_task_generation: bool = False,
    feedback_latency_hours: float = 1.0,
    skill_transfer: float = 0.5,       # how transferable skills are
    economic_reality: float = 0.5,     # how real the economic signal is
) -> tuple[float, LabValueBreakdown]:
    """Calculate lab value score (0-1, higher = better training environment).

    Returns (lab_value_score, breakdown).
    """
    bd = LabValueBreakdown()

    # Verifier strength
    bd.verifier_strength = 1.0 if deterministic_verifier else 0.5

    # Replayability
    bd.replayability = 1.0 if local_eval_available else 0.2

    # Iteration frequency
    if fresh_task_generation:
        bd.iteration_frequency = 0.8  # new tasks frequently
    else:
        bd.iteration_frequency = 0.3

    # Feedback richness
    bd.feedback_richness = max(0.1, 1.0 - min(1.0, feedback_latency_hours / 24.0))

    # Skill transferability
    bd.skill_transferability = skill_transfer

    # Artifact reusability
    artifact_map = {
        118: 0.8,   # memory patterns reusable
        62: 0.95,   # code is highly reusable
        6: 0.7,     # forecasting skills reusable
        15: 0.6,    # shopping patterns somewhat reusable
        67: 0.8,    # research skills reusable
        107: 0.4,   # genomics less reusable
        56: 0.6,    # automl somewhat reusable
        61: 0.7,    # security skills reusable
        114: 0.5,   # compression moderately reusable
        120: 0.3,   # model optimization less reusable
        97: 0.3,    # distillation less reusable
        1: 0.7,     # research routing reusable
    }
    bd.artifact_reusability = artifact_map.get(netuid, 0.5)

    # Curriculum generatability
    bd.curriculum_generatability = 0.9 if fresh_task_generation and local_eval_available else 0.4

    # Economic reality
    bd.economic_reality = economic_reality

    # Weighted sum
    lab_value = (
        0.20 * bd.verifier_strength
        + 0.18 * bd.replayability
        + 0.15 * bd.iteration_frequency
        + 0.12 * bd.feedback_richness
        + 0.12 * bd.skill_transferability
        + 0.10 * bd.artifact_reusability
        + 0.08 * bd.curriculum_generatability
        + 0.05 * bd.economic_reality
    )

    return lab_value, bd
