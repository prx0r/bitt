"""CP4: Opportunity Decision Engine.

Every 5 minutes asks: "Which action has the best EV right now?"

Actions:
- MINE: Register as miner on subnet X
- BUY: Buy alpha tokens on subnet X
- STAKE: Stake TAO to validator on subnet X
- HOLD: Keep 100% TAO (default)
- WAIT: No action, data insufficient

Decision flow:
1. Scan all subnets for opportunities
2. Score each action by EV = P(profit) * expected_profit - P(loss) * expected_loss
3. Rank by EV
4. Output ranked action list with confidence
"""
import sqlite3
import json
import math
from pathlib import Path
from datetime import datetime
from typing import Optional


DB = Path("/root/bitt/oracle.db")
MARKET_DB = Path("/root/bitt/market.duckdb")


class OpportunityAction:
    """Represents a potential action with EV calculation."""
    
    def __init__(self, action_type: str, netuid: int, **kwargs):
        self.action_type = action_type  # MINE, BUY, STAKE, HOLD, WAIT
        self.netuid = netuid
        self.expected_tao_day = kwargs.get("expected_tao_day", 0)
        self.expected_alpha_day = kwargs.get("expected_alpha_day", 0)
        self.probability_profitable = kwargs.get("probability_profitable", 0.5)
        self.capital_at_risk = kwargs.get("capital_at_risk", 0)
        self.sunk_cost = kwargs.get("sunk_cost", 0)
        self.confidence = kwargs.get("confidence", 0.5)
        self.reasons = kwargs.get("reasons", [])
        self.factors = kwargs.get("factors", {})
    
    def ev(self) -> float:
        """Calculate expected value."""
        if self.action_type == "HOLD":
            return 0.0
        if self.action_type == "WAIT":
            return -0.01  # Small negative (opportunity cost)
        
        # EV = P(win) * gain - P(lose) * loss
        gain = self.expected_tao_day * 7  # 7-day horizon
        loss = self.capital_at_risk + self.sunk_cost
        
        ev = self.probability_profitable * gain - (1 - self.probability_profitable) * loss
        return ev
    
    def to_dict(self) -> dict:
        return {
            "action": self.action_type,
            "netuid": self.netuid,
            "ev": round(self.ev(), 4),
            "expected_tao_day": self.expected_tao_day,
            "probability_profitable": self.probability_profitable,
            "capital_at_risk": self.capital_at_risk,
            "sunk_cost": self.sunk_cost,
            "confidence": self.confidence,
            "reasons": self.reasons,
            "factors": self.factors,
        }


def get_subnet_data() -> list[dict]:
    """Get current subnet data from oracle.db."""
    conn = sqlite3.connect(str(DB))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        'SELECT data FROM subnet_snapshots WHERE scanned_at = (SELECT MAX(scanned_at) FROM subnet_snapshots)'
    ).fetchall()
    conn.close()
    return [json.loads(r['data']) for r in rows]


def get_pool_data(netuid: int) -> dict:
    """Get latest pool data for a subnet."""
    conn = sqlite3.connect(str(MARKET_DB))
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM pool_state WHERE netuid = ? ORDER BY timestamp DESC LIMIT 1",
        (netuid,)
    ).fetchone()
    conn.close()
    return dict(row) if row else {}


def evaluate_mining(subnet: dict) -> Optional[OpportunityAction]:
    """Evaluate mining opportunity for a subnet."""
    netuid = subnet.get('netuid', 0)
    neurons = subnet.get('neuron_count', 0)
    active = subnet.get('active_count', 0)
    emitting = subnet.get('emitting_count', 0)
    emission = subnet.get('tao_equiv_day', 0)
    price = subnet.get('alpha_price', 0)
    
    if emission <= 0 or neurons <= 0:
        return None
    
    # Estimate per-miner emission
    emission_per = emission / max(emitting, 1)
    
    # Competition score (fewer emitters = better)
    competition = emitting / max(neurons, 1)
    
    # Probability of earning >= 1 TAO/day
    if emission_per >= 1.0 and competition < 0.5:
        prob = 0.7
    elif emission_per >= 0.5 and competition < 0.7:
        prob = 0.5
    elif emission_per >= 0.1:
        prob = 0.3
    else:
        prob = 0.1
    
    # Entry cost (registration + collateral)
    reg_cost = 0.5  # Approximate
    sunk = reg_cost
    
    reasons = []
    if competition < 0.3:
        reasons.append(f"low competition ({competition:.1%})")
    if emission_per > 0.5:
        reasons.append(f"high emission/neuron ({emission_per:.2f})")
    if emitting < 50:
        reasons.append(f"few emitters ({emitting})")
    
    return OpportunityAction(
        action_type="MINE",
        netuid=netuid,
        expected_tao_day=emission_per,
        probability_profitable=prob,
        capital_at_risk=0,
        sunk_cost=sunk,
        confidence=prob * (1 - competition),
        reasons=reasons,
        factors={
            "competition": competition,
            "emission_per": emission_per,
            "emitting": emitting,
        }
    )


