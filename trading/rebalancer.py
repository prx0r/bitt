"""Rebalancer — asks one question every 5 minutes:

"Is holding 100% TAO still the highest-probability choice,
or is there enough evidence to allocate X% of the stack to subnet Y?"

HOLD_TAO is a real decision, not absence of a decision.
Every decision gets recorded through QDW ledger.
"""
import sqlite3
import json
from pathlib import Path
from typing import Literal


DB_PATH = Path("/root/bitt/market.duckdb")


def calculate_yield_price(netuid: int, candles: list[dict]) -> float:
    """Calculate yield/price ratio for a subnet.
    
    FIXED: candles are stored newest-first, so index 0 = most recent.
    Returns are calculated forward in time (older -> newer).
    """
    if not candles:
        return 0.0

    valid_candles = [c for c in candles if c.get('close_tao') is not None]
    if not valid_candles:
        return 0.0

    latest = valid_candles[0]  # Most recent candle (newest-first order)
    price = latest.get('close_tao', 0) or 0

    if len(valid_candles) >= 288:
        returns = []
        # candles are newest-first, so walk from oldest to newest
        for i in range(len(valid_candles) - 1, max(0, len(valid_candles) - 289), -1):
            curr = valid_candles[i].get('close_tao', 0) or 0
            prev = valid_candles[i + 1].get('close_tao', 0) or 0  # i+1 is older
            if prev > 0:
                returns.append((curr - prev) / prev)
        avg_return = sum(returns) / len(returns) if returns else 0
        annual_yield = avg_return * 365 * 288
    else:
        annual_yield = 0.0

    return annual_yield / price if price and price > 0 else 0.0


def detect_setup(netuid: int, candles: list[dict], macro: dict) -> dict:
    """Detect if a subnet has a setup for allocation."""
    if not candles or len(candles) < 2:
        return {"setup": False, "reason": "insufficient data"}

    # Filter out None values
    valid_candles = [c for c in candles if c.get('close_tao') is not None]
    if len(valid_candles) < 2:
        return {"setup": False, "reason": "insufficient valid data"}

    # Calculate relative momentum (4h)
    if len(valid_candles) >= 48:
        recent = valid_candles[0]['close_tao']
        four_hours_ago = valid_candles[47]['close_tao']
        momentum_4h = (recent - four_hours_ago) / four_hours_ago if four_hours_ago and four_hours_ago > 0 else 0
    else:
        momentum_4h = 0.0

    # Calculate relative momentum (24h)
    if len(valid_candles) >= 288:
        recent = valid_candles[0]['close_tao']
        day_ago = valid_candles[287]['close_tao']
        momentum_24h = (recent - day_ago) / day_ago if day_ago and day_ago > 0 else 0
    else:
        momentum_24h = 0.0

    # Volume acceleration (FIXED: use volume_tao column, not volume)
    if len(valid_candles) >= 10:
        recent_vol = sum(c.get('volume_tao', 0) or 0 for c in valid_candles[:10]) / 10
        prev_vol = sum(c.get('volume_tao', 0) or 0 for c in valid_candles[10:20]) / 10 if len(valid_candles) >= 20 else recent_vol
        vol_accel = recent_vol / max(prev_vol, 1) - 1
    else:
        vol_accel = 0.0

    # Setup detection
    setup = False
    reasons = []

    if momentum_4h > 0.02:
        setup = True
        reasons.append(f"4h momentum: {momentum_4h:.1%}")

    if momentum_24h > 0.05:
        setup = True
        reasons.append(f"24h momentum: {momentum_24h:.1%}")

    if vol_accel > 1.5:
        setup = True
        reasons.append(f"Volume acceleration: {vol_accel:.1%}")

    # Yield/price check
    yield_price = calculate_yield_price(netuid, valid_candles)
    if yield_price > 100:
        setup = True
        reasons.append(f"High yield/price: {yield_price:.0f}")

    return {
        "setup": setup,
        "reasons": reasons,
        "momentum_4h": momentum_4h,
        "momentum_24h": momentum_24h,
        "vol_accel": vol_accel,
        "yield_price": yield_price,
    }


def decide(netuid: int, candles: list[dict], macro: dict,
           portfolio: dict, context: dict = None) -> dict:
    """Make a decision: HOLD_TAO or ALLOCATE X% to subnet.

    This is the core function. One question:
    "Is holding 100% TAO still the highest-probability choice?"

    Context features from BTC/ETH/TAO help answer:
    "Is this subnet showing real strength or just riding the market?"
    """
    setup = detect_setup(netuid, candles, macro)

    if not setup["setup"]:
        return {
            "action": "HOLD_TAO",
            "confidence": 0.9,
            "reason": f"No setup detected for SN{netuid}: {setup.get('reason', 'no signal')}",
            "factors": setup,
        }

    # Calculate target weight
    yield_price = setup["yield_price"]
    momentum = setup["momentum_4h"]

    # Context-adjusted scoring
    regime = context.get("regime", "sideways") if context else "sideways"
    tao_ret = context.get("tao", {}).get("ret_24h", 0) if context else 0

    # Base score from setup
    score = 0
    if yield_price > 100:
        score += 0.4
    if momentum > 0.02:
        score += 0.3
    if setup["vol_accel"] > 1.5:
        score += 0.2
    if setup["momentum_24h"] > 0.05:
        score += 0.1

    # Context adjustments
    if regime == "bear":
        score *= 0.5  # Reduce allocation in bear market
    elif regime == "bull":
        score *= 1.2  # Increase allocation in bull market

    # If TAO itself is pumping, subnet might just be riding the wave
    if tao_ret > 0.05:
        score *= 0.8  # Reduce — might be TAO effect, not idiosyncratic

    # Convert score to weight (max 20% per position)
    target_weight = min(0.20, score * 0.25)

    if target_weight < 0.05:
        return {
            "action": "HOLD_TAO",
            "confidence": 0.8,
            "reason": f"SN{netuid} score {score:.2f} below threshold (regime={regime})",
            "factors": setup,
            "regime": regime,
        }

    return {
        "action": "ALLOCATE",
        "netuid": netuid,
        "target_weight": target_weight,
        "confidence": min(0.95, score),
        "reason": f"SN{netuid} score {score:.2f}, yield/price={yield_price:.0f}, momentum={momentum:.1%}, regime={regime}",
        "factors": setup,
        "regime": regime,
    }


def record_decision(decision: dict, timestamp: str):
    """Record decision through QDW ledger."""
    # This would call self.ledger.append_event() in production
    # For now, print the decision
    print(f"  DECISION: {decision['action']} confidence={decision['confidence']:.2f}")
    print(f"  REASON: {decision['reason']}")
