# Bittensor miner deep dive — Harnyx, RedTeam, Ridges + exact local eval paths

**Date:** Wed, 2 Sep 2026 18:50:30 -0700

---

# Bittensor miner deep dive — where I would actually attack first

## Bottom line

Priority for your current goal (recurring low-hanging TAO, not jackpot hunting):

1. **Harnyx SN67 — strongest immediate fit**
2. **RedTeam SN61 — second, with FlowRadar v2 the cleanest first challenge**
3. **Ridges SN62 — useful research target but currently winner-take-all, so not aligned with recurring-income thesis**

The important correction is that Ridges should move to the jackpot queue. Its current incentive docs state the all-time-high agent gets 100% of miner incentive until dethroned. Harnyx and RedTeam both let us earn without being #1.

---

# 1. HARNYX SN67 — BEST FIT

Official repo:
https://github.com/harnyx/harnyx

Miner docs:
https://github.com/harnyx/harnyx/tree/main/miner

## Why it fits us

Harnyx pays both:
- a **champion component**, and
- a **participant component** from the latest completed miner-task batch.

Under the current public rules, participant reward is tiered by BOTH performance and novelty.

Current policy:
- participation multiplier: top 50% = 1x, top 10% = 2x, main tier = 5x
- novelty multiplier: near-duplicate = 1x, notable change = 3x, novel = 5x
- participant share is proportional to the product, capped at 25
- duplicates, zero-response artifacts and artifacts outside reward tiers get no participant share

So for us the first target is **not champion**. It is:

> reliably finish in the paid half, while being classified notable/novel.

That is exactly the recurring-income profile we wanted.

## What the miner actually does

You submit ONE Python file (`agent.py`). Validators run it in a sandbox against research questions.

Contract:

```python
from harnyx_miner_sdk.context import ContextSnapshot
from harnyx_miner_sdk.decorators import entrypoint
from harnyx_miner_sdk.query import Query, Response

@entrypoint("query")
async def query(query: Query, context: ContextSnapshot) -> Response:
    ...
```

Tasks are mixed across factual recall, explanation, comparison, synthesis and structured-output requests.

Ordinary queries are scored pairwise against a stronger reference answer. Fast queries are correctness-only and penalize excessive content.

Tie-breakers prefer lower total tool cost.

## What I think a strong miner should look like

I would NOT build a generic “search then summarize” agent. That will be structurally near-duplicate to everyone else.

I would build a **claim-graph research controller**:

1. Classify request:
   - fast factual
   - factual research
   - comparative
   - synthesis
   - structured-output
2. Decompose requested answer into explicit claims / slots.
3. Create an evidence ledger per claim.
4. Search in parallel using 2–4 query formulations only where needed.
5. Rank evidence by directness/authority.
6. Run a contradiction/missing-claim pass.
7. Spend remaining budget only on unresolved claims.
8. Synthesize answer directly from the ledger.
9. Attach only citations supporting load-bearing claims.
10. For `fast=True`, bypass the research pipeline and produce a terse high-recall/high-precision answer with no citation overhead.

This architecture has a genuinely different controller/evidence flow, which matters because Harnyx explicitly classifies novelty structurally.

### Harnyx-specific optimization targets

The local evaluator exposes losses due to:
- missing evidence
- weak synthesis
- unsupported claims
- excessive cost
- slow execution
- retries/tool failures
- exceptions

So WorkerKit/Hydra can optimize those dimensions directly.

Our Harnyx score should be something like:

```text
HARNYX_FIT =
  mean_task_score
+ paid_tier_probability
+ novelty_multiplier_expectation
- tool_cost
- timeout_probability
- failure_probability
```

## Exact local evaluation

From repo root:

```bash
git clone https://github.com/harnyx/harnyx.git
cd harnyx
uv sync --all-packages --dev
```

Create `.env` from `.env.example`.

Minimum typical setup:

```bash
PLATFORM_BASE_URL=https://api.harnyx.ai
CHUTES_API_KEY=...
SEARCH_PROVIDER=desearch
DESEARCH_API_KEY=...
```

Then:

```bash
uv run --package harnyx-miner harnyx-miner-local-eval \
  --agent-path ./agent.py
```

Default mode is **vs-champion**.

It runs BOTH our local artifact and the recorded champion artifact and writes:
- raw head-to-head totals
- wins/losses/ties
- cost/runtime
- task-level details
- simulated champion-selection outcome

Pin a completed batch for repeatability:

```bash
uv run --package harnyx-miner harnyx-miner-local-eval \
  --agent-path ./agent.py \
  --batch-id <BATCH_ID>
```

Focused diagnosis:

