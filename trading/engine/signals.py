"""Signal Library — curated signals from OpenTaoTrader + our research.

Each signal is a function that takes observation data and returns a score.
These feed into the rebalancing algo as ranked signals.

Signals:
1. Low Volatility (our research, IC=-0.17)
2. Support Bounce (our research, +3.89% edge)
3. Squeeze Detection (our research + OpenTaoTrader RCB)
4. Stake Velocity (OpenTaoTrader — on-chain fundamental)
5. Whale Inflow (OpenTaoTrader WSI)
6. Emission Yield Carry (OpenTaoTrader EYC)
7. Mean Reversion (OpenTaoTrader + our research)
8. Anti-Yield Trap (our research, IC=-0.13)
"""
import sqlite3
import math
from pathlib import Path
from collections import deque


MDB = Path("/root/bitt/market.duckdb")

# Per-subnet ring buffers for time-series signals
_PRICE_HIST = {}  # netuid -> deque of prices
_STAKE_HIST = {}  # netuid -> deque of total_stake


def push_price(netuid: int, price: float, maxlen: int = 1440):
    """Add price to ring buffer (30d at 30-min bars)."""
    dq = _PRICE_HIST.setdefault(netuid, deque(maxlen=maxlen))
    dq.append(price)


def push_stake(netuid: int, stake: float, maxlen: int = 1440):
    """Add stake to ring buffer."""
    dq = _STAKE_HIST.setdefault(netuid, deque(maxlen=maxlen))
    dq.append(stake)


# === SIGNAL 1: LOW VOLATILITY ===
def signal_low_vol(prices: list[float]) -> float:
    """Low volatility signal. Higher score = lower vol = better.
    
    From our research: IC=-0.17, strongest predictive factor.
    """
    if len(prices) < 48:
        return 0
    
    rets = [(prices[i] - prices[i-1]) / prices[i-1] for i in range(1, len(prices)) if prices[i-1] > 0]
    if not rets:
        return 0
    
    vol = (sum(r**2 for r in rets) / len(rets)) ** 0.5
    
    # Invert: low vol = high score
    if vol < 0.001:
        return 1.0
    elif vol < 0.005:
        return 0.8
    elif vol < 0.01:
        return 0.6
    elif vol < 0.03:
        return 0.4
    elif vol < 0.05:
        return 0.2
    else:
        return 0


# === SIGNAL 2: SUPPORT BOUNCE ===
def signal_support(prices: list[float]) -> float:
    """Support bounce signal. Near 20-day low = high score.
    
    From our research: +3.89% edge buying near support.
    """
    if len(prices) < 480:
        return 0
    
    current = prices[-1]
    low_20d = min(prices[-480:])
    
    if low_20d <= 0:
        return 0
    
    distance = (current - low_20d) / low_20d
    
    if distance < 0.01:
        return 1.0  # Within 1% of support
    elif distance < 0.02:
        return 0.8
    elif distance < 0.05:
        return 0.5
    elif distance < 0.10:
        return 0.2
    else:
        return 0


# === SIGNAL 3: SQUEEZE (Range Compression) ===
def signal_squeeze(prices: list[float]) -> float:
    """Volatility squeeze signal. 24h range compressed vs 7d range.
    
    From our research: +1.83% edge. OpenTaoTrader RCB confirmed.
    """
    if len(prices) < 336:
        return 0
    
    range_24h = prices[-48:]
    range_7d = prices[-336:]
    
    if len(range_24h) < 10 or len(range_7d) < 50:
        return 0
    
    r24 = (max(range_24h) - min(range_24h)) / max(min(range_24h), 0.0001)
    r7d = (max(range_7d) - min(range_7d)) / max(min(range_7d), 0.0001)
    
    if r7d <= 0:
        return 0
    
    compression = r24 / r7d
    
    if compression < 0.2:
        return 1.0  # Very compressed
    elif compression < 0.3:
        return 0.8
    elif compression < 0.5:
        return 0.5
    elif compression < 0.7:
        return 0.2
    else:
        return 0


# === SIGNAL 4: STAKE VELOCITY ===
def signal_stake_velocity(stakes: list[float]) -> float:
    """Stake velocity signal. Stake growing faster than price = bullish.
    
    From OpenTaoTrader: whale/institutional accumulation signal.
    """
    if len(stakes) < 48:
        return 0
    
    # 24h stake change
    if stakes[-48] <= 0:
        return 0
    
    sv_24h = (stakes[-1] - stakes[-48]) / stakes[-48]
    
    # 72h stake change
    if len(stakes) >= 144 and stakes[-144] > 0:
        sv_72h = (stakes[-1] - stakes[-144]) / stakes[-144]
    else:
        sv_72h = sv_24h
    
    # Both positive = strong signal
    if sv_24h > 0.05 and sv_72h > 0.03:
        return 1.0
    elif sv_24h > 0.03 and sv_72h > 0.01:
        return 0.8
    elif sv_24h > 0.01:
        return 0.5
    elif sv_24h > 0:
        return 0.3
    elif sv_24h < -0.03:
        return 0  # Draining — avoid
    else:
        return 0.1


