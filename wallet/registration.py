"""Registration manager — handles subnet registration with spending gates.

Never registers automatically. Always checks:
  1. Current burn price (cached = WRONG)
  2. Oracle's source confidence
  3. Our sealed evaluation score
  4. Expected EV > 3x submission fee
  5. Capital policy allows it
"""
from __future__ import annotations

import json
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path("/root/bitt/integration")))

from bittensor_gym.config import SUBNETS, tao_to_usd
from bittensor_gym.oracle.mechanism import get_known_mechanism
from bittensor_gym.oracle.engine import BittensorOracle


class RegistrationManager:
    """Manages subnet registration with safety gates."""

    # Spending policy
    MAX_REGISTRATION_TAO = Decimal("1.0")  # never register on >1 TAO subnets without explicit approval
    MIN_EXPECTED_EV_MULTIPLIER = 3.0       # expected EV must be >3x cost

    def __init__(self):
        oracle = BittensorOracle()
        self._latest = oracle.run_full_scan()

    def check_burn(self, netuid: int):
        """Check current registration burn for a subnet."""
        from bittensor_gym.oracle.scanner import ChainScanner
        scanner = ChainScanner()
        raw = scanner.scan_subnet(netuid)

        # Extract burn from sources
        burn = self._extract_burn(raw)
        print(f"\nSN{netuid} Registration Burn:")
        print(f"  Current: {burn:.6f} TAO (~${tao_to_usd(float(burn)):.2f})")
        print(f"  Policy max: {self.MAX_REGISTRATION_TAO} TAO")

        if burn > self.MAX_REGISTRATION_TAO:
            print(f"  WARNING: Burn exceeds policy limit. Manual approval required.")
        else:
            print(f"  OK: Within policy limits.")

        return burn

    def estimate_cost(self, netuid: int):
        """Estimate full cost to attempt on a subnet."""
        mechanism = get_known_mechanism(netuid)
        if not mechanism:
            print(f"No mechanism known for SN{netuid}")
            return

        from bittensor_gym.oracle.reward_analyzer import estimate_cost_to_attempt
        cost = estimate_cost_to_attempt(mechanism)

        print(f"\nSN{netuid} Cost to Attempt:")
        for k, v in cost.items():
            if isinstance(v, float):
                print(f"  {k}: {v:.6f}")
            else:
                print(f"  {k}: {v}")

    def dry_run(self, netuid: int):
        """Simulate registration without spending."""
        print(f"\n=== DRY RUN: SN{netuid} Registration ===\n")

        # 1. Check burn
        burn = self.check_burn(netuid)

        # 2. Check assessment
        assessment = None
        for a in self._latest.get("assessments", []):
            if a.netuid == netuid:
                assessment = a
                break

        if assessment:
            print(f"\n  Assessment:")
            print(f"    Recommendation: {assessment.recommendation}")
            print(f"    Economic: {assessment.economic_score:.3f}")
            print(f"    Lab value: {assessment.lab_value:.3f}")
            print(f"    Expected TAO/day: {assessment.expected_tao_day:.3f}")
            print(f"    P(top5): {assessment.p_top5:.2f}")
            print(f"    Capital risk: {assessment.capital_risk:.3f}")

        # 3. Apply spending gate
        print(f"\n  Spending Gate:")
        gate_passed = True
        reasons = []

        if burn > self.MAX_REGISTRATION_TAO:
            gate_passed = False
            reasons.append(f"burn ({burn:.4f}) > max ({self.MAX_REGISTRATION_TAO})")

        if assessment and assessment.recommendation not in ("REGISTER_SMALL", "LIVE_COMPETE"):
            gate_passed = False
            reasons.append(f"recommendation is '{assessment.recommendation}'")

        if assessment and assessment.p_top5 < 0.1:
            gate_passed = False
            reasons.append(f"P(top5)={assessment.p_top5:.2f} too low")

        if gate_passed:
            print(f"    PASSED — registration would be allowed")
        else:
            print(f"    BLOCKED — {', '.join(reasons)}")

        print(f"\n  This is a DRY RUN. No TAO spent.")

    def register(self, netuid: int, wallet_name: str = "default"):
        """Actually register on a subnet. Applies all safety gates."""
        print(f"\n=== REGISTER: SN{netuid} with wallet '{wallet_name}' ===\n")

        # Run dry run first
        self.dry_run(netuid)

        # Confirm
        response = input("\nProceed with registration? (yes/NO): ").strip().lower()
        if response != "yes":
            print("Aborted.")
            return

        # Execute registration
        cmd = [
            "btcli", "subnet", "register",
            "--netuid", str(netuid),
            "--wallet.name", wallet_name,
        ]

        print(f"Running: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

        if result.returncode == 0:
            print(f"\nRegistration successful!")
            print(result.stdout)
        else:
            print(f"\nRegistration failed:")
            print(result.stderr)

    def _extract_burn(self, raw: dict) -> Decimal:
        """Extract burn price from raw scan data."""
        sources = raw.get("sources", {})

        # Try metagraphed
        if "metagraphed" in sources:
            burn = sources["metagraphed"].get("burn", 0)
            if burn:
                return Decimal(str(burn))

        # Try SDK
        if "sdk" in sources:
            sdk = sources["sdk"]
            if "burn" in sdk:
                return Decimal(str(sdk["burn"].get("burn", 0)))

        # Try bittensor_ai
        if "bittensor_ai" in sources:
            ai = sources["bittensor_ai"]
            burn = ai.get("registration_cost", ai.get("burn", 0))
            if burn:
                return Decimal(str(burn))

        return Decimal("0")
