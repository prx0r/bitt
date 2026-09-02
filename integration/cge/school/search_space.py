"""School search space — declares what parameters evolve and their ranges.

The school config has two levels:
1. Pool configs: per-pool scoring weights (how pool HydraDB ranks fish)
2. Global config: pool splits + regime adjustments

These map directly to the ArchitectureGenome in fleece.
"""
from __future__ import annotations


# Fish registry (fixed — not evolved)
SCHOOL_FISH = {
    "momentum-call":      {"type": "call",       "regime_sensitivity": {"bull": 1.3, "sideways": 0.8, "bear": 0.4}},
    "defensive-put":      {"type": "put",        "regime_sensitivity": {"bull": 0.6, "sideways": 0.9, "bear": 1.4}},
    "breakout-spread":    {"type": "call_spread", "regime_sensitivity": {"bull": 1.2, "sideways": 0.7, "bear": 0.5}},
    "mean-reversion-put": {"type": "put",        "regime_sensitivity": {"bull": 0.5, "sideways": 1.1, "bear": 1.2}},
    "volatility-condor":  {"type": "condor",     "regime_sensitivity": {"bull": 0.8, "sideways": 1.3, "bear": 0.6}},
}

# Pool types (fixed — not evolved)
POOL_TYPES = ["calls", "puts", "spreads"]

# Pool membership (fixed — not evolved)
POOL_MEMBERSHIP = {
    "calls":   ["momentum-call"],
    "puts":    ["defensive-put", "mean-reversion-put"],
    "spreads": ["breakout-spread", "volatility-condor"],
}


# ---------------------------------------------------------------------------
# Search space declaration (what evolves)
# ---------------------------------------------------------------------------

SCHOOL_SEARCH_SPACE = {
    # --- Pool scoring weights (per pool type) ---
    # How the pool HydraDB ranks fish: score = w_wr*wr + w_pnl*pnl + w_sharpe*sharpe
    "pool_calls_score_win_rate":   {"min": 0.10, "max": 0.60, "step": 0.05},
    "pool_calls_score_pnl":       {"min": 0.10, "max": 0.60, "step": 0.05},
    "pool_calls_score_sharpe":    {"min": 0.05, "max": 0.40, "step": 0.05},
    "pool_calls_score_consistency": {"min": 0.02, "max": 0.30, "step": 0.02},
    "pool_calls_score_recency":   {"min": 0.01, "max": 0.20, "step": 0.01},

    "pool_puts_score_win_rate":   {"min": 0.10, "max": 0.60, "step": 0.05},
    "pool_puts_score_pnl":       {"min": 0.10, "max": 0.60, "step": 0.05},
    "pool_puts_score_sharpe":    {"min": 0.05, "max": 0.40, "step": 0.05},
    "pool_puts_score_consistency": {"min": 0.02, "max": 0.30, "step": 0.02},
    "pool_puts_score_recency":   {"min": 0.01, "max": 0.20, "step": 0.01},

    "pool_spreads_score_win_rate": {"min": 0.10, "max": 0.60, "step": 0.05},
    "pool_spreads_score_pnl":     {"min": 0.10, "max": 0.60, "step": 0.05},
    "pool_spreads_score_sharpe":  {"min": 0.05, "max": 0.40, "step": 0.05},
    "pool_spreads_score_consistency": {"min": 0.02, "max": 0.30, "step": 0.02},
    "pool_spreads_score_recency": {"min": 0.01, "max": 0.20, "step": 0.01},

    # --- Global pool splits ---
    "global_split_calls":   {"min": 0.10, "max": 0.60, "step": 0.05},
    "global_split_puts":    {"min": 0.10, "max": 0.60, "step": 0.05},
    "global_split_spreads": {"min": 0.10, "max": 0.60, "step": 0.05},

    # --- Regime adjustments (multiplier on base split) ---
    "adj_calm_newbie":   {"min": 0.4, "max": 1.5, "step": 0.1},
    "adj_calm_elite":    {"min": 0.8, "max": 2.0, "step": 0.1},
    "adj_elevated_newbie": {"min": 0.5, "max": 1.8, "step": 0.1},
    "adj_elevated_elite":  {"min": 0.3, "max": 1.2, "step": 0.1},
    "adj_crisis_newbie":  {"min": 0.8, "max": 2.5, "step": 0.1},
    "adj_crisis_elite":   {"min": 0.2, "max": 1.0, "step": 0.1},

    # --- Thresholds ---
    "min_pool_pct": {"min": 0.02, "max": 0.15, "step": 0.01},
    "stale_min_pct": {"min": 0.005, "max": 0.05, "step": 0.005},
}