def evaluate_buy(subnet: dict) -> Optional[OpportunityAction]:
    """Evaluate buying alpha tokens on a subnet."""
    netuid = subnet.get('netuid', 0)
    price = subnet.get('alpha_price', 0)
    emission = subnet.get('tao_equiv_day', 0)
    neurons = subnet.get('neuron_count', 0)
    
    if price <= 0 or emission <= 0:
        return None
    
    # Yield proxy: emission / neurons / price
    yield_proxy = emission / max(neurons, 1) / price
    
    # Higher yield = more attractive
    if yield_proxy > 10:
        prob = 0.6
    elif yield_proxy > 5:
        prob = 0.4
    elif yield_proxy > 1:
        prob = 0.3
    else:
        prob = 0.2
    
    capital = 10.0  # Assume 10 TAO position
    
    reasons = []
    if yield_proxy > 5:
        reasons.append(f"high yield/price ({yield_proxy:.1f})")
    if neurons < 50:
        reasons.append(f"low competition ({neurons} miners)")
    
    return OpportunityAction(
        action_type="BUY",
        netuid=netuid,
        expected_tao_day=emission / max(neurons, 1),
        probability_profitable=prob,
        capital_at_risk=capital,
        sunk_cost=0,
        confidence=prob * min(yield_proxy / 10, 1),
        reasons=reasons,
        factors={"yield_proxy": yield_proxy}
    )


def evaluate_stake(subnet: dict) -> Optional[OpportunityAction]:
    """Evaluate staking TAO to a validator on a subnet."""
    netuid = subnet.get('netuid', 0)
    emission = subnet.get('tao_equiv_day', 0)
    validators = subnet.get('validator_count', 0)
    
    if emission <= 0 or validators <= 0:
        return None
    
    # Simplified: staking return is proportional to emission
    daily_return = emission * 0.01  # Assume 1% of subnet emission
    
    prob = 0.5  # Moderate confidence
    capital = 100.0  # Assume 100 TAO stake
    
    return OpportunityAction(
        action_type="STAKE",
        netuid=netuid,
        expected_tao_day=daily_return,
        probability_profitable=prob,
        capital_at_risk=capital,
        sunk_cost=0,
        confidence=0.4,
        reasons=[f"staking return estimate"],
        factors={}
    )


def run_decision_engine() -> dict:
    """Run the full decision engine."""
    subnets = get_subnet_data()
    actions = []
    
    for subnet in subnets:
        # Evaluate each action type
        mine = evaluate_mining(subnet)
        buy = evaluate_buy(subnet)
        stake = evaluate_stake(subnet)
        
        for action in [mine, buy, stake]:
            if action and action.ev() > 0:
                actions.append(action)
    
    # Add HOLD as baseline
    actions.append(OpportunityAction(
        action_type="HOLD",
        netuid=0,
        confidence=0.9,
        reasons=["default baseline"]
    ))
    
    # Sort by EV
    actions.sort(key=lambda a: a.ev(), reverse=True)
    
    # Take top 10
    top_actions = actions[:10]
    
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "subnets_scanned": len(subnets),
        "total_actions": len(actions),
        "top_actions": [a.to_dict() for a in top_actions],
        "recommended": top_actions[0].to_dict() if top_actions else None,
    }


def format_decision_report(result: dict) -> str:
    """Format decision engine output."""
    lines = [
        "=" * 70,
        "OPPORTUNITY DECISION ENGINE (CP4)",
        "=" * 70,
        f"Timestamp: {result['timestamp']}",
        f"Subnets scanned: {result['subnets_scanned']}",
        f"Total actions evaluated: {result['total_actions']}",
        "",
        "TOP ACTIONS BY EV:",
        f"{'#':<4} {'Action':<7} {'SN':<5} {'EV':<10} {'P(win)':<8} {'Conf':<6} {'Reasons'}",
        "-" * 70,
    ]
    
    for i, action in enumerate(result['top_actions'], 1):
        reasons = "; ".join(action['reasons'][:2]) if action['reasons'] else ""
        lines.append(
            f"{i:<4} {action['action']:<7} {action['netuid']:<5} "
            f"{action['ev']:<+10.4f} {action['probability_profitable']:<8.2f} "
            f"{action['confidence']:<6.2f} {reasons}"
        )
    
    # Recommendation
    rec = result.get('recommended')
    if rec and rec['action'] != 'HOLD':
        lines.extend([
            "",
            f"RECOMMENDATION: {rec['action']} on SN{rec['netuid']}",
            f"  EV: {rec['ev']:+.4f} TAO (7-day)",
            f"  P(profitable): {rec['probability_profitable']:.1%}",
            f"  Confidence: {rec['confidence']:.1%}",
            f"  Reasons: {'; '.join(rec['reasons'])}",
        ])
    else:
        lines.extend(["", "RECOMMENDATION: HOLD TAO (no positive-EV opportunities)"])
    
    lines.append("=" * 70)
    return "\n".join(lines)


if __name__ == "__main__":
    result = run_decision_engine()
    print(format_decision_report(result))
    
    # Save
    output = Path("/root/bitt/trading/experiments/decision_engine.json")
    with open(output, "w") as f:
        json.dump(result, f, indent=2)
    print(f"\nSaved to {output}")
