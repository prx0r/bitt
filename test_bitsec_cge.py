"""Test the CGE learning loop with Bitsec world.

Runs a minimal CGE cycle:
  1. Create world from genome
  2. Worker analyzes code
  3. Score against ground truth
  4. Feed failure back to adversary
  5. Mutate world
  6. Repeat
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path("/root/mwgym")))
sys.path.insert(0, str(Path("/root/bitt/integration")))

from mwgym.worlds.cge_adapter import ActionSpec, ActionResult, compile_world
from mwgym.schema.world import WorldGenome
from bittensor_gym.bitsec_world import BitsecWorld


def test_bitsec_world():
    """Test one cycle of the CGE loop."""
    # Create a world genome
    genome = WorldGenome(
        family_id="bittensor.bitsec",
        difficulty=3,
        seed=42,
        structure={"max_steps": 5},
        information={"noise_level": 0.1},
        resources={"budget_usd": 0.01},
    )

    # Compile world
    world = BitsecWorld(genome)

    # Reset
    state = world.reset(seed=42)
    print(f"World created. Hidden vulns: {state.hidden['vulnerabilities']}")
    print(f"Expected findings: {state.hidden['expected_findings']}")
    print(f"Code length: {len(state.observable['code'])} chars")

    # Simulate worker actions
    step = 0
    while not world.terminal(state) and step < 5:
        actions = world.actions(state)
        if not actions:
            break

        # Worker chooses to analyze then submit
        action = actions[0] if step == 0 else actions[2]  # ANALYZE then SUBMIT
        result = ActionResult(status="ok", cash_cost=0.001)
        state = world.apply(state, action, result)
        step += 1
        print(f"  Step {step}: {action.kind} → correctness={state.correctness:.2f} completeness={state.completeness:.2f}")

    # Score
    metrics = world.score(state)
    print(f"\nFinal score:")
    for m in metrics.metrics:
        print(f"  {m.name}: {m.value:.2f}")

    # Failure vector
    fv = world.to_failure_vector(state)
    print(f"\nFailure modes: {fv.failure_modes}")
    print(f"Gates passed: {fv.gates_passed}/{fv.gates_total}")

    return fv


if __name__ == "__main__":
    print("=== Bitsec CGE World Test ===\n")
    test_bitsec_world()
    print("\n=== Test passed ===")
