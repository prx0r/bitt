Yes. **One Lab, many Studios, one WorkerKit.** Metaculus and Bittensor should not become separate architectural projects. They are two different experimental environments plugged into the same laboratory.

The useful thing in `qdw-workbench` is exactly its narrow-waist philosophy: the Workbench is a control plane rather than another agent framework; execution nodes are disposable; context is compiled rather than treated as truth; costs remain dimensionally separate; and memory is candidate context rather than authority. The UI itself is much less mature than the architecture—the current app is still mostly a shell, and even the Cost panel explicitly says it is awaiting telemetry—so I would **reuse the Tauri/qdw-node/control-plane chassis, not preserve the QDW-specific information architecture**.

`cg` should supply the scientific doctrine. It already has the right concepts: content-addressed runs, dev/validation/secret suites, quality gates before cost optimization, immutable receipts, a derived Hydra experience graph, and graph-informed proposals that still have to compete on hidden evaluation. Its explicit rule that Hydra is disposable and rebuildable from canonical receipts is particularly important.

And the current `mw` branch tells us why this consolidation needs to happen **now**. The latest self-review says real Letta execution works and the wallet/broker/graph plumbing exists, but outcomes and costs are largely synthetic, Harbor is absent, and much of the E2E evidence is mock-derived. So the next milestone should not be “better Ditto score.” It should be **turn the existing pieces into one scientifically clean Lab**.

Current Letta still supports persistent editable agent memory, shared memory blocks, and git-backed memory, which makes it a good **subject memory runtime**. But Moltwork should control what gets promoted into that memory; Letta memory itself must not become the experiment database.

This is the specification I would hand to the coding agent.

# MOLTWORK PRIVATE LAB v0.1
## Constitution, Architecture and Implementation Specification

### Status

This document defines what a Moltwork Lab is.

Do not add another opportunity integration, Bittensor subnet, benchmark, market, or agent framework until the contracts in this document exist and the first checkpoints pass.

The primary research question is:

> Can an autonomous worker become measurably better at a family of tasks over time, while learning how to allocate its own limited computational/economic resources?

External earnings are evidence of transfer, not the definition of success.

---

# 1. Core architecture

There is exactly:

```text
ONE MOLTWORK LAB
        │
        ├── WorkerKit
        ├── Event Ledger
        ├── Git lineage
        ├── Letta workers
        ├── CG evaluation
        ├── CGE curriculum/evolution
        ├── Hydra experience graph
        ├── Budget/Compute Wallet
        └── Workbench control plane
                 │
                 ├── Studio: Metaculus
                 ├── Studio: Bittensor/Ditto
                 ├── Studio: Bittensor/Ridges
                 ├── Studio: Security
                 ├── Studio: Vesuvius
                 └── future Studios
```

A Studio is NOT another Lab.

A Studio supplies a domain.

The Lab supplies the scientific method.

---

# 2. Definitions

## Lab

The complete experimental system responsible for:

- worker identity;
- immutable worker versions;
- task execution;
- provenance;
- cost accounting;
- evaluation;
- experimental comparison;
- curriculum generation;
- memory/skill proposals;
- promotion/rejection;
- experience storage;
- cross-domain learning;
- resource allocation.

The Lab does not know what Metaculus, Ditto or Vesuvius mean.

---

## Studio

A domain adapter that supplies:

```text
task distribution
environment
replay data
evaluator/verifier
live venue adapter
economic observations
domain-specific curriculum hooks
```

Examples:

```text
studio/metaculus
studio/bittensor-118-ditto
studio/bittensor-62-ridges
```

Studios may have radically different tasks but implement the same contract.

---

## Worker

A persistent subject being studied.

Example:

```text
worker/researcher-03
```

A Worker owns a lineage of immutable WorkerVersions.

A Worker is NOT equivalent to:

- model;
- Letta conversation;
- Git branch;
- prompt;
- MemFS commit.

Those are dependencies of WorkerVersions/Runs.

---

## WorkerVersion

The exact immutable executable cognitive configuration tested by the Lab.

