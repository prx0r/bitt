"""SchoolWorld — meta-world for evolving allocation architectures.

A "school" is a capital allocation system: pools of strategies, each pool
with its own scoring dynamics, composed by a global allocator.

The world simulates a market with regime changes. The school's "action"
is to allocate capital across pools. The world applies market returns
and scores the allocation.

This world is the substrate for cogym's evo loop to evolve schools.
"""
from __future__ import annotations

import copy
import hashlib
import json
import random
from dataclasses import dataclass, field

from cogym_kernel.kernel.contracts import (ActionResult, ActionSpec, Metric,
                                MetricVector, WorldSpec)


# ---------------------------------------------------------------------------
# Fish (strategies) — fixed, known from literature
# ---------------------------------------------------------------------------

FISH = {
    "momentum-call":      {"type": "call",       "regime_sensitivity": {"bull": 1.3, "sideways": 0.8, "bear": 0.4}},
    "defensive-put":      {"type": "put",        "regime_sensitivity": {"bull": 0.6, "sideways": 0.9, "bear": 1.4}},
    "breakout-spread":    {"type": "call_spread", "regime_sensitivity": {"bull": 1.2, "sideways": 0.7, "bear": 0.5}},
    "mean-reversion-put": {"type": "put",        "regime_sensitivity": {"bull": 0.5, "sideways": 1.1, "bear": 1.2}},
    "volatility-condor":  {"type": "condor",     "regime_sensitivity": {"bull": 0.8, "sideways": 1.3, "bear": 0.6}},
}

# Default pool membership
DEFAULT_POOLS = {
    "calls":   ["momentum-call"],
    "puts":    ["defensive-put", "mean-reversion-put"],
    "spreads": ["breakout-spread", "volatility-condor"],
}

# Regime market returns (what the market does)
REGIME_RETURNS = {
    "calm_bull":     0.008,
    "normal_bull":   0.005,
    "normal_sideways": -0.001,
    "calm_sideways":  0.002,
    "elevated_bear": -0.015,
    "crisis_bear":   -0.035,
    "elevated_bull":  0.003,
    "crisis_sideways": -0.008,
}

REGIME_SEQUENCE = [
    "calm_bull", "calm_bull", "normal_bull", "normal_bull",
    "normal_sideways", "calm_sideways", "normal_bull",
    "elevated_bear", "crisis_bear", "elevated_bear",
    "normal_sideways", "calm_bull", "normal_bull",
    "elevated_bull", "crisis_sideways", "elevated_bear",
    "normal_sideways", "calm_bull", "calm_bull", "normal_bull",
]


def _fish_return(fish_type: str, regime: str, market_return: float,
                 fish_perf: float) -> float:
    """Compute a fish's return given regime and its performance factor."""
    level, trend = regime.split("_", 1) if "_" in regime else (regime, "sideways")
    trend_key = trend

    type_mult = {
        "call": 1.0 if market_return > 0 else -0.6,
        "put": -0.6 if market_return > 0 else 1.2,
        "call_spread": 0.8 if market_return > 0 else -0.4,
        "condor": 0.3 - abs(market_return) * 5,  # condors lose on big moves
    }
    m = type_mult.get(fish_type, 1.0)

    from cogym_kernel.worlds.school.search_space import SCHOOL_FISH
    sensitivity = SCHOOL_FISH.get(fish_type, {}).get("regime_sensitivity", {}).get(trend_key, 1.0)

    return market_return * m * sensitivity * fish_perf


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

@dataclass
class SchoolState:
    """State of a school evaluation episode."""
    step: int = 0
    regime_idx: int = 0
    capital: float = 1000.0
    pool_capitals: dict = field(default_factory=dict)  # pool_name -> capital
    fish_capitals: dict = field(default_factory=dict)  # fish_id -> capital
    equity_curve: list = field(default_factory=list)
    trades: list = field(default_factory=list)
    regime_history: list = field(default_factory=list)


# ---------------------------------------------------------------------------
# SchoolWorld
# ---------------------------------------------------------------------------

