# Bittensor Low-Hanging TAO Oracle — live miner breadth + daily on-chain technical spec

**Date:** Wed, 2 Sep 2026 18:42:42 -0700

---

# Bittensor Low-Hanging TAO Oracle

## Thesis

The oracle should answer one question every day:

> **Where is TAO being emitted right now where a merely competent miner can capture a recurring slice before competition notices?**

The key correction from our earlier work: **miner complexity is secondary. Prize breadth is primary.**

A subnet paying 20–40 miners 0.5–2 TAO/day each is more attractive for our current objective than a technically trivial winner-take-all subnet with a 30 TAO/day headline pool.

The first objective is recurring TAO, even if it starts at ~1 TAO/day. Once we have reliable income and operational experience, we can attack harder jackpot subnets.

---

# 1. The primary oracle metric: TAO-depth

Stop ranking primarily by `active_miners`, `emission / miner_count`, or nominal miner pool.

For each subnet, reconstruct the **actual latest settled miner payout curve** directly from the metagraph / epoch emission vector and calculate:

```text
N_0_10 = number of miner hotkeys earning >= 0.10 TAO/day
N_0_25 = number earning >= 0.25 TAO/day
N_0_50 = number earning >= 0.50 TAO/day
N_1    = number earning >= 1.00 TAO/day
N_2    = number earning >= 2.00 TAO/day
N_5    = number earning >= 5.00 TAO/day
```

This is the metric we actually care about.

Then calculate:

```text
paid_miners
median_paid_tao_day
p10_paid_tao_day
p25_paid_tao_day
p50_paid_tao_day
p75_paid_tao_day
p90_paid_tao_day
bottom_paid_tao_day
min_prunable_tao_day
max_paid_tao_day
top1_share
top3_share
top10_share
HHI
Gini
```

Most importantly:

```text
TAO_DEPTH_1 = N_1
```

If a subnet has 15 seats paying >=1 TAO/day, that is a much more attractive income opportunity than a subnet with one seat paying 50 TAO/day.

A second derived metric:

```text
ENTRY_PERCENTILE_1TAO = N_1 / realistic_miner_population
```

This estimates how good we actually need to be to clear 1 TAO/day.

---

# 2. Why `active_miners` is misleading

Current explorers can report very different notions of “miner”:

- registered UID
- axon-serving UID
- active UID
- miner-classified UID
- artifact submitter
- hotkey receiving non-zero incentive

These are not equivalent.

The oracle should derive `N_paid` itself from the latest settled epoch:

```python
metagraph = await client.subnets.metagraph(netuid)

for neuron in metagraph.neurons:
    if neuron is validator:
        continue
    payout_alpha_epoch = neuron.emission
    if payout_alpha_epoch > 0:
        paid_miners.append(neuron)
```

Convert epoch alpha payout into TAO/day using the **price at the same pinned block** and the subnet tempo.

Do not use current price against an old epoch.

Example conceptual conversion:

```text
epochs_per_day = 7200 / tempo_blocks
alpha_day = alpha_epoch * epochs_per_day
tao_day = alpha_day * alpha_price_at_block
```

Use the SDK's exact Balance/unit semantics; do not assume the explorer display field is already per-day.

Official docs explicitly state the metagraph emission field is the UID's combined payout from the most recent epoch and is a per-tempo amount.

---

# 3. Current live screening: what looks interesting under the new criterion

## Tier A — investigate immediately

### SN67 Harnyx

Why it moves UP under the new criterion:

- explicitly has **participation emission beyond the champion**
- reward tiers include broader participant groups, rather than only winner
- participant rewards incorporate performance + novelty
- no miner GPU requirement; miners submit research-agent scripts
- current miner-side pool is roughly 16–20 TAO/day depending snapshot/source
- current evidence suggests a large number of earning participants
- mechanism is directly compatible with our WorkerKit/Hydra learning loop

The important point is not whether champion reward is huge. It is whether our agent can cheaply enter the top rewarded participation tier and stay there.

The oracle should query Harnyx's public evaluation records and map:

```text
artifact -> score -> novelty class -> hotkey -> on-chain payout
```

Then estimate the minimum benchmark score needed historically for:

```text
0.25 TAO/day
0.5 TAO/day
1 TAO/day
2 TAO/day
```

This is almost a perfect first “income school” because rewards extend beyond #1.

Official repo:
https://github.com/harnyx/harnyx

### SN61 RedTeam

Why interesting:

- reward share is based on performance and diversity rather than a single permanent crown
- scores decay, so old leaders lose income unless they keep improving
- multiple accepted novel solutions can remain rewarded
- directly overlaps our security lab / BitSec / bug-bounty capability
- containers can be developed and replayed offline

Downside:

- current miner-burn mechanism is substantial, reducing miner-side economics
- current miner software has had recent operational compatibility issues, so deployment reliability must be checked

This is still strategically valuable because even small TAO reward teaches us a reusable security skill.

Repos:
https://github.com/RedTeamSubnet/RedTeam
https://github.com/RedTeamSubnet/miner

### SN62 Ridges

Why still interesting:

- live miner pool around ~32–35 TAO/day in current public data
- low registration floor historically/currently cheap
- no local GPU required
- excellent local replay surface
- software-engineering agent work maps directly onto our coding-agent stack
- official repo has a local miner runner and Harbor task support

However, public sources currently disagree about how many distinct miners are actually earning. This is EXACTLY why the oracle must derive `N_paid` from chain state itself.

If the actual latest payout curve has many >0 positions, this becomes Tier A. If it collapses to one/few meaningful weights, downgrade it.

Repo:
https://github.com/ridgesai/ridges

## Tier B — watch / opportunistic

### SN16 trav / BitAds transition

Interesting because:

- very young/recent ownership/mechanism change
- 238 open UID slots in current snapshot
- small subnet
- miner activity is off-chain marketing/sales rather than heavy compute
- nominal miner allocation currently several TAO/day

BUT current explorer state is inconsistent: Bittensor.ai showed zero on-chain miners while describing active off-chain miner logic, and another live surface showed miner emissions at zero. Therefore this is **MECHANISM_UNVERIFIED** until the oracle confirms actual paid hotkeys at a finalized block.

This is exactly the kind of early weird opportunity we want to detect, but NEVER spend based on a dashboard description alone.

### SN26 Perturb

Current chain surfaces show around 10 miners / low-ish emission and cheap-looking economics, but I do not yet have enough first-party evidence about how broadly rewards are allocated. Keep in the daily candidate set; auto-escalate if `N_0.5` or `N_1` rises.

---

# 4. Explicitly downgrade despite headline economics

These may be great research targets later, but they do NOT fit our first recurring-income goal.

### SN10 Pareton

Headline miner pool appears huge, but current Pareton docs explicitly say **only the seated campaign leader earns; no runner-up, no partial credit**. Everything else burns.

=> reject for recurring-income queue unless we have a campaign-specific attack where P(win) is high.

### SN108 Prometheon

Current public mechanism says top submissions carry forward but the highest scorer receives the meaningful miner weight; effectively winner-take-all.

=> jackpot queue, not income queue.

### SN126 Poker44

Current policy allocates ~95% to the deterministic winning miner.

=> jackpot queue.

### SN114 SOMA

Current mechanism is described as weekly winner-take-all competition.

=> jackpot queue.

### SN56 Gradients

Current tournament structure pays only the top few positions heavily.

=> useful lab challenge, but not the first recurring-income target.

This separation should be hard-coded:

```text
INCOME_QUEUE
JACKPOT_QUEUE
```

Never let a 100-TAO nominal pool crowd the dashboard if only one miner actually gets it.

---

# 5. Daily oracle: canonical on-chain collector

Use direct Bittensor chain as canonical state.

Run at a single finalized block:

```python
import bittensor as bt

async with bt.AsyncSubtensor(network="finney") as live:
    block = await live.get_current_block()
    sub = live.at(block=block)
```

Use the current v11 SDK namespaces where supported.

For every active netuid collect:

## Subnet-level state

```text
block
netuid
subnet_instance_id
network_added_block
age_blocks
name
symbol
owner_coldkey
owner_hotkey
alpha_price
moving_price / EMA price
TAO pool reserve
alpha pool reserve
subnet TAO emission share
subnet_emission_enabled
alpha_out
miner_burned
owner_cut_enabled
registration_allowed
burn
collateral_lock_share
collateral_drain_ratio
min_burn
max_burn
burn_half_life
burn_increase_mult
max_allowed_uids
immunity_period
activity_cutoff
tempo
blocks_until_epoch
Yuma3On
liquid_alpha
commit_reveal
```