Conceptually:

```text
WorkerVersion
├── parent_version
├── agent_runtime
├── model policy
├── system/identity
├── memory revision
├── skill versions
├── tool policy
├── process policy
├── routing policy
├── context policy
└── source Git commits/digests
```

`researcher-v8` means something concrete and reproducible.

If any behaviourally significant component changes, create another WorkerVersion.

Never silently mutate a production WorkerVersion.

---

## TaskInstance

One frozen task presented to a worker.

Examples:

```text
historical Metaculus question #312
DittoBench seed 43891
Harbor issue instance abc
Minos genomic region xyz
```

TaskInstance includes split:

```text
TRAIN
DEV
VALIDATION
SECRET
LIVE
```

A Worker/CGE may receive feedback from TRAIN/DEV.

SECRET data never enters proposal generation.

---

## Run

One WorkerVersion attempting one TaskInstance under one BudgetEnvelope.

This is the atomic unit of evidence.

A Run must answer:

```text
WHO acted?
WHICH exact version?
ON WHAT exact task?
WHAT information was available?
WHAT tools were available?
WHAT budget existed?
WHAT actions occurred?
WHAT did it produce?
HOW was it evaluated?
WHAT did it cost?
WHAT happened externally?
```

---

## Experiment

A controlled comparison between WorkerVersions or policies.

Example:

```text
Hypothesis:
explicit base-rate extraction improves forecasting calibration.

Control:
forecaster-v7

Candidate:
forecaster-v8

Evaluation:
80 paired SECRET questions

Decision:
PROMOTE / REJECT
```

A collection of Runs is not automatically an Experiment.

An Experiment must contain a predeclared hypothesis and comparison.

---

## LearningProposal

A proposed change derived from experience.

Examples:

```text
memory patch
skill patch
routing-policy patch
tool-selection patch
process patch
context-retrieval patch
```

A LearningProposal is not knowledge.

It is a hypothesis.

---

## Promotion

The only operation by which a proposed change enters a production WorkerVersion.

Promotion requires experimental evidence.

No:

```text
"agent reflected and thought this seemed useful"
```

promotion.

---

# 3. The universal WorkerKit run

Every Studio uses this exact lifecycle:

```text
TaskInstance
     │
     ▼
RunSpec
     │
     ├── WorkerVersion
     ├── BudgetEnvelope
     ├── ContextPack
     └── execution policy
     │
     ▼
fresh execution session
     │
     ▼
Worker acts
     │
     ├── model calls
     ├── tools
     ├── files
     ├── searches
     └── decisions
     │
     ▼
Artifact(s)
     │
     ▼
Evaluator
     │
     ▼
EvaluationResult
     │
     ▼
RunReceipt
     │
     ├── canonical ledger
     ├── Git/artifact references
     └── trajectory reference
     │
     ▼
Hydra projection
```

Then, separately:

```text
many RunReceipts
       │
       ▼
failure analysis
       │
       ▼
LearningProposal
       │
       ▼
CGE curriculum / candidate generation
       │
       ▼
CG evaluation
       │
       ▼
SECRET paired experiment
       │
       ├── FAIL → reject
       │
       └── PASS → WorkerVersion n+1
```

That is Moltwork learning.

Everything else is infrastructure.

---

# 4. The agent's exact experience

At the beginning of a Run, the agent receives:

```text
TaskInstance
Worker identity
Studio policy
ContextPack
BudgetEnvelope
allowed tools
output contract
```

It does NOT receive:

```text
secret evaluator labels
future outcomes
all previous trajectories
arbitrary contents of Hydra
unvalidated global Lab observations
other candidate's secret results
```

A run should normally use a fresh conversation/session while retaining the persistent Worker identity.

This keeps:

```text
persistent organism
+
independent task episode
```

rather than one giant contaminated chat history.

---

# 5. Five kinds of learning

Never merge these into one metric.

## L1 — Context learning

WorkerVersion unchanged.

Lab retrieves better prior evidence.

Test:

```text
v1 without Lab context
vs
v1 + Lab ContextPack
```

This measures organizational memory.

---

## L2 — Worker learning

Worker's durable memory/skill/process changes.

Test:

```text
v1 + identical context
vs
v2 + identical context
```

This measures persistent worker improvement.

---

## L3 — Budget learning

Worker unchanged except resource-allocation policy.

Examples:

```text
which model
when to search
when to escalate
how many samples
when to stop
```

Measure quality/cost frontier.

---

## L4 — Curriculum/evolution learning

CGE/Hydra become better at producing useful candidate WorkerVersions.

Measure:

```text
candidates needed per successful promotion
cost per promotion
promotion magnitude
regression rate
```

---

## L5 — Transfer learning

A finding from Studio A improves Studio B.

Example:

```text
Ditto learns:
"retrieve temporally relevant memory before generic semantic memory"

Metaculus tests the same retrieval strategy.

Only if Metaculus improves:
Finding
    ──TRANSFERRED_TO──>
Metaculus
```

This is the strongest evidence of genuine general learning.

---

# 6. Canonical data architecture

Do not ask one database to do everything.

## Layer A — immutable truth

Canonical:

```text
WorkerKit event ledger
RunReceipts
EvaluationReceipts
ExperimentSpecs
ExperimentResults
BudgetEvents
ExternalOutcomeReceipts
```

Properties:

```text
append only
schema validated
content addressed where practical
rebuildable
never silently corrected
```

Use Pydantic models and canonical serialization.

---

## Layer B — Git

Git stores versioned intellectual artifacts:

```text
Worker manifests
Skills
process definitions
Studio manifests
evaluation code
experiment specs
CGE recipes
promoted memory patches
ContextPack policies
budget policies
```

A WorkerVersion must resolve to exact Git commits/digests.

Git answers:

> What changed?

The event ledger answers:

> What happened?

---

## Layer C — artifact store

Large immutable objects:

```text
trajectories
model transcripts
search tapes
datasets
generated files
screenshots
checkpoints
evaluation outputs
```

Address using digest.

RunReceipts reference them.

Do not dump them into Hydra.

---

## Layer D — Letta memory

Letta is the Worker's subjective persistent memory.

It may contain:

```text
lessons
working principles
skills
task heuristics
personal scratch
recurring failure warnings
```

Letta is NOT canonical evidence.

A memory statement such as:

```text
"deep research usually helps geopolitical forecasts"
```

is an agent belief.

Hydra/receipts determine whether evidence supports it.

All promoted durable memory changes must map to a MemoryRevision.

---

## Layer E — Hydra

Hydra is the derived experience graph.

Delete Hydra:

```text
Lab remains intact.
```

Rebuild Hydra:

```text
same meaningful graph.
```

Hydra exists for:

```text
retrieval
association
lineage
correlation
proposal biasing
cross-Studio discovery
```

Never authority.

---

# 7. One global Hydra graph

YES: use one global experience graph.

NO: do not use one global undifferentiated memory pool.

Logical structure:

```text
GLOBAL LAB GRAPH

Studio
Worker
WorkerVersion
TaskFamily
TaskInstance
Run
Artifact
Evaluation
BudgetDecision
Model
Tool
SkillVersion
MemoryRevision
ContextPack
Experiment
LearningProposal
Finding
Outcome
```

Important edges:

```text
WorkerVersion ─PARENT_OF→ WorkerVersion

WorkerVersion ─RAN→ Run
Run ─IN_STUDIO→ Studio
Run ─ATTEMPTED→ TaskInstance
Run ─USED→ SkillVersion
Run ─USED→ MemoryRevision
Run ─USED→ ContextPack
Run ─USED_MODEL→ Model
Run ─PRODUCED→ Artifact
Run ─RECEIVED→ Evaluation
Run ─COST→ BudgetEvent
Run ─RESULTED_IN→ Outcome

Experiment ─TESTED→ LearningProposal
LearningProposal ─CREATED→ WorkerVersion

WorkerVersion
    ─IMPROVED_ON→
TaskFamily

Finding ─SUPPORTED_BY→ Experiment
Finding ─VALID_IN→ Studio
Finding ─TRANSFERRED_TO→ Studio
```

