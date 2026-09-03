"""Three-View Payout Model — the playbook's killer feature.

For every miner seat, calculate three views:
1. settled_alpha_day — protocol-native, price-insensitive
2. spot_marked_tao_day — alpha * spot_price
3. realizable_tao_day — what you'd actually get selling (quote_unstake with slippage)

Plus: seat persistence, churn, and survival metrics.
"""
import sqlite3
import json
from pathlib import Path
from datetime import datetime


MARKET_DB = Path("/root/bitt/market.duckdb")
ORACLE_DB = Path("/root/bitt/oracle.db")


def init_payout_tables():
    """Create three-view payout tables."""
    conn = sqlite3.connect(str(MARKET_DB))
    conn.executescript("""
        -- Three-view payout per miner per epoch
        CREATE TABLE IF NOT EXISTS miner_payouts (
            block INTEGER NOT NULL,
            netuid INTEGER NOT NULL,
            uid INTEGER NOT NULL,
            hotkey TEXT,
            coldkey TEXT,
            -- View 1: Protocol-native
            settled_alpha_day REAL,
            -- View 2: Spot-marked
            alpha_spot_price REAL,
            spot_marked_tao_day REAL,
            -- View 3: Realizable (estimated with slippage)
            realizable_tao_day REAL,
            slippage_estimate REAL,
            -- Seat metrics
            payout_rank INTEGER,
            above_01_tao INTEGER,
            above_025_tao INTEGER,
            above_05_tao INTEGER,
            above_1_tao INTEGER,
            consecutive_epochs_paid INTEGER,
            PRIMARY KEY (block, netuid, uid)
        );
        
        -- Seat persistence summary per subnet
        CREATE TABLE IF NOT EXISTS seat_persistence (
            block INTEGER NOT NULL,
            netuid INTEGER NOT NULL,
            -- Seat counts at thresholds
            seats_ge_001 INTEGER,
            seats_ge_01 INTEGER,
            seats_ge_025 INTEGER,
            seats_ge_05 INTEGER,
            seats_ge_1 INTEGER,
            seats_ge_5 INTEGER,
            seats_ge_10 INTEGER,
            -- Percentiles
            p10_alpha REAL,
            p25_alpha REAL,
            median_alpha REAL,
            p75_alpha REAL,
            p90_alpha REAL,
            -- Distribution
            top1_share REAL,
            top3_share REAL,
            top5_share REAL,
            top10_share REAL,
            hhi REAL,
            gini REAL,
            -- Churn
            effective_earners INTEGER,
            churn_rate REAL,
            median_seat_lifetime_epochs REAL,
            PRIMARY KEY (block, netuid)
        );
        
        -- Collateral economics per subnet
        CREATE TABLE IF NOT EXISTS collateral_economics (
            block INTEGER NOT NULL,
            netuid INTEGER NOT NULL,
            registration_cost_tao REAL,
            collateral_share REAL,
            sunk_burn_tao REAL,
            locked_collateral_tao REAL,
            opportunity_cost_tao REAL,
            total_entry_cost_tao REAL,
            expected_unlock_epochs INTEGER,
            probability_unlock_before_prune REAL,
            effective_irr REAL,
            PRIMARY KEY (block, netuid)
        );
        
        -- Mine-vs-buy decision
        CREATE TABLE IF NOT EXISTS mine_vs_buy (
            block INTEGER NOT NULL,
            netuid INTEGER NOT NULL,
            -- Mining side
            mining_cost_per_alpha REAL,
            mining_entry_cost_tao REAL,
            expected_daily_alpha REAL,
            days_to_breakeven REAL,
            -- Market side
            market_cost_per_alpha REAL,
            -- Decision
            decision TEXT,
            alpha_advantage_pct REAL,
            confidence REAL,
            PRIMARY KEY (block, netuid)
        );
        
        -- Registration timing
        CREATE TABLE IF NOT EXISTS registration_timing (
            block INTEGER NOT NULL,
            netuid INTEGER NOT NULL,
            current_burn_tao REAL,
            ev_register_now REAL,
            ev_wait_1_epoch REAL,
            ev_wait_n_blocks REAL,
            action TEXT,
            burn_trend TEXT,
            capacity_pressure TEXT,
            recommended_delay_blocks INTEGER,
            PRIMARY KEY (block, netuid)
        );
    """)
    conn.commit()
    conn.close()


