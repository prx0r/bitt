# Full Context Review — 2026-09-02

Everything we built, what works, what's broken, how it connects.

---

## The Four Repos

```
/mw (Oracle)              /bitt (WorkerKit)           /cg (cogymkernel)          /root/mwgym (MWGym)
Finds work                Does the work               Deterministic evolution    Trains & learns
"I see $X available"      "Here's my submission"      "Replayable proof"         "That worked, here's why"
```

---

## 1. /mw — Oracle (Market Intelligence)

**Purpose:** DefiLlama/Dune for machine work. Best public dataset of autonomous economic activity.

**Status:** Built but empty data. API on port 8788 (not running).

| Component | Status | Notes |
|-----------|--------|-------|
| 35-table SQLite schema | Built | oracle.db is 0 bytes (needs init) |
| 27+ REST endpoints | Built | DeFiLlama-style v1 API |
| 19 work source feeds | Built | BountyBook, GitHub, SuperTeam, Metaculus, etc. |
| 12 service source feeds | Built | x402, Apify, Smithery, OpenRouter, etc. |
| Taxonomy (shared ontology) | Built | 150+ source:category -> canonical task families |
| MCP server (14 tools) | Built | mol_pulse, mol_work, mol_brief, etc. |
| Resolution ladder | Built | 9-tier human dependency resolution |
| Marketplace intelligence | Built | 335+ marketplaces, 18 skill families |

**Key files:**
- `store.py` — SQLite schema (35 tables), upsert, query
- `api.py` — FastAPI app (27+ endpoints)
- `feeds/work.py` — 19 work source normalizers
- `feeds/svc.py` — 12 service source normalizers
- `taxonomy.py` — Shared ontology mapping
- `mcp.py` — MCP server (14 tools)
- `config.py` — DB = DATA / "oracle.db"

**To activate:**
```python
from oracle.store import init
init()  # Creates 35 tables in oracle.db
```

---

## 2. /bitt — WorkerKit (Execution Engine)

**Purpose:** Execute work, produce receipts, learn from outcomes.

**Status:** ~70% built. Architecture solid. Data plumbing broken.

