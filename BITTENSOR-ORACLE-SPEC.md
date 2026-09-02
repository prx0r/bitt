# Moltwork Bittensor Opportunity Engine — Implementation Specification

## Mission

Build a mechanism-aware Bittensor opportunity scanner and experiment controller.

It must answer:

**"Given our current WorkerVersions, capital, compute, API credits, hardware and historical performance, which subnet should Moltwork work on next, what experiment should it run, and should it remain offline or spend TAO to enter?"**

Do not rank subnets by headline emissions.

The output must distinguish:

1. economic attractiveness;
2. attainable expected reward;
3. training value to Moltwork;
4. difficulty;
5. entry/capital risk;
6. feedback quality;
7. skill transfer;
8. source/data confidence.

---

# 1. Create `BittensorOpportunitySnapshot`

One immutable snapshot per subnet per crawl.

Required fields:

```python
@dataclass
class BittensorOpportunitySnapshot:
    observed_at: datetime
    netuid: int
    name: str

    # Chain state
    alpha_price_tao: Decimal
    miner_pool_alpha_day: Decimal | None
    miner_pool_tao_equiv_day: Decimal | None
    owner_share: float | None
    validator_share: float | None
    miner_share: float | None

    registration_burn_tao: Decimal
    collateral_lock_share: float
    min_burn_tao: Decimal | None
    max_burn_tao: Decimal | None
    burn_half_life_blocks: int | None
    burn_increase_mult: float | None

    neuron_capacity: int
    registered_neurons: int
    validator_count: int

    registered_miner_uids: int | None
    emitting_miners: int | None
    benchmark_scored_competitors: int | None

    tempo_blocks: int
    immunity_blocks: int | None

    # Mechanism
    task_family: str
    scoring_type: str
    reward_mechanism: str
    payout_curve: dict
    eligibility_rules: dict
    submission_fee_tao: Decimal
    cooldown_seconds: int | None
    feedback_latency_seconds: int | None

    # Environment
    local_eval_available: bool
    replay_available: bool
    deterministic_verifier: bool
    hidden_eval: bool
    fresh_task_generation: bool

    gpu_required: bool
    min_vram_gb: float | None
    min_ram_gb: float | None
    min_storage_gb: float | None

    API_cost_estimate_usd_episode: Decimal | None
    estimated_compute_usd_episode: Decimal | None

    # Repository/protocol health
    repo_last_commit_at: datetime | None
    commits_30d: int | None
    protocol_version: str | None

    # Quality/provenance
    mechanism_source: str
    mechanism_source_commit: str | None
    chain_block: int
    source_confidence: float
    discrepancy_flags: list[str]
```

Never overwrite a snapshot.

Hydra should be able to reconstruct what Moltwork believed about SN118 at a particular historical decision.

---

# 2. Source hierarchy

Economics and mechanics are different data domains.

### Chain economics

Prefer direct Bittensor SDK/CLI chain reads.

The agent should discover current operations from the SDK rather than hardcode CLI syntax.

Start every runtime with:

```bash
btcli tools
```

and use the SDK tool/read catalogs.

All read commands should use machine-readable JSON.

Important reads include:

```text
subnets
subnet
metagraph
burn
subnet-hyperparameters
collateral-policy
alpha-price
alpha-prices
epoch-status
blocks-until-next-epoch
neurons
```

Examples:

```bash
btcli query subnets --json
btcli query metagraph --netuid 118 --json
btcli query burn --netuid 118 --json
```

The exact installed CLI schema wins over copied documentation.

### Scoring/reward mechanism

Priority:

```text
1. live subnet API / network-config endpoint
2. active validator code at exact current commit
3. current official subnet repo documentation
4. Bittensor explorer metadata
5. third-party research
6. social media
```

Never infer a payout mechanism from metagraph incentives alone.

For every subnet, explicitly identify:

```text
burn UID
owner UID
validator UIDs
miner UIDs
reserved UIDs
special-purpose UIDs
```

before estimating contestable rewards.

### Contradiction handling

If two authoritative sources disagree:

```text
mechanism_status = UNVERIFIED
block_mainnet_spend = True
```

until a live endpoint/current validator implementation resolves it.

Examples already encountered:

