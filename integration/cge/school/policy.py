"""School policy factory — converts CandidateArtifact config into an allocator.

The school's "policy" is an allocation function:
  observe(pool_capitals, regime) → {pool: new_capital}

This is what the cogym runner calls as `policy.act()`.
"""
from __future__ import annotations

from dataclasses import dataclass

from cogym_kernel.kernel.contracts import ActionSpec, PolicyDecision


@dataclass
class SchoolPolicy:
    """Allocates capital across pools based on regime + config."""
    config: dict
    pools: dict  # pool_name -> [fish_ids]

    def initialize(self, world_spec):
        pass  # school policy is stateless

    def act(self, obs: dict, actions: tuple[ActionSpec, ...],
            pstate=None) -> PolicyDecision:
        """Decide how to allocate capital across pools."""
        regime = obs.get("regime", "normal_sideways")
        pool_capitals = obs.get("pool_capitals", {})
        total = obs.get("total_capital", 1000.0)

        gc = self.config.get("global_config", {})
        base_splits = gc.get("base_splits", {})
        regime_adj = gc.get("regime_adjustments", {})
        min_pool_pct = gc.get("min_pool_pct", 0.05)

        # Determine regime level for adjustment lookup
        level = regime.split("_")[0] if "_" in regime else "normal"
        level_adj = regime_adj.get(level, {})

        # Compute new splits: base × regime adjustment
        raw = {}
        for pool_name in base_splits:
            base = base_splits[pool_name]
            adj = level_adj.get(pool_name, 1.0)
            raw[pool_name] = base * adj

        # Normalize
        total_raw = sum(raw.values()) or 1.0
        new_splits = {k: max(min_pool_pct, v / total_raw) for k, v in raw.items()}
        total_split = sum(new_splits.values())
        new_splits = {k: v / total_split for k, v in new_splits.items()}

        # Convert to capital allocations
        new_capitals = {k: total * v for k, v in new_splits.items()}

        # Reallocate fish within each pool based on scoring weights
        pc = self.config.get("pool_configs", {})
        for pool_name, fish_ids in self.pools.items():
            pool_cap = new_capitals.get(pool_name, 0)
            pool_cfg = pc.get(pool_name, {})
            # Simple proportional scoring (in real system, this queries pool HydraDB)
            n = len(fish_ids)
            for fid in fish_ids:
                new_capitals[f"{pool_name}:{fid}"] = pool_cap / n

        return PolicyDecision(
            action=ActionSpec(
                kind="reallocate",
                payload={"new_capitals": new_capitals, "new_splits": new_splits},
                executor_kind="deterministic",
            ),
            rationale=f"regime={regime} level={level} splits={new_splits}",
            confidence=0.7,
        )


def school_policy_factory(candidate) -> SchoolPolicy:
    """Create a SchoolPolicy from a CandidateArtifact."""
    from .search_space import POOL_MEMBERSHIP
    return SchoolPolicy(
        config=candidate.config,
        pools=POOL_MEMBERSHIP,
    )