Every node/edge carries:

```text
studio_id
source receipt IDs
observed_at
schema version
confidence/evidence state
```

---

# 8. Knowledge tiers

This is essential.

Hydra observations have four epistemic levels.

## OBSERVATION

One/few Runs.

Example:

```text
v7 failed because it ignored temporal wording.
```

Never globally injected.

---

## STUDIO_FINDING

Validated inside one Studio.

Example:

```text
temporal retrieval improves DittoBench by +4.1 points
on 80 secret instances.
```

Usable as Studio context.

---

## TRANSFER_CLAIM

Explicitly tested in another Studio.

Example:

```text
temporal retrieval also improves Metaculus replay.
```

May now enter global context retrieval.

---

## DOCTRINE

Repeated cross-domain result accepted as a Lab-wide process rule.

Very rare.

Example:

```text
production worker changes require paired sealed evaluation.
```

The graph can contain everything.

The Context Compiler decides which tier the Worker actually sees.

---

# 9. ContextPack

Every Run records an immutable ContextPack ID.

A ContextPack is a deterministic compilation of:

```text
Lab doctrine
Studio policy
Worker durable memory
validated relevant Studio findings
validated global transfer findings
similar successful Runs
relevant failure warnings
task-specific material
budget information
```

Each fragment has:

```text
source ID
source type
trust tier
observed time
digest
token count
selection reason
```

The compiler returns both:

```text
included fragments
dropped fragments
```

No invisible truncation.

This directly inherits the strongest design from qdw-workbench.

---

# 10. Pydantic contracts

Implement these first:

```text
LabManifest
StudioManifest

Worker
WorkerVersion

TaskInstance
RunSpec
RunReceipt

ArtifactRef
TrajectoryRef

BudgetEnvelope
BudgetEvent
RouteDecision

EvaluationSpec
EvaluationResult

ExperimentSpec
ExperimentResult

LearningProposal
MemoryRevision
SkillVersion
ProcessVersion

Finding
TransferClaim

ContextFragment
ContextPack

ExternalSubmissionReceipt
ExternalOutcomeReceipt
```

All cross-module interfaces exchange these contracts.

Do not pass mystery dictionaries through the Lab.

---

# 11. Minimum RunSpec

```python
class RunSpec(BaseModel):
    run_id: str

    lab_id: str
    studio_id: str

    task_instance_id: str
    split: Literal[
        "TRAIN", "DEV", "VALIDATION", "SECRET", "LIVE"
    ]

    worker_id: str
    worker_version_id: str

    context_pack_id: str
    budget_envelope_id: str

    evaluator_version_id: str

    seed: int | None

    mode: Literal[
        "REPLAY", "SHADOW", "LIVE"
    ]
```

No Run starts without a valid RunSpec.

---

# 12. BudgetEnvelope

This becomes first-class.

Never reduce resources to one fake dollar number.

```text
cash_usd
token_limit
wall_seconds
model_call_limit
search_call_limit
compute_ms/GPU seconds
subscription units
provider quota units
external capital risk
human seconds
```

A BudgetEnvelope also contains:

```text
hard limits
soft targets
allowed providers
quality floor
escalation policy
```

---

# 13. Budget truth vs shadow economics

Maintain separately:

```text
ACTUAL CASH COST
SHADOW QUOTA COST
SUBSCRIPTION CONSUMPTION
LOCAL COMPUTE
HUMAN TIME
CAPITAL AT RISK
```

Never:

```text
free credit = $0
subscription = fake USD
local compute = $0 therefore free
```

Store raw dimensions.

The economic policy may derive shadow values.

Those derived values are versioned policy outputs.

---

# 14. BATS experiment

Budget optimization is an experimental problem.

Every Studio can compare:

```text
F = free/minimum-cost
M = Moltwork adaptive routing
Q = quality ceiling
```

On the SAME paired task instances.