## Full neuron state from metagraph

The official v11 query is essentially:

```python
metagraph = await client.subnets.metagraph(netuid)
```

or synchronous:

```python
sub.read("metagraph", netuid=netuid)
```

Each neuron should be stored with:

```text
uid
hotkey
coldkey
registration_block
validator_permit
axon status
incentive
emission
stake
alpha_stake
root_stake
collateral_locked
collateral_min
collateral_earned
is_immune
blocks_since_update
```

This one table is the foundation of the payout-depth model.

Official docs:
https://www.bittensor.com/docs/query/metagraph
https://www.bittensor.com/docs/concepts/emissions

---

# 6. Canonical storage schema

Create a new analytical layer, separate from mechanism notes.

```sql
CREATE TABLE subnet_epoch (
  block BIGINT,
  timestamp TIMESTAMP,
  instance_id TEXT,
  netuid INTEGER,
  age_blocks BIGINT,
  alpha_price DOUBLE,
  moving_price DOUBLE,
  tao_pool DOUBLE,
  alpha_pool DOUBLE,
  emission_share DOUBLE,
  emission_enabled BOOLEAN,
  miner_pool_alpha_epoch DOUBLE,
  miner_pool_tao_day DOUBLE,
  burn_tao DOUBLE,
  collateral_share DOUBLE,
  owner_cut_enabled BOOLEAN,
  registration_allowed BOOLEAN,
  max_uids INTEGER,
  neuron_count INTEGER,
  tempo INTEGER,
  PRIMARY KEY(block, instance_id)
);
```

```sql
CREATE TABLE neuron_epoch (
  block BIGINT,
  instance_id TEXT,
  netuid INTEGER,
  uid INTEGER,
  hotkey TEXT,
  coldkey TEXT,
  validator_permit BOOLEAN,
  registration_block BIGINT,
  incentive DOUBLE,
  emission_alpha_epoch DOUBLE,
  emission_tao_day DOUBLE,
  collateral_locked DOUBLE,
  immune BOOLEAN,
  PRIMARY KEY(block, instance_id, uid)
);
```

```sql
CREATE TABLE payout_curve (
  block BIGINT,
  instance_id TEXT,
  paid_miners INTEGER,
  n_ge_0_10 INTEGER,
  n_ge_0_25 INTEGER,
  n_ge_0_50 INTEGER,
  n_ge_1 INTEGER,
  n_ge_2 INTEGER,
  n_ge_5 INTEGER,
  p10_tao_day DOUBLE,
  p25_tao_day DOUBLE,
  median_tao_day DOUBLE,
  p75_tao_day DOUBLE,
  p90_tao_day DOUBLE,
  top1_share DOUBLE,
  top3_share DOUBLE,
  hhi DOUBLE,
  gini DOUBLE,
  prune_floor_tao_day DOUBLE,
  PRIMARY KEY(block, instance_id)
);
```

Store every epoch forever. This lets us see opportunities BEFORE we acted and evaluate whether the scanner was correct.

---

# 7. The daily income score

Do NOT make this one vague composite initially. Keep the components visible.

Hard gate:

```text
registration_allowed = true
emission mechanism verified
latest epoch fresh
N_paid > 0
source_confidence >= VERIFIED
```

Then rank primarily by:

```text
1. N_1
2. N_0.5
3. median_paid_tao_day
4. p25_paid_tao_day
5. registration sunk cost
6. pruning risk
7. payout persistence
8. mechanism reproducibility
```

Suggested first score:

```python
income_score = (
    5.0 * log1p(N_1)
  + 3.0 * log1p(N_0_5)
  + 2.0 * log1p(N_0_25)
  + 2.0 * min(median_paid_tao_day, 3)
  + 1.5 * payout_persistence_7d
  + 1.0 * open_slot_score
  - 2.0 * sunk_burn_tao
  - 2.0 * churn_risk
  - 3.0 * mechanism_uncertainty
)
```