class SchoolWorld:
    """Meta-world for school evaluation.

    Actions are allocation decisions (how much capital to each pool/fish).
    The world applies market returns and scores the school.
    """

    def __init__(self, n_steps: int = 20, initial_capital: float = 1000.0,
                 pools: dict | None = None):
        self.n_steps = n_steps
        self.initial_capital = initial_capital
        self.pools = pools or copy.deepcopy(DEFAULT_POOLS)
        self._spec = None

    @property
    def world_spec(self) -> WorldSpec:
        if self._spec is None:
            pool_hash = hashlib.sha256(json.dumps(self.pools, sort_keys=True).encode()).hexdigest()[:12]
            self._spec = WorldSpec(
                world_kind="school", version="1",
                instance_set_hash=f"school-pools-{pool_hash}",
                environment_hash="regime-sequence-v1",
                oracle_hash="deterministic-returns")
        return self._spec

    @property
    def worldpack_id(self) -> str:
        from cogym_kernel.kernel.ids import content_id
        return content_id("wp", {"kind": "school", "pools": self.pools})

    def reset(self, *, instance_id: str, seed: int) -> SchoolState:
        rng = random.Random(seed)
        state = SchoolState(capital=self.initial_capital)
        # Equal initial allocation across pools
        n_pools = len(self.pools)
        for pool_name in self.pools:
            state.pool_capitals[pool_name] = self.initial_capital / n_pools
        # Equal initial allocation across fish within pools
        for pool_name, fish_ids in self.pools.items():
            pool_cap = state.pool_capitals[pool_name]
            for fid in fish_ids:
                state.fish_capitals[fid] = pool_cap / len(fish_ids)
        state.equity_curve = [self.initial_capital]
        return state

    def observe(self, state: SchoolState) -> dict:
        """Observe current state: pool capitals, regime, step."""
        regime = REGIME_SEQUENCE[state.regime_idx % len(REGIME_SEQUENCE)]
        return {
            "step": state.step,
            "n_steps": self.n_steps,
            "regime": regime,
            "pool_capitals": dict(state.pool_capitals),
            "fish_capitals": dict(state.fish_capitals),
            "total_capital": state.capital,
            "equity_curve": state.equity_curve[-5:],
        }

    def actions(self, state: SchoolState) -> tuple[ActionSpec, ...]:
        """Available actions: reallocate capital across pools."""
        return (ActionSpec(
            kind="reallocate",
            payload={"pool_capitals": state.pool_capitals},
            executor_kind="deterministic",
        ),)

    def apply(self, state: SchoolState, action: ActionSpec,
              result: ActionResult) -> SchoolState:
        """Apply market return based on current allocation."""
        regime = REGIME_SEQUENCE[state.regime_idx % len(REGIME_SEQUENCE)]
        market_return = REGIME_RETURNS.get(regime, 0.0)

        # Compute returns for each fish
        total_pnl = 0.0
        for pool_name, fish_ids in self.pools.items():
            for fid in fish_ids:
                fish_cap = state.fish_capitals.get(fid, 0)
                if fish_cap <= 0:
                    continue
                fish_info = FISH.get(fid, {})
                fish_type = fish_info.get("type", "call")
                fish_perf = 1.0  # could be evolved per fish
                fr = _fish_return(fish_type, regime, market_return, fish_perf)
                pnl = fish_cap * fr
                state.fish_capitals[fid] = fish_cap + pnl
                total_pnl += pnl
                state.trades.append({
                    "fish_id": fid, "regime": regime,
                    "market_return": market_return, "fish_return": fr,
                    "pnl": pnl, "step": state.step,
                })

        # Update pool capitals from fish
        for pool_name, fish_ids in self.pools.items():
            state.pool_capitals[pool_name] = sum(
                state.fish_capitals.get(fid, 0) for fid in fish_ids)

        state.capital += total_pnl
        state.equity_curve.append(state.capital)
        state.regime_history.append(regime)
        state.step += 1
        state.regime_idx += 1

        return state

    def terminal(self, state: SchoolState) -> bool:
        return state.step >= self.n_steps

    def score(self, state: SchoolState) -> MetricVector:
        """Score the school: return, sharpe, max drawdown."""
        if len(state.equity_curve) < 2:
            return MetricVector(metrics=())

        returns = [(state.equity_curve[i] / state.equity_curve[i - 1]) - 1
                   for i in range(1, len(state.equity_curve))]
        total_return = (state.capital / self.initial_capital) - 1.0

        mean_r = sum(returns) / len(returns) if returns else 0
        std_r = (sum((r - mean_r) ** 2 for r in returns) / max(len(returns) - 1, 1)) ** 0.5
        sharpe = mean_r / std_r if std_r > 0 else 0

        peak = self.initial_capital
        max_dd = 0.0
        for eq in state.equity_curve:
            peak = max(peak, eq)
            dd = (peak - eq) / peak if peak > 0 else 0
            max_dd = max(max_dd, dd)

        return MetricVector(metrics=(
            Metric("total_return", total_return, "max"),
            Metric("sharpe", sharpe, "max"),
            Metric("max_drawdown", -max_dd, "max"),  # less negative = better
            Metric("final_capital", state.capital, "max"),
            Metric("n_trades", len(state.trades), "min"),
        ))