Measure:

```text
quality
success probability
cash
quota consumption
latency
model calls
tool calls
human intervention
```

Do not immediately scalarize them.

CG should apply:

```text
1. hard quality gates
2. allowed quality regression margin
3. cost
4. latency/resource use
```

lexicographically.

---

# 15. CG's role

CG is the independent experimental kernel.

It owns:

```text
task split discipline
paired comparison
secret evaluation
quality gates
statistics
promotion evidence
replayability
```

CG does NOT own Worker memory.

CG does NOT decide what to work on economically.

CG does NOT execute live submissions.

CG answers:

> Did candidate B actually outperform control A under the declared experiment?

---

# 16. CGE's role

CGE is a proposal/curriculum generator.

Input:

```text
TRAIN/DEV failures
Hydra findings
worker lineage
search space
budget
```

Output:

```text
candidate mutations
targeted curriculum
counterfactual tasks
experiment hypotheses
```

CGE never sees SECRET labels.

CGE never promotes candidates.

CGE scores cannot promote a worker.

Only CG sealed evaluation can promote.

---

# 17. Letta's role

Letta is the persistent subject runtime.

For every Worker:

```text
worker_id
    ↕ permanent mapping
letta_agent_id
```

For every Run:

```text
same persistent Agent
+
fresh execution Conversation/Session
```

Worker memory changes are initially controlled.

Recommended lifecycle:

```text
experience occurs
     ↓
reflection
     ↓
LearningProposal
     ↓
candidate MemFS branch/revision
     ↓
CG experiment
     ↓
PASS
     ↓
merge/promote
```

Do not initially allow unconstrained live production memory mutation.

Scratch memory may remain ephemeral or run-scoped.

Durable memory is experimental state.

---

# 18. Studio contract

Every Studio implements something equivalent to:

```python
class StudioAdapter(Protocol):

    def manifest(self) -> StudioManifest:
        ...

    def get_task(
        self,
        split: Split,
        seed: int | None
    ) -> TaskInstance:
        ...

    async def prepare(
        self,
        task: TaskInstance,
        run: RunSpec
    ) -> PreparedEnvironment:
        ...

    async def evaluate(
        self,
        run: RunReceipt
    ) -> EvaluationResult:
        ...

    async def observe_external_outcome(
        self,
        submission_id: str
    ) -> ExternalOutcomeReceipt | None:
        ...

    def curriculum_features(
        self,
        run: RunReceipt
    ) -> dict:
        ...
```

Everything above this boundary is shared WorkerKit.

---

# 19. Metaculus Studio

Supplies:

```text
historical questions
resolution criteria
point-in-time evidence packets
known resolutions
proper scoring rule
live question adapter
```

Modes:

```text
REPLAY
SECRET HISTORICAL
LIVE
```

Primary metrics:

```text
Brier/log score
calibration
cost
search calls
confidence errors
update quality
```

---

# 20. Bittensor Studio

Do NOT make "Bittensor" itself the Studio.

Each subnet is a different environment.

Examples:

```text
studio/bittensor/118-ditto
studio/bittensor/62-ridges
```

The generic Bittensor package handles:

```text
wallet
registration
subnet economics
miner lifecycle
submission
emission observation
```

The Studio handles:

```text
task semantics
local benchmark
evaluator
curriculum
```

Thus Ditto and Ridges share both:

```text
WorkerKit
BittensorVenueAdapter
```

but have different StudioAdapters.

---

# 21. External outcomes are NOT evaluation truth

Example:

A brilliant security report can earn $0.

A mediocre hackathon entry can win money.

A Metaculus forecast can temporarily look bad before resolution.

Therefore store separately:

```text
EvaluationResult
ExternalOutcomeReceipt
SettlementReceipt
```

Never use:

```text
won == good
lost == bad
```

as the learning objective.

Money is one signal.

---

# 22. The Workbench becomes Private Lab

Fork/rename `qdw-workbench`.

Preserve:

```text
Tauri shell
qdw-node concept
workspace/git tooling
PTY/process system
ACP/agent panel
context compiler
node telemetry
handover mechanism
human approval architecture
cost dimensionality doctrine
```

Replace the QDW-specific bridge with:

```text
lab-api
```

---

# 23. New dashboard information architecture

Primary tabs:

```text
CONTROL
STUDIOS
WORKERS
EXPERIMENTS
RUNS
EVIDENCE
BUDGET
GRAPH
CODE
```

---

## CONTROL

The home screen answers:

```text
What is running?
What is learning?
What changed?
What needs approval?
How much are we spending?
Are workers improving?
```

Cards:

```text
active runs
active experiments
pending promotions
cash today
quota remaining
recent WorkerVersion promotions
failed experiments
Studio health
```

---

## STUDIOS

Cards:

```text
Metaculus
Ditto
Ridges
...
```

Each shows:

```text
status
task count
current Worker
baseline
champion
quality trend
cost trend
experiments
live mode status
```

---

## WORKERS

Display lineage:

```text
researcher-v1
      │
      ├── v2 rejected
      │
      └── v3 promoted
             │
             ├── v4 rejected
             └── v5 champion
```

Click version:

```text
exact dependencies
Git commits
MemFS revision
skills
models
budget policy
runs
experiments
why promoted
```

---

## EXPERIMENTS

Most important screen.

Display:

```text
hypothesis
control
candidate
Studio
suite
n
quality delta
confidence interval
cost delta
regressions
status
```

Statuses:

```text
DESIGNED
RUNNING
VALIDATING
SUPPORTED
REFUTED
DISPUTED
```

---

## RUNS

Immutable execution browser.

One row:

```text
run
studio
task
worker version
score
cost
duration
artifact
trajectory
outcome
```

Run detail should expose full provenance.

---

## EVIDENCE

Show:

```text
Observations
Studio Findings
Transfer Claims
Doctrine
```

Every statement clickable back to experiments/runs.

No floating unsourced "insights."

---

## BUDGET

Show:

```text
cash
quotas
subscription resources
compute
external capital
human time
```

Then:

```text
quality/cost frontier
routing decisions
free credit expiry
model/provider performance
budget experiments
```

---

## GRAPH

Hydra visualization.

Filters:

```text
studio
worker
task family
skill
memory
model
finding tier
time
```

Useful graph paths:

```text
skill → runs → score
memory revision → experiments → promotion
model → task family → quality/cost
finding → transferred studio
worker lineage
```

---

# 24. Global graph, local default retrieval

Hydra is global.

Context retrieval defaults to:

```text
current Worker
+
current Studio
+
validated global TransferClaims
```

It must NOT default to every Run in every Studio.

This gives:

```text
global intelligence
without
global contamination
```

---

# 25. Repo structure

Target:

```text
private-lab/
├── README.md
├── AGENTS.md
├── LAB-SPEC.md
├── METHODS.md
├── CHECKPOINTS.md
├── DATA-MODEL.md
├── BUDGETING.md
├── LEARNING.md
├── TESTING.md
│
├── lab/
│   ├── contracts/
│   ├── ledger/
│   ├── artifacts/
│   ├── projection/
│   ├── context/
│   ├── workers/
│   ├── experiments/
│   ├── learning/
│   ├── budget/
│   └── orchestration/
│
├── studios/
│   ├── metaculus/
│   └── bittensor/
│       ├── common/
│       ├── ditto/
│       └── ridges/
│
├── integrations/
│   ├── letta/
│   ├── hydra/
│   ├── cg/
│   └── cge/
│
├── apps/
│   └── desktop/
│
├── data/
│   ├── events/
│   ├── receipts/
│   ├── artifacts/
│   └── projections/
│
└── tests/
```

Do not copy CG into this repository.

CG/CGE remain independent engines used through stable adapters.

---

# 26. Checkpoints

These are the project roadmap.

External revenue is deliberately late.

## CP0 — Instrumented reality

Pass when ONE real Worker executes ONE real task and produces:

```text
valid RunSpec
event chain
trajectory
artifact
EvaluationResult
real CostEvents
RunReceipt
Git references
Hydra projection
```

No synthetic success values.

---

## CP1 — Rebuild proof

Delete:

```text
Hydra
dashboard DB/projection
indexes/caches
```

Replay canonical records.

Pass if the meaningful projection rebuilds identically.

This proves we actually know where truth lives.

---

## CP2 — Stable baseline

Choose one narrow Studio.

Run ≥30 sealed TaskInstances.

Establish:

```text
quality distribution
cost distribution
latency
failure taxonomy
variance
```

No learning yet.

We need to know what "v1" actually is.

---

## CP3 — Lab context works

Same WorkerVersion.

Paired tasks:

```text
A: no Lab context
B: validated ContextPack
```

Pass only if ContextPack creates measurable benefit or equivalent quality at meaningfully lower resource use.

This proves Hydra/context has value.

---

## CP4 — Worker learns

Generate one LearningProposal.

Create candidate WorkerVersion.

Paired SECRET evaluation:

```text
v1
vs
v2
```

Pass if:

```text
quality gates pass
no material hidden regression
declared primary objective improves
evidence survives statistical rule
```

THIS IS THE FIRST TRUE MOLTWORK RESULT.

---

## CP5 — Budget learner works

Compare:

```text
F
M
Q
```

Pass if Moltwork routing moves the quality/resource Pareto frontier.

Examples:

```text
same quality, 40% lower cash
higher quality, same cash
same quality, materially lower scarce quota use
```

---

## CP6 — CGE accelerates learning

Compare candidate generation:

```text
random mutation
vs
Hydra+CGE
```

Equal experiment budget.

Measure:

```text
cost per successful promotion
experiments per successful promotion
mean promoted delta
```

CGE must beat the baseline.

---

## CP7 — Cross-Studio transfer

Take one validated Studio Finding.

Apply it unchanged or minimally adapted to another Studio.

Run paired secret evaluation.

Pass if the second Studio improves.

Now the global Hydra graph has demonstrated value.

---

## CP8 — Autonomous research allocation

Give Lab several possible experiments and a finite budget.

Lab decides:

```text
what to investigate
which worker
which Studio
which mutation
how much budget
when to stop
```

Compare its allocation strategy against a simple baseline.

This tests whether the Lab learns how to learn.

---

## CP9 — Live economic transfer

Only now care seriously about:

```text
Bittensor alpha
Metaculus prizes
security payouts
client revenue
bounties
```

Pass condition is not "made money once."

Measure:

```text
predicted EV
actual result
quality transfer
cash spent
capital risk
model calibration
```

---

# 27. Primary dashboard KPI

Do NOT make:

```text
money earned
Bittensor rank
number of runs
```

the primary KPI.

The Lab's primary chart should be:

```text
QUALITY
   ↑
   │                       v12
   │                  v9
   │             v6
   │       v4
   │  v1
   └────────────────────────────→ RESOURCE COST
```

Then show movement through time.

The actual question is:

> Is our attainable quality/cost frontier improving?

---

# 28. Secondary learning metrics

Track:

```text
promotion rate
candidate → promotion conversion
regression rate
learning velocity
cost per successful promotion
runs per insight
insight → validated finding rate
finding → transfer rate
context uplift
memory uplift
budget-policy uplift
cross-Studio uplift
```

These are more important than vanity run counts.

---

# 29. Human approvals

Keep the qdw-workbench HumanQueue idea.

Require approval initially for:

```text
production WorkerVersion promotion
durable global Doctrine promotion
large cash spend
Bittensor registration
external submission
credential scope expansion
destructive Git operation
```

Later individual policies may become autonomous.

Approval itself becomes an event.

---

# 30. Non-negotiable invariants

