"""Data validation — honest, not performative.

Every check is either:
  CHAIN_ONLY  — we have one source, can't cross-check
  PINNED      — block matches capture block (atomicity verified)
  EXACT       — two sources match exactly
  DISCREPANCY — two sources disagree (flagged, not resolved)

Never manufacture VERIFIED.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ValidationResult:
    field: str
    status: str  # CHAIN_ONLY, PINNED, EXACT, DISCREPANCY
    details: str
    chain_value: str = ""
    comparison_value: str = ""


def validate_capture(capture: dict) -> list[ValidationResult]:
    """Validate a capture against itself (atomicity) + known facts."""
    results = []
    block = capture.get("block_number")

    # 1. Atomicity: all subnets at same block
    all_same_block = all(
        s.get("block_number") == block
        for s in capture.get("subnets", {}).values()
        if "block_number" in s
    )
    results.append(ValidationResult(
        field="atomicity",
        status="PINNED" if all_same_block else "DISCREPANCY",
        details=f"all {capture.get('subnets_count', 0)} subnets at block {block}" if all_same_block
                else "subnets at different blocks",
    ))

    # 2. For each subnet, validate known invariants
    for netuid_str, s in capture.get("subnets", {}).items():
        if "error" in s:
            continue
        netuid = int(netuid_str)

        # Emission must be non-negative
        if s.get("total_alpha_epoch", 0) < 0:
            results.append(ValidationResult(
                field=f"SN{netuid}.emission",
                status="DISCREPANCY",
                details=f"negative emission: {s['total_alpha_epoch']}",
            ))

        # Burn must be in [min_burn, max_burn]
        hp = s.get("hyperparams", {})
        min_burn = (hp.get("min_burn") or 0) / 1e9
        max_burn = (hp.get("max_burn") or 0) / 1e9
        burn = s.get("burn_tao", 0)
        if min_burn <= burn <= max_burn:
            results.append(ValidationResult(
                field=f"SN{netuid}.burn",
                status="CHAIN_ONLY",
                details=f"{burn:.9f} TAO in [{min_burn}, {max_burn}]",
                chain_value=str(burn),
            ))
        else:
            results.append(ValidationResult(
                field=f"SN{netuid}.burn",
                status="DISCREPANCY",
                details=f"{burn:.9f} outside [{min_burn}, {max_burn}]",
            ))

        # Emission split: owner + validators + miners ≈ total
        owner_cut = s.get("owner_cut_pct", 18) / 100
        val_tao = s.get("validator_tao_day", 0)
        total_tao = s.get("total_tao_day", 0)
        if total_tao > 0:
            accounted = val_tao + s.get("contestable_miner_tao_day", 0) + (total_tao * owner_cut)
            discrepancy = abs(accounted - total_tao) / total_tao
            if discrepancy < 0.05:
                results.append(ValidationResult(
                    field=f"SN{netuid}.emission_split",
                    status="CHAIN_ONLY",
                    details=f"split accounts for {discrepancy:.1%} discrepancy",
                ))
            else:
                results.append(ValidationResult(
                    field=f"SN{netuid}.emission_split",
                    status="DISCREPANCY",
                    details=f"split accounts for {discrepancy:.1%} discrepancy (owner={owner_cut:.0%})",
                ))

    return results