def config_from_flat(flat: dict) -> dict:
    """Convert flat search space dict to nested school config."""
    pool_configs = {}
    for pool in POOL_TYPES:
        prefix = f"pool_{pool}_"
        pool_configs[pool] = {
            "score_win_rate": flat.get(f"{prefix}score_win_rate", 0.35),
            "score_pnl": flat.get(f"{prefix}score_pnl", 0.30),
            "score_sharpe": flat.get(f"{prefix}score_sharpe", 0.20),
            "score_consistency": flat.get(f"{prefix}score_consistency", 0.10),
            "score_recency": flat.get(f"{prefix}score_recency", 0.05),
        }

    # Normalize splits to sum to 1.0
    splits = {
        "calls": flat.get("global_split_calls", 0.4),
        "puts": flat.get("global_split_puts", 0.3),
        "spreads": flat.get("global_split_spreads", 0.3),
    }
    total = sum(splits.values()) or 1.0
    splits = {k: v / total for k, v in splits.items()}

    return {
        "pool_configs": pool_configs,
        "global_config": {
            "base_splits": splits,
            "regime_adjustments": {
                "calm": {
                    "calls": flat.get("adj_calm_newbie", 0.8),
                    "puts": 1.0,
                    "spreads": flat.get("adj_calm_elite", 1.2),
                },
                "elevated": {
                    "calls": flat.get("adj_elevated_newbie", 1.1),
                    "puts": 1.0,
                    "spreads": flat.get("adj_elevated_elite", 0.8),
                },
                "crisis": {
                    "calls": flat.get("adj_crisis_newbie", 1.3),
                    "puts": 1.0,
                    "spreads": flat.get("adj_crisis_elite", 0.7),
                },
            },
            "min_pool_pct": flat.get("min_pool_pct", 0.05),
            "stale_min_pct": flat.get("stale_min_pct", 0.02),
        },
    }


def flat_from_config(config: dict) -> dict:
    """Convert nested school config back to flat search space dict."""
    flat = {}
    pool_configs = config.get("pool_configs", {})
    for pool in POOL_TYPES:
        pc = pool_configs.get(pool, {})
        prefix = f"pool_{pool}_"
        flat[f"{prefix}score_win_rate"] = pc.get("score_win_rate", 0.35)
        flat[f"{prefix}score_pnl"] = pc.get("score_pnl", 0.30)
        flat[f"{prefix}score_sharpe"] = pc.get("score_sharpe", 0.20)
        flat[f"{prefix}score_consistency"] = pc.get("score_consistency", 0.10)
        flat[f"{prefix}score_recency"] = pc.get("score_recency", 0.05)

    gc = config.get("global_config", {})
    splits = gc.get("base_splits", {})
    flat["global_split_calls"] = splits.get("calls", 0.4)
    flat["global_split_puts"] = splits.get("puts", 0.3)
    flat["global_split_spreads"] = splits.get("spreads", 0.3)

    adj = gc.get("regime_adjustments", {})
    flat["adj_calm_newbie"] = adj.get("calm", {}).get("calls", 0.8)
    flat["adj_calm_elite"] = adj.get("calm", {}).get("spreads", 1.2)
    flat["adj_elevated_newbie"] = adj.get("elevated", {}).get("calls", 1.1)
    flat["adj_elevated_elite"] = adj.get("elevated", {}).get("spreads", 0.8)
    flat["adj_crisis_newbie"] = adj.get("crisis", {}).get("calls", 1.3)
    flat["adj_crisis_elite"] = adj.get("crisis", {}).get("spreads", 0.7)

    flat["min_pool_pct"] = gc.get("min_pool_pct", 0.05)
    flat["stale_min_pct"] = gc.get("stale_min_pct", 0.02)

    return flat
