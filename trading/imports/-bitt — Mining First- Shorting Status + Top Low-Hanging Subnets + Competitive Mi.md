# /bitt — Mining First: Shorting Status + Top Low-Hanging Subnets + Competitive Miner Build Plans

**Date:** Wed, 2 Sep 2026 20:37:28 -0700

---

# /bitt — Mining First
## Shorting status, priority subnets, and full competitive-miner build plan

Date: 3 September 2026

## Executive conclusion

Yes: **I would make low-hanging mining the first monetization priority for /bitt right now**, while the allocator/Incubator continues collecting data in parallel.

Why mining first:

1. It can produce TAO without requiring us to prove a trading strategy statistically first.
2. Several current subnets reward exactly the capabilities we are already building: coding agents, agent skills, research agents, OSS contribution and security detection.
3. Every mining attempt produces clean Moltwork/Hydra training material: task → hypothesis → WorkerVersion → local score → submission → on-chain payout → lesson.
4. We can use /bitt’s scanner to avoid wasting effort on mechanisms where headline emissions are misleading.
5. The resulting WorkerVersions transfer outside Bittensor into bounties, software work, security work and the wider Moltwork marketplace.

The rule should be:

> **Do not register because a dashboard says “11 miners.” Register only when the exact payout-vector scanner says meaningful seats exist AND our local benchmark says our WorkerVersion has a credible probability of reaching one.**

Public explorer metrics are discovery. The chain payout tail is the economic arbiter.

---

# 1. Can we short subnet alpha today?

## Native mainnet: no, not yet

There is a genuine Bittensor runtime design for subnet-alpha shorting, but as of 3 September 2026 it is **not live on mainnet**.

TAOStats’ current “Shorting (PR)” documentation tracks Subtensor PR #2764, the Fixed-Liability Covered Continuous-Unwind shorting model. It explicitly marks the feature as pending/not live, and the runtime design includes a `ShortsEnabled` gate that defaults false until trading-games activation.

Source:
https://docs.taostats.io/docs/shorting

This is important: shorting is not a fantasy feature; protocol work exists. /bitt should prepare now.

## HODL/SN118 derivatives

HODL’s roadmap mentions futures/options in its V3/Q3 2026 roadmap, but I did not verify a currently live, liquid subnet-alpha derivatives venue today. Treat it as a watch target rather than current execution infrastructure.

## SN88 negative allocations are simulated

Investing subnet strategies may permit negative exposures inside its competition environment, but that is not equivalent to borrowing and short-selling actual alpha on mainnet.

## Build the short research stack now

Add:

`GET /v1/short-candidates`

Even without execution, freeze hypothetical short hypotheses and score them prospectively.

Candidate downside signals:

- strongly negative native TAO-flow acceleration
- root-manager exits
- moving-price/spot downside divergence
- emission-gate deterioration
- paid-miner seat collapse
- rising recipient sell pressure
- protocol-buy pressure fading
- liquidity deterioration
- developer/owner/mechanism abandonment
- registration collapse
- subnet-instance dissolution risk
- valuation far ahead of fundamentals

Store hypothetical entry, horizon and cover rule, then evaluate later. When `ShortsEnabled` becomes live or a real liquid derivatives venue appears, /bitt already has a historical short model rather than starting from zero.

I would also create a simple watcher for the runtime flag / protocol release so we know immediately when this becomes executable.

---

# 2. Priority order

## Tier A — build miners now

### #1 SN62 — Ridges
**Best immediate target.**

Why:

- Current public screen suggests roughly ~35 TAO/day miner-side value.
- Only ~11 miners shown on the current public screen.
- Registration burn screen is extremely low (~0.0005 TAO).
- No local GPU requirement.
- The mining task is literally: build a software-engineering agent.
- It has first-party local tooling.
- It aligns directly with WorkerKit, coding agents, model routing, experiment tracking and Hydra.
- Even if we fail to earn, the resulting SWE WorkerVersion is commercially reusable.

Current first-party repo:
https://github.com/ridgesai/ridges

