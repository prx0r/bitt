"""Security transfer detection — uses TransferClaim contracts.

Implements the transfer ladder from email 2:
  BitSec → BountyBench (near transfer)
  BitSec → XBOW (web security transfer)
  BitSec → RedTeam SN61 (far transfer)

Each transfer test is a controlled experiment:
  same WorkerVersion, same task, same budget, same model
  A = no transferred finding
  B = transferred validated finding
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from lab.contracts import (
    Finding, FindingTier, TransferClaim, CapabilityScope, Split,
)
from lab.contracts import SCHEMA_VERSION


def create_transfer_claim(
    finding: Finding,
    source_venue: str,
    target_venue: str,
    evidence_run_ids: list[str],
    confidence: float = 0.0,
) -> TransferClaim:
    """Create a TransferClaim contract for a finding crossing venues.

    The finding must be a STUDIO_FINDING (validated in source venue)
    before it can be claimed to transfer.
    """
    if finding.tier != FindingTier.STUDIO_FINDING:
        raise ValueError(
            f"Cannot transfer finding {finding.finding_id}: "
            f"tier={finding.tier}, must be STUDIO_FINDING"
        )

    return TransferClaim(
        claim_id=f"transfer-{finding.finding_id}-{source_venue}-to-{target_venue}",
        finding_id=finding.finding_id,
        source_venue=source_venue,
        target_venue=target_venue,
        evidence_run_ids=evidence_run_ids,
        confidence=confidence,
        status="pending",
    )


def evaluate_transfer(
    claim: TransferClaim,
    control_f1: float,
    candidate_f1: float,
    n_tasks: int,
) -> TransferClaim:
    """Evaluate a transfer claim. Returns updated claim.

    If candidate (with transferred finding) beats control (without),
    the claim is SUPPORTED. Otherwise REJECTED.
    """
    delta = candidate_f1 - control_f1
    # Require meaningful improvement and sufficient sample
    supported = delta > 0.02 and n_tasks >= 5

    return TransferClaim(
        claim_id=claim.claim_id,
        finding_id=claim.finding_id,
        source_venue=claim.source_venue,
        target_venue=claim.target_venue,
        evidence_run_ids=claim.evidence_run_ids,
        confidence=abs(delta),
        status="supported" if supported else "rejected",
    )


# ─── Transfer Ladder Stages ──────────────────────────────────────────

TRANSFER_LADDER = {
    "near_transfer": {
        "source": "bitsec",
        "targets": ["bountybench", "sherlock", "cantina", "immunefi"],
        "description": "Historical bug-bounty / audit replay",
    },
    "live_near_transfer": {
        "source": "bitsec",
        "targets": ["hackerone", "hackenproof", "intigriti"],
        "description": "Real authorized audit / bug-bounty opportunity",
    },
    "far_transfer": {
        "source": "bitsec",
        "targets": ["sn61-redteam"],
        "description": "RedTeam SN61 challenge (different security school)",
    },
}


def plan_transfer_experiments(
    findings: list[Finding],
    source_venue: str = "bitsec",
) -> list[dict]:
    """Plan transfer experiments for validated findings.

    Returns a list of planned experiments, one per finding per target venue.
    """
    validated = [f for f in findings if f.tier == FindingTier.STUDIO_FINDING]
    plans = []

    for finding in validated:
        for stage_name, stage in TRANSFER_LADDER.items():
            for target in stage["targets"]:
                if target == source_venue:
                    continue
                plans.append({
                    "finding_id": finding.finding_id,
                    "claim": finding.claim,
                    "source_venue": source_venue,
                    "target_venue": target,
                    "stage": stage_name,
                    "hypothesis": (
                        f"Finding '{finding.claim}' validated in {source_venue} "
                        f"will improve performance on {target}"
                    ),
                    "experiment_design": {
                        "control": "same worker, no transferred finding",
                        "candidate": "same worker + transferred finding",
                        "same_model": True,
                        "same_budget": True,
                        "same_tasks": True,
                    },
                })

    return plans
