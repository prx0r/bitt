"""Hypothesis Library — all 54 strategies from imported emails, machine-readable.

Each hypothesis is a structured claim that can be compiled into a strategy,
tested against data, and optimized by the CGE.
"""
import json
from pathlib import Path
from datetime import datetime


HYPOTHESES_DIR = Path("/root/bitt/trading/studio/hypotheses")
HYPOTHESES_DIR.mkdir(exist_ok=True)


HYPOTHESIS_LIBRARY = [
    # === TIER 0: Volatility (proven by backtest) ===
    {
        "id": "H001",
        "claim": "Low 7d volatility subnets outperform high volatility subnets",
        "factors": ["vol_7d"],
        "direction": "asc",
        "horizon": "1d",
        "status": "TESTED",
        "result": "+2.48% support_5pos",
        "source": "email: comprehensive factor analysis",
    },
    {
        "id": "H002",
        "claim": "Buying subnets near 20-day support outperforms",
        "factors": ["support_20d"],
        "direction": "asc",
        "horizon": "1d",
        "status": "TESTED",
        "result": "+2.48% support_5pos",
        "source": "email: comprehensive factor analysis",
    },
    {
        "id": "H003",
        "claim": "Child composite (vol + momentum + support) outperforms single factors",
        "factors": ["vol_7d", "momentum_7d", "support_20d"],
        "direction": "composite",
        "horizon": "1d",
        "status": "TESTED",
        "result": "+1.72% child_5pos",
        "source": "email: comprehensive factor analysis",
    },
    
    # === TIER 1: Volatility definition (from research emails) ===
    {
        "id": "H010",
        "claim": "Upside volatility predicts positive returns, downside volatility predicts negative",
        "factors": ["vol_7d_upside", "vol_7d_downside"],
        "direction": "split",
        "horizon": "1d",
        "status": "UNTESTED",
        "source": "email: Batista & Fernandes 2026",
    },
    {
        "id": "H011",
        "claim": "HAR-RV forecast volatility beats historical volatility",
        "factors": ["har_rv_forecast"],
        "direction": "asc",
        "horizon": "1d",
        "status": "UNTESTED",
        "source": "email: Corsi HAR-RV + Huang regime switching",
    },
    {
        "id": "H012",
        "claim": "Two-state HMM: trade P(CALM tomorrow) not vol_7d",
        "factors": ["hmm_prob_calm"],
        "direction": "asc",
        "horizon": "1d",
        "status": "UNTESTED",
        "source": "email: Huang regime switching",
    },
    {
        "id": "H013",
        "claim": "Low downside vol + positive trend beats raw low vol",
        "factors": ["vol_7d_downside", "momentum_7d"],
        "direction": "composite",
        "horizon": "1d",
        "status": "UNTESTED",
        "source": "email: Batista + Moreira/Muir",
    },
    
    # === TIER 2: Bittensor mechanics (from playbook emails) ===
    {
        "id": "H020",
        "claim": "AMM size premium: small pool subnets earn higher returns (Maymin 2026)",
        "factors": ["pool_size"],
        "direction": "asc",
        "horizon": "1d",
        "status": "UNTESTED",
        "source": "email: Maymin Common Risk Factors",
    },
    {
        "id": "H021",
        "claim": "Pool depth predicts forward returns (deeper = more stable)",
        "factors": ["pool_depth"],
        "direction": "desc",
        "horizon": "1d",
        "status": "UNTESTED",
        "source": "email: Maymin CEV process",
    },
    {
        "id": "H022",
        "claim": "Stake velocity predicts price movement (stake leads price)",
        "factors": ["stake_velocity_24h"],
        "direction": "asc",
        "horizon": "1d",
        "status": "UNTESTED",
        "source": "email: OpenTaoTrader stake_velocity",
    },
    {
        "id": "H023",
        "claim": "Whale inflow (97th percentile) predicts 48h returns",
        "factors": ["whale_inflow"],
        "direction": "asc",
        "horizon": "2d",
        "status": "UNTESTED",
        "source": "email: OpenTaoTrader WSI",
    },
    
    # === TIER 3: Cross-sectional (from factor analysis emails) ===
    {
        "id": "H030",
        "claim": "Low emission per neuron subnets outperform (anti-yield trap)",
        "factors": ["emit_per"],
        "direction": "asc",
        "horizon": "1d",
        "status": "TESTED",
        "result": "IC=-0.129",
        "source": "email: comprehensive factor analysis",
    },
    {
        "id": "H031",
        "claim": "Distributed emissions (low HHI) outperform concentrated",
        "factors": ["hhi_emit"],
        "direction": "asc",
        "horizon": "1d",
        "status": "TESTED",
        "result": "IC=-0.101",
        "source": "email: comprehensive factor analysis",
    },
    {
        "id": "H032",
        "claim": "High active ratio outperforms (alive subnets)",
        "factors": ["active_ratio"],
        "direction": "desc",
        "horizon": "1d",
        "status": "TESTED",
        "result": "IC=+0.053",
        "source": "email: comprehensive factor analysis",
    },
    {
        "id": "H033",
        "claim": "Price level predicts returns (established subnets outperform)",
        "factors": ["price_level"],
        "direction": "desc",
        "horizon": "1d",
        "status": "TESTED",
        "result": "IC=+0.080",
        "source": "email: comprehensive factor analysis",
    },
    
    # === TIER 4: Pairs/relative value ===
    {
        "id": "H040",
        "claim": "Pair mean reversion: correlated subnets mean-revert spread",
        "factors": ["pair_spread_zscore"],
        "direction": "asc",
        "horizon": "3d",
        "status": "UNTESTED",
        "source": "email: OpenTaoTrader PMR",
    },
    {
        "id": "H041",
        "claim": "Cross-sectional momentum: past winners beat past losers",
        "factors": ["momentum_7d"],
        "direction": "desc",
        "horizon": "7d",
        "status": "UNTESTED",
        "source": "email: Fieberg CTREND",
    },
    {
        "id": "H042",
        "claim": "Short-horizon reversal + longer-horizon trend coexist",
        "factors": ["zscore_7d", "momentum_7d"],
        "direction": "composite",
        "horizon": "1d",
        "status": "UNTESTED",
        "source": "email: Fieberg CTREND",
    },
    
    # === TIER 5: Regime/flow ===
    {
        "id": "H050",
        "claim": "Regime detection (CALM/WILD) improves allocation timing",
        "factors": ["regime_state"],
        "direction": "conditional",
        "horizon": "1d",
        "status": "UNTESTED",
        "source": "email: Huang regime switching",
    },
    {
        "id": "H051",
        "claim": "Cross-sectional breadth predicts network-level returns",
        "factors": ["breadth"],
        "direction": "desc",
        "horizon": "1d",
        "status": "UNTESTED",
        "source": "email: breadth/regime indicator",
    },
    {
        "id": "H052",
        "claim": "Volatility-of-volatility predicts regime transitions",
        "factors": ["vol_of_vol"],
        "direction": "asc",
        "horizon": "3d",
        "status": "UNTESTED",
        "source": "email: Corsi HAR-RV",
    },
    
    # === TIER 6: Execution/sizing ===
    {
        "id": "H060",
        "claim": "Inverse-vol sizing beats equal weight",
        "factors": ["vol_7d"],
        "direction": "inverse_sizing",
        "horizon": "1d",
        "status": "UNTESTED",
        "source": "email: Moreira/Muir volatility-managed",
    },
    {
        "id": "H061",
        "claim": "Risk-parity allocation beats equal weight",
        "factors": ["vol_7d", "pool_depth"],
        "direction": "risk_parity",
        "horizon": "1d",
        "status": "UNTESTED",
        "source": "email: Moreira/Muir",
    },
    {
        "id": "H062",
        "claim": "Position size should scale with pool depth (slippage constraint)",
        "factors": ["pool_depth"],
        "direction": "proportional_sizing",
        "horizon": "1d",
        "status": "UNTESTED",
        "source": "email: Dong liquidity + AMM capacity",
    },
]