The repo describes Ridges as an open-source software-engineering agent competition. Validators pull the submitted code, run benchmark problems, and reward the highest-scoring agent.

### #2 SN74 — Gittensor
**Best boring-value target.**

Why:

- No conventional miner daemon is required for OSS contribution mining.
- Miners earn through real merged pull requests to recognized repositories.
- Current public screen suggests ~12–13 TAO/day miner-side value and relatively few apparent miners.
- It transforms our coding agent into productive open-source work rather than synthetic benchmark work.
- Every successful PR builds public track record as well as Bittensor income.
- It gives Moltwork an extremely clean real-world learning environment: issue → patch → CI → review → merge → reward.

First-party repo:
https://github.com/entrius/gittensor

### #3 SN11 — TrajectoryRL
**Best Moltwork/Hydra research target.**

Why:

- Mining is writing a `SKILL.md`, not running infrastructure.
- No GPU/server/uptime burden.
- Validators give the skill to a small open-source model and evaluate it on Terminal-Bench-style tasks.
- This is almost exactly our “skills + WorkerVersion + empirical learning” thesis.
- Public screens currently show extremely sparse miner participation.
- It is winner-take-all/high variance, so do not burn submissions until local results say we can win.

First-party repo:
https://github.com/trajectoryRL/trajectoryRL

### #4 SN67 — Harnyx
**Highest transfer-value research miner.**

Why:

- ~20 TAO/day miner-side value in the recent public screen.
- No GPU required.
- Miner is a research agent using LLM/search tools.
- First-party repository already includes an AutoResearch loop that is astonishingly close to Moltwork/Hydra: hypotheses, focused diagnostics, experiment ledger, score/cost measurement, keep/discard.
- Competition is materially higher than Ridges/Trajectory, so it is not the easiest cash target, but it may be the best learning target.

First-party repo:
https://github.com/harnyx/harnyx

### #5 SN61 — RedTeam, specifically AB Sniffer
**Best security-lab target.**

Why:

- Directly develops our AI/agent security specialization.
- Current competition has a detection challenge where the miner identifies automation frameworks/headless sessions.
- No giant GPU requirement for the detection artifact itself.
- Success transfers to BitSec, bug bounty research and commercial bot/agent-security work.
- Focus on defensive detection, not automation-evasion/humanization.

Current RedTeam repos/docs:
https://github.com/RedTeamSubnet

## Tier B — investigate immediately but do not register blindly

### SN82 — current identity/metadata anomaly

A recent public screen showed an extraordinary-looking profile: ~12.8 TAO/day miner-side value, only one apparent miner and tiny burn.

But public metadata around SN82 appears stale/inconsistent with the current subnet identity/mechanism. This may be a reused netuid or a recent owner/mechanism transition.

This is exactly why we need:

`subnet_instance_id = netuid + registration_block`

Before doing anything:

- query current registration block
- current owner
- current identity
- current repo
- exact payout vector
- exact one miner’s settled alpha/day
- current mechanism

If chain truth confirms “one economically paid miner + ~12 TAO/day pool + reproducible mechanism,” SN82 instantly becomes Priority #1. Until then it is an **information-arbitrage investigation**, not a miner target.

## Tier C — next wave

### SN114 SOMA
Agent context/compression competition. Highly aligned with our memory/context work and worth adding after the first five.

### SN1 Apex
Agentic solution competition with very low apparent miner count but high winner-take-all variance. Good lab target once our submission/evaluation machinery is standardized.

---

# 3. Universal miner-lab architecture

Do **not** build five unrelated miners manually.

Build one common framework:

```text
/bitt/mining_lab/
├── registry.yaml
├── common/
│   ├── economics.py
│   ├── experiment.py
│   ├── hypothesis.py
│   ├── benchmark.py
│   ├── submit_gate.py
│   ├── payout.py
│   └── hydra.py
│
├── sn62_ridges/
│   ├── adapter.py
│   ├── agent.py
│   ├── benchmark.py
│   └── evolve.py
│
├── sn74_gittensor/
│   ├── adapter.py
│   ├── scout.py
│   ├── pr_worker.py
│   └── evaluator.py
│
├── sn11_trajectoryrl/
│   ├── adapter.py
│   ├── SKILL.md
│   ├── benchmark.py
│   └── evolve.py
│
├── sn67_harnyx/
│   ├── adapter.py
│   ├── train.py
│   └── evolve.py
│
└── sn61_redteam/
    ├── adapter.py
    ├── detector/
    ├── test_matrix.py
    └── benchmark.py
```

Every adapter implements the same interface:

```python
discover()       # current mechanism/rules/task snapshot
economics()      # payout seats, burn/collateral, expected EV
benchmark()      # local evaluation of WorkerVersion
candidate()      # current immutable WorkerVersion
improve()        # one hypothesis-driven mutation
submit_plan()    # what will be submitted and expected cost
submit()         # disabled unless explicitly approved
observe()        # score/result/chain payout
evaluate()       # outcome vs hypothesis
```

## Universal submission gate

No candidate reaches chain/platform submission unless:

```text
mechanism_version_known == true
rules_hash == benchmark_rules_hash
benchmark_delta > 0
heldout_score >= target
estimated_paid_probability >= threshold
expected_EV_after_costs > 0
submission_cost_within_grant == true
human_approval == true
```

This prevents hallucinating ourselves into registrations/submissions.

---

# 4. Exact economics gate before touching a subnet

For every candidate, run the full payout-vector scan.

Persist every non-validator UID:

- settled alpha/epoch
- settled alpha/day
- spot-marked TAO/day
- exact realizable TAO/day using `quote_unstake`
- incentive
- UID
- hotkey
- coldkey where useful
- registration block / lineage

Then derive:

- N_0.01
- N_0.05
- N_0.1
- N_0.25
- N_0.5
- N_1
- N_2
- N_5
- p10/p25/median/p75/p90
- top1/top3/top5/top10 concentration
- HHI
- Gini
- effective earners
- 1d/7d seat survival
- seat churn

Also persist:

- current registration burn
- collateral share
- true sunk burn
- locked collateral
- max neurons / capacity
- immunity period
- registration rate
- pruning cutoff/risk
- mechanism version

The decision is not “SN62 has 11 miners.”

The decision is:

> “SN62 currently has X stable seats above Y realizable TAO/day; our held-out benchmark puts us above the estimated paid cutoff with probability P; entry costs C; expected net EV is Z.”

---

# 5. SN62 Ridges — full competitive miner plan

## First-party setup

```bash
git clone https://github.com/ridgesai/ridges.git
cd ridges
uv sync --extra miner
# or pip install -e ".[miner]"

ridges miner setup
```

Configure the generated miner environment with an allowed inference provider. Current first-party tooling supports OpenRouter, Targon and Chutes.

Run local tasks:

```bash
ridges miner run-local
```

Scripted:

```bash
ridges miner run-local \
  --task-path /path/to/task.tar.gz \
  --agent-path /root/bitt/mining_lab/sn62_ridges/agent.py \
  --provider openrouter \
  --non-interactive
```

The miner contract is effectively:

```python
agent_main(input) -> str
```

where output is the code diff.

## Competitive architecture

Do not write “Claude Code but smaller.” Optimize specifically for benchmark success **under the validator cost/time envelope**.

### Stage 1 — task triage

Parse:

- task request
- repo language/framework
- likely target files
- available tests
- likely evaluation path

Classify task:

```text
BUG_FIX
TEST_FAILURE
FEATURE
REFACTOR
DEPENDENCY
CONFIG
DOCS_WITH_TEST
UNKNOWN
```

### Stage 2 — cheap repository reconnaissance

Before using expensive reasoning:

- inspect root tree
- inspect relevant manifests
- search symbols/errors
- locate test files
- read only likely implementation neighborhoods

Never dump whole repo into context.

### Stage 3 — baseline reproduction

Run the narrowest likely failing test immediately.