```text
Ditto:
live leaderboard and static miner guide have shown different benchmark versions.

Minos:
cached docs have contained different burn/winner policies.

SOMA:
explorer miner counts have been inconsistent with other snapshots.

Ditto/Bittensor.ai:
explorer description still contains legacy HODL mechanism text.
```

These are expected conditions, not exceptional ones.

---

# 3. Track reward distributions, not just pools

For every current metagraph collect miner incentive shares.

Calculate:

```python
p = normalized_current_miner_incentive_shares

HHI = sum(x*x for x in p)

effective_earners = 1 / HHI
top1_share = p[0]
top3_share = sum(p[:3])
top5_share = sum(p[:5])
top10_share = sum(p[:10])
```

Also store the explicit protocol payout curve.

For Ditto:

```python
[0.65, 0.14, 0.10, 0.07, 0.04]
```

For Gradients:

```text
top two in each tournament:
approximately 80 / 20
then multiply by tournament-type allocation
and champion-decay/multiplier rules.
```

For winner-take-all protocols:

```python
[1.0, 0, 0, ...]
```

For dynamic mechanisms, fetch them every crawl.

---

# 4. Calculate *attainable* reward

The core quantity is not:

```text
miner_pool_tao_day
```

It is:

```text
expected_attainable_tao_day
```

For ranked protocols:

```python
expected_attainable_tao_day = sum(
    P(rank == r | our sealed evaluation distribution)
    * payout_share[r]
    * contestable_miner_pool_tao_equiv_day
    for r in paid_ranks
)
```

For continuous/proportional protocols use the subnet's actual scoring-to-weight transform.

Do not invent a generic approximation if validator code exposes the real transform.

Store:

```text
P(any_reward)
P(top10)
P(top5)
P(top3)
P(champion)
expected_tao_day
p05_tao_day
p50_tao_day
p95_tao_day
```

Probabilities must come from Moltwork's own sealed evaluations where possible.

---

# 5. Model cost properly

`CostToAttempt`:

```text
registration burn actually lost
+ non-refundable submission fees
+ expected re-registration/pruning cost
+ API inference
+ local compute
+ rented GPU
+ server
+ data transfer/storage
+ human intervention
```

Registration burn is NOT fixed.

Refresh immediately before registration.

Registration price dynamically decays and jumps after other registrations.

Never cache it as an opportunity constant.

---

# 6. Model alpha risk

Miner rewards are subnet alpha.

Explorer TAO-equivalent values are valuation snapshots.

Record:

```text
reward_alpha_day
alpha_price_tao
TAO_equivalent_day
alpha_pool_depth
24h volume
7d alpha volatility
30d alpha volatility
slippage to exit reward
```

Calculate:

```python
liquidatable_tao_day =
    expected_reward_alpha_day
    * executable_alpha_to_tao_price
```

not merely spot alpha price.

Stress test at:

```text
spot
-20%
-40%
-60%
```

No Moltwork economic decision may assume today's TAO-equivalent persists for 30 days.

---

# 7. Difficulty model

Difficulty must be empirical.

Create:

```python
Difficulty =
    0.20 * competitive_depth
  + 0.20 * score_gap_to_paid
  + 0.15 * reward_concentration
  + 0.10 * domain_specialization
  + 0.10 * compute_barrier
  + 0.10 * entry_risk
  + 0.05 * feedback_latency
  + 0.05 * benchmark_uncertainty
  + 0.05 * protocol_instability
```

All terms normalized 0-1.

The most important field is:

```text
score_gap_to_paid
```

It comes from actually running our worker.

Do not say Ditto is "hard" because good miners exist.

Say:

```text
incumbent WorkerVersion:
sealed mean     0.719
95% CI          [0.701, 0.737]

current #5      0.745

estimated P(top5) = 0.17
estimated P(top3) = 0.02
```

That gives us something Hydra can optimize.

---

# 8. LabValue

Economic reward and training usefulness are separate.

Calculate:

```python
LabValue =
    0.20 * verifier_strength
  + 0.18 * replayability
  + 0.15 * iteration_frequency
  + 0.12 * feedback_richness
  + 0.12 * skill_transferability
  + 0.10 * artifact_reusability
  + 0.08 * curriculum_generatability
  + 0.05 * economic_reality
```

