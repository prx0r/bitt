# bittensor_gym

Bridge between Bittensor subnet economies and MWGym evolution.

## What This Does

Plugs Bittensor's live agent evaluation networks into MWGym's CGE
(Competitive Game Environment) framework. This means:

- **Train** workers against Bittensor subnet objectives locally
- **Evolve** worker policies via CGE adversarial curriculum
- **Transfer** lab-trained organisms into live TAO emission networks
- **Track** cost/quality/runtime across synthetic and economic worlds

## Target Subnets

| SN | Name | Objective | Family ID |
|----|------|-----------|-----------|
| 67 | Harnyx | Deep research (quality + cost + latency + novelty) | `bittensor.deep_research` |
| 62 | Ridges | Coding/SWE agents (executable tests) | `bittensor.swe_coding` |
| 6 | Numinous | Forecasting + persistent memory (Brier score) | `bittensor.persistent_forecasting` |
| 15 | ORO | Shopping/product agents (ShoppingBench) | `bittensor.shopping_agents` |

## Architecture

```
MWGym CGE World ←── BittensorWorld subclass
       ↓
   FamilyWorldSpec (bittensor.*)
       ↓
   Adversary mutates (difficulty, cost, noise)
       ↓
   Curriculum selects next world
       ↓
   BittensorHarness.run() executes agent
       ↓
   FailureVector → Hydra records → CGE evolves
       ↓
   Winner → live Bittensor network
```

## Quick Start

```python
# 1. Import and auto-registers everything
from bittensor_gym import families, worlds

# 2. Use BittensorHarness in MWGym's wired loop
from bittensor_gym.harness import BittensorHarness, BittensorHarnessConfig

config = BittensorHarnessConfig(subnet_id=67, mode="SUBNET_EMULATE")
harness = BittensorHarness(config)

# 3. Run through MWGym pipeline
# (families + worlds are auto-registered)
```

## Modes

| Mode | What | Wallet Required | Network |
|------|------|-----------------|---------|
| `SUBNET_EMULATE` | Run cloned subnet code locally | No | No |
| `SUBNET_LOCAL` | Run subnet miner in Docker sandbox | No | No |
| `SUBNET_REMOTE` | Query subnet axons via Bittensor | Yes | Yes |

## Directory Structure

```
bitt/
├── core/           # Bittensor SDK, subnet template, governance
├── subnets/        # Cloned subnet repos (SN6, SN15, SN62, SN67)
├── tooling/        # Explorer APIs, miner automation, chain tools
├── reference/      # Metaculus bots, forecasting tools, awesome-bittensor
├── community/      # Community subnet implementations
└── integration/    # THIS PACKAGE — bittensor_gym
    ├── pyproject.toml
    └── bittensor_gym/
        ├── __init__.py
        ├── config.py       # Subnet registry, RPC endpoints, wallet config
        ├── harness.py      # BittensorHarness (HarnessAdapter protocol)
        ├── worlds.py       # CGE world classes (DeepResearch, SWE, Forecasting, Shopping)
        ├── families.py     # FamilyWorldSpec registrations
        └── bats_bridge.py  # BATS router extensions + inference client
```

## Extending

### Adding a new subnet

1. Add `SubnetConfig` in `config.py`
2. Create `BaseWorld` subclass in `worlds.py`
3. Register in `BITTENSOR_WORLD_CLASSES`
4. FamilyWorldSpec auto-created from SubnetConfig

### Using Bittensor models via BATS

```python
from bittensor_gym.bats_bridge import patch_bats_router
from mwgym.harnesses.pydantic_bats import BATSRouter

patch_bats_router(BATSRouter)
# Bittensor models now available in BATS routing
```

## Cloned Repos

### Core
- `opentensor/bittensor` — Bittensor SDK (v11 in subtensor monorepo)
- `opentensor/bittensor-subnet-template` — Official subnet template

### Target Subnets
- `harnyx/harnyx` — SN67 deep research
- `ridgesai/ridges` — SN62 coding agents
- `numinouslabs/numinous` — SN6 forecasting
- `ORO-AI/oro` — SN15 shopping agents

### Reference
- `Metaculus/forecasting-tools` — Metaculus bot framework
- `masxai/masxai-subnet` — Bittensor forecasting subnet
- `corvxai/almanac` — Dual-incentive forecasting subnet

### Tooling
- `JSONbored/metagraphed` — Subnet integration registry
- `RyanMercier/OpenTaoAPI` — Self-hosted Taostats alternative
- `taostat/chainwake` — Event-driven chain monitoring
- `hienpatch/bittensor-miner-automation-toolkit` — Miner automation