Capture:

- command
- exit code
- failure class
- stack/error

If no explicit test exists, derive the smallest reproducible check from task description.

### Stage 4 — plan minimal patch

Use strongest allowed reasoning model only after localization.

Require plan fields:

```json
{
  "root_cause": "...",
  "files": ["..."],
  "minimal_change": "...",
  "test": "...",
  "risk": "..."
}
```

### Stage 5 — patch

Prefer smallest valid diff.

Avoid:

- opportunistic refactors
- dependency upgrades unless required
- formatting unrelated files
- architectural rewrites

### Stage 6 — test ladder

```text
specific failing test
→ related test module
→ package test subset
→ lint/typecheck if relevant
→ broader suite only if budget remains
```

### Stage 7 — bounded repair

If failure:

1. classify failure
2. inspect new evidence
3. make one revised hypothesis
4. patch
5. rerun narrow test

Cap repair iterations based on remaining dollar/time budget.

### Stage 8 — diff sanitation

Before return:

- only intended files changed
- no generated junk
- no secrets
- diff parses/applies
- no debug prints
- task acceptance satisfied

Return the exact diff only.

## Model routing

Build a router around task difficulty:

```text
cheap model:
- task classification
- file selection
- search-query generation
- obvious edits

premium model:
- root-cause reasoning
- multi-file behavior changes
- repair after failed tests
```

Measure **benchmark points per $** and **points per second**, not just raw quality.

## Hydra loop

Each Ridges run creates:

```text
TaskReceipt
WorkerVersion
model route
files inspected
commands
cost
latency
patch size
test failures
final local result
validator result
on-chain payout
```

Aggregate failure taxonomy:

- wrong localization
- misunderstood requirement
- incomplete patch
- test not run
- time exhaustion
- model hallucination
- dependency/environment

Then evolve exactly one failure class at a time.

## Registration/submission

Do not upload until the held-out benchmark says the candidate is competitive.

Current first-party upload path:

```bash
ridges upload --file agent.py
```

The current CLI also documents upload credits and OpenRouter credential requirements. Follow the current repo at submission time rather than hard-coding these details into Moltwork.

---

# 6. SN74 Gittensor — full competitive miner plan

## Setup

```bash
git clone https://github.com/entrius/gittensor.git
cd gittensor
uv sync
```

Register appropriately on SN74, then configure a fine-grained GitHub PAT.

Current first-party miner flow:

```bash
export GITTENSOR_MINER_PAT=...
gitt miner post --wallet <wallet> --hotkey <hotkey>
gitt miner check --wallet <wallet> --hotkey <hotkey>
```

The key point: OSS contribution mining does **not** require us to operate a normal always-on miner neuron. Validators verify real merged contributions.

## Build an OSS Opportunity Oracle

Pull the currently recognized repository set and their emission allocations.

For every repo calculate:

```text
expected_repo_value =
emission_share
× expected_contribution_score
× merge_probability
÷ expected_competition
÷ expected_agent_hours
```

Then find candidate work.

### Issue-selection score

Prefer issues with:

- maintainer active recently
- clear reproducible bug / acceptance requirement
- tests available
- narrow scope
- strong chance of merge
- no active competing PR
- code language/type carrying reasonable scoring weight
- meaningful actual value
- manageable review latency

Avoid:

- huge feature requests
- contentious design work
- stale repos
- obvious “good first issue” pile-ons with 10 competitors
- cosmetic spam
- docs typo farming unless legitimately useful

## Agent workflow

```text
repository ranking
→ issue scout
→ issue qualification
→ reproduce locally
→ failing test
→ minimal fix
→ local tests/lint/types
→ human review
→ PR
→ review-response agent
→ merge
→ observe Gittensor reward
```

### PR worker

The coding worker should:

1. read CONTRIBUTING.md
2. read issue/comments
3. reproduce problem
4. produce a failing regression test if appropriate
5. implement smallest fix
6. run project-required checks
7. generate concise PR explanation
8. link evidence/tests
9. never fabricate test results

