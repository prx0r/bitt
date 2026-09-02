"""Bittensor FamilyWorldSpec entries — register Bittensor subnet families in CGE.

These specs tell the CGE adversary how to generate, mutate, and evaluate
worlds for each Bittensor subnet objective.
"""
from __future__ import annotations

import sys
from pathlib import Path

if str(Path("/root/mwgym")) not in sys.path:
    sys.path.insert(0, str(Path("/root/mwgym")))

from mwgym.worlds.schema import FamilyWorldSpec, register_family

from .config import SUBNETS


def register_bittensor_families():
    """Register all Bittensor subnet families with MWGym's CGE."""

    for netuid, subnet in SUBNETS.items():
        register_family(FamilyWorldSpec(
            family_id=subnet.family_id,
            task_family=subnet.family_id,
            submission_type=f"bittensor_subnet_{netuid}",
            capabilities=subnet.capabilities,
            gates=subnet.gates,
            generator=f"bittensor.sn{netuid}.{subnet.name.lower()}.v1",
            verifier=f"bittensor.sn{netuid}.{subnet.name.lower()}.verifier.v1",
            mutator_families=subnet.mutator_families,
            min_difficulty=1,
            max_difficulty=10,
            default_resources={
                "budget_usd": 0.05,
                "time_limit_s": 300,
                "subnet_id": netuid,
                "tao_budget": subnet.registration_cost_approx * 2,
            },
        ))


# Also register composite Bittensor family for multi-subnet optimization
def register_bittensor_composite():
    """Multi-subnet worker that routes across all Bittensor objectives."""
    register_family(FamilyWorldSpec(
        family_id="bittensor.composite",
        task_family="bittensor.composite",
        submission_type="bittensor_multi_subnet",
        capabilities=(
            "subnet.select",
            "task.classify",
            "quality.estimate",
            "cost.minimize",
            "latency.minimize",
            "novelty.evaluate",
        ),
        gates=("subnet_selected", "budget_respected", "quality_threshold_met"),
        generator="bittensor.composite.v1",
        verifier="bittensor.composite.verifier.v1",
        mutator_families=("economic", "information", "temporal"),
        default_resources={
            "budget_usd": 0.20,
            "time_limit_s": 600,
            "available_subnets": list(SUBNETS.keys()),
        },
    ))


# Auto-register on import
register_bittensor_families()
register_bittensor_composite()
