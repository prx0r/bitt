# Bittensor Strategy — Capability Arbitrage

## The Model

Bittensor tells the lab what capabilities are currently valuable.
The private lab learns those capabilities.
Then /mw looks for every other place those same capabilities can earn money.

**Flow:** Bittensor opportunity → benchmark → learn → earn TAO → reuse capability externally → earn again.

## Economic Surfaces (Ranked)

| Opportunity | Fit | Monetization |
|------------|-----|--------------|
| Subnet mining intelligence | 10/10 | Use ourselves; later API |
| Mining itself | 10/10 | Alpha/TAO emissions |
| Bounty subnets | 10/10 | Discrete prizes |
| External bounties using learned skills | 10/10 | Cash/crypto |
| Strategy mining / SN88 | 10/10 | Emissions |
| Own TAO/subnet allocation | 9/10 | Investment return |
| Incentive-mechanism auditing | 9/10 | Audits/consulting |
| Subnet launch/testing infrastructure | 9/10 | SaaS/services |
| Historical research/data API | 9/10 | API/data licensing |

## The Key Insight: Capability Arbitrage

One capability → multiple monetization surfaces:

```
"agent writes reliable patches"
  → SN11 TrajectoryRL (skills)
  → Gittensor (issue bounties)
  → SN62 Ridges (coding agent)
  → GitHub bounties
  → Contract development
  → Hackathons
  → Security remediation
```

## Architecture

```
Bittensor Oracle → opportunities
       ↓
Private Lab (WorkerKit, Hydra, CG)
       ↓
Reusable capabilities
       ↓
  ┌────┼────┐
  ▼    ▼    ▼
SN11  /mw  Capital
SN60  bugs  TAO
SN61  gigs  subnet α
SN62  consulting  SN88
```

## Priority Subnets

| Subnet | Match | Lab Adapter |
|--------|-------|-------------|
| SN60 BitSec | Security agents | security-01 |
| SN61 RedTeam | Dockerized challenges | CG technique |
| SN62 Ridges | Coding agent | WorkerKit |
| SN88 Investing | Portfolio management | strategy → allocation |
| SN11 TrajectoryRL | Skill production | learned skill |

## The Moat

> A continually growing private dataset of tasks → attempts → techniques → costs → failures → scores → rewards across many real economic environments.

Bittensor supplies continuous, objectively scored, financially incentivized tasks. External opportunities become additional environments where accumulated intelligence can be monetized.
