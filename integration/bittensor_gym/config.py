"""Configuration for Bittensor-MWGym integration."""
from __future__ import annotations

from dataclasses import dataclass, field


# ─── Subnet Registry ─────────────────────────────────────────────────

@dataclass(frozen=True)
class SubnetConfig:
    """Configuration for a single Bittensor subnet."""
    netuid: int
    name: str
    family_id: str              # MWGym FamilyWorldSpec ID
    description: str
    capabilities: tuple[str, ...]
    gates: tuple[str, ...]
    mutator_families: tuple[str, ...]
    alpha_price_approx: float   # TAO alpha token price (volatile)
    emission_per_day_approx: float  # TAO/day to miners (volatile)
    registration_cost_approx: float  # TAO burn to register
    neuron_count: int           # typically 256
    dockerized: bool            # whether subnet uses Docker sandbox
    official_repo: str          # GitHub URL
    score_dimensions: tuple[str, ...] = ()  # what validators score on


SUBNETS: dict[int, SubnetConfig] = {
    67: SubnetConfig(
        netuid=67,
        name="Harnyx",
        family_id="bittensor.deep_research",
        description="Autonomous deep research. Miners submit research systems.",
        capabilities=(
            "research.question_analyze",
            "research.source_find",
            "research.source_verify",
            "research.synthesize",
            "reason.causal",
            "text.write",
            "cost.minimize",
            "latency.minimize",
        ),
        gates=("output_quality_above_threshold", "sources_cited", "no_plagiarism"),
        mutator_families=("information", "source", "temporal", "cost"),
        alpha_price_approx=0.0055,
        emission_per_day_approx=20.7,
        registration_cost_approx=0.018,
        neuron_count=256,
        dockerized=True,
        official_repo="https://github.com/harnyx/harnyx",
        score_dimensions=("quality", "cost", "latency", "novelty"),
    ),
    62: SubnetConfig(
        netuid=62,
        name="Ridges",
        family_id="bittensor.swe_coding",
        description="Coding/SWE agents. Executable test verification.",
        capabilities=(
            "code.understand",
            "code.write",
            "code.debug",
            "code.test",
            "process.verify",
            "architecture.decide",
        ),
        gates=("builds", "tests_pass", "no_regression"),
        mutator_families=("repo", "information", "temporal", "tool_failure"),
        alpha_price_approx=0.011,
        emission_per_day_approx=34.7,
        registration_cost_approx=0.0005,
        neuron_count=256,
        dockerized=True,
        official_repo="https://github.com/ridgesai/ridges",
        score_dimensions=("test_pass_rate", "code_quality", "cost", "latency"),
    ),
    6: SubnetConfig(
        netuid=6,
        name="Numinous",
        family_id="bittensor.persistent_forecasting",
        description="Event forecasting with persistent memory. 24h re-forecast cycles.",
        capabilities=(
            "forecast.probability",
            "forecast.calibrate",
            "memory.manage",
            "reason.uncertain",
            "source.integrate",
        ),
        gates=("probability_valid", "confidence_calibration", "memory_persisted"),
        mutator_families=("information", "temporal", "source"),
        alpha_price_approx=0.0029,
        emission_per_day_approx=9.3,
        registration_cost_approx=0.05,
        neuron_count=256,
        dockerized=True,
        official_repo="https://github.com/numinouslabs/numinous",
        score_dimensions=("brier_score", "calibration", "novelty"),
    ),
    15: SubnetConfig(
        netuid=15,
        name="ORO",
        family_id="bittensor.shopping_agents",
        description="AI shopping agents. 2.5M real products. ShoppingBench ground truth.",
        capabilities=(
            "product.search",
            "product.recommend",
            "product.compare",
            "tool.invoke",
            "intent.understand",
        ),
        gates=("recommendation_valid", "format_compliant", "product_found"),
        mutator_families=("information", "tool_failure", "temporal"),
        alpha_price_approx=0.035,
        emission_per_day_approx=0,  # need fresh data
        registration_cost_approx=0.1,
        neuron_count=256,
        dockerized=True,
        official_repo="https://github.com/ORO-AI/oro",
        score_dimensions=("accuracy", "format_compliance", "cost"),
    ),
}

# ─── TAO Economics ──────────────────────────────────────────────────

TAO_PRICE_USD = 1.0  # placeholder — fetch live from CoinGecko/MEXC

def tao_to_usd(tao: float) -> float:
    return tao * TAO_PRICE_USD

def usd_to_tao(usd: float) -> float:
    return usd / TAO_PRICE_USD if TAO_PRICE_USD > 0 else 0


# ─── RPC Endpoints ──────────────────────────────────────────────────

RPC_ENDPOINTS = {
    "mainnet": {
        "substrate": "wss://entrypoint-finney.opentensor.ai",
        "evm": "https://lite.chain.opentensor.ai",
        "blockmachine": "https://rpc.blockmachine.io",
        "onfinality": "https://bittensor-finney.api.onfinality.io/public",
    },
    "testnet": {
        "substrate": "wss://test.entrypoint-finney.opentensor.ai",
        "evm": "https://test.chain.opentensor.ai",
    },
}

# ─── API Endpoints ──────────────────────────────────────────────────

API_ENDPOINTS = {
    "taostats": "https://taostats.io",
    "taostats_api": "https://docs.taostats.io",
    "metagraph": "https://api.metagraph.sh/api/v1",
    "metagraph_mcp": "https://api.metagraph.sh/mcp",
    "taomarketcap": "https://api.taomarketcap.com",
    "coingecko": "https://www.coingecko.com/en/api/bittensor",
    "opentaoapi": "https://opentao.rpmsystems.io",
}

# ─── Wallet Config ──────────────────────────────────────────────────

@dataclass
class WalletConfig:
    """Bittensor wallet configuration."""
    coldkey: str = ""
    hotkey: str = ""
    wallet_path: str = "~/.bittensor/wallets/"
    network: str = "finney"  # finney or testnet

WALLET = WalletConfig()
