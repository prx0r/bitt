"""Bitsec CGE World — training environment for vulnerability detection.

This world models the Bitsec subnet evaluation:
  - Worker receives code to analyze
  - Worker produces vulnerability report
  - Validator scores against ground truth
  - CGE adversary mutates difficulty, code patterns, evaluation pressure

The learning loop:
  1. CGE generates code samples with known vulnerabilities
  2. Worker analyzes and produces reports
  3. Reports scored against ground truth (TP/FP/FN)
  4. Failure patterns fed back to adversary
  5. Adversary mutates to target weak spots
  6. Worker improves, repeat
"""
from __future__ import annotations

import random
from pathlib import Path

import sys
if str(Path("/root/mwgym")) not in sys.path:
    sys.path.insert(0, str(Path("/root/mwgym")))

from mwgym.worlds.cge_adapter import (
    ActionSpec, ActionResult, BaseWorld, Metric, MetricVector, WorldState,
)
from mwgym.schema.world import (
    CapabilityScore, FailureVector, GateResult, WorldGenome,
)


# ─── Vulnerability patterns for world generation ──────────────────

VULN_PATTERNS = {
    "reentrancy": {
        "severity": "CRITICAL",
        "category": "reentrancy",
        "template": """
contract Vulnerable {{
    mapping(address => uint256) balances;
    function withdraw(uint256 amount) public {{
        require(balances[msg.sender] >= amount);
        (bool ok,) = msg.sender.call{{value: amount}}("");
        require(ok);
        balances[msg.sender] -= amount;
    }}
}}""",
        "fix": "Add ReentrancyGuard or checks-effects-interactions",
    },
    "unchecked_return": {
        "severity": "HIGH",
        "category": "unchecked_return",
        "template": """
contract Vulnerable {{
    function callExternal(address target, bytes memory data) public {{
        // No check on return value
        target.call(data);
    }}
}}""",
        "fix": "Check return value: (bool ok,) = target.call(data); require(ok);",
    },
    "access_control": {
        "severity": "HIGH",
        "category": "access_control",
        "template": """
contract Vulnerable {{
    address public owner;
    function destroy() public {{
        // No onlyOwner modifier
        selfdestruct(payable(msg.sender));
    }}
}}""",
        "fix": "Add onlyOwner modifier or role-based access control",
    },
    "tx_origin": {
        "severity": "MEDIUM",
        "category": "access_control",
        "template": """
contract Vulnerable {{
    function transfer(address to) public {{
        require(tx.origin == owner);
        // ...
    }}
}}""",
        "fix": "Use msg.sender instead of tx.origin",
    },
    "integer_overflow": {
        "severity": "HIGH",
        "category": "arithmetic",
        "template": """
contract Vulnerable {{
    mapping(address => uint8) counts;
    function increment() public {{
        counts[msg.sender]++;
        // uint8 overflow at 255
    }}
}}""",
        "fix": "Use SafeMath or Solidity 0.8+ (built-in checks)",
    },
    "front_running": {
        "severity": "MEDIUM",
        "category": "general",
        "template": """
contract Vulnerable {{
    function submit(bytes32 hash) public {{
        // Commit-reveal without delay
        commitments[msg.sender] = hash;
        // Can be front-run
    }}
}}""",
        "fix": "Add commit-reveal with time delay",
    },
}

SAFE_PATTERNS = {
    "safe_math": """
contract Safe {{
    using SafeMath for uint256;
    mapping(address => uint256) balances;
    function withdraw(uint256 amount) public {{
        require(balances[msg.sender] >= amount);
        balances[msg.sender] = balances[msg.sender].sub(amount);
        (bool ok,) = msg.sender.call{{value: amount}}("");
        require(ok);
    }}
}}""",
    "access_control": """
contract Safe {{
    address public owner;
    modifier onlyOwner() {{ require(msg.sender == owner); _; }}
    function destroy() public onlyOwner {{
        selfdestruct(payable(msg.sender));
    }}
}}""",
    "checks_effects": """
contract Safe {{
    mapping(address => uint256) balances;
    function withdraw(uint256 amount) public {{
        require(balances[msg.sender] >= amount);
        balances[msg.sender] -= amount;  // state change BEFORE external call
        (bool ok,) = msg.sender.call{{value: amount}}("");
        require(ok);
    }}
}}""",
}


