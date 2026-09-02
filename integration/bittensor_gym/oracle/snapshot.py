"""BittensorOpportunitySnapshot — immutable record of what Moltwork believed about a subnet at a point in time.

One snapshot per subnet per crawl. Never overwrite. Hydra reconstructs history.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class BittensorOpportunitySnapshot:
    """Immutable snapshot of a subnet's state and opportunity assessment.

    Created once per scanner crawl. Never mutated. Hydra stores all versions.
    """
    observed_at: datetime
    netuid: int
    name: str

    # ─── Chain economics ─────────────────────────────────────────────
    alpha_price_tao: Decimal = Decimal("0")
    miner_pool_alpha_day: Decimal | None = None
    miner_pool_tao_equiv_day: Decimal | None = None
    owner_share: float | None = None
    validator_share: float | None = None
    miner_share: float | None = None

    # Registration dynamics
    registration_burn_tao: Decimal = Decimal("0")
    collateral_lock_share: float = 0.0
    min_burn_tao: Decimal | None = None
    max_burn_tao: Decimal | None = None
    burn_half_life_blocks: int | None = None
    burn_increase_mult: float | None = None

    # Neuron topology
    neuron_capacity: int = 256
    registered_neurons: int = 0
    validator_count: int = 0
    emitting_miners: int | None = None
    benchmark_scored_competitors: int | None = None

    tempo_blocks: int = 100
    immunity_blocks: int | None = None

    # ─── Mechanism ───────────────────────────────────────────────────
    task_family: str = ""
    scoring_type: str = ""           # ranked, proportional, winner_take_all, tournament
    reward_mechanism: str = ""       # description of how rewards flow
    payout_curve: dict = field(default_factory=dict)  # explicit payout shares
    eligibility_rules: dict = field(default_factory=dict)
    submission_fee_tao: Decimal = Decimal("0")
    cooldown_seconds: int | None = None
    feedback_latency_seconds: int | None = None

    # ─── Environment ─────────────────────────────────────────────────
    local_eval_available: bool = False
    replay_available: bool = False
    deterministic_verifier: bool = False
    hidden_eval: bool = False
    fresh_task_generation: bool = False

    gpu_required: bool = False
    min_vram_gb: float | None = None
    min_ram_gb: float | None = None
    min_storage_gb: float | None = None

    api_cost_estimate_usd_episode: Decimal | None = None
    estimated_compute_usd_episode: Decimal | None = None

    # ─── Repository health ───────────────────────────────────────────
    repo_url: str = ""
    repo_last_commit_at: datetime | None = None
    commits_30d: int | None = None
    protocol_version: str | None = None

    # ─── Reward distribution analysis ────────────────────────────────
    incentive_shares: tuple[float, ...] = ()  # normalized miner shares
    hhi: float = 0.0                          # Herfindahl-Hirschman Index
    effective_earners: float = 0.0            # 1/HHI
    top1_share: float = 0.0
    top3_share: float = 0.0
    top5_share: float = 0.0
    top10_share: float = 0.0

    # ─── Attainable reward ──────────────────────────────────────────
    p_any_reward: float = 0.0
    p_top10: float = 0.0
    p_top5: float = 0.0
    p_top3: float = 0.0
    p_champion: float = 0.0
    expected_tao_day: float = 0.0
    p05_tao_day: float = 0.0
    p50_tao_day: float = 0.0
    p95_tao_day: float = 0.0

    # ─── Cost model ─────────────────────────────────────────────────
    cost_to_attempt_tao: Decimal = Decimal("0")  # total cost to enter
    cost_breakdown: dict = field(default_factory=dict)

    # ─── Alpha risk ─────────────────────────────────────────────────
    alpha_volatility_7d: float = 0.0
    alpha_volatility_30d: float = 0.0
    alpha_pool_depth: Decimal | None = None
    alpha_volume_24h: Decimal | None = None
    stress_test_spot: float = 0.0
    stress_test_neg20: float = 0.0
    stress_test_neg40: float = 0.0
    stress_test_neg60: float = 0.0

    # ─── Difficulty ─────────────────────────────────────────────────
    difficulty_score: float = 0.0  # 0-1, higher = harder
    difficulty_breakdown: dict = field(default_factory=dict)

    # ─── Lab value ──────────────────────────────────────────────────
    lab_value: float = 0.0  # 0-1, higher = better training environment
    lab_value_breakdown: dict = field(default_factory=dict)

    # ─── Opportunity assessment ─────────────────────────────────────
    economic_score: float = 0.0
    capital_risk: float = 0.0
    recommendation: str = "WATCH"  # from spec's allowed states

    # ─── Provenance ─────────────────────────────────────────────────
    mechanism_source: str = ""       # where we got mechanism info
    mechanism_source_commit: str | None = None
    chain_block: int = 0
    source_confidence: float = 0.0   # 0-1, how confident in our data
    discrepancy_flags: list[str] = field(default_factory=list)

    # ─── Raw data (for debugging / future re-analysis) ─────────────
    raw_chain_data: dict = field(default_factory=dict)
    raw_mechanism_data: dict = field(default_factory=dict)

    @property
    def snapshot_id(self) -> str:
        """Deterministic ID for this snapshot."""
        payload = f"{self.observed_at.isoformat()}:{self.netuid}:{self.chain_block}"
        return hashlib.sha256(payload.encode()).hexdigest()[:16]

    def to_dict(self) -> dict:
        """Serialize to JSON-compatible dict."""
        d = {}
        for k, v in self.__dict__.items():
            if isinstance(v, Decimal):
                d[k] = str(v)
            elif isinstance(v, datetime):
                d[k] = v.isoformat()
            elif isinstance(v, tuple):
                d[k] = list(v)
            else:
                d[k] = v
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, default=str)

    @classmethod
    def from_dict(cls, d: dict) -> BittensorOpportunitySnapshot:
        """Deserialize from dict."""
        d = dict(d)
        for k in ("observed_at", "repo_last_commit_at"):
            if k in d and isinstance(d[k], str):
                d[k] = datetime.fromisoformat(d[k])
        for k in ("alpha_price_tao", "registration_burn_tao", "submission_fee_tao",
                   "min_burn_tao", "max_burn_tao", "cost_to_attempt_tao",
                   "api_cost_estimate_usd_episode", "estimated_compute_usd_episode",
                   "alpha_pool_depth", "alpha_volume_24h"):
            if k in d and isinstance(d[k], str):
                d[k] = Decimal(d[k])
        if "incentive_shares" in d and isinstance(d["incentive_shares"], list):
            d["incentive_shares"] = tuple(d["incentive_shares"])
        if "discrepancy_flags" in d and isinstance(d["discrepancy_flags"], list):
            d["discrepancy_flags"] = tuple(d["discrepancy_flags"])
        # Filter to known fields
        known = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in d.items() if k in known})