```bash
LOG_LEVEL=DEBUG uv run --package harnyx-miner harnyx-miner-local-eval \
  --agent-path ./agent.py \
  --batch-id <BATCH_ID> \
  --task-id <TASK_ID> \
  --mode target-only \
  > local-eval-paths.json \
  2> local-eval-debug.log
```

It exposes tool requests, responses, usage, cost, budget, elapsed time and failures.

## Open benchmark evaluation

Harnyx also packages benchmark suites:

```bash
uv run --package harnyx-miner harnyx-miner-local-benchmark --list-suites

uv run --package harnyx-miner harnyx-miner-local-benchmark \
  --suite webwalkerqa \
  --agent-path ./agent.py \
  --source-batch-id <BATCH_ID>
```

Current suites include DRACO as well.

## Best bit: AutoResearch is already built

They literally provide an autonomous miner research loop:

https://github.com/harnyx/harnyx/blob/main/miner/AUTO-RESEARCH.md

Setup:

```bash
cd miner
uv run prepare.py --benchmark-suite <suite>
printf 'commit\tscore_a\tscore_b\tcost_usd\tstatus\tdescription\n' > results.tsv
mkdir -p .autoresearch
touch .autoresearch/experiment-ledger.md
```

The agent edits only `train.py`, runs focused diagnostics, then full evaluation when justified, and records every experiment.

This maps almost one-to-one onto our WorkerKit + Hydra learning loop.

### Immediate action

Clone Harnyx into `/bitt/targets/harnyx` and wrap their AutoResearch loop with our run ledger/HydraDB.

## The “someone left a good miner public” angle

Harnyx is even better than that: their official Mining Runbook intentionally tells miners to query the public platform MCP:

`https://api.harnyx.ai/mcp`

Then:
1. `get_champion`
2. `get_miner_script(artifact_id=champion.script_id, include_content=true)`
3. if script content is available, decode `content_b64`
4. use it as baseline
5. locally evaluate modifications against it

So the champion code may be deliberately available through the protocol itself. No need to hunt for leaked private repos.

Their docs explicitly say: “Champion code is a baseline, not finished work.”

There is also a public `cdylan320/harnyx` repository with an `agent.py`, but it appears to be based on an older Harnyx state and older participant-reward policy. I would not treat it as current winning code. Use current platform champion context instead.

---

# 2. REDTEAM SN61 — SECOND PRIORITY

Main repo:
https://github.com/RedTeamSubnet/RedTeam

Miner repo:
https://github.com/RedTeamSubnet/miner

Docs:
https://docs.theredteam.io/latest/miner/

## Why it fits us

RedTeam does NOT require #1.

Accepted submissions earn according to their validator score / consensus weighting.

Important mechanics:
- scores normalized rather than pure winner-take-all
- plagiarism/similarity penalty
- penalty >= 0.6 causes rejection
- accepted submission receives full freshness for days 0–10
- decay days ~10–15
- after ~15 days it earns zero
- submitting a new commit immediately replaces the old one

This creates recurring openings because old good solutions decay out.

The ideal RedTeam strategy is therefore:

> maintain several independently improvable challenge adapters and submit genuinely new improvements before our current score starts decaying.

## Active challenges I found

Current docs include:
- AB Sniffer v6
- Humanize Behaviour v5
- ADA detection
- Bot Virus
- FlowRadar v2

I think **FlowRadar v2 is the best first target**.

Why:
- deterministic classification
- full local scorer
- no expensive browser farm
- 100k-row training set
- 400k-row local scoring set
- 110 features
- scikit-learn explicitly installed
- exact F1 objective
- very cheap automated experimentation

### Important discovery: reference baseline is weak

Checked-in baseline `train.py` learns only ONE quantity:

```text
ratio = bwd_sum_pkt_len / fwd_sum_pkt_len
threshold = midpoint(mean VPN ratio, mean clean ratio)
```

Then `submissions.py` predicts VPN if ratio >= threshold.

That is an extremely weak baseline for a 110-column dataset.

Official scoring container includes:
- pandas 2.2
- NumPy
- scikit-learn 1.4+

This is low-hanging fruit.

## What I would build for FlowRadar

Do not hardcode trained weights: rules prohibit externally learned/pretrained weights.

Instead train everything inside `train.py` during the scoring run.

Best first candidate:

### Pipeline A — compact logistic model

`train.py`:

1. Load 100k rows.
2. Split train/validation stratified.
3. Convert numeric columns robustly.
4. Generate useful derived features:
   - packet byte ratios
   - packet-count ratios
   - bytes/sec
   - packets/sec
   - directional IAT ratios
   - duration/log duration
   - variance / std ratios
   - TCP flag combinations