class BitsecWorld(BaseWorld):
    """CGE world for Bitsec vulnerability detection training.

    The worker must:
    1. Analyze code for vulnerabilities
    2. Report findings with correct severity/category
    3. Minimize false positives
    4. Stay within budget

    The adversary mutates:
    - Code pattern mix (vulnerable vs safe)
    - Vulnerability complexity (obvious vs subtle)
    - Number of vulnerabilities per sample
    - False positive pressure (near-miss patterns)
    """

    def _generate_truth(self, rng: random.Random) -> dict:
        difficulty = self.genome.difficulty / 10.0
        n_vulns = 1 if difficulty < 0.3 else rng.randint(1, int(1 + difficulty * 4))
        n_safe = rng.randint(0, int(difficulty * 3))

        # Pick vulnerability types
        vuln_types = rng.sample(list(VULN_PATTERNS.keys()),
                                 min(n_vulns, len(VULN_PATTERNS)))

        # Pick safe patterns
        safe_types = rng.sample(list(SAFE_PATTERNS.keys()),
                                 min(n_safe, len(SAFE_PATTERNS)))

        return {
            "difficulty": difficulty,
            "vulnerabilities": vuln_types,
            "safe_patterns": safe_types,
            "expected_findings": n_vulns,
            "severity_distribution": {vt: VULN_PATTERNS[vt]["severity"] for vt in vuln_types},
        }

    def _generate_observable(self, rng: random.Random, hidden: dict) -> dict:
        # Build code sample from patterns
        code_parts = []
        for vt in hidden["vulnerabilities"]:
            code_parts.append(VULN_PATTERNS[vt]["template"])
        for st in hidden["safe_patterns"]:
            code_parts.append(SAFE_PATTERNS[st])

        rng.shuffle(code_parts)

        return {
            "code": "\n\n".join(code_parts),
            "language": "solidity",
            "n_vulns": hidden["expected_findings"],
            "severity_targets": list(hidden["severity_distribution"].values()),
        }

    def _generate_actions(self, state: WorldState) -> list[dict]:
        if state.terminal:
            return []
        return [
            {"kind": "ANALYZE_CODE", "payload": {"code": state.observable["code"]},
             "estimated_cost": 0.001},
            {"kind": "RUN_STATIC", "payload": {}, "estimated_cost": 0.0005},
            {"kind": "SUBMIT_REPORT", "payload": {}, "estimated_cost": 0.0},
            {"kind": "ABORT", "payload": {}, "estimated_cost": 0.0},
        ]

    def _process_result(self, state: WorldState, action: ActionSpec, result: ActionResult):
        if action.kind == "ANALYZE_CODE":
            # Worker analyzed — correctness based on how well they found vulns
            # In real evaluation, this would compare against ground truth
            state.model_calls += 1
            state.evidence_quality = min(1.0, state.evidence_quality + 0.3)
        elif action.kind == "RUN_STATIC":
            state.model_calls += 1
            state.evidence_quality = min(1.0, state.evidence_quality + 0.2)
        elif action.kind == "SUBMIT_REPORT":
            # Score against ground truth
            n_expected = state.hidden.get("expected_findings", 0)
            # Simulate scoring: correctness = f(found, expected, false_positives)
            found = state.model_calls  # proxy for findings
            false_positives = max(0, found - n_expected) * 0.3
            true_positives = min(found, n_expected)
            state.correctness = max(0.0, (true_positives * 1.0 - false_positives * 0.5) / max(n_expected, 1))
            state.completeness = min(1.0, true_positives / max(n_expected, 1))
            state.terminal = True
        elif action.kind == "ABORT":
            state.correctness = 0.0
            state.terminal = True

    def _evaluate_gates(self, state: WorldState) -> list[GateResult]:
        n_expected = state.hidden.get("expected_findings", 0)
        return [
            GateResult(
                gate_id="g0", gate_name="found_vulnerabilities",
                passed=state.correctness > 0,
                actual=f"{state.correctness:.2f}",
            ),
            GateResult(
                gate_id="g1", gate_name="low_false_positive_rate",
                passed=state.correctness > 0.5,
                actual=f"{state.correctness:.2f}",
            ),
            GateResult(
                gate_id="g2", gate_name="severity_correct",
                passed=state.completeness >= 0.5,
                actual=f"{state.completeness:.2f}",
            ),
        ]

    def _detect_failure_modes(self, state: WorldState) -> list[str]:
        modes = []
        if state.correctness < 0.3:
            modes.append("low_detection_rate")
        if state.correctness < 0 and abs(state.correctness) > 0.1:
            modes.append("high_false_positive_rate")
        if state.total_cost_usd > 0.01:
            modes.append("excessive_cost")
        n_expected = state.hidden.get("expected_findings", 0)
        if n_expected > 2 and state.correctness < 0.5:
            modes.append("complex_vulns_missed")
        return modes

    def _score_capabilities(self, state: WorldState) -> list[CapabilityScore]:
        return [
            CapabilityScore("vuln.detect", state.correctness, 1, 0.5),
            CapabilityScore("vuln.classify", state.completeness, 1, 0.5),
            CapabilityScore("cost.minimize", max(0, 1.0 - state.total_cost_usd / 0.01), 1, 0.3),
            CapabilityScore("false_positive控制", state.correctness * 0.8, 1, 0.4),
        ]