Ditto/Ridges/Harnyx should score extremely high even when their current direct EV is mediocre.

---

# 9. Opportunity score

Keep separate components visible.

Do not collapse everything into one unexplained number.

Return:

```json
{
  "economic_score": 0.81,
  "lab_value": 0.97,
  "difficulty": 0.82,
  "capital_risk": 0.14,
  "expected_tao_day": 1.38,
  "p_any_reward": 0.42,
  "confidence": 0.78,
  "recommendation": "OFFLINE_TRAIN"
}
```

Allowed recommendation states:

```text
IGNORE
WATCH
CLONE_AND_REPLAY
OFFLINE_TRAIN
SHADOW
REGISTER_SMALL
LIVE_COMPETE
DEFEND_POSITION
EXIT
```

---

# 10. Mainnet spending gate

Never register merely because a subnet looks attractive.

A subnet moves through:

```text
DISCOVER
   ↓
REPRODUCE
   ↓
LOCAL BASELINE
   ↓
HYDRA/CGE TRAINING
   ↓
SEALED EVALUATION
   ↓
SHADOW ECONOMIC MODEL
   ↓
MAINNET
```

For expensive registration:

```text
burn > 0.25 TAO
```

require:

```text
mechanism_confidence >= 0.95
AND sealed evaluation exists
AND positive expected EV
AND explicit capital policy allows it
```

For paid submissions such as Ditto:

```python
submit_only_if(
    expected_marginal_reward_of_submission
    > 3 * submission_fee
)
```

Do not spam evaluations.

---

# 11. Hydra integration

One experiment:

```yaml
experiment:
  id: ditto-memory-routing-0042
  parent_worker: ditto-worker-v17
  world: bittensor/118/dittobench-v12
  mutation:
    memory_retrieval:
      strategy: temporal_hybrid
    tool_policy:
      parallel_search: true

  budget:
    usd: 2.50
    max_tokens: 180000

  evaluation:
    profile: sealed
    seeds: 30

  result:
    mean: 0.754
    ci95: [0.742, 0.766]
    cost_usd: 1.91

  decision:
    promoted: true
```

Hydra must retain:

```text
worker lineage
git commit
environment version
benchmark version
dataset/seed set
cost
score
failure categories
candidate lessons
promotion decision
```

No experiment result without a Git commit.

---

# 12. CGE integration

CGE should generate curriculum from real failure clusters.

Ditto examples:

```text
temporal memory mutation
contradictory remembered facts
lexical-gap retrieval
stored prompt injection
unnecessary search
failure to parallelize tools
wrong tool arguments
excessive tool use
```

Ridges:

```text
repo navigation
failing to inspect tests
patch too broad
incorrect dependency assumption
timeout
unnecessary LLM calls
wrong file edited
tests pass locally but verifier fails
```

Minos:

```text
precision/recall balance
region sensitivity
mapping-quality thresholds
base-quality thresholds
caller selection
overfitting one chromosome/window
```

Hydra clusters real failures.

CGE creates targeted worlds.

Worker trains.

Then it must return to sealed original-distribution evaluation.

CGE scores NEVER directly promote production workers.

Only sealed evaluation can promote.

---

# 13. Initial Moltwork Bittensor schools

Implement adapters in this order:

```text
F10 METACULUS
    forecasting/research/calibration

F11 DITTO SN118
    memory/tool judgment

F12 RIDGES SN62
    software engineering

F13 MINOS SN107
    evolutionary scientific optimization

F14 GRADIENTS SN56
    AutoML / RL / training recipes

F15 HARNYX SN67
    deep research / cost-quality routing

F16 REDTEAM SN61
    authorized security evaluation

F17 SOMA SN114
    context compression

F18 AFFINE / ALBEDO
    model optimization ceiling environments
```

Metaculus is the cheap control laboratory.

Bittensor is adversarial real-economy transfer.

External bounties/client work are downstream transfer evaluations.

---

# 14. First three concrete experiments

## Experiment A - Ditto

Clone the official Ditto miner starter environment.

Create:

```text
workers/ditto/incumbent
workers/ditto/candidates/*
worlds/ditto/
hydra/ditto/
```