def save_all_hypotheses():
    """Save all hypotheses to files."""
    for h in HYPOTHESIS_LIBRARY:
        path = HYPOTHESES_DIR / f"{h['id']}.json"
        with open(path, "w") as f:
            json.dump(h, f, indent=2)
    print(f"Saved {len(HYPOTHESIS_LIBRARY)} hypotheses")


def get_hypotheses_by_status(status: str) -> list:
    """Get all hypotheses with given status."""
    return [h for h in HYPOTHESIS_LIBRARY if h["status"] == status]


def get_hypotheses_by_tier(tier: int) -> list:
    """Get hypotheses from a specific tier."""
    return [h for h in HYPOTHESIS_LIBRARY if h["id"].startswith(f"H{tier:02d}")]


if __name__ == "__main__":
    print("=== Hypothesis Library ===\n")
    
    save_all_hypotheses()
    
    # Summary
    tested = get_hypotheses_by_status("TESTED")
    untested = get_hypotheses_by_status("UNTESTED")
    
    print(f"Total: {len(HYPOTHESIS_LIBRARY)}")
    print(f"Tested: {len(tested)}")
    print(f"Untested: {len(untested)}")
    
    print(f"\nTested hypotheses:")
    for h in tested:
        print(f"  {h['id']}: {h['claim'][:60]}... → {h['result']}")
    
    print(f"\nUntested by tier:")
    for tier in range(7):
        tier_h = [h for h in untested if h["id"].startswith(f"H{tier:02d}")]
        if tier_h:
            print(f"  Tier {tier}: {len(tier_h)} hypotheses")
            for h in tier_h[:3]:
                print(f"    {h['id']}: {h['claim'][:60]}...")
