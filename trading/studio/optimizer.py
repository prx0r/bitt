"""Fleece-style Optimizer — Thompson sampling + CGE for strategy evolution.

Like Fleece:
- Each strategy is a "fish" with win/loss history
- Thompson sampling decides capital allocation
- CGE proposes mutations (new factor weights, thresholds)
- Graveyard preserves failed experiments
- Regime detection adapts allocation
"""
import json
import random
import sqlite3
from pathlib import Path
from datetime import datetime
from collections import defaultdict


STUDIO_DIR = Path("/root/bitt/trading/studio")
GRAVEYARD_DIR = STUDIO_DIR / "graveyard"
GRAVEYARD_DIR.mkdir(parents=True, exist_ok=True)


class ThompsonPool:
    """Bayesian bandit for strategy allocation.
    
    Each strategy is a "fish" with win/loss history.
    Posterior: Beta(alpha0 + wins, beta0 + losses)
    Sample from posterior → weight by sampled rate.
    """
    
    def __init__(self):
        self.history = defaultdict(lambda: {"wins": 1, "losses": 1})
    
    def update(self, strategy_id: str, won: bool):
        """Update win/loss after a trade."""
        if won:
            self.history[strategy_id]["wins"] += 1
        else:
            self.history[strategy_id]["losses"] += 1
    
    def sample_weights(self, strategy_ids: list, n_samples: int = 1000) -> dict:
        """Sample allocation weights from posteriors."""
        weights = {}
        for sid in strategy_ids:
            h = self.history[sid]
            samples = [random.betavariate(h["wins"], h["losses"]) for _ in range(n_samples)]
            weights[sid] = sum(samples) / len(samples)
        
        # Normalize
        total = sum(weights.values())
        if total > 0:
            weights = {k: v / total for k, v in weights.items()}
        
        return weights
    
    def get_rankings(self) -> list:
        """Get strategies ranked by expected win rate."""
        rankings = []
        for sid, h in self.history.items():
            expected = h["wins"] / (h["wins"] + h["losses"])
            rankings.append({"strategy": sid, "expected_win_rate": expected, 
                           "wins": h["wins"], "losses": h["losses"]})
        return sorted(rankings, key=lambda x: x["expected_win_rate"], reverse=True)


class CGE:
    """Combinatorial Genetic Evolution — proposes strategy mutations.
    
    Like Fleece's Orca: reads what worked, proposes improvements,
    never judges its own proposals.
    """
    
    def __init__(self):
        self.mutations_tried = []
        self.graveyard = []
    
    def propose_mutation(self, current_best: dict) -> dict:
        """Propose a mutation of the best strategy."""
        # Random mutation type
        mutation_type = random.choice([
            "adjust_weight",
            "change_threshold",
            "add_factor",
            "remove_factor",
            "change_lookback",
            "combine_factors",
        ])
        
        if mutation_type == "adjust_weight":
            # Adjust a random factor's weight
            factors = current_best.get("factors", [])
            if factors:
                idx = random.randint(0, len(factors) - 1)
                factor = factors[idx].copy()
                factor["weight"] *= random.uniform(0.5, 2.0)
                new_factors = factors.copy()
                new_factors[idx] = factor
                return {"type": "adjust_weight", "factors": new_factors}
        
        elif mutation_type == "change_threshold":
            return {"type": "change_threshold", 
                    "entry_threshold": current_best.get("entry_threshold", 0.3) * random.uniform(0.5, 2.0)}
        
        elif mutation_type == "combine_factors":
            # Combine two strategies
            return {"type": "combine", "note": "Combine with another top strategy"}
        
        return {"type": "unknown"}
    
    def evaluate_proposal(self, proposal: dict, backtest_result: dict) -> bool:
        """Decide whether to accept a proposal."""
        # Accept if return improves
        return backtest_result.get("return_pct", 0) > 0
    
    def archive_failure(self, strategy_id: str, reason: str):
        """Move failed strategy to graveyard."""
        self.graveyard.append({
            "strategy_id": strategy_id,
            "reason": reason,
            "archived_at": datetime.utcnow().isoformat(),
        })


class FleeceOptimizer:
    """Complete Fleece-like optimization loop."""
    
    def __init__(self, studio_dir: Path):
        self.studio_dir = studio_dir
        self.thompson = ThompsonPool()
        self.cge = CGE()
        self.generation = 0
        self.history = []
    
    def run_generation(self, strategies: list, backtest_fn) -> dict:
        """Run one generation of evolution."""
        self.generation += 1
        
        # 1. Backtest all strategies
        results = {}
        for strat in strategies:
            result = backtest_fn(strat)
            results[strat["id"]] = result
            
            # Update Thompson pool
            won = result.get("return_pct", 0) > 0
            self.thompson.update(strat["id"], won)
        
        # 2. Get Thompson weights
        strategy_ids = [s["id"] for s in strategies]
        weights = self.thompson.sample_weights(strategy_ids)
        
        # 3. Propose mutations for top strategy
        rankings = self.thompson.get_rankings()
        if rankings:
            best = rankings[0]
            proposal = self.cge.propose_mutation(best)
        
        # 4. Log
        gen_result = {
            "generation": self.generation,
            "timestamp": datetime.utcnow().isoformat(),
            "strategies_tested": len(strategies),
            "results": {k: {"return": v.get("return_pct", 0), "trades": v.get("trades", 0)} 
                       for k, v in results.items()},
            "weights": weights,
            "rankings": rankings[:5],
            "proposal": proposal if rankings else None,
        }
        
        self.history.append(gen_result)
        return gen_result
    
    def save_state(self):
        """Save optimizer state."""
        state = {
            "generation": self.generation,
            "thompson_history": dict(self.thompson.history),
            "cge_graveyard": self.cge.graveyard,
            "history": self.history[-10:],  # Last 10 generations
        }
        
        path = self.studio_dir / "optimizer_state.json"
        with open(path, "w") as f:
            json.dump(state, f, indent=2)


if __name__ == "__main__":
    print("=== Fleece-style Optimizer ===\n")
    
    optimizer = FleeceOptimizer(STUDIO_DIR)
    
    # Load strategies from leaderboard
    lb_path = STUDIO_DIR / "leaderboard.json"
    if lb_path.exists():
        with open(lb_path) as f:
            lb = json.load(f)
        
        strategies = []
        for key, entry in lb["strategies"].items():
            strategies.append({
                "id": entry["strategy"],
                "name": entry["name"],
                "params": entry["params"],
            })
        
        # Simulate one generation
        def mock_backtest(strat):
            return {"return_pct": 0, "trades": 0}
        
        result = optimizer.run_generation(strategies, mock_backtest)
        
        print(f"Generation: {result['generation']}")
        print(f"Strategies tested: {result['strategies_tested']}")
        print(f"Rankings:")
        for r in result["rankings"][:5]:
            print(f"  {r['strategy']}: {r['expected_win_rate']:.1%}")
        
        optimizer.save_state()
        print(f"\nState saved to {STUDIO_DIR}/optimizer_state.json")