1. Runs are evidence; summaries are not.
2. Projections are disposable.
3. Hydra is never canonical truth.
4. Letta memory is never canonical truth.
5. No production WorkerVersion silently mutates.
6. Every behavioral change creates a version.
7. Every promotion points to an ExperimentResult.
8. CGE never sees SECRET labels.
9. Secret evaluation never feeds direct curriculum.
10. External reward is distinct from evaluator quality.
11. Quota/subscription/local compute are not silently converted to fake USD.
12. Every model/tool/skill/memory dependency is attributable to a Run.
13. ContextPack contents are recorded.
14. Dropped context fragments are recorded.
15. Mock/synthetic/live Runs are explicitly distinguishable.
16. A green checker that cannot detect a deliberately broken candidate is itself broken.
17. Cross-Studio knowledge is not globally injected without transfer evidence.
18. Bittensor, Metaculus and future venues never define the Lab architecture.
19. Git answers what changed.
20. Receipts answer what happened.

---

# 31. Immediate implementation order

Do this before serious Bittensor optimization.

### Step 1

Fork/rename qdw-workbench to Private Lab Workbench.

Remove QDW product/factory semantics from the center.

Preserve node/git/context/PTY/ACP/handover/security architecture.

### Step 2

Create `LAB-SPEC.md`, `DATA-MODEL.md`, `LEARNING.md`, `CHECKPOINTS.md`.

Treat this document as initial source.

### Step 3

Move canonical Pydantic contracts into:

```text
lab/contracts/
```

Do not let each integration invent its own Run schema.

### Step 4

Wire current WorkerKit EventLedger into the control plane.

Events are canonical.

### Step 5

Make real Hydra a rebuildable projection.

SQLite may remain a local read model/cache, but call it a projection.

### Step 6

Implement immutable:

```text
Worker
WorkerVersion
RunSpec
RunReceipt
ExperimentSpec
ExperimentResult
LearningProposal
PromotionDecision
```

### Step 7

Wire real CostEvents from model/tool execution.

Remove fake zero costs wherever the resource was merely unpriced.

### Step 8

Wire Letta identity + fresh-session-per-Run + explicit memory revisions.

### Step 9

Wire CG as the sole promotion evaluator.

### Step 10

Wire CGE as candidate/curriculum generator.

### Step 11

Implement dashboard:

```text
Control
Studios
Workers
Experiments
Runs
Evidence
Budget
Graph
```

All dashboard state must come from Lab projections.

### Step 12

Create only TWO Studio adapters:

```text
Metaculus Replay
Ditto local benchmark
```

Do not register for anything yet.

### Step 13

Complete CP0 → CP4.

Only after CP4 decide which live environment deserves capital.

---

# 32. First canonical experiment

The first experiment should be intentionally boring.

One Worker.

One task family.

One evaluator.

One mutation.

For example:

```text
Worker:
forecaster-01

Studio:
Metaculus replay

Training:
50 historical questions

Hypothesis:
forcing explicit prior/base-rate extraction
reduces overconfidence.

Control:
forecaster-v1

Candidate:
forecaster-v2

Secret:
50 unseen historical questions

Metrics:
Brier
calibration
cash
tokens
searches
wall time
```

If v2 wins under the declared promotion rule:

```text
MOLTWORK HAS LEARNED SOMETHING.
```

Then repeat the exact architecture with Ditto.

The exciting result is not:

```text
"we entered Bittensor."
```

It is:

```text
"the same laboratory that improved forecasting
also improved a completely different persistent-agent benchmark."
```

That is the real Moltwork thesis.

The most important architectural decision there is the **one global Hydra graph but gated retrieval**. CG already demonstrates the right principle: graph information can bias candidate generation, but graph-informed candidates still have to survive the same hidden evaluation. That is exactly how cross-Studio intelligence should work.

I would also copy `qdw-workbench`'s anti-cheat testing philosophy nearly unchanged: real Git repos for Git tests, real spawned processes for node contracts, deliberately broken variants for trust-critical checks, immutable command/artifact evidence, and no UI-supplied `passed=true`.

The immediate priority is therefore **CP0 → CP4, not Ditto rank**. Once CP4 passes, Bittensor and Metaculus become incredibly useful because they give the same Lab two radically different external environments. Until CP4 passes, chasing their leaderboards mainly adds noise.