## Human approval initially

Do not unleash an autonomous PR spammer.

For the first phase:

- agent discovers
- agent implements
- agent validates
- human approves public PR

Once quality/merge rate is proven, gradually loosen permissions.

## Hydra features

Record:

- repo
- issue type
- maintainer response time
- time to first review
- CI pass/fail
- requested changes
- merge outcome
- contribution score
- eventual alpha/TAO reward
- agent cost

After 50–100 attempts, `/bitt` can learn which OSS work is economically worth taking.

This becomes useful outside Gittensor too: it is literally an autonomous software-work allocator.

---

# 7. SN11 TrajectoryRL — full competitive miner plan

## Setup

Current miner is a `SKILL.md` pack.

```bash
git clone https://github.com/trajectoryRL/trajectoryRL.git
cd trajectoryRL
pip install -e .
```

Build:

```bash
trajectoryrl-miner build SKILL.md -o pack.json
```

Validate locally before any submission.

Current first-party docs say web submission is the live submission channel and charges a default 50-alpha recycle fee, with a cooldown. Therefore **do not use the chain as an experiment loop**. Use local benchmark first.

## Competitive SKILL architecture

The skill must improve a weaker base model across many Terminal-Bench-like domains rather than overfit one scenario.

I would structure SKILL.md around an explicit operational controller:

### 1. Orient

Always establish:

- requested deliverable
- current directory
- files/repo state
- available tests/tools
- exact success condition

### 2. Observe before editing

Mandate:

```text
pwd
ls/tree selectively
read target files
inspect manifests
run baseline validation/tests
```

### 3. Localize failure

Search exact error/symbol/expected output before modifying anything.

### 4. Minimal hypothesis

State internally:

```text
Observed failure
Likely cause
Minimal intervention
How I will falsify it
```

### 5. Execute safely

- quote shell paths
- verify file exists
- backup only when necessary
- do not destroy unrelated state
- prefer deterministic tools over freehand rewriting

### 6. Verify iteratively

```text
narrow check → broader check → inspect deliverable
```

### 7. Recover by failure class

Instruction branches for:

- path/file mismatch
- package/dependency failure
- permission issue
- syntax/compile failure
- test assertion mismatch
- network/tool unavailability
- wrong deliverable format

### 8. Stop correctly

Require verification of:

- expected file/path exists
- format correct
- tests pass where available
- no unrelated destructive changes

## Skill Incubator

This subnet is perfect for an evolutionary loop.

Split SKILL.md into modules:

```text
orientation
planning
shell safety
coding
file operations
debugging
testing
recovery
completion
```

For each child:

- mutate ONE module
- freeze hypothesis
- benchmark on train scenarios
- benchmark on held-out scenarios
- reject if no held-out improvement
- store failure-by-scenario

Do not just let an LLM rewrite the whole skill repeatedly.

## Submission

Only after significant held-out improvement:

```bash
trajectoryrl-miner build SKILL.md -o pack.json
trajectoryrl-miner web-submit pack.json
```

Because submissions recycle alpha, the Treasury grant should cap how many submissions can occur per day/week.

---

# 8. SN67 Harnyx — full competitive miner plan

Harnyx has already built much of the experimental harness we want.

## Setup

```bash
git clone https://github.com/harnyx/harnyx.git
cd harnyx
uv sync --all-packages --dev
```

Configure the current supported LLM/search provider credentials according to its miner README.

## Use their AutoResearch harness

From the miner directory:

```bash
uv run prepare.py --benchmark-suite <suite>
printf 'commit\tscore_a\tscore_b\tcost_usd\tstatus\tdescription\n' > results.tsv
mkdir -p .autoresearch
touch .autoresearch/experiment-ledger.md
```

The repo’s AutoResearch policy already says:

- inspect concrete weak/failing cases
- choose one bottleneck
- write a hypothesis
- run focused diagnostics
- full eval only when justified
- record quality/cost/status
- keep or discard candidate

Integrate that ledger with Hydra rather than replacing it.