But the dashboard must expose the raw curve so we do not hide bad assumptions inside a score.

---

# 8. Payout persistence: crucial

One epoch of 1 TAO/day equivalent can be noise.

For every hotkey rank / payout bucket compute:

```text
% of last 7 days position >= 0.25 TAO/day
% >= 0.5
% >= 1
median consecutive paid epochs
median lifespan of paid seat
reward turnover rate
```

A subnet with 20 `N_1` seats today but complete rank turnover every epoch is less useful than one with 8 stable `N_1` seats miners hold for weeks.

Define:

```text
SEAT_HALF_LIFE
```

= median time a miner remains above the target daily income threshold.

This could become one of our best metrics.

---

# 9. Registration timing layer

Current registration cost decays every block and jumps after successful registrations.

For each candidate store:

```text
burn_now
burn_min
burn_1h_ago
burn_6h_ago
burn_24h_ago
registrations_1h
registrations_24h
burn_half_life
burn_increase_mult
collateral_lock_share
```

Then calculate the true sunk cost:

```text
sunk_burn = burn_now * (1 - collateral_lock_share)
recoverable_lock = burn_now * collateral_lock_share
```

The agent can alert:

> “SN67 is attractive but burn is 4× its 24h resting level; wait one tempo unless payout depth changes.”

Official docs:
https://www.bittensor.com/docs/guides/mining/burn
https://www.bittensor.com/docs/guides/mining/collateral

---

# 10. New subnet early-entry scanner

Every time a new `subnet_instance_id` appears, automatically create a research job.

Within the first minutes:

1. fetch on-chain identity
2. locate official repo
3. clone repo
4. parse README/docs/miner code
5. classify payout topology
6. test whether local replay/eval exists
7. calculate max UID / open slots / immunity
8. monitor first 10 epochs of miner weights
9. calculate TAO-depth after rewards start
10. compare against historical successful new-subnet instances

Critical classifier:

```text
PAYOUT_TOPOLOGY =
  PROPORTIONAL
  BROAD_PARTICIPATION
  TOP_K
  DECAYING_PORTFOLIO
  WINNER_TAKE_ALL
  BOUNTY
  EXTERNAL_ACTIVITY
  UNKNOWN
```

For our current goal:

```text
PROPORTIONAL            highest priority
BROAD_PARTICIPATION     highest priority
DECAYING_PORTFOLIO      high priority
TOP_K                    depends on K
WINNER_TAKE_ALL          jackpot queue
UNKNOWN                  research only
```

The oracle should discover this from both:

- actual on-chain reward curve
- validator/miner source code

If code says broad payout but chain shows one hotkey getting 95%, trust the chain.

---

# 11. Detect fresh low-hanging opportunities automatically

Alerts should fire on CHANGE, not just absolute state.

Examples:

```text
NEW_SUBNET(instance_id)
N_1 crosses 5
N_1 increases >50% week/week
N_0.5 increases while registered miners stay flat
miner_pool_tao_day rises >50%
burn falls >75%
max_allowed_uids increases
registration re-opens
owner_cut_enabled flips false
collateral_lock_share increases
major leaderboard miner disappears
high-ranked miner deregisters
new mechanism release
new challenge starts
payout changes winner-take-all -> participation
```

The last one is particularly important. Harnyx-style changes can transform an unattractive subnet into exactly the kind of opportunity we want overnight.

---

# 12. Resource allocation workflow

Do not auto-register from a score.

Pipeline:

```text
CHAIN SCAN
   ↓
PAYOUT DEPTH
   ↓
MECHANISM CLASSIFIER
   ↓
INCOME CANDIDATE
   ↓
CLONE REPO
   ↓
LOCAL BASELINE
   ↓
ESTIMATE EXPECTED PAYOUT RANK
   ↓
PAPER DECISION
   ↓
HUMAN APPROVAL
   ↓
REGISTER
   ↓
RUN MINER
   ↓
TRACK REAL PAYOUT
   ↓
HYDRA LEARNS
```

We only need to establish one thing initially:

> Can our baseline clear the 1-TAO/day seat threshold?

Do NOT spend two weeks optimizing for #1 when rank #17 already pays enough.

---

# 13. WorkerKit/Hydra integration

