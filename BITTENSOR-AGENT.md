# Bittensor Agent — Private Economic Agent

## Mandate

Maximize risk-adjusted economic output and learning from Bittensor using the resources available to the lab.

## Architecture

```
              WALLET
                │
      ┌─────────┴──────────┐
      │                    │
      ▼                    ▼
   CAPITAL                LABOR
      │                    │
      ▼                    ▼
 allocator          opportunity oracle
      │                    │
 TAO / α             candidate subnets
                           │
                           ▼
                    capability match
                           │
                           ▼
                       benchmark
                           │
                           ▼
                    build miner adapter
                           │
                           ▼
                        deploy
                           │
              ┌────────────┘
              ▼
          rewards/scores
              │
              ▼
            HYDRA
```

## Three Uses of Resources

```
TAO
 ├── HOLD
 ├── ALLOCATE → subnet alpha
 └── SPEND
      ├── miner registration
      ├── inference
      ├── compute
      └── experiments

AGENT TIME
 ├── SN11 (skills)
 ├── SN60 (security)
 ├── SN61 (redteam)
 ├── SN62 (coding)
 ├── SN74 (OSS)
 ├── SN88 (allocation)
 └── new opportunities

INTELLIGENCE
 ├── improve allocation
 ├── improve miners
 ├── identify exploits/risks
 └── feed /mw
```

## What We Store (the moat)

Observations the chain CANNOT reconstruct:
- SN62 README version at time T
- Validator code commits
- Benchmark versions
- GitHub velocity
- API expenditure
- Discord announcements
- Our local benchmark scores
- Our agent's estimated capability
- Previous failures on similar tasks
- Hydra memories available at that point
- Expected daily revenue
- The exact strategy we evaluated
- Why we rejected/accepted it

## What We DON'T Store

The blockchain itself — it's the historical ledger.

## Data Model

```
observation
  observed_at, block_hash, block_number
  entity, source, source_version, content_hash
  raw_evidence, parsed_facts

derived_feature
  observed_at, feature_version
  github_acceleration, emission_growth
  miner_competition, estimated_operating_cost
  survival_threshold, lab_fit, security_risk

decision
  decision_time, knowledge_cutoff
  available_capital, available_compute
  candidates[], predicted_reward[], predicted_cost[]
  action, rationale, confidence
  strategy_commit, hydra_context_digest

outcome
  realized_cost, realized_reward
  score, emissions, UID_survival
  PnL, failure_reason
```

## Competitive Landscape

| Project | What | Our Edge |
|---------|------|----------|
| AlphaGap | 20+ signals, top-10 index | Autonomous learning |
| SubnetStats | Chain data analytics | Security analysis |
| TrustedStake | Non-custodial execution | CG/CGE |
| SN88 | Portfolio management | Submit strategies |
| dtao-trader | Signal generation | Full loop |

## The Moat

> A continually growing private dataset of tasks → attempts → techniques → costs → failures → scores → rewards across many real economic environments.

Bittensor supplies continuous, objectively scored, financially incentivized tasks. External opportunities become additional environments where accumulated intelligence can be monetized.
