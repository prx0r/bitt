"""Main Oracle engine — orchestrates scanning, analysis, scoring, and reporting.

This is the entry point for the Bittensor opportunity engine.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from .snapshot import BittensorOpportunitySnapshot
from .scanner import ChainScanner, ScannerConfig, ScannerStore
from .mechanism import (
    MechanismInfo, get_known_mechanism, parse_mechanism_from_data,
    KNOWN_MECHANISMS,
)
from .reward_analyzer import (
    analyze_reward_distribution, calculate_alpha_risk, estimate_cost_to_attempt,
)
from .difficulty import calculate_difficulty, calculate_lab_value
from .scorer import (
    score_opportunity, rank_opportunities, OpportunityAssessment,
)

from ..config import SUBNETS, SubnetConfig


# ─── Target subnets (priority order) ────────────────────────────────

TARGET_SUBNETS = [
    118,  # Ditto — memory/tool judgment
    62,   # Ridges — SWE coding
    107,  # Minos — genomic optimization
    56,   # Gradients — AutoML
    61,   # RedTeam — security
    114,  # SOMA — compression
    67,   # Harnyx — deep research
    120,  # Affine — model optimization
    97,   # Albedo — distillation
    6,    # Numinous — forecasting
    15,   # ORO — shopping
    1,    # Apex — distributed research
]

# ─── Registered subnet configs (from our config.py) ──────────────────

for netuid, cfg in SUBNETS.items():
    if netuid not in [s.netuid for s in KNOWN_MECHANISMS.values()]:
        pass  # mechanism will be auto-parsed


class BittensorOracle:
    """Main oracle engine. Scans, analyzes, scores, and reports.

    Usage:
        oracle = BittensorOracle()
        report = oracle.run_full_scan()
        print(report["daily_report"])
    """

    def __init__(self, config: ScannerConfig | None = None):
        self.scanner = ChainScanner(config or ScannerConfig())
        self.store = ScannerStore()
        self._latest_assessments: list[OpportunityAssessment] = []

    def run_full_scan(self, netuids: list[int] | None = None) -> dict:
        """Run full scan, analysis, and report generation.

        Returns dict with:
          - snapshots: list of BittensorOpportunitySnapshot
          - assessments: list of OpportunityAssessment
          - daily_report: formatted string
          - raw_data: dict of raw scan data
        """
        targets = netuids or TARGET_SUBNETS
        now = datetime.utcnow()

        snapshots = []
        assessments = []
        raw_scans = {}

        for netuid in targets:
            try:
                snap, assessment, raw = self._scan_and_assess(netuid, now)
                snapshots.append(snap)
                assessments.append(assessment)
                raw_scans[netuid] = raw
            except Exception as e:
                raw_scans[netuid] = {"error": str(e)}

        # Store snapshots
        for snap in snapshots:
            self.store.store(snap)

        # Rank
        ranked = rank_opportunities(assessments)
        self._latest_assessments = ranked

        # Generate report
        report = self._generate_daily_report(ranked, raw_scans)

        return {
            "snapshots": snapshots,
            "assessments": ranked,
            "daily_report": report,
            "raw_data": raw_scans,
            "generated_at": now.isoformat(),
        }

    def _scan_and_assess(
        self, netuid: int, now: datetime
    ) -> tuple[BittensorOpportunitySnapshot, OpportunityAssessment, dict]:
        """Scan one subnet and produce snapshot + assessment."""
        # 1. Scan chain data
        raw = self.scanner.scan_subnet(netuid)

        # 2. Get mechanism info
        mechanism = get_known_mechanism(netuid)
        if not mechanism:
            mechanism = parse_mechanism_from_data(netuid, raw)

        # 3. Extract chain economics
        chain_econ = self._extract_economics(netuid, raw)

        # 4. Get previous snapshot for trend
        prev = self.store.get_latest(netuid)

        # 5. Build snapshot
        snap = self._build_snapshot(netuid, now, chain_econ, mechanism, raw, prev)

        # 6. Analyze reward distribution
        miner_incentives = chain_econ.get("miner_incentives", [])
        pool_tao = float(snap.miner_pool_tao_equiv_day or 0)
        reward = analyze_reward_distribution(
            miner_incentives=miner_incentives,
            pool_tao_day=pool_tao,
            mechanism=mechanism,
            owner_share=snap.owner_share,
            validator_share=snap.validator_share,
        )

        # 7. Calculate difficulty
        diff_score, diff_bd = calculate_difficulty(
            netuid=netuid,
            emitting_miners=snap.emitting_miners,
            registered_neurons=snap.registered_neurons,
            hhi=reward.hhi,
            gpu_required=mechanism.eligibility.require_gpu,
            min_vram_gb=mechanism.eligibility.min_vram_gb,
            registration_burn_tao=float(snap.registration_burn_tao),
            feedback_latency_hours=(snap.feedback_latency_seconds or 3600) / 3600,
            local_eval=mechanism.local_eval_available,
        )

        # 8. Calculate lab value
        lab_score, lab_bd = calculate_lab_value(
            netuid=netuid,
            local_eval_available=mechanism.local_eval_available,
            deterministic_verifier=mechanism.deterministic_verifier,
            fresh_task_generation=mechanism.fresh_task_generation,
            feedback_latency_hours=(snap.feedback_latency_seconds or 3600) / 3600,
        )

        # 9. Score opportunity
        assessment = score_opportunity(
            snapshot=snap,
            mechanism=mechanism,
            reward=reward,
            difficulty_score=diff_score,
            difficulty_breakdown=diff_bd,
            lab_value_score=lab_score,
            lab_value_breakdown=lab_bd,
            current_miner_count=snap.emitting_miners or 0,
        )

        return snap, assessment, raw

    def _extract_economics(self, netuid: int, raw: dict) -> dict:
        """Extract economic data from raw scan results.

        SDK v11 data is primary. Taostats is supplementary.
        """
        sources = raw.get("sources", {})
        result = {
            "miner_pool_tao_day": 0.0,
            "alpha_price_tao": 0.0,
            "registration_burn": 0.0,
            "miner_incentives": [],
            "owner_share": None,
            "validator_share": None,
            "emitting_miners": None,
            "active_miners": None,
            "validators": None,
            "neuron_count": 256,
            "alpha_price": 0.0,
        }

        # Source 1: SDK (primary — verified working)
        if "sdk" in sources:
            sdk = sources["sdk"]

            # Registration burn
            if "burn" in sdk:
                try:
                    result["registration_burn"] = float(sdk["burn"])
                except (ValueError, TypeError):
                    pass

            # Subnet info
            if "subnet" in sdk:
                sub = sdk["subnet"]
                if "neuron_count" in sub:
                    result["neuron_count"] = sub["neuron_count"]

            # Metagraph ( richest data source )
            if "metagraph" in sdk:
                mg = sdk["metagraph"]
                if "price" in mg:
                    result["alpha_price_tao"] = mg["price"]
                    result["alpha_price"] = mg["price"]
                if "neurons" in mg:
                    result["neuron_count"] = mg["neurons"]

            # Derived metrics from neuron data
            if "incentive_shares" in sdk:
                result["miner_incentives"] = sdk["incentive_shares"]
            if "active_miners" in sdk:
                result["active_miners"] = sdk["active_miners"]
            if "emitting_miners" in sdk:
                result["emitting_miners"] = sdk["emitting_miners"]
            if "validators" in sdk:
                result["validators"] = sdk["validators"]

            # Calculate actual TAO-equivalent/day from emission + price
            if "metagraph" in sdk:
                mg = sdk["metagraph"]
                neuron_data = mg.get("neuron_data", [])
                if neuron_data and mg.get("price", 0) > 0:
                    total_alpha = sum(n.get("emission", 0) for n in neuron_data) / 1e9
                    alpha_price = mg["price"]
                    result["miner_pool_tao_day"] = total_alpha * alpha_price
                    result["alpha_price_tao"] = alpha_price

        # Source 2: Taostats (supplementary)
        if "taostats" in sources:
            ts = sources["taostats"]
            if isinstance(ts, dict) and "_error" not in ts:
                # Fill in any missing fields
                if not result["miner_pool_tao_day"]:
                    result["miner_pool_tao_day"] = float(ts.get("miner_emission", 0) or 0)

        return result

    def _build_snapshot(
        self,
        netuid: int,
        now: datetime,
        chain_econ: dict,
        mechanism: MechanismInfo,
        raw: dict,
        prev: BittensorOpportunitySnapshot | None,
    ) -> BittensorOpportunitySnapshot:
        """Build a BittensorOpportunitySnapshot from all available data."""
        name = mechanism.task_family
        for cfg_netuid, cfg in SUBNETS.items():
            if cfg_netuid == netuid:
                name = cfg.name
                break

        # Detect discrepancies
        flags = raw.get("flags", [])
        if mechanism.discrepancy_flags:
            flags.extend(mechanism.discrepancy_flags)

        return BittensorOpportunitySnapshot(
            observed_at=now,
            netuid=netuid,
            name=name,

            # Chain economics (from live SDK)
            alpha_price_tao=Decimal(str(chain_econ.get("alpha_price_tao", 0))),
            miner_pool_tao_equiv_day=Decimal(str(chain_econ.get("miner_pool_tao_day", 0))),
            owner_share=chain_econ.get("owner_share"),
            validator_share=chain_econ.get("validator_share"),

            registration_burn_tao=Decimal(str(chain_econ.get("registration_burn", 0))),
            emitting_miners=chain_econ.get("emitting_miners"),
            registered_neurons=chain_econ.get("neuron_count", 256),

            # Mechanism
            task_family=mechanism.task_family,
            scoring_type=mechanism.scoring_type,
            reward_mechanism=mechanism.reward_mechanism,
            submission_fee_tao=mechanism.submission_fee_tao,
            local_eval_available=mechanism.local_eval_available,
            deterministic_verifier=mechanism.deterministic_verifier,
            hidden_eval=mechanism.hidden_eval,
            fresh_task_generation=mechanism.fresh_task_generation,
            feedback_latency_seconds=mechanism.feedback_latency_seconds,

            # Provenance
            mechanism_source=mechanism.source,
            source_confidence=mechanism.source_confidence,
            chain_block=raw.get("chain_block", 0),
            discrepancy_flags=tuple(flags),

            # Raw
            raw_chain_data=raw,
        )

    def _generate_daily_report(
        self,
        ranked: list[OpportunityAssessment],
        raw_scans: dict,
    ) -> str:
        """Generate the daily BITTENSOR OPPORTUNITY REPORT."""
        lines = []
        lines.append("=" * 70)
        lines.append("BITTENSOR OPPORTUNITY REPORT")
        lines.append(f"Generated: {datetime.utcnow().isoformat()}")
        lines.append("=" * 70)
        lines.append("")

        if not ranked:
            lines.append("No subnets scanned.")
            return "\n".join(lines)

        # Section 1: Best thing to work on today
        lines.append("1. BEST THING TO WORK ON TODAY")
        lines.append("-" * 40)
        top = ranked[0]
        lines.append(f"   #{top.priority_rank} {top.name} (SN{top.netuid})")
        lines.append(f"   Recommendation: {top.recommendation}")
        lines.append(f"   Reason: {top.recommendation_reason}")
        lines.append(f"   Priority score: {top.priority_score:.3f}")
        lines.append(f"   Economic: {top.economic_score:.3f} | Lab: {top.lab_value:.3f} | Diff: {top.difficulty:.3f}")
        lines.append(f"   Expected: {top.expected_tao_day:.3f} TAO/day | P(top5): {top.p_top5:.2f}")
        lines.append("")

        # Section 2: Best offline experiment
        lines.append("2. BEST OFFLINE EXPERIMENT")
        lines.append("-" * 40)
        offline = [a for a in ranked if a.recommendation in ("OFFLINE_TRAIN", "CLONE_AND_REPLAY")]
        if offline:
            exp = offline[0]
            lines.append(f"   {exp.name} (SN{exp.netuid})")
            lines.append(f"   Action: {exp.recommendation}")
            lines.append(f"   Lab value: {exp.lab_value:.3f}")
        else:
            lines.append("   No strong offline targets found.")
        lines.append("")

        # Section 3: Best mainnet entry
        lines.append("3. BEST MAINNET ENTRY")
        lines.append("-" * 40)
        mainnet = [a for a in ranked if a.recommendation in ("REGISTER_SMALL", "LIVE_COMPETE")]
        if mainnet:
            entry = mainnet[0]
            lines.append(f"   {entry.name} (SN{entry.netuid})")
            lines.append(f"   Action: {entry.recommendation}")
            lines.append(f"   P(top5): {entry.p_top5:.2f} | Expected: {entry.expected_tao_day:.3f} TAO/day")
        else:
            lines.append("   No mainnet-ready targets.")
        lines.append("")

        # Section 4: Full ranking
        lines.append("4. FULL RANKING")
        lines.append("-" * 40)
        lines.append(f"   {'Rank':<5} {'Name':<15} {'SN':<5} {'Econ':<8} {'Lab':<8} {'Diff':<8} {'P5':<8} {'Rec':<20}")
        for a in ranked:
            lines.append(
                f"   {a.priority_rank:<5} {a.name:<15} {a.netuid:<5} "
                f"{a.economic_score:<8.3f} {a.lab_value:<8.3f} {a.difficulty:<8.3f} "
                f"{a.p_top5:<8.2f} {a.recommendation:<20}"
            )
        lines.append("")

        # Section 5: Protocol changes / flags
        lines.append("5. PROTOCOL CHANGES & FLAGS")
        lines.append("-" * 40)
        all_flags = []
        for a in ranked:
            # Check raw scan for flags
            raw = raw_scans.get(a.netuid, {})
            flags = raw.get("flags", [])
            if flags:
                all_flags.append(f"   SN{a.netuid} {a.name}: {', '.join(flags)}")
        if all_flags:
            lines.extend(all_flags)
        else:
            lines.append("   No flags.")
        lines.append("")

        # Section 6: Summary
        lines.append("6. SUMMARY")
        lines.append("-" * 40)
        rec_counts = {}
        for a in ranked:
            rec_counts[a.recommendation] = rec_counts.get(a.recommendation, 0) + 1
        for rec, count in sorted(rec_counts.items()):
            lines.append(f"   {rec}: {count}")
        lines.append("")

        lines.append("=" * 70)
        return "\n".join(lines)

    def get_latest_assessments(self) -> list[OpportunityAssessment]:
        return self._latest_assessments

    def get_snapshot_history(self, netuid: int) -> list[BittensorOpportunitySnapshot]:
        return self.store.get_history(netuid)