## Competitive agent architecture

### Query-mode router

Distinguish:

```text
FAST
RESEARCH
STRUCTURED
```

Fast queries need precision/recall and low excess content.

Research queries need strong evidence support.

Structured queries must satisfy schema exactly.

### Evidence planner

For research:

1. decompose into fact requirements
2. run independent searches in parallel where useful
3. rank sources by authority/freshness/relevance
4. fetch only load-bearing sources
5. maintain evidence table:

```text
claim → receipt_id → result_id → support strength
```

6. synthesize
7. cite only claims that need support

### Search cost control

Search is not free. Stop when evidence sufficiency threshold is reached.

### Model routing

Use smaller/cheaper model for:

- classification
- query generation
- extraction

Reserve stronger model for:

- synthesis
- conflict resolution
- hard reasoning

### Optimize three objectives separately

- score
- cost
- runtime

The Harnyx rules explicitly create opportunities to dethrone via meaningful improvements on these axes, so every experiment should declare which axis it is targeting.

## Hydra transfer

This WorkerVersion becomes the natural research layer behind TaoToad/TAOWL as well as a Harnyx miner.

---

# 9. SN61 RedTeam — competitive AB Sniffer miner

I would target the **defensive automation-detection challenge**, not the automation-evasion/humanization challenge.

That gives us highly transferable security research without optimizing bypass behavior.

Current AB Sniffer task broadly asks miners to identify among supported automation frameworks/headless sessions while avoiding false positives on human browsers. Human false positives are extremely costly, so high precision matters more than aggressive detection.

## Architecture

Build a detector ensemble:

```text
hard framework signatures
+ browser/runtime consistency checks
+ weak behavioral/runtime indicators
→ calibrated per-class score
→ abstain/no-detection unless threshold clears
```

### Probe families

Use defensive fingerprints such as:

- framework-specific injected globals/objects
- prototype/property descriptor inconsistencies
- native-function/error-stack differences
- automation/CDP observable side effects
- browser API consistency
- renderer/device/media/WebGL consistency for headless classification

Do **not** build general-purpose evasion or “make bots look human” machinery.

### High-precision thresholding

Maintain:

```text
hard signature weight
weak signal weight
collision matrix
human false-positive set
```

Require combinations for weak signatures rather than triggering from one fragile clue.

### Local test matrix

Test each detector against:

- each supported automation framework
- headed/headless variants where relevant
- multiple browser versions
- clean human Chrome/Chromium sessions
- benign extension variation
- platform/renderer variation where available

Metrics:

```text
per-class precision
per-class recall
human false-positive rate
cross-framework collision rate
runtime
```

Primary constraint:

`human_FP == 0` on our held-out human matrix before submission.

### Hydra experiments

Every new probe is a hypothesis:

```text
probe_name
framework_target
expected distinguishing property
browser versions tested
true positives
false positives
collisions
runtime cost
keep/reject
```

This produces reusable browser/agent-security research even if the subnet economics later decline.

---

# 10. SN82 anomaly investigation

Build a generic mechanism-mismatch scanner:

```text
latest subnet registration block
latest owner
on-chain identity
current repo URL
repo recent activity
third-party metadata owner/name/repo
payout distribution
```

Alert if:

```text
registration block changed
OR owner changed
OR identity repo changed
BUT public mechanism metadata still references previous instance
```

This is potentially one of the best edge classes because competitors often reason from cached descriptions.

For SN82 specifically:

1. derive current `subnet_instance_id`
2. fetch current identity/repo from chain
3. run full current payout-vector scan
4. verify whether that apparent one miner is truly a non-validator earning meaningful emission
5. find current validator scoring source
6. reproduce locally
7. only then decide whether it is mineable

---

# 11. Treasury / agent permissions

Do not give any miner unrestricted wallet access.

Each subnet gets its own grant:

```text
SN62 grant:
- max registration burn X
- max upload cost Y
- allowed netuid 62
- no transfer
- expires date/time
- human approval for registration

SN11 grant:
- max recycle alpha per submission
- max submissions/week
- allowed netuid 11

SN74 grant:
- no chain action except required registration/config
- GitHub PR creation initially human-approved
```