Every candidate subnet becomes a School:

```text
school_id = miner:<instance_id>:<mechanism_version>
```

Every experiment records:

```text
artifact_hash
worker_version
mechanism_version
benchmark_score
estimated_rank
estimated_tao_day
actual_rank
actual_alpha_epoch
actual_tao_day
api_cost
compute_cost
registration_amortization
net_tao_day
```

Hydra question:

> “What is the cheapest mutation likely to move this miner above the next TAO-depth threshold?”

Thresholds become meaningful learning objectives:

```text
0 -> 0.25 TAO/day
0.25 -> 0.5
0.5 -> 1
1 -> 2
2 -> 5
```

Much better than blindly optimizing benchmark score.

---

# 14. Daily report format

The oracle should email/dashboard something like:

```text
LOW-HANGING TAO — 2026-09-03

INCOME TARGET: >=1 TAO/day

1. SN67 Harnyx
   N_1: 8
   N_0.5: 21
   paid miners: 124
   median: 0.31 TAO/day
   miner pool: 18.4 TAO/day
   burn: 0.02 TAO
   topology: BROAD_PARTICIPATION
   seat half-life >=1 TAO: 4.2d
   local replay: YES
   recommendation: BENCHMARK NOW

2. SN62 Ridges
   N_1: [chain-derived]
   N_0.5: [chain-derived]
   miner pool: ~33 TAO/day
   topology: VERIFY
   local replay: YES
   recommendation: RESOLVE PAYOUT CURVE

3. SN61 RedTeam
   N_1: ...
   topology: DECAYING_PORTFOLIO
   security skill overlap: HIGH
   recommendation: RUN BASELINE
```

Never fabricate these numbers: populate from the epoch DB.

---

# 15. Repos to clone / reuse

Already useful in `/bitt`:

- `buckZz7/dtao-trader` — chain economics / SubnetExcessTao extraction
- `RyanMercier/OpenTaoAPI` — direct-chain history/backfill infrastructure
- `EZTrades-dev/miner-spy` — coldkey/IP concentration
- `metagraphed` — broad chain and subnet surface registry

Worth adding if not already present:

```bash
git clone https://github.com/RyanMercier/OpenTaoTrader.git vendor/OpenTaoTrader
git clone https://github.com/harnyx/harnyx.git vendor/harnyx
git clone https://github.com/ridgesai/ridges.git vendor/ridges
git clone https://github.com/RedTeamSubnet/RedTeam.git vendor/redteam
git clone https://github.com/RedTeamSubnet/miner.git vendor/redteam-miner
```

Do not inherit their economic assumptions. We use their protocol/runtime/eval plumbing and calculate economics ourselves from current chain state.

---

# 16. Build order

## CP0 — payout depth scanner

Implement first. No LLM needed.

Input: current finalized block.

Output for all subnets:

```text
netuid
instance_id
miner_pool_tao_day
paid_miners
N_0.25
N_0.5
N_1
N_2
median payout
p25 payout
top1 share
HHI
burn
sunk_burn
slots_open
prune risk
```

This alone should immediately reveal opportunities our current scanner misses.

## CP1 — epoch history

Persist every epoch and calculate seat half-life / reward turnover.

## CP2 — mechanism classifier

Automatically clone/review official repos and label payout topology.

## CP3 — local benchmark adapters

Start with:

1. Harnyx
2. Ridges
3. RedTeam

## CP4 — opportunity decision engine

Answer:

```text
If I register this WorkerVersion now,
what is P(net >= 1 TAO/day for 7 days)?
```

## CP5 — human-approved live miner deployment

Only then spend/register.

---

# Bottom line

The most useful mental model is no longer “find the easiest subnet.”

It is:

> **Find the subnet with the deepest prize curve relative to the competence we already have.**

We do not need to beat the champion.

If a subnet has a stable tail of 10–30 miners making 0.5–2 TAO/day, that is exactly the boring low-hanging TAO we want.

The oracle’s competitive advantage is simply that almost everyone looks at headline emission, token price, or top miner rewards. We will continuously reconstruct the full payout curve for every subnet, notice when previously unattractive mechanisms become broad-paying, reproduce them locally, and enter before the obvious income gets crowded.