def calculate_three_views(neurons: list, alpha_price: float, 
                          pool_tao: float, pool_alpha: float) -> list:
    """Calculate three payout views for each miner.
    
    View 1: settled_alpha_day — raw alpha emission per day
    View 2: spot_marked_tao_day — alpha * spot_price
    View 3: realizable_tao_day — actual TAO after slippage
    """
    results = []
    
    for n in neurons:
        emission_rao = n.get("emission", 0)
        settled_alpha = emission_rao / 1e9  # Convert rao to alpha units
        
        # View 2: Spot marked
        spot_tao = settled_alpha * alpha_price if alpha_price > 0 else 0
        
        # View 3: Realizable (simplified slippage model)
        # Slippage increases with trade size relative to pool
        if pool_tao > 0 and settled_alpha > 0:
            trade_pct = settled_alpha / max(pool_alpha, 1)
            # Approximate slippage: ~0.05% base + 0.5% per 10% of pool
            slippage = 0.0005 + (trade_pct * 0.005)
            slippage = min(slippage, 0.2)  # Cap at 20%
            realizable = spot_tao * (1 - slippage)
        else:
            slippage = 0
            realizable = spot_tao
        
        # Payout rank
        payout_rank = 0  # Will be set after sorting
        
        # Threshold membership
        daily_tao = realizable
        results.append({
            "uid": n.get("uid", 0),
            "hotkey": n.get("hotkey", ""),
            "settled_alpha_day": round(settled_alpha, 8),
            "spot_marked_tao_day": round(spot_tao, 8),
            "realizable_tao_day": round(realizable, 8),
            "slippage_estimate": round(slippage, 6),
            "above_01_tao": 1 if daily_tao >= 0.1 else 0,
            "above_025_tao": 1 if daily_tao >= 0.25 else 0,
            "above_05_tao": 1 if daily_tao >= 0.5 else 0,
            "above_1_tao": 1 if daily_tao >= 1.0 else 0,
        })
    
    # Assign ranks
    results.sort(key=lambda x: x["realizable_tao_day"], reverse=True)
    for i, r in enumerate(results):
        r["payout_rank"] = i + 1
    
    return results