5. Remove near-constant features.
6. Standardize.
7. Fit class-balanced logistic regression.
8. Search classification threshold that maximizes validation F1.
9. Serialize ONLY:
   - selected feature names
   - means/stds
   - coefficients
   - intercept
   - threshold
   into JSON.

`submissions.py`:
- reconstruct feature vector
- normalize from JSON model
- compute logistic score manually
- compare with learned threshold
- never throw on missing/null values

This is fully compliant because all learned coefficients are generated during the current scoring run.

Then test:
- logistic regression
- SGD logistic
- LinearSVC converted to manual linear scoring
- shallow decision tree serialized to JSON
- small RandomForest if JSON limit/runtime allow it
- hand-designed feature ensemble

Hydra records cross-validation + full local score.

## Exact FlowRadar local eval

```bash
git clone https://github.com/RedTeamSubnet/flowradar-challenge.git
cd flowradar-challenge
git lfs pull
```

Required data:

```text
volumes/storage/flowradar-challenge/data/v2_train_data.csv
volumes/storage/flowradar-challenge/data/v2_test_data.csv
```

Compile:

```bash
python3 -m py_compile \
  src/flr_challenge/challenge/flowradar/src/train.py \
  src/flr_challenge/challenge/flowradar/src/submissions.py
```

Run training directly:

```bash
python3 src/flr_challenge/challenge/flowradar/src/train.py \
  volumes/storage/flowradar-challenge/data/v2_train_data.csv \
  /tmp/flowradar_model.json
```

Validate model:

```bash
python3 -m json.tool /tmp/flowradar_model.json >/dev/null
```

Production-equivalent local scorer:

```bash
cp .env.example .env

docker compose up -d --build --remove-orphans
python3 skills/challenge-score/scripts/check_score.py
```

Useful debugging endpoints:

```text
GET /health
GET /status
POST /score
GET /results
GET /telemetry
```

Official solver skill:
https://github.com/RedTeamSubnet/flowradar-challenge/blob/main/skills/challenge-solver-guide/SKILL.md

That skill itself recommends combining duration, packet lengths, IAT and TCP flags and tuning precision/recall rather than using one cutoff.

This target is very compatible with fully autonomous agent experimentation.

## AB Sniffer

Repo/docs provide a local challenge environment.

Current v6 requires detection across multiple automation frameworks plus human/headless behavior.

Local process roughly:

```bash
git clone https://github.com/RedTeamSubnet/ab-sniffer.git
cd ab-sniffer
python3 skills/validate-submission/scripts/validate_submission.py
cp .env.example .env
docker compose up -d
```

Then run framework browser sessions and call `/score` through a bot runner.

This is interesting but needs browser-runner infrastructure across framework/version/OS combinations, so I would do it after FlowRadar.

## Humanize Behaviour

Local evaluator exists:

```bash
git clone https://github.com/RedTeamSubnet/humanize-behaviour-challenge.git
cd humanize-behaviour-challenge
cp ./templates/compose/compose.override.dev.yml ./compose.override.yml
docker compose up -d
```

Then use local `/score` on port 10001.

Winning features include:
- velocity variation
- speed profiles
- non-linear trajectories
- non-perfect Bezier paths
- keypress timing variation
- varied movement across sessions

This is also automatable, but empirical browser simulation is more operationally annoying.

## Public miner hunting

I searched GitHub globally for current challenge implementation signatures.

I did **not** find a clearly current, obvious high-scoring third-party FlowRadar/AB/Humanize miner repository.

That is probably because RedTeam submissions are mainly packaged into Docker images rather than normal source repos.

The RedTeam docs actually warn miners NOT to name their Docker Hub image after the challenge or username because other miners can scan Docker Hub and submit the image themselves.

We should not steal someone else's active submission, but this confirms the ecosystem has public-container leakage risk. For us, the useful action is to mine public techniques/code and use them as research inputs—not submit identical code, because the subnet's similarity penalty makes exact copying useless anyway.

---

# 3. RIDGES SN62 — JACKPOT, NOT INCOME

Official repo:
https://github.com/ridgesai/ridges

Benchmarks:
https://github.com/ridgesai/ridges-bench

## Current mechanism

Current incentive docs say **winner takes all**.

A new agent is evaluated on coding tasks. If it gets an all-time-high overall score, that miner receives 100% incentive until dethroned.

Therefore this is not our first recurring-income target.

Still worth developing because the potential daily pool is large and all dev work transfers to coding-agent capabilities.

## Agent contract

One `agent.py`:

```python
def agent_main(input: dict) -> str:
    # solve the issue
    # return unified diff
```

