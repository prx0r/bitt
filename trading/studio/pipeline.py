"""Hypothesis → Strategy → Test → Optimize Pipeline.

The full loop:
1. HYPOTHESIS: structured claim about market behavior
2. STRATEGY: machine-readable rules derived from hypothesis
3. TEST: backtest against historical data
4. OPTIMIZE: Fleece-style evolution (Thompson + CGE)
5. LOG: immutable results in HydraDB format

Each step is a function. The pipeline is composable.
"""
import json
import hashlib
import sqlite3
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Optional


# === HYPOTHESIS FORMAT ===

@dataclass
class Hypothesis:
    """Structured claim about market behavior."""
    hypothesis_id: str = ""
    claim: str = ""
    rationale: str = ""
    domain: str = "bittensor_subnet_trading"
    factors: list = field(default_factory=list)
    horizon: str = "1d"
    expected_direction: str = "positive"
    confidence_before: float = 0.5
    
    # Provenance
    source: str = ""  # email, paper, observation
    created_at: str = ""
    data_cutoff: str = ""
    
    def to_dict(self) -> dict:
        d = asdict(self)
        if not self.hypothesis_id:
            d["hypothesis_id"] = f"hyp_{hashlib.sha256(self.claim.encode()).hexdigest()[:12]}"
        if not self.created_at:
            d["created_at"] = datetime.utcnow().isoformat()
        return d
    
    @classmethod
    def from_dict(cls, d: dict) -> "Hypothesis":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


# === STRATEGY FORMAT ===

@dataclass
class Strategy:
    """Machine-readable trading rules."""
    strategy_id: str = ""
    name: str = ""
    hypothesis_id: str = ""
    
    # Factor definitions
    factors: list = field(default_factory=list)  # [{name, column, direction, weight, lookback}]
    
    # Entry/exit rules
    entry_threshold: float = 0.3
    exit_rules: list = field(default_factory=list)
    
    # Position sizing
    top_n: int = 5
    max_position_pct: float = 0.20
    cash_pct: float = 0.05
    
    # Risk
    stop_loss: Optional[float] = None
    max_hold_hours: int = 168
    
    # Metadata
    version: str = "1.0"
    created_at: str = ""
    
    def to_dict(self) -> dict:
        d = asdict(self)
        if not self.strategy_id:
            d["strategy_id"] = f"strat_{hashlib.sha256(self.name.encode()).hexdigest()[:12]}"
        if not self.created_at:
            d["created_at"] = datetime.utcnow().isoformat()
        return d
    
    @classmethod
    def from_dict(cls, d: dict) -> "Strategy":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})
    
    def to_sn88_csv(self, hotkey: str, allocation: dict) -> str:
        """Convert to SN88-compatible CSV."""
        lines = ["uid,date,block,init,fund,strat"]
        strat_dict = {int(k): round(v, 4) for k, v in allocation.items() if v > 0}
        lines.append(f"{hotkey},{datetime.utcnow().strftime('%Y-%m-%d')},0,1,2000,{str(strat_dict)}")
        return "\n".join(lines)


# === TEST RESULT FORMAT ===

@dataclass
class TestResult:
    """Immutable test result."""
    result_id: str = ""
    hypothesis_id: str = ""
    strategy_id: str = ""
    run_id: str = ""
    
    # Metrics
    return_pct: float = 0.0
    max_drawdown: float = 0.0
    sharpe: float = 0.0
    sortino: float = 0.0
    win_rate: float = 0.0
    n_trades: int = 0
    profit_factor: float = 0.0
    
    # Factor ICs
    factor_ics: dict = field(default_factory=dict)
    
    # Walk-forward
    n_folds: int = 0
    fold_returns: list = field(default_factory=list)
    walk_forward_return: float = 0.0
    
    # Provenance
    data_start: str = ""
    data_end: str = ""
    n_subnets: int = 0
    n_observations: int = 0
    manifest_hash: str = ""
    created_at: str = ""
    
    def to_dict(self) -> dict:
        d = asdict(self)
        if not self.result_id:
            d["result_id"] = f"res_{hashlib.sha256(json.dumps(d, sort_keys=True).encode()).hexdigest()[:12]}"
        if not self.created_at:
            d["created_at"] = datetime.utcnow().isoformat()
        return d


# === HYDRA FORMAT (for learning) ===

@dataclass
class Observation:
    """Single observation in the learning graph."""
    timestamp: str
    entity_type: str  # "subnet", "strategy", "hypothesis"
    entity_id: str
    event_type: str  # "created", "tested", "promoted", "rejected"
    data: dict
    source: str = ""
    
    def to_event(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "event_type": self.event_type,
            "data": self.data,
            "source": self.source,
        }


# === PIPELINE ===

