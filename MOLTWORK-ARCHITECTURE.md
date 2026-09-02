# Moltwork Architecture — The Machine

## The Hierarchy

```
                 MW ORACLE
             "Where is money?"
                    │
            ┌───────┼────────┐
            ▼       ▼        ▼
        Bittensor  bounties  gigs
            │
            ▼
       Environment Oracle
       "What exactly?"
            │
            ▼
        PRIVATE LAB
        "Can we do it?"
            │
            ▼
        WorkerKit
        "Do the work"
            │
            ▼
         Treasury
        "Get paid"
            │
            ▼
           Hydra
         "Learn"
```

## Moltwork = Operating System for Economically Autonomous Agents

Not a crypto wallet company. Not a miner toolkit. An OS.

### Core Components

```
MOLTWORK DESKTOP
│
├── WorkerKit
│   ├── agents
│   ├── skills
│   ├── benchmarks
│   └── Hydra learning loop
│
├── MoltVault
│   └── capability vault (not just secrets)
│       ├── API credentials
│       ├── scoped signing credentials
│       └── agent permissions
│
├── Oracles
│   ├── Bittensor Oracle
│   ├── MW opportunity Oracle
│   └── later finance/market Oracles
│
├── Treasury
│   ├── Bittensor
│   │   ├── TAO
│   │   ├── alpha positions
│   │   ├── miner hotkeys
│   │   └── rebalancer
│   └── later EVM/Solana/etc.
│
└── Opportunity adapters
    ├── SN11 (skills)
    ├── SN60 (security)
    ├── SN61 (redteam)
    ├── SN62 (coding)
    ├── SN74 (OSS)
    ├── SN88 (allocation)
    ├── GitHub bounties
    ├── bug bounties
    └── hackathons
```

## The Key Insight

**Bittensor is Moltwork's first fully machine-native economy.**

It supplies:
- Continuous, objectively scored tasks
- Financial incentives (TAO/alpha)
- On-chain identity and payments
- Proxy-based security

The agent doesn't need to understand Bittensor. It just needs:
1. An agent
2. A wallet
3. A budget

Moltwork figures out the rest.

## The Moat

> A continually growing private dataset of tasks → attempts → techniques → costs → failures → scores → rewards across many real economic environments.

Bittensor is one environment. External bounties, gigs, hackathons are others. The same accumulated intelligence transfers across all of them.

## The Product Structure

### Open layer (distribution)
- Moltwork desktop
- WorkerKit interface
- Bittensor wallet adapter
- Subnet adapter SDK
- Logging schema
- Intent format

### Proprietary intelligence (defensibility)
- MW Oracle
- Capability matcher
- Opportunity rankings
- ROI estimates
- Benchmark priors
- Hydra-derived intelligence

The desktop app connects to Moltwork Intelligence. The intelligence stays private.