Benchmark incumbent.

Run at least 100 local/sealed episodes across multiple generated seeds.

Hydra clusters failures.

CGE constructs curricula around the largest failure classes.

Generate 10-30 candidate WorkerVersions.

Perform successive halving:

```text
30 candidates x cheap eval
10 candidates x medium eval
3 candidates x sealed expensive eval
1 candidate promoted
```

Do not pay 0.04 TAO until the sealed candidate has a realistic probability of reaching the paid top five.

## Experiment B - Ridges

Clone Ridges.

Run the provided local Harbor workflow.

Establish baseline `agent.py`.

Import a broad sealed Harbor task set.

Track:

```text
task success
cost
wall time
files inspected
tests run
patch size
LLM calls
failure category
```

Hydra evolves the coding harness.

This worker should also become Moltwork's own internal coding worker.

## Experiment C - Minos

Do NOT register immediately.

Clone Minos.

Run demo/practice modes.

Fetch current parameter ranges and live network reward config.

Build a parameter-search world.

Start with:

```text
random search
Bayesian optimization
CGE evolutionary mutation
MAP-Elites
```

Compare them under exactly equal experiment budgets.

Use multiple genomic regions as train/dev/sealed distributions.

Only consider paying the ~1 TAO registration cost if the resulting policy has demonstrated competitive performance across held-out practice worlds.

---

# 15. Wallet architecture

The autonomous agent must never possess the master coldkey seed.

Use:

```text
PRIMARY COLDKEY
offline / hardware / air-gapped
holds TAO
        |
        v
NONTRANSFER MANAGER PROXY
prefer delayed
        |
        +-- REGISTRATION PROXY
        |      subnet registration only
        |
        +-- other narrowly scoped proxies as needed
```

Bittensor supports an explicit `Registration` proxy type for neuron registration.

The operational agent should preferably possess only the narrowly scoped delegate.

One hotkey per meaningful subnet/experiment boundary is preferable to one universal hotkey because compromise and accounting remain isolated.

Hydra may store:

```text
SS58 public addresses
hotkey names
proxy types
transaction hashes
block numbers
TAO amounts
```

Hydra MUST NEVER store:

```text
mnemonics
coldkey private keys
unencrypted proxy private keys
provider API secrets
```

---

# 16. AgentVault

Treat AgentVault as a credential/signing isolation layer, not as the source of truth for Bittensor wallet semantics.

There are multiple products/projects using the name AgentVault, and public documentation does not establish that every implementation safely handles native Bittensor sr25519 coldkey/hotkey signing.

Therefore:

```text
master Bittensor coldkey
    NEVER inside generic agent context

AgentVault
    provider API credentials
    operational secrets
    optionally scoped Bittensor proxy signer
    ONLY if native signing is verified
```

If native Bittensor signing is not supported, build a narrow signer adapter around the Bittensor wallet/proxy key.

Expose capabilities such as:

```text
get_balance
get_registration_price
plan_registration
register_hotkey
get_transaction_status
```

Do not expose arbitrary `sign(bytes)` to the LLM.

---

# 17. SDK spending policy

Use Bittensor's native Policy mechanism.

The coding agent must plan every transaction before execution.

Conceptually:

```python
policy = bt.Policy(
    max_spend_tao=<small bounded value>,
    allowed_netuids=[118, 62]
)
```

For each transaction:

```text
PLAN
↓
record predicted effects + fee
↓
policy check
↓
compare current burn with Oracle snapshot
↓
execute only within cap
↓
record receipt
```

Do not automatically raise a spending limit because registration has become more expensive.

A floating registration price exceeding the cap should produce a new economic decision, not an automatic retry.

---

# 18. Continuous scanner cadence

Chain/economic snapshot:

```text
every hour
```

For currently targeted subnets:

```text
every tempo / around major epoch transitions
```

Repositories/mechanism changes:

```text
poll commits/releases several times daily
```

Live benchmark leaderboard:

```text
appropriate to subnet cadence
```

On every material change:

```text
recompute:
difficulty
attainable EV
entry gate
recommended next experiment
```

Examples of material changes:

```text
registration burn +/-25%
miner pool +/-15%
new benchmark version
payout rule change
new champion
paid cutoff changes materially
new model pin
new task family
new miner eligibility rules
subnet suddenly loses validators
```

---

# 19. Daily output

Generate:

```text
BITTENSOR OPPORTUNITY REPORT

1. BEST THING TO WORK ON TODAY
2. BEST OFFLINE EXPERIMENT
3. BEST MAINNET ENTRY
4. BEST HIGH-RISK/HIGH-UPSIDE TARGET
5. TARGETS THAT BECAME WORSE
6. PROTOCOL CHANGES
7. WALLET/CAPITAL EXPOSURE
8. ACTIVE WORKER PERFORMANCE
9. NEXT CGE CURRICULUM
10. EXACT ACTIONS FOR CODING AGENT
```

The report must explain *why* the ranking changed.

Never output merely:

```text
SN107 emission went up -> pursue
```

Output:

```text
SN107 emission +14%;
registration burn -31%;
live winner allocation unchanged;
our Minos-v14 sealed percentile moved 72nd -> 94th;
estimated P(rank1) now 0.08;
P(any paid rank) 0.81;
7-day risk-adjusted EV became positive;
recommendation OFFLINE_TRAIN -> REGISTER_SMALL.
```

That is the Moltwork Oracle.

---

# Current Bittensor opportunity ranking

| Priority | Subnet             | Current miner pool* | Entry snapshot | Competition              | Lab fit | Difficulty | Action                     |
|----------|--------------------|--------------------:|---------------:|--------------------------|--------:|-----------:|----------------------------|
| **1**    | **Ditto SN118**    |   **34.49 tau/day** | 0.0005 tau + 0.04/submission | top 5 only; 35 scored | **10/10** | 8.5 | **Build now** |
| **2**    | **Ridges SN62**    |   **34.77 tau/day** | 0.0005 tau | ~11 emitting miners | **10/10** | 8 | **Build in parallel** |
| **3**    | **Minos SN107**    | **221.06 tau/day** headline | 0.99 tau | ~20 active, winner-heavy | **9.5/10** | 9 | **Offline CGE attack now** |
| **4**    | **Gradients SN56** |   **50.87 tau/day** | .0005 + .20-.35/tournament | ~6 miners; top 2/track | **9.5/10** | 9 | second wave |
| **5**    | **RedTeam SN61**   |   **38.45 tau/day** | .047 tau | 48 active | 9/10 | 8.5 | security school |
| **6**    | **SOMA SN114**     |   **44.51 tau/day** | .25 tau | telemetry currently odd | 9.5/10 | ? | investigate |
| **7**    | **Harnyx SN67**    |   **20.73 tau/day** | .018 tau | **129 miners** | **10/10** | 9 | great school, crowded |
| **8**    | **Affine SN120**   |  **172.92 tau/day** | .881 tau | ~3 miners; WTA-ish | 9/10 | **10** | ceiling target |
| **9**    | **Albedo SN97**    |  **85.49 tau/day** | .650 tau | 4 miners; WTA | 8.5/10 | **10** | later GPU target |

---

# Moltwork thesis (qualified)

**Bounties should be treated as transfer tests and asymmetric upside, not the economic foundation.**

**The foundation should be repeatable evaluation economies where the Lab can generate hundreds of episodes, measure improvement, and eventually get paid for being objectively better.**

That means **Metaculus + Bittensor + other evaluation protocols** become the training ground. Historical/local evaluation produces cheap learning; live Bittensor produces adversarial economic validation; only after workers become demonstrably strong do we point them at audits, research prizes, hackathons, customer work, etc.

```text
                    MOLTWORK LAB
                         |
          +--------------+--------------+
          |                             |
     METACULUS                     BITTENSOR
   cheap replay                       |
          |                 +---------+---------+
          |                 |                   |
    forecasting          DITTO               RIDGES
    cognition            memory               code
          |                 |                   |
          +--------------+--+-------------------+
                         |
                    HYDRA + CGE
                         |
                 improved general worker
                         |
          +--------------+--------------+
          v              v              v
        MINOS        GRADIENTS       HARNYX
      evolution       AutoML         research
          |
          v
      real bounties
      audit contests
      hackathons
      client products
```
