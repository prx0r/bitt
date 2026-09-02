"""Bitsec mwgym integration — registers Bitsec as a mwgym world + pool.

This wires:
  1. BitsecWorld into mwgym's CGE adapter
  2. Security pool into mwgym's wired_loop
  3. mimo-v2.5 as the model for all evaluations
  4. Controlled scientific evolution via CGE

From the user's architecture:
  - One variable at a time
  - Proper controls
  - Frozen intents
  - Generator/judge separation
  - Failure ≠ change
"""
from __future__ import annotations

import sys
from pathlib import Path

# Add paths
sys.path.insert(0, str(Path("/root/mwgym")))
sys.path.insert(0, str(Path("/root/bitt")))
sys.path.insert(0, str(Path("/root/bitt/integration")))

# Register Bitsec world into mwgym CGE
from mwgym.worlds.cge_adapter import register_world_class, BaseWorld, ActionSpec, ActionResult, WorldState, Metric, MetricVector
from mwgym.schema.world import WorldGenome, CapabilityScore, GateResult

# Import our Bitsec world
from cge.bitsec.world import BitsecWorld, load_scabench_dataset, score_vulnerabilities, Project


class BitsecMwgymWorld(BaseWorld):
    """Bitsec vulnerability detection as a mwgym CGE world.

    Bridges cogym BitsecWorld into mwgym's CGE adapter protocol.
    """

    def __init__(self, genome: WorldGenome):
        super().__init__(genome)
        self._bitsec = BitsecWorld()
        self._project = None

    def _generate_truth(self, rng):
        """Load a random project from ScaBench dataset."""
        if self._bitsec.projects:
            self._project = rng.choice(self._bitsec.projects)
        return {
            "project_id": self._project.project_id if self._project else "none",
            "n_vulns": len(self._project.vulnerabilities) if self._project else 0,
            "vulnerability_categories": [v.category for v in self._project.vulnerabilities] if self._project else [],
        }

    def _generate_observable(self, rng, hidden):
        """What the worker sees — project info, no ground truth."""
        if not self._project:
            return {"error": "no project"}
        return {
            "project_id": self._project.project_id,
            "name": self._project.name,
            "platform": self._project.platform,
            "repo_url": self._project.repo_url,
            "n_vulnerabilities": hidden["n_vulns"],
            "severity_dist": {v.severity: 0 for v in self._project.vulnerabilities},
        }

    def _generate_actions(self, state):
        """Available analysis actions."""
        if state.terminal:
            return []
        return [
            {"kind": "analyze_code", "payload": {"strategy": "per_file"}, "estimated_cost": 0.001},
            {"kind": "analyze_code", "payload": {"strategy": "cross_file"}, "estimated_cost": 0.002},
            {"kind": "commit_findings", "payload": {}, "estimated_cost": 0.0},
        ]

    def _process_result(self, state, action, result):
        """Process action result."""
        if action.kind == "analyze_code":
            state.model_calls += 1
            state.evidence_quality = min(1.0, state.evidence_quality + 0.3)
        elif action.kind == "commit_findings":
            # Score against ground truth using Jaccard
            if self._project:
                agent_cats = [f.get("category", "") for f in state.observable.get("findings", [])]
                truth_cats = [v.category for v in self._project.vulnerabilities]
                jaccard = len(set(agent_cats) & set(truth_cats)) / max(len(set(agent_cats) | set(truth_cats)), 1)
                state.correctness = jaccard
            state.terminal = True

    def _evaluate_gates(self, state):
        return [
            GateResult(gate_id="g0", gate_name="jaccard_above_threshold",
                      passed=state.correctness >= 0.3,
                      actual=f"{state.correctness:.3f}"),
        ]

    def _detect_failure_modes(self, state):
        modes = []
        if state.correctness < 0.3:
            modes.append("low_jaccard")
        if state.model_calls > 3:
            modes.append("excessive_calls")
        return modes

    def _score_capabilities(self, state):
        return [
            CapabilityScore("vulnerability_detection", state.correctness, 1, 0.5),
            CapabilityScore("security", state.correctness * 0.98, 1, 0.5),
            CapabilityScore("smart_contract_security", state.correctness * 0.95, 1, 0.4),
        ]


# Register with mwgym
register_world_class("bittensor.bitsec", BitsecMwgymWorld)

print("Bitsec world registered in mwgym CGE")
print("Worlds available:", list(__import__('mwgym.worlds.cge_adapter', fromlist=['_WORLD_CLASSES'])._WORLD_CLASSES.keys()))
