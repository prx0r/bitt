"""Strategy Framework — define edges, backtest, paper trade.

Like SN88 but for our own strategies. Each edge is a structured definition
that can be backtested, paper traded, and compared.

Usage:
  # Define a strategy
  strategy = Strategy("low_vol_alpha", factors={"vol_7d": -0.17}, top_quintile=True)
  
  # Backtest it
  result = backtest(strategy, start="2026-07-23", end="2026-09-03")
  
  # Paper trade live
  signal = strategy.generate_signal(current_data)
"""
import sqlite3
import json
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Optional


MDB = Path("/root/bitt/market.duckdb")
STRATEGIES_DIR = Path("/root/bitt/trading/strategies")
STRATEGIES_DIR.mkdir(exist_ok=True)


@dataclass
class FactorDef:
    """Definition of a single factor."""
    name: str
    column: str          # Column name in observation data
    direction: str       # "asc" (low = good) or "desc" (high = good)
    weight: float = 1.0  # Weight in composite signal
    lookback: int = 168  # Hours to look back (168 = 7d)
    normalize: bool = True  # Z-score normalize


@dataclass
class StrategyDef:
    """Complete strategy definition."""
    name: str
    description: str
    factors: list[FactorDef]
    top_quintile_pct: float = 0.2   # Top 20% to go long
    bottom_quintile_pct: float = 0.2  # Bottom 20% to short
    hold_period_hours: int = 24     # How long to hold
    min_observations: int = 100     # Minimum data points needed
    universe: str = "all"           # "all", "value", "growth", etc.
    
    # Metadata
    author: str = "system"
    created: str = ""
    hypothesis: str = ""  # What we believe and why
    status: str = "draft"  # draft, backtested, paper_trading, live, archived
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)
    
    @classmethod
    def from_json(cls, json_str: str) -> "StrategyDef":
        data = json.loads(json_str)
        factors = [FactorDef(**f) for f in data.pop("factors", [])]
        return cls(factors=factors, **data)


# === PREDEFINED STRATEGIES ===

STRATEGIES = {
    "low_vol_alpha": StrategyDef(
        name="low_vol_alpha",
        description="Buy lowest-volatility subnets. Volatility is the strongest predictor (IC=-0.17).",
        factors=[
            FactorDef(name="vol_7d", column="vol_7d", direction="asc", weight=3.0, lookback=168),
        ],
        hypothesis="Low volatility subnets are stable, paying regularly. High vol = instability/dying.",
        status="backtested",
    ),
    
    "low_vol_active": StrategyDef(
        name="low_vol_active",
        description="Low vol + high active ratio. Calm subnets with miners actually showing up.",
        factors=[
            FactorDef(name="vol_7d", column="vol_7d", direction="asc", weight=3.0, lookback=168),
            FactorDef(name="active_ratio", column="active_ratio", direction="desc", weight=1.0, lookback=0),
        ],
        hypothesis="Alive subnets with low volatility outperform.",
        status="backtested",
    ),
    
    "anti_yield_trap": StrategyDef(
        name="anti_yield_trap",
        description="AVOID high yield per neuron. The market exploits yield chasers.",
        factors=[
            FactorDef(name="vol_7d", column="vol_7d", direction="asc", weight=3.0, lookback=168),
            FactorDef(name="emit_per_neuron", column="emit_per_neuron", direction="asc", weight=2.0, lookback=0),
        ],
        hypothesis="High yield attracts miners → dilution → negative returns. Short high-yield.",
        status="backtested",
    ),
    
    "distributed_value": StrategyDef(
        name="distributed_value",
        description="Low HHI (distributed emissions) + low vol + high active ratio.",
        factors=[
            FactorDef(name="vol_7d", column="vol_7d", direction="asc", weight=3.0, lookback=168),
            FactorDef(name="hhi_emit", column="hhi_emit", direction="asc", weight=2.0, lookback=0),
            FactorDef(name="active_ratio", column="active_ratio", direction="desc", weight=1.0, lookback=0),
        ],
        hypothesis="Distributed, calm, alive subnets are the real value.",
        status="backtested",
    ),
    
    "established_quality": StrategyDef(
        name="established_quality",
        description="Higher price + low vol + high active ratio. Bluechip quality.",
        factors=[
            FactorDef(name="price", column="price", direction="desc", weight=1.0, lookback=0),
            FactorDef(name="vol_7d", column="vol_7d", direction="asc", weight=2.0, lookback=168),
            FactorDef(name="active_ratio", column="active_ratio", direction="desc", weight=1.0, lookback=0),
        ],
        hypothesis="Established subnets with quality fundamentals outperform.",
        status="backtested",
    ),
}