Worker can benchmark freely; money-moving actions remain gated.

---

# 12. Unified ExperimentReceipt

Every local or live candidate produces:

```json
{
  "hypothesis_id": "hyp_...",
  "netuid": 62,
  "subnet_instance_id": "62:<registration_block>",
  "mechanism_version": "<hash>",
  "worker_version": "ridges-v17",
  "git_sha": "...",
  "rules_hash": "...",
  "benchmark_snapshot": "...",
  "data_cutoff": "...",
  "cost_usd": 0.23,
  "runtime_s": 91,
  "local_score": 0.78,
  "estimated_paid_probability": 0.64,
  "expected_alpha_day": 120.3,
  "realized_alpha_day": null,
  "marked_tao_day": null,
  "realizable_tao_day": null,
  "status": "CANDIDATE"
}
```

After evaluation/payout, append outcome; never rewrite the original hypothesis.

---

# 13. What I would do this week

## Day 1

1. Finish exact payout-vector live scanner.
2. Run it across all current subnet instances.
3. Re-rank candidates using actual 0.1/0.25/0.5/day seats and payout breadth.
4. Resolve SN82 identity/mechanism anomaly.
5. Create `mining_lab` common interface.

## Day 2

1. Clone Ridges.
2. Get baseline `agent.py` running locally.
3. Build Ridges benchmark runner + experiment receipt.
4. Run 20+ baseline tasks.
5. Identify dominant failure classes.

In parallel:

1. Clone Gittensor.
2. Build repo/opportunity scout.
3. Produce first 10 qualified OSS issues.

## Day 3

1. Start Ridges single-hypothesis evolution.
2. Build TrajectoryRL local skill incubator.
3. Establish baseline SKILL score by scenario.

## Day 4

1. Integrate Harnyx AutoResearch with Hydra.
2. Run baseline research agent.
3. Determine score/cost/runtime bottleneck.

## Day 5

1. Build RedTeam AB Sniffer local matrix.
2. Establish human-FP baseline.
3. Add first framework-specific high-confidence probes.

## Day 6–7

Re-run live economics.

Only promote miners where BOTH are true:

- economics still attractive
- our local held-out benchmark predicts paid rank

Then request human approval for registration/submission.

---

# 14. Final priority

If limited to one target today:

> **SN62 Ridges first.**

It is the cleanest combination of current reward opportunity, low visible competition, near-zero apparent entry burn, no GPU, first-party local evaluation, and exact overlap with the coding-agent infrastructure we want anyway.

Then:

> **SN74 Gittensor** for durable real-world OSS earnings and public track record.

Then:

> **SN11 TrajectoryRL** as the purest Moltwork/Hydra skill-learning experiment.

Then:

> **SN67 Harnyx** because its AutoResearch system is practically a ready-made Moltwork research world.

Then:

> **SN61 RedTeam AB Sniffer** because it compounds our security specialization.

And in parallel:

> **Investigate SN82 immediately** because the apparent economics are weird enough that, if chain truth confirms them, it could leapfrog everything.

The larger strategy is not “pick the best subnet once.”

It is:

> /bitt continuously finds underexploited reward pools; Moltwork builds/evolves the appropriate WorkerVersion; the exact payout vector tells us whether it is paying; Hydra learns whether the method transferred; Treasury lets the worker act within hard bounds; when edge decays, rotate.

That is the mining business.

## Primary sources

Bittensor mining/registration concepts:
https://www.bittensor.com/docs/guides/mining

Bittensor shorting PR status:
https://docs.taostats.io/docs/shorting

Ridges:
https://github.com/ridgesai/ridges

TrajectoryRL:
https://github.com/trajectoryRL/trajectoryRL

Harnyx:
https://github.com/harnyx/harnyx

Gittensor:
https://github.com/entrius/gittensor

RedTeam:
https://github.com/RedTeamSubnet