| Component | Status | Notes |
|-----------|--------|-------|
| Vault (AES-256-GCM) | ✅ Working | 11 keys encrypted in .vault/ |
| Contracts (30 frozen Pydantic) | ✅ Working | Integration boundary between all agents |
| Ledger (append-only SQLite) | ✅ Working | Chain-hashed, triggers reject UPDATE/DELETE |
| ArtifactStore (SHA-256 CAS) | ✅ Working | Content-addressed, dedup |
| ExperimentLifecycle | ✅ Working | propose -> seal -> evaluate -> reject |
| HydraProjector | ✅ Working | Ledger events -> HydraDB graph |
| CG World (bitsec.scabench) | ✅ Working | Deterministic reset, hidden ground truth |
| WorkerKit (PydanticBATS) | ✅ Working | Real LLM calls via CF Workers AI |
| Pool Knowledge | ✅ Working | Doctrine + skills in lab/pools/ |
| BATS routing | ✅ Working | Budget-aware token scheduler |
| Learning loop | ✅ Working | Runs cycles, REJECTS when CI crosses zero |
| Trading replay | ⚠️ Fixed | Rewritten for Binance data, -0.1% return |
| Market DB | ⚠️ Fixed | 504 candles from Binance (BTC/ETH/SOL) |
| TAOStats API | ❌ Broken | Key returns 403 (expired?) |
| Wallet (no TAO) | ❌ Blocked | Can't register on subnets |
| Replay (Bittensor) | ❌ Broken | Wrong table name (crypto_5m doesn't exist) |
| Schema corruption | ❌ Broken | market.py stores emission as price |
| Non-determinism | ❌ Broken | LLM output varies, temp/seed not set |

**Key files:**
- `workers/bitsec/miner_v5.py` — 4-arm security auditor
- `workers/bitsec/cg_bridge.py` — CG -> qdw-workbench bridge
- `workers/bitsec/learning_loop.py` — Full learning cycle
- `workers/bitsec/pool_knowledge.py` — Security doctrine + skills
- `trading/rebalancer.py` — HOLD_TAO vs ALLOCATE decisions
- `trading/market.py` — 5m candle storage
- `trading/factors.py` — 5 trading signals
- `trading/baselines.py` — 5 baseline strategies
- `trading/replay.py` — Historical simulation
- `lab-interfaces/studios/bitsec_adapter.py` — TaskInstance -> RunReceipt
- `lab-interfaces/scientist/genome.py` — Compositional mutation space
- `oracle/bittensor/__init__.py` — TAOStats API wrapper
- `oracle/opportunities.py` — 129 subnet ranking
- `oracle/sn88/__init__.py` — 5 portfolio strategies
- `vault/__init__.py` — AES-256-GCM credential store

**Architecture:**
```
CG Kernel -> BitSec World -> WorkerKit -> Ledger -> HydraDB -> CGE -> Learning
```

---

## 3. /cg — cogymkernel (Deterministic Evolution Lab)

**Purpose:** Deterministic agentic evolution laboratory. Same (worldpack, instance_id, seed, candidate) always produces same run_id.

**Status:** Working. 4 commits. 3 worlds registered.

| Component | Status | Notes |
|-----------|--------|-------|
| Core kernel (ids, contracts, runner) | ✅ Working | Content-addressed receipts (blake3) |
| 3 worlds registered | ✅ Working | toy, school, bitsec.scabench |
| 10 evolution recipes | ✅ Working | random_search, elitist_mutation, tournament, etc. |
| 33 reasoning styles | ✅ Working | cot, reflexion, self_refine, etc. |
| Quality gates | ✅ Working | Wilson score, bootstrap CI, lexicographic |
| Three-tier verification | ✅ Working | deterministic -> binary criteria -> reconcile |
| MCP server | ✅ Working | 14 tools for LLM integration |
| CLI | ✅ Working | status, worlds, run, evolve, claim-create |
| BitSec world | ✅ Working | ScaBench as deterministic security benchmark |

**Key files:**
- `cogym_kernel/kernel/ids.py` — blake3/sha256 content_id, strip_volatile, events_root merkle
- `cogym_kernel/kernel/contracts.py` — WorldSpec, ActionSpec, RunReceipt, MetricVector (frozen dataclasses)
- `cogym_kernel/kernel/runner.py` — AsyncRunner + ExecutorRegistry + run_suite_parallel
- `cogym_kernel/worlds/registry.py` — @register decorator, FACTORIES dict, create()
- `cogym_kernel/worlds/bitsec.py` — BitSecWorld (ScaBench security benchmark)
- `cogym_kernel/worlds/school/world.py` — SchoolWorld (allocation architecture evolution)
- `cogym_kernel/eval/gates.py` — QualityGate, wilson(), bootstrap_ci()
- `cogym_kernel/evo/recipes.py` — 10 evolution recipes
- `cogym_kernel/evo/loop.py` — EvolutionCampaign (async)
- `cogym_kernel/science/verify.py` — Three-tier verification

**BitSec world:**
- Loads from `/root/bitt/subnets/sn60-bitsec/tools/scabench/curated-*.json`
- Loads cloned repos from `/root/bitt/data/scabench-repos/<project_id>/`
- Two actions: FIND_VULNERABILITIES (LLM), SUBMIT_FINDINGS (deterministic)
- Scoring: title word overlap (50%), description overlap (30%), severity match (10%)
- 9 metrics: detection_rate, f1_score, precision, jaccard, tp, fp, fn, n_expected, n_found

**Bug:** `import os` at line 289 is too late — `os.walk()` used at line 111.

---

## 4. /root/mwgym — MWGym (Training Layer)

**Purpose:** Gymnasium for AI workers. Adversarial curriculum training.

**Status:** Working. 10 commits. Wired loop functional.

| Component | Status | Notes |
|-----------|--------|-------|
| PydanticBATSHarness | ✅ Working | One LLM call, structured output, hard budget |
| BATS routing | ✅ Working | Budget-Aware Token Scheduler |
| UsageLimits enforcement | ✅ Working | Pre-request gate pattern |
| 8 harness adapters | ✅ Working | Direct, Fast, Letta, RealLetta, Forecasting, Router |
| Adversary (MAP-Elites) | ✅ Working | Mutates world genomes on failure |
| Curriculum | ✅ Working | Persisted to HydraDB |
| 4 CGE world families | ✅ Working | software, research, forecasting, compute.routing |
| Wired loop | ✅ Working | `python3 mwgym/wired_loop.py --rounds 5` |

**Key files:**
- `mwgym/harnesses/pydantic_bats.py` — PydanticBATSHarness, BATSRouter, UsageLimits
- `mwgym/harnesses/base.py` — HarnessAdapter protocol, HarnessRun, HarnessInstance
- `mwgym/workspace.py` — LabWorkspace with Git worktrees
- `mwgym/wired_loop.py` — Main entry point
- `mwgym/hydra_unified.py` — UnifiedHydra (SQLite-backed graph DB adapter)

**BATS models:**
| Model | Provider | Cost/1k in | Quality |
|-------|----------|-----------|---------|
| mimo-v2.5 | opencode-go | $0.00014 | 0.7 |
| llama-3.3-70b-versatile | groq | $0.00059 | 0.85 |
| llama-3.1-8b-instant | groq | $0.00005 | 0.8 |
| Meta Llama 3.1 8B | openrouter | $0.0 | 0.65 |

---

## 5. /root/aisec — AISec (Security Observatory)

**Purpose:** Intelligence platform for autonomous AI agent security.

**Status:** Prototype. 2 commits. Schemas real, rest is mockup.

| Component | Status | Notes |
|-----------|--------|-------|
| Pydantic schemas (7 models) | ✅ Real | Frozen, versioned, SHA-256 content hashing |
| Ingestion pipeline | ⚠️ Shallow | 10 sources, 2 claims (regex only) |
| Website (4 HTML pages) | ⚠️ Mockup | Hardcoded, not from data |
| API (4 GET endpoints) | ⚠️ Minimal | Reads JSON files |
| LLM extraction | ❌ Missing | Needs LLM, not regex |
| CG integration | ❌ Missing | Spec only |
| Audit chatbot | ❌ Fake | Client-side JS keyword matching |

---

## 6. /root/lifeOS — LifeOS (Personal Productivity)

**Purpose:** Life operating system for one person (Tom).

**Status:** Working app. 18 commits. Zero dependencies.

| Component | Status | Notes |
|-----------|--------|-------|
| Life Clock countdown | ✅ Working | Hours/days to ages 40, 90, end of 20s |
| Do Now priorities | ✅ Working | 12 age-adaptive priorities |
| Weekly habits | ✅ Working | 8-track grid, localStorage |
| 90-Day Sprint | ✅ Working | 12-week plan, 3/12 complete |
| Path to 35 | ✅ Working | 5-stage roadmap |
| AI Chat | ✅ Working | OpenCode Go / mimo-v2.5 |
| Research Lab | ✅ Working | Frozen targets, nightly ritual, hypotheses |
| Thesis (Svatantrya Protocol) | ✅ Working | 1695-line philosophical synthesis |

---

## 7. HydraDB (Graph Database)

**Status:** Running. Docker container up 14 hours.

| Property | Value |
|----------|-------|
| Container | hydradb |
| Bolt | bolt://127.0.0.1:7687 |
| HTTPS | http://127.0.0.1:8443 |
| Admin | http://127.0.0.1:9090 |
| Auth | neo4j / private-lab-hydradb-token-2026-secure |

**Cypher constraints (CRITICAL):**
```python
# ✅ WORKS
CREATE (a:Worker {id: 1})-[:HAS_VERSION]->(b:WorkerVersion {id: 2})  # CREATE with edge
MATCH (n:Worker) RETURN n.id AS id                                      # property return
MATCH (n:Worker) RETURN count(*) AS count                               # count(*)
MATCH (n:Worker {id: $id}) DETACH DELETE n                              # delete

# ❌ BROKEN
CREATE (n:Worker {id: "x"})                    # standalone CREATE
MERGE (n:Worker {id: 1})                        # MERGE
MATCH (a) CREATE (a)-[:EDGE]->(b)               # MATCH+CREATE
MATCH (n) RETURN n                              # whole node return
MATCH (n) RETURN count(n)                       # count(n)
```

**Node id property MUST be integer** — use `hash_id()` for string IDs.

**Test results:**
- Health: ready
- Write: creates Worker + WorkerVersion via CREATE edge pattern
- Read: MATCH with label + count(*) works
- Cleanup: MATCH + DETACH DELETE works

---

## 8. Connections Between Repos

### Data Flow

```
/mw Oracle
  │ discovers opportunities (440+ opps, 576+ services)
  │ normalizes to shared ontology (taxonomy.py)
  │
  ▼
/bitt WorkerKit
  │ executes work via PydanticBATS
  │ produces RunReceipts (frozen contracts)
  │ records to Ledger (append-only, chain-hashed)
  │ projects to HydraDB via HydraProjector
  │
  ▼
/cg cogymkernel
  │ runs deterministic episodes
  │ produces content-addressed RunReceipts (blake3)
  │ evolves policies via 10 recipes
  │ enforces quality gates (Wilson, bootstrap CI)
  │
  ▼
/mwgym MWGym
  │ trains workers via adversarial curriculum
  │ feeds failure vectors to adversary
  │ persists to HydraDB
  │ routes via BATS (budget-aware)
  │
  ▼
HydraDB (shared graph)
  │ all repos project here
  │ append-only, rebuildable from receipts
  │ Bolt on :7687, HTTPS on :8443
```

### Shared Contracts

The contracts in `/root/bitt/private-lab/lab/contracts/__init__.py` are the integration boundary:
- `Worker`, `WorkerVersion` — identity + immutable lineage
- `TaskInstance` — task to execute (with Split for contamination control)
- `RunSpec`, `RunReceipt` — run specification and outcome
- `EvaluationSpec`, `EvaluationResult` — evaluation
- `ExperimentSpec`, `ExperimentResult` — controlled comparison
- `LearningProposal`, `ImprovementReceipt` — learning loop primitives
- `Finding`, `TransferClaim` — evidence with tier system

### Shared Ontology

`/root/mw/taxonomy.py` maps raw source categories to canonical task families.
`/root/bitt/workers/bitsec/pool_knowledge.py` loads doctrine + skills.
Both feed into the same capability pool system.

---

## 9. What's Actually Working End-to-End

| Pipeline | Status | Evidence |
|----------|--------|----------|
| CG World reset -> observe -> score | ✅ | BitSec world loads ScaBench, deterministic reset |
| WorkerKit LLM call -> structured output | ✅ | PydanticBATS with mimo-v2.5, UsageLimits enforced |
| Ledger append -> chain hash verification | ✅ | SQLite WAL, triggers reject UPDATE/DELETE |
| Learning loop: propose -> evaluate -> reject | ✅ | Runs cycles, REJECTS when CI crosses zero |
| HydraDB write -> read -> cleanup | ✅ | CREATE edge pattern works, MATCH works |
| Trading replay (Binance) | ✅ | 504 candles, momentum strategy, -0.1% return |

---

## 10. What's Broken or Missing

| Issue | Root Cause | Impact |
|-------|-----------|--------|
| TAOStats API 403 | Key expired or rate limited | Can't get Bittensor subnet data |
| No wallet TAO | Not funded | Can't register on subnets |
| Market DB schema corruption | emission stored as price | Trading signals wrong |
| Non-deterministic LLM | temp/seed not set | Experiments not reproducible |
| oracle.db empty | Not initialized | No opportunity data |
| Oracle API not running | Module import path wrong | Can't query opportunities |
| AISec is mockup | Only schemas real | No actual security intelligence |
| No Git lineage tracking | WorkerVersion not in Git | Can't reproduce builds |
| HydraDB Cypher limitations | Custom implementation | Only CREATE edge pattern works |

---

## 11. Environment & Secrets

**Vault location:** `/root/bitt/.vault/`
- `credentials.enc` — AES-256-GCM encrypted
- `.master_key` — base64 AES key

**Keys stored:**
- `opencode_go_api_key` — sk-fv9GA... (OpenCode Go)
- `groq_api_key` — gsk_vwd... (Groq)
- `taostats_api_key` — tao-126d... (TAOStats)
- `cf_api_token`, `cf_account_id`, `cf_r2_access_key`, `cf_r2_secret_key` — Cloudflare
- `gmail_client_id`, `gmail_client_secret`, `gmail_refresh_token` — Gmail OAuth

**Access pattern:**
```python
from vault import Vault
v = Vault()
key = v.get('opencode_go_api_key')
```

---

## 12. What the Next Agent Should Do

1. **Initialize oracle.db** — `from oracle.store import init; init()`
2. **Get TAOStats API access** — current key returns 403
3. **Fix market.py schema** — store alpha_price, not emission
4. **Wire Git lineage** — WorkerVersion → Git commit hash
5. **Run 10 paired evaluations** — statistical significance
6. **Fix non-determinism** — temperature=0, seed
7. **Clone Vida agent wallet** — reference/vida
8. **Run full replay** — get first real return numbers

---

## 13. Moltwork Architecture (Vision)

```
MW ORACLE
    │
    ├── "Where is money?"
    │
    ▼
┌───────────┬───────────┬───────────┐
│ Bittensor │ bounties  │   gigs    │
│    │      │           │           │
│    ▼      │           │           │
│ Environment Oracle     │           │
│ "What exactly?"        │           │
│    │                   │           │
│    ▼                   │           │
│ PRIVATE LAB            │           │
│ "Can we do it?"        │           │
│    │                   │           │
│    ▼                   │           │
│ WorkerKit              │           │
│ "Do the work"          │           │
│    │                   │           │
│    ▼                   │           │
│ Treasury               │           │
│ "Get paid"             │           │
│    │                   │           │
│    ▼                   │           │
│ Hydra                  │           │
│ "Learn"                │           │
└─────────────────────────────────────┘
```

**Bittensor is Moltwork's first fully machine-native economy.**

The Oracle is the moat — a continually growing private dataset of tasks → attempts → techniques → costs → failures → scores → rewards.

---

*Review completed 2026-09-02. All repos checked live. HydraDB tested with proper client.*