def calculate_signal(observations: list[dict], strategy: StrategyDef) -> list[dict]:
    """Calculate composite signal for each observation."""
    for o in observations:
        signal = 0
        for factor in strategy.factors:
            val = o.get(factor.column, 0)
            # Direction: "asc" means low values are good (positive signal)
            # "desc" means high values are good
            if factor.direction == "asc":
                signal += -val * factor.weight  # Negate: low = good
            else:
                signal += val * factor.weight
        o["signal"] = signal
    return observations


def evaluate_strategy(observations: list[dict], strategy: StrategyDef) -> dict:
    """Evaluate a strategy on observation data."""
    if len(observations) < strategy.min_observations:
        return {"error": f"Insufficient data: {len(observations)} < {strategy.min_observations}"}
    
    # Calculate signals
    observations = calculate_signal(observations, strategy)
    
    # Sort by signal
    observations.sort(key=lambda x: x["signal"], reverse=True)
    
    # Split into quintiles
    n = len(observations)
    top_n = int(n * strategy.top_quintile_pct)
    bot_n = int(n * strategy.bottom_quintile_pct)
    
    top_q = observations[:top_n]
    bot_q = observations[-bot_n:]
    
    # Metrics
    avg_top = sum(o["fwd_return"] for o in top_q) / len(top_q)
    avg_bot = sum(o["fwd_return"] for o in bot_q) / len(bot_q)
    win_top = len([o for o in top_q if o["fwd_return"] > 0]) / len(top_q)
    win_bot = len([o for o in bot_q if o["fwd_return"] > 0]) / len(bot_q)
    
    # Sharpe (simplified)
    returns_top = [o["fwd_return"] for o in top_q]
    avg_r = sum(returns_top) / len(returns_top)
    std_r = (sum((r - avg_r)**2 for r in returns_top) / len(returns_top)) ** 0.5
    sharpe = avg_r / std_r if std_r > 0 else 0
    
    # Max drawdown
    cumulative = 1.0
    peak = 1.0
    max_dd = 0
    for r in returns_top:
        cumulative *= (1 + r)
        if cumulative > peak:
            peak = cumulative
        dd = (peak - cumulative) / peak
        if dd > max_dd:
            max_dd = dd
    
    # Factor ICs
    factor_ics = {}
    for factor in strategy.factors:
        vals = [o[factor.column] for o in observations]
        rets = [o["fwd_return"] for o in observations]
        factor_ics[factor.name] = spearman_ic(vals, rets)
    
    return {
        "strategy": strategy.name,
        "n_observations": n,
        "long_return": round(avg_top, 4),
        "short_return": round(avg_bot, 4),
        "spread": round(avg_top - avg_bot, 4),
        "long_win_rate": round(win_top, 4),
        "short_win_rate": round(win_bot, 4),
        "sharpe": round(sharpe, 4),
        "max_drawdown": round(max_dd, 4),
        "annualized": round((1 + avg_top) ** (365 * 24 // strategy.hold_period_hours) - 1, 4),
        "factor_ics": factor_ics,
        "hold_period_hours": strategy.hold_period_hours,
    }


def spearman_ic(a, b):
    n = len(a)
    if n < 10: return 0
    ra = sorted(range(n), key=lambda i: a[i])
    rb = sorted(range(n), key=lambda i: b[i])
    ranks_a = [0]*n; ranks_b = [0]*n
    for r,i in enumerate(ra): ranks_a[i]=r
    for r,i in enumerate(rb): ranks_b[i]=r
    m_a=sum(ranks_a)/n; m_b=sum(ranks_b)/n
    cov=sum((ranks_a[i]-m_a)*(ranks_b[i]-m_b) for i in range(n))
    s_a=(sum((x-m_a)**2 for x in ranks_a)/n)**0.5
    s_b=(sum((x-m_b)**2 for x in ranks_b)/n)**0.5
    return cov/(n*s_a*s_b) if s_a>0 and s_b>0 else 0


def build_observations() -> list[dict]:
    """Build observation dataset from price + metagraph data."""
    conn = sqlite3.connect(str(MDB))
    conn.row_factory = sqlite3.Row
    
    # Get subnets with both price and metagraph
    price_netuids = conn.execute(
        "SELECT DISTINCT netuid FROM pool_state WHERE alpha_price > 0 GROUP BY netuid HAVING COUNT(*) > 50"
    ).fetchall()
    price_netuids = [r['netuid'] for r in price_netuids]
    
    mg_netuids = conn.execute("SELECT DISTINCT netuid FROM subnet_metrics_live").fetchall()
    mg_netuids = [r['netuid'] for r in mg_netuids]
    common = list(set(price_netuids) & set(mg_netuids))
    
    # Get metagraph features
    mg_features = {}
    for netuid in common:
        mg = conn.execute(
            "SELECT * FROM subnet_metrics_live WHERE netuid = ? ORDER BY block DESC LIMIT 1",
            (netuid,)
        ).fetchone()
        if mg:
            mg_features[netuid] = {k: (mg[k] or 0) for k in mg.keys() if k not in ('block', 'netuid', 'owner')}
    
    # Get neuron features
    neuron_features = {}
    for netuid in common:
        neurons = conn.execute(
            "SELECT * FROM metagraph_snapshot WHERE netuid = ?", (netuid,)
        ).fetchall()
        if not neurons: continue
        
        emissions = [n['emission'] for n in neurons if n['emission'] > 0]
        stakes = [n['stake'] for n in neurons if n['stake'] > 0]
        if not emissions: continue
        
        total_emit = sum(emissions)
        total_stake = sum(stakes)
        sorted_e = sorted(emissions, reverse=True)
        
        neuron_features[netuid] = {
            "emit_per_neuron": total_emit / max(len(emissions), 1),
            "active_ratio": len([n for n in neurons if n['active']]) / max(len(neurons), 1),
            "emit_ratio": len(emissions) / max(len(neurons), 1),
            "top1_emit": sorted_e[0] / total_emit if total_emit > 0 else 0,
            "top5_emit": sum(sorted_e[:5]) / total_emit if total_emit > 0 else 0,
            "hhi_emit": sum((e/total_emit)**2 for e in emissions) if total_emit > 0 else 1,
        }
    
    conn.close()
    
    # Build observations
    conn2 = sqlite3.connect(str(MDB))
    observations = []
    
    for netuid in common:
        if netuid not in neuron_features: continue
        
        prices = conn2.execute(
            "SELECT alpha_price FROM pool_state WHERE netuid = ? AND alpha_price > 0 ORDER BY timestamp",
            (netuid,)
        ).fetchall()
        price_list = [p[0] for p in prices]
        if len(price_list) < 100: continue
        
        nf = neuron_features[netuid]
        mg = mg_features.get(netuid, {})
        
        for i in range(48, len(price_list) - 24):
            entry = price_list[i]
            fwd = price_list[i + 24]
            fwd_return = (fwd - entry) / entry if entry > 0 else 0
            
            window = price_list[max(0,i-168):i]
            if len(window) > 10:
                rets = [(window[j] - window[j-1]) / window[j-1] for j in range(1, len(window)) if window[j-1] > 0]
                vol_7d = (sum(r**2 for r in rets) / len(rets)) ** 0.5 if rets else 0
            else:
                vol_7d = 0
            
            observations.append({
                "netuid": netuid, "fwd_return": fwd_return,
                "vol_7d": vol_7d, "price": entry,
                **nf, **{k: v for k, v in mg.items() if isinstance(v, (int, float))},
            })
    
    conn2.close()
    return observations


if __name__ == "__main__":
    print("=== Strategy Framework ===\n")
    
    # Build observations
    observations = build_observations()
    print(f"Observations: {len(observations)}")
    
    # Evaluate all predefined strategies
    print(f"\n--- Evaluating {len(STRATEGIES)} strategies ---\n")
    
    results = {}
    for name, strategy in STRATEGIES.items():
        result = evaluate_strategy(observations, strategy)
        results[name] = result
        
        print(f"{name}:")
        print(f"  Long: {result.get('long_return', 0):+.2%}, Short: {result.get('short_return', 0):+.2%}")
        print(f"  Spread: {result.get('spread', 0):+.2%}, Sharpe: {result.get('sharpe', 0):.2f}")
        print(f"  Win rate: {result.get('long_win_rate', 0):.0%}, Max DD: {result.get('max_drawdown', 0):.1%}")
        print()
    
    # Save all results
    output = Path("/root/bitt/trading/experiments/strategy_evaluation.json")
    with open(output, "w") as f:
        json.dump(results, f, indent=2)
    
    # Save strategy definitions
    for name, strategy in STRATEGIES.items():
        strat_file = STRATEGIES_DIR / f"{name}.json"
        with open(strat_file, "w") as f:
            f.write(strategy.to_json())
    
    print(f"Saved to {output}")
    print(f"Strategy definitions to {STRATEGIES_DIR}")