def calculate_seat_persistence(payouts: list) -> dict:
    """Calculate seat persistence metrics from payout data."""
    if not payouts:
        return {}
    
    tao_values = [p["realizable_tao_day"] for p in payouts]
    tao_values.sort(reverse=True)
    n = len(tao_values)
    total = sum(tao_values)
    
    # Thresholds
    thresholds = [0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 5.0, 10.0]
    seat_counts = {}
    for t in thresholds:
        seat_counts[f"seats_ge_{str(t).replace('.', '')}"] = len([v for v in tao_values if v >= t])
    
    # Percentiles
    if n > 0:
        p10 = tao_values[min(int(n * 0.9), n - 1)]
        p25 = tao_values[min(int(n * 0.75), n - 1)]
        median = tao_values[n // 2]
        p75 = tao_values[min(int(n * 0.25), n - 1)]
        p90 = tao_values[0] if tao_values else 0
    else:
        p10 = p25 = median = p75 = p90 = 0
    
    # Shares
    if total > 0:
        shares = [v / total for v in tao_values]
        top1 = shares[0]
        top3 = sum(shares[:3])
        top5 = sum(shares[:5])
        top10 = sum(shares[:10])
    else:
        top1 = top3 = top5 = top10 = 0
    
    # HHI
    hhi = sum((v / total) ** 2 for v in tao_values) if total > 0 else 1.0
    
    # Gini
    if n > 1:
        sorted_v = sorted(tao_values)
        gini_num = sum((2 * i - n - 1) * sorted_v[i] for i in range(n))
        gini = gini_num / (n * sum(sorted_v)) if sum(sorted_v) > 0 else 0
    else:
        gini = 0
    
    # Effective earners (earning > 0)
    effective = len([v for v in tao_values if v > 0])
    
    return {
        **seat_counts,
        "p10_alpha": round(p10, 8),
        "p25_alpha": round(p25, 8),
        "median_alpha": round(median, 8),
        "p75_alpha": round(p75, 8),
        "p90_alpha": round(p90, 8),
        "top1_share": round(top1, 4),
        "top3_share": round(top3, 4),
        "top5_share": round(top5, 4),
        "top10_share": round(top10, 4),
        "hhi": round(hhi, 4),
        "gini": round(gini, 4),
        "effective_earners": effective,
    }


def calculate_collateral_economics(subnet_info: dict) -> dict:
    """Calculate true entry cost with collateral economics.
    
    sunk_burn = (1-p)*T where T = registration price, p = collateral share
    locked_collateral = p*T
    total_entry = sunk_burn + opportunity_cost
    """
    reg_cost_rao = float(subnet_info.get("neuron_registration_cost", 0) or 0)
    reg_cost_tao = reg_cost_rao / 1e9
    
    collateral_share = float(subnet_info.get("collateral_lock_share", 0) or 0)
    drain_ratio = float(subnet_info.get("collateral_drain_ratio", 1) or 1)
    
    # Sunk burn (cannot recover)
    sunk_burn = reg_cost_tao * (1 - collateral_share)
    
    # Locked collateral (recoverable eventually)
    locked_collateral = reg_cost_tao * collateral_share
    
    # Opportunity cost (assume 5% annual on locked capital, 30-day lock)
    opportunity_rate = 0.05 / 365
    expected_lock_days = 30
    opportunity_cost = locked_collateral * opportunity_rate * expected_lock_days
    
    # Total entry cost
    total_entry = sunk_burn + opportunity_cost
    
    # Expected unlock timing
    # Drain ratio determines how fast collateral is released
    if drain_ratio > 0:
        expected_epochs = int(1 / drain_ratio) if drain_ratio > 0 else 999
    else:
        expected_epochs = 999
    
    # Probability of unlock before prune (simplified)
    # Higher immunity + lower drain = higher probability
    immunity = int(subnet_info.get("immunity_period", 7200) or 7200)
    prune_risk = min(1.0, expected_epochs / max(immunity, 1))
    prob_unlock = max(0, 1 - prune_risk)
    
    # Effective IRR (annualized return on locked capital)
    # Assuming 30-day lock with daily emissions
    if locked_collateral > 0:
        daily_return = 0.01  # Assume 1% daily on collateral
        irr = daily_return * 365
    else:
        irr = 0
    
    return {
        "registration_cost_tao": round(reg_cost_tao, 8),
        "collateral_share": round(collateral_share, 4),
        "sunk_burn_tao": round(sunk_burn, 8),
        "locked_collateral_tao": round(locked_collateral, 8),
        "opportunity_cost_tao": round(opportunity_cost, 8),
        "total_entry_cost_tao": round(total_entry, 8),
        "expected_unlock_epochs": expected_epochs,
        "probability_unlock_before_prune": round(prob_unlock, 4),
        "effective_irr": round(irr, 4),
    }


def calculate_mine_vs_buy(settled_alpha_day: float, alpha_price: float,
                          entry_cost_tao: float, pool_tao: float) -> dict:
    """Mine-vs-buy arbitrage calculator.
    
    MINE if: mining cost per alpha < market cost per alpha
    BUY if: market cheaper
    PASS if: neither has attractive EV
    """
    # Mining cost per alpha
    # Assume 30-day amortization of entry cost
    daily_entry_cost = entry_cost_tao / 30
    mining_cost_per_alpha = daily_entry_cost / max(settled_alpha_day, 1e-9)
    
    # Market cost per alpha
    market_cost_per_alpha = alpha_price
    
    # Decision
    if mining_cost_per_alpha < market_cost_per_alpha * 0.8:
        decision = "MINE"
        advantage = (market_cost_per_alpha - mining_cost_per_alpha) / market_cost_per_alpha * 100
    elif market_cost_per_alpha < mining_cost_per_alpha * 0.8:
        decision = "BUY"
        advantage = (mining_cost_per_alpha - market_cost_per_alpha) / mining_cost_per_alpha * 100
    else:
        decision = "PASS"
        advantage = 0
    
    # Days to breakeven
    daily_earnings = settled_alpha_day * alpha_price
    days_to_breakeven = entry_cost_tao / max(daily_earnings, 1e-9)
    
    return {
        "mining_cost_per_alpha": round(mining_cost_per_alpha, 8),
        "market_cost_per_alpha": round(market_cost_per_alpha, 8),
        "decision": decision,
        "alpha_advantage_pct": round(advantage, 2),
        "days_to_breakeven": round(days_to_breakeven, 1),
        "entry_cost_tao": round(entry_cost_tao, 8),
        "daily_earnings_tao": round(daily_earnings, 8),
    }


def calculate_registration_timing(subnet_info: dict, current_burn: float) -> dict:
    """Registration timing optimizer.
    
    EV(register_now) vs EV(wait_1_epoch)
    """
    # Current burn
    burn = current_burn
    
    # Expected burn trend (simplified)
    registrations_24h = int(subnet_info.get("neuron_registrations_this_interval", 0) or 0)
    if registrations_24h > 5:
        burn_trend = "RISING"
        capacity_pressure = "HIGH"
    elif registrations_24h > 1:
        burn_trend = "STABLE"
        capacity_pressure = "MEDIUM"
    else:
        burn_trend = "FALLING"
        capacity_pressure = "LOW"
    
    # EV calculations (simplified)
    # Register now: pay current burn, start earning immediately
    ev_now = -burn  # Cost now
    
    # Wait 1 epoch: burn might change, but you miss earnings
    expected_burn_change = 0.1 if burn_trend == "RISING" else -0.05 if burn_trend == "FALLING" else 0
    ev_wait = -(burn * (1 + expected_burn_change))  # Slightly different cost
    
    # Decision
    if ev_now > ev_wait:
        action = "REGISTER_NOW"
        delay = 0
    else:
        action = "WAIT"
        delay = 360  # 1 epoch
    
    return {
        "current_burn_tao": round(burn, 8),
        "ev_register_now": round(ev_now, 8),
        "ev_wait_1_epoch": round(ev_wait, 8),
        "action": action,
        "burn_trend": burn_trend,
        "capacity_pressure": capacity_pressure,
        "recommended_delay_blocks": delay,
    }


if __name__ == "__main__":
    print("=== Three-View Payout Model ===\n")
    
    init_payout_tables()
    
    # Load oracle data
    conn = sqlite3.connect(str(ORACLE_DB))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        'SELECT data FROM subnet_snapshots WHERE scanned_at = (SELECT MAX(scanned_at) FROM subnet_snapshots)'
    ).fetchall()
    conn.close()
    
    subnets = [json.loads(r['data']) for r in rows]
    print(f"Loaded {len(subnets)} subnets")
    
    # Calculate for each subnet
    for subnet in subnets[:5]:  # Demo: first 5
        netuid = subnet.get('netuid', 0)
        neurons = subnet.get('neurons_data', [])
        emission = subnet.get('tao_equiv_day', 0)
        price = subnet.get('alpha_price', 0)
        
        if not neurons:
            continue
        
        # Mock neuron data from aggregate
        mock_neurons = [
            {"uid": i, "emission": emission / max(len(neurons), 1) * 1e9,
             "hotkey": "", "coldkey": ""}
            for i in range(min(len(neurons), 20))
        ]
        
        # Three views
        views = calculate_three_views(mock_neurons, price, 1000, 100000)
        persistence = calculate_seat_persistence(views)
        
        print(f"\nSN{netuid}:")
        print(f"  Top miner: {views[0]['realizable_tao_day']:.4f} TAO/day (realizable)")
        print(f"  Seats >= 0.1 TAO: {persistence.get('seats_ge_01', 0)}")
        print(f"  Seats >= 1 TAO: {persistence.get('seats_ge_1', 0)}")
        print(f"  HHI: {persistence.get('hhi', 0):.4f}")
        print(f"  Gini: {persistence.get('gini', 0):.4f}")
    
    print("\nTables initialized in market.duckdb")