class Pipeline:
    """Hypothesis → Strategy → Test → Optimize."""
    
    def __init__(self, studio_dir: Path):
        self.studio_dir = studio_dir
        self.hypotheses_dir = studio_dir / "hypotheses"
        self.compiled_dir = studio_dir / "compiled"
        self.results_dir = studio_dir / "results"
        self.graveyard_dir = studio_dir / "graveyard"
        
        for d in [self.hypotheses_dir, self.compiled_dir, self.results_dir, self.graveyard_dir]:
            d.mkdir(parents=True, exist_ok=True)
    
    def submit_hypothesis(self, hypothesis: Hypothesis) -> str:
        """Step 1: Submit a hypothesis."""
        h = hypothesis.to_dict()
        path = self.hypotheses_dir / f"{h['hypothesis_id']}.json"
        with open(path, "w") as f:
            json.dump(h, f, indent=2)
        return h["hypothesis_id"]
    
    def compile_strategy(self, hypothesis: Hypothesis, factors: list) -> Strategy:
        """Step 2: Compile hypothesis into machine-readable strategy."""
        strategy = Strategy(
            hypothesis_id=hypothesis.hypothesis_id or f"hyp_{hashlib.sha256(hypothesis.claim.encode()).hexdigest()[:12]}",
            name=hypothesis.claim[:50],
            factors=factors,
        )
        
        path = self.compiled_dir / f"{strategy.strategy_id}.json"
        with open(path, "w") as f:
            json.dump(strategy.to_dict(), f, indent=2)
        
        return strategy
    
    def run_test(self, strategy: Strategy, data_start: str, data_end: str) -> TestResult:
        """Step 3: Test strategy against data."""
        # This calls the backtester
        from trading.engine.backtester_v2 import run_backtest
        
        result = TestResult(
            hypothesis_id=strategy.hypothesis_id,
            strategy_id=strategy.strategy_id,
            data_start=data_start,
            data_end=data_end,
        )
        
        # Run backtest
        bt_result = run_backtest(strategy, data_start, data_end)
        result.return_pct = bt_result.get("return_pct", 0)
        result.max_drawdown = bt_result.get("max_drawdown", 0)
        result.sharpe = bt_result.get("sharpe", 0)
        result.n_trades = bt_result.get("n_trades", 0)
        result.win_rate = bt_result.get("win_rate", 0)
        
        # Save
        r = result.to_dict()
        path = self.results_dir / f"{r['result_id']}.json"
        with open(path, "w") as f:
            json.dump(r, f, indent=2)
        
        return result
    
    def evaluate_and_decide(self, result: TestResult) -> str:
        """Step 4: Decide promote/reject/archive."""
        if result.return_pct > 1.0 and result.sharpe > 0.5:
            return "PROMOTE"
        elif result.return_pct > 0:
            return "ARCHIVE"
        else:
            return "REJECT"
    
    def archive_graveyard(self, strategy: Strategy, result: TestResult, reason: str):
        """Move to graveyard with tombstone."""
        tombstone = {
            "strategy": strategy.to_dict(),
            "result": result.to_dict(),
            "reason": reason,
            "archived_at": datetime.utcnow().isoformat(),
        }
        path = self.graveyard_dir / f"{strategy.strategy_id}.json"
        with open(path, "w") as f:
            json.dump(tombstone, f, indent=2)


# === FACTOR LIBRARY ===

FACTORS = {
    "vol_7d": {"name": "7-day Volatility", "column": "vol", "direction": "asc", "weight": 3.0, "lookback": 336},
    "vol_24h": {"name": "24h Volatility", "column": "vol", "direction": "asc", "weight": 2.0, "lookback": 48},
    "vol_6h": {"name": "6h Volatility", "column": "vol", "direction": "asc", "weight": 1.5, "lookback": 72},
    "momentum_7d": {"name": "7d Momentum", "column": "mom", "direction": "desc", "weight": 1.0, "lookback": 336},
    "momentum_24h": {"name": "24h Momentum", "column": "mom", "direction": "desc", "weight": 1.0, "lookback": 48},
    "zscore_7d": {"name": "7d Z-Score", "column": "zsc", "direction": "asc", "weight": 1.5, "lookback": 336},
    "support_20d": {"name": "20d Support", "column": "sup", "direction": "asc", "weight": 2.0, "lookback": 480},
    "squeeze": {"name": "Range Squeeze", "column": "sq", "direction": "desc", "weight": 1.5, "lookback": 336},
    "active_ratio": {"name": "Active Neuron Ratio", "column": "active_ratio", "direction": "desc", "weight": 1.0, "lookback": 0},
    "emit_per": {"name": "Emission per Neuron", "column": "emit_per", "direction": "asc", "weight": 0.5, "lookback": 0},
    "price_level": {"name": "Price Level", "column": "price", "direction": "desc", "weight": 0.5, "lookback": 0},
}


if __name__ == "__main__":
    print("=== Hypothesis → Strategy → Test Pipeline ===\n")
    print("Factor Library:")
    for name, info in FACTORS.items():
        print(f"  {name}: {info['name']} (weight={info['weight']}, lookback={info['lookback']})")
