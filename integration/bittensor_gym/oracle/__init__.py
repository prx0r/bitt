"""Bittensor Oracle — opportunity scanner and experiment controller.

Scans Bittensor subnets, analyzes economics, calculates difficulty/lab value,
and produces actionable recommendations for the Moltwork learning loop.
"""
from .snapshot import BittensorOpportunitySnapshot
from .scanner import ChainScanner, ScannerConfig, ScannerStore
from .mechanism import MechanismInfo, get_known_mechanism, KNOWN_MECHANISMS
from .reward_analyzer import analyze_reward_distribution, RewardAnalysis
from .difficulty import calculate_difficulty, calculate_lab_value
from .scorer import score_opportunity, rank_opportunities, OpportunityAssessment
from .engine import BittensorOracle, TARGET_SUBNETS

__all__ = [
    "BittensorOpportunitySnapshot",
    "ChainScanner",
    "ScannerConfig",
    "ScannerStore",
    "MechanismInfo",
    "get_known_mechanism",
    "KNOWN_MECHANISMS",
    "analyze_reward_distribution",
    "RewardAnalysis",
    "calculate_difficulty",
    "calculate_lab_value",
    "score_opportunity",
    "rank_opportunities",
    "OpportunityAssessment",
    "BittensorOracle",
    "TARGET_SUBNETS",
]