# === SIGNAL 5: WHALE INFLOW ===
def signal_whale_inflow(stakes: list[float]) -> float:
    """Whale stake inflow signal. 97th percentile delta = whale.
    
    From OpenTaoTrader WSI.
    """
    if len(stakes) < 100:
        return 0
    
    # Calculate deltas
    deltas = [stakes[i] - stakes[i-1] for i in range(1, len(stakes))]
    
    if len(deltas) < 50:
        return 0
    
    # Current delta
    current_delta = deltas[-1]
    
    if current_delta <= 0:
        return 0
    
    # Percentile
    sorted_deltas = sorted(deltas)
    percentile = sum(1 for d in sorted_deltas if d <= current_delta) / len(sorted_deltas)
    
    if percentile > 0.99:
        return 1.0  # Extreme whale
    elif percentile > 0.97:
        return 0.8
    elif percentile > 0.95:
        return 0.6
    elif percentile > 0.90:
        return 0.3
    else:
        return 0


# === SIGNAL 6: EMISSION YIELD CARRY ===
def signal_yield_carry(emission: float, stake: float) -> float:
    """Emission yield = emission_rate / total_stake.
    
    From OpenTaoTrader EYC. Top yield = under-staked.
    """
    if stake <= 0:
        return 0
    
    yield_rate = emission / stake
    
    # Higher yield = more attractive (but not too high = trap)
    if yield_rate > 0.1:
        return 0.5  # Too high might be trap
    elif yield_rate > 0.05:
        return 1.0  # Sweet spot
    elif yield_rate > 0.02:
        return 0.8
    elif yield_rate > 0.01:
        return 0.5
    elif yield_rate > 0.005:
        return 0.3
    else:
        return 0.1


# === SIGNAL 7: MEAN REVERSION ===
def signal_mean_reversion(prices: list[float]) -> float:
    """Z-score mean reversion. Far below 7d mean = buy.
    
    From OpenTaoTrader mean_reversion + our research.
    """
    if len(prices) < 336:
        return 0
    
    window = prices[-336:]
    mean = sum(window) / len(window)
    std = (sum((x - mean)**2 for x in window) / len(window)) ** 0.5
    
    if std <= 0:
        return 0
    
    z_score = (prices[-1] - mean) / std
    
    # Negative z = below mean = buy signal
    if z_score < -2.0:
        return 1.0
    elif z_score < -1.5:
        return 0.8
    elif z_score < -1.0:
        return 0.5
    elif z_score < -0.5:
        return 0.3
    else:
        return 0


# === SIGNAL 8: ANTI-YIELD TRAP ===
def signal_anti_yield(emission_per_neuron: float) -> float:
    """Avoid high yield per neuron. Market exploits yield chasers.
    
    From our research: IC=-0.13.
    """
    # Lower yield = better (avoid traps)
    if emission_per_neuron > 10:
        return 0  # High yield trap
    elif emission_per_neuron > 5:
        return 0.2
    elif emission_per_neuron > 1:
        return 0.5
    elif emission_per_neuron > 0.1:
        return 0.8
    else:
        return 1.0


# === COMPOSITE SIGNAL ===
def calculate_composite_signal(netuid: int, prices: list[float], 
                               stakes: list[float], emission: float,
                               stake: float, emission_per_neuron: float) -> dict:
    """Calculate composite signal from all factors."""
    signals = {
        "low_vol": signal_low_vol(prices),
        "support": signal_support(prices),
        "squeeze": signal_squeeze(prices),
        "stake_velocity": signal_stake_velocity(stakes),
        "whale_inflow": signal_whale_inflow(stakes),
        "yield_carry": signal_yield_carry(emission, stake),
        "mean_reversion": signal_mean_reversion(prices),
        "anti_yield": signal_anti_yield(emission_per_neuron),
    }
    
    # Weights (from IC magnitudes)
    weights = {
        "low_vol": 3.0,       # IC=-0.17
        "support": 2.5,       # +3.89% edge
        "squeeze": 1.5,       # +1.83% edge
        "stake_velocity": 1.0, # On-chain fundamental
        "whale_inflow": 1.0,  # Whale detection
        "yield_carry": 0.8,   # Cross-sectional yield
        "mean_reversion": 0.5, # Mean reversion
        "anti_yield": 1.5,    # IC=-0.13
    }
    
    composite = sum(signals[k] * weights[k] for k in signals) / sum(weights.values())
    
    return {
        "netuid": netuid,
        "composite": round(composite, 3),
        "signals": {k: round(v, 2) for k, v in signals.items()},
    }


if __name__ == "__main__":
    print("=== Signal Library ===\n")
    print("Signals available:")
    for name in ["low_vol", "support", "squeeze", "stake_velocity", 
                  "whale_inflow", "yield_carry", "mean_reversion", "anti_yield"]:
        print(f"  {name}")