Inference through OpenRouter/Targon/Chutes.

## Local evaluation

```bash
git clone https://github.com/ridgesai/ridges.git
cd ridges
pip install -e '.[miner]'
# or uv sync --extra miner

ridges miner setup
```

Configure `<workspace>/.env.miner`.

Then:

```bash
ridges miner run-local
```

or deterministic scripted mode:

```bash
ridges miner run-local \
  --task-path /path/to/task \
  --agent-path /path/to/agent.py \
  --provider openrouter \
  --non-interactive
```

Clone sample benchmark pack:

```bash
git clone https://github.com/ridgesai/ridges-bench.git
```

Each task contains:
- instruction.md
- task.toml
- environment/
- tests/
- solution/

Run:

```bash
ridges miner run-local \
  --task-path ./ridges-bench/30_06_2026/<TASK>
```

Output includes reward and passed/failed tests.

Warning: local tasks are samples and do NOT reproduce official platform distribution or budget restrictions.

## Public winner code?

Ridges historically emphasized open-source miner code, but the Aug 4 v0.2.4 release explicitly added **“Hide top agent code across all competitions.”**

So I did not find a current top-agent leak worth relying on.

There may be old agent versions in forks/archives, but they are stale against the latest judge policy and incentive mechanism.

That makes Ridges less attractive than Harnyx for our “bootstrap from incumbent” loop.

---

# IMPLEMENTATION ORDER FOR /BITT

## CP0 — Harnyx adapter

Create:

```text
targets/harnyx/
  upstream/
  adapter.py
  eval.py
  experiments/
  hydra_writer.py
```

Functions:

```text
fetch_current_champion()
fetch_champion_script()
fetch_latest_completed_batch()
run_local_vs_champion(candidate)
run_benchmark(candidate, suite)
extract_failure_taxonomy(report)
record_experiment()
```

Agent loop:

```text
champion
  ↓
current failures
  ↓
propose one mechanism change
  ↓
focused task eval
  ↓
full pinned batch eval
  ↓
benchmark eval
  ↓
Hydra evidence
  ↓
keep / reject
```

Goal 1:
**paid top-50% probability >70% across held-out batches**

Goal 2:
**novel/notable classification rather than near-duplicate**

Goal 3:
**expected participant payout > registration + inference cost**

Only then register/submit.

## CP1 — FlowRadar autonomous optimizer

Create:

```text
targets/redteam/flowradar/
  upstream/
  candidate/
      train.py
      submissions.py
  experiment.py
  scoreboard.csv
```

Experiment dimensions:
- feature subsets
- derived feature sets
- classifier family
- class weights
- regularization
- threshold
- feature selection

Every run stores:

```text
commit
model_family
features
params
local_f1
precision
recall
TP FP TN FN
training_seconds
model_json_bytes
status
```

Run CGE/Hydra against this until score stabilizes.

Then make a genuinely distinct final implementation before RedTeam submission to minimize similarity penalty.

## CP2 — RedTeam browser challenges

After FlowRadar:
- AB Sniffer
- Humanize Behaviour
- Bot Virus

These require more infra but are good permanent security-skill generators.

## CP3 — Ridges

Treat as moonshot only once coding agent skill is already strong.

---

# My actual recommendation

If we wanted to start earning rather than theorize, I would do this:

**Today:**
1. clone `harnyx/harnyx`
2. connect its public MCP
3. fetch current champion context/script if exposed
4. run current champion through local eval
5. build one structurally different claim-graph agent
6. run Harnyx AutoResearch overnight-style loops
7. estimate top-50% paid probability

**In parallel:**
1. clone `RedTeamSubnet/flowradar-challenge`
2. replace the one-feature baseline with a compact scikit-learn-trained model
3. run fully local F1 optimization
4. only register when we already clear the minimum acceptance threshold robustly

That is the cleanest path I have found so far to actual repeatable low-hanging TAO.

Sources checked:
- https://github.com/harnyx/harnyx
- https://github.com/harnyx/harnyx/blob/main/miner/mining-runbook.md
- https://github.com/harnyx/harnyx/blob/main/miner/AUTO-RESEARCH.md
- https://github.com/harnyx/harnyx/blob/main/miner/local-eval.md
- https://github.com/ridgesai/ridges
- https://github.com/ridgesai/ridges-bench
- https://docs.ridges.ai/incentive-mechanism
- https://github.com/RedTeamSubnet/RedTeam
- https://docs.theredteam.io/latest/miner/
- https://github.com/RedTeamSubnet/flowradar-challenge
- https://github.com/RedTeamSubnet/flowradar-challenge/blob/main/skills/challenge-solver-guide/SKILL.md
