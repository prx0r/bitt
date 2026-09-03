# Re: work for bitt agent

**Date:** Wed, 2 Sep 2026 06:16:10 +0700

---

Yes. This materially changes how I think we should build the Security Lab. 
We should **steal the mature scientific and operational primitives and make 
WorkerKit the layer that compares, composes and learns when to use them**. 
I’ve also emailed this research into the existing **“work for bitt agent”** 
thread.

The strongest current evidence for this approach is that the open-source 
AI-security ecosystem has matured extremely quickly. A July 2026 review by 
Semgrep already divides current systems into three fairly distinct classes: 
execution-verified exploit/fuzz harnesses, model “skill boosting” 
methodologies, and SAST+LLM hybrids. Most mature systems independently 
converged on separate discovery and verification agents, adversarial 
false-positive checking, structured findings, and increasingly 
execution-backed validation. ([Semgrep][1])

## What we should steal immediately

| Primitive                                | What we use it for             
            | Lab role           | Priority |
| ---------------------------------------- | 
------------------------------------------ | ------------------ | -------: |
| **BountyBench**                          | Real bug-bounty 
detect/exploit/patch tasks | WORLD + EVALUATOR  |   **P0** |
| **ScaBench**                             | Smart-contract audit tasks     
            | WORLD + EVALUATOR  |   **P0** |
| **Hound**                                | Graph-driven long-horizon 
auditing         | PROCESS            |   **P0** |
| **Cloudflare security-audit-skill**      | Parallel hunt + adversarial 
verify         | PROCESS            |   **P0** |
| **Trail of Bits skills**                 | Dozens of specialist audit 
primitives      | SKILL/TOOL         |   **P0** |
| **Semgrep / CodeQL / Slither / fuzzers** | Deterministic evidence 
generation          | TOOL               |   **P0** |
| **Google Mantis**                        | Find → reproduce → patch 
skills            | PROCESS            |   **P1** |
| **VulnHuntr**                            | Python remote attack-surface 
reasoning     | PROCESS            |   **P1** |
| **XBOW Validation Benchmarks**           | Web-app vulnerability 
evaluation           | WORLD              |   **P1** |
| **garak**                                | LLM red-team probes/detectors 
             | AI-REDTEAM WORLD   |   **P1** |
| **PyRIT**                                | Multi-turn adversarial 
campaigns           | AI-REDTEAM PROCESS |   **P1** |
| **AgentDojo / WASP**                     | Prompt injection against 
agents            | WORLD              |   **P1** |
| **Arcanum corpus/taxonomy**              | Retrieval, taxonomy, 
curriculum            | CORPUS             |   **P1** |
| **CyberGym / AutoPatchBench**            | Hard real-world native 
security            | WORLD              |       P2 |
| **CyBench / CyberSecEval 4**             | General security breadth       
            | WORLD              |       P2 |
| **PrimeVul / NIST SARD**                 | Cheap diagnostics/regressions 
             | TRAINING DATA      |       P2 |

### BountyBench is almost exactly CP2 already built

This is the biggest find.

The current open BountyBench environment contains **46 real bug bounties 
across 31 software systems**, split into 138 tasks covering three phases: 
vulnerability detection, exploitation and patching. Tasks run in isolated 
containers and are graded using concrete hidden verification scripts rather 
than an LLM saying “looks good.” ([GitHub][2])

That means instead of building:

> `BugBountyReplayWorld`

from scratch, wrap BountyBench.

```text
BitSec / ScaBench
        │
        │ learn
        ▼
security-01/vN
        │
        │ zero extra learning
        ▼
BountyBench DETECT
        │
        ▼
did performance transfer?
```

This is an exceptionally clean CP2.

[BountyBench repository](
https://github.com/EnvCommons/BountyBench?utm_source=chatgpt.com)

## Hound: stop partially rebuilding it

This one matters because `/bitt` has already copied some of its 
architecture.

Hound builds **agent-designed knowledge graphs**, supports different views 
such as system architecture, authorization, state mutation and 
inter-contract relationships, maintains persistent hypotheses with 
confidence, and divides exploration between broad “sweep” and targeted 
“intuition” phases. ([GitHub][3])

The published Hound work reports, on a small five-project ScaBench subset, 
recall increasing from 8.3% for its baseline to 31.2% with Hound and F1 
from 9.8% to 14.2%. That's a small benchmark, so I would not treat the 
exact numbers as gospel, but it is enough to justify testing the 
architecture directly. ([arXiv][4])

Your current miner v4 has essentially started recreating:

```text
Scout
Strategist
GraphStore-ish reasoning
Hypotheses
```

Don't continue.

Create:

```text
ProcessVersion:
    hound@<commit>
```

and make CG test:

```text
current-moltwork
vs
hound
vs
hybrid
```

[Hound](https://github.com/scabench-org/hound?utm_source=chatgpt.com)

And importantly, Hound is already sitting in `/bitt/reference`.

## Cloudflare's audit methodology should probably become a baseline

Cloudflare has released a remarkably relevant coding-agent security skill. 
It explicitly implements:

```text
recon
→ parallel hunting
→ independent adversarial validation
→ reporting
→ structured findings.json
→ fresh independent verification
```

The finder does **not** validate its own finding. Multiple runs are 
intentionally additive because different runs discover different regions of 
the attack surface. ([GitHub][5])

This is almost exactly our CG philosophy applied inside one audit.

I would therefore test:

```text
security-01/v0-current
security-01/v0+cloudflare-audit-process
```

before inventing more prompt architecture.

[Cloudflare security-audit-skill](
https://github.com/cloudflare/security-audit-skill?utm_source=chatgpt.com)

## Trail of Bits gives us a Security Skill Store

This is probably the richest library to absorb.

Their current agent skills include dedicated modules for smart-contract 
auditing, entry-point analysis, codebase context building, false-positive 
checking, differential security review, C/C++ review, Rust review, 
CodeQL/Semgrep static analysis, supply-chain analysis, property-based 
testing, variant analysis, protocol/spec compliance and more. Their 
property-testing skill explicitly covers Solidity tooling such as Echidna 
and Medusa. ([GitHub][6])

That means CGE's mutation space stops looking like:

```text
"rewrite prompt slightly"
```

and starts looking like:

```text
ProcessCandidate #183

audit_context_building = true
entry_point_analyzer   = true
hound_graph            = authorization+value_flow
slither                 = true
semgrep                 = false
property_testing        = echidna
fp_check                = true

scout_model             = cheap
strategist_model        = strong
verifier_model          = independent
```

**That is a much more meaningful genome.**

[Trail of Bits security skills](
https://github.com/trailofbits/skills?utm_source=chatgpt.com)

## There is now a whole second lane for AI red teaming

For the `ai-redteam` school, garak should be foundational.

Garak already has exactly the abstractions we'd otherwise invent: 
**generators, probes, detectors, harnesses and evaluators**. It supports 
REST targets and LiteLLM and writes structured JSONL attempt reports/hit 
logs. Its probe catalog spans prompt injection, encoded attacks, 
jailbreaks, leakage, malicious package hallucination and numerous other 
failure classes. ([GitHub][7])

Map it like this:

| garak        | Moltwork                    |
| ------------ | --------------------------- |
| generator    | target/model adapter        |
| probe        | attack/curriculum generator |
| detector     | evaluator                   |
| harness      | world runner                |
| report JSONL | Run artifact                |
| hit          | finding                     |

Don't port its probes.

Wrap:

```text
garak run
→ normalize result
→ EvaluationResult
```

[NVIDIA garak](https://github.com/NVIDIA/garak?utm_source=chatgpt.com)

Microsoft's **PyRIT** complements rather than duplicates this. PyRIT gives 
us composable datasets, attack techniques, targets, scorers and scenario 
runners, including multi-turn attacks such as Crescendo and TAP. Its newer 
benchmark mode can keep the target and dataset fixed while varying the 
adversarial helper model, which is almost a ready-made Moltwork 
**budget/model-routing experiment**. ([Microsoft GitHub][8])

[Microsoft PyRIT](https://github.com/microsoft/PyRIT?utm_source=chatgpt.com)

Then add **AgentDojo** for tool-using agent prompt-injection attacks and 
defenses, and Meta's **WASP** for executable prompt injection against web 
agents. ([GitHub][9])

That gives:

```text
AI REDTEAM SCHOOL

Arcanum taxonomy
       │
       ▼
garak ─────── PyRIT
  │             │
  └─────┬───────┘
        ▼
    AgentDojo
        +
       WASP
        │
        ▼
 sealed AI-redteam score
        │
        ▼
    RedTeam SN61
```

Now SN61 isn't our training environment. It becomes another **live external 
transfer venue**.

## Jason Haddix / Arcanum is useful, but use each repo differently

I researched the current Arcanum material rather than treating it as one 
thing.

The **Prompt Injection Taxonomy** is extremely useful. Current v1.6.1 has 
**172 entries**: 27 intents, 70 techniques, 63 evasions and 12 input 
vectors. More importantly, entries carry aliases linking Arcanum's 
classification to OWASP, MITRE ATLAS, NIST, garak and others. The canonical 
data exists as JSON. ([GitHub][10])

That should become the classification language of the AI-redteam capability 
graph.

```text
Finding
  PIT-T-xx
  OWASP-LLM-...
  MITRE-ATLAS-...
```

not some Moltwork-invented taxonomy.

`sec-context` is also excellent, but it's a **retrieval corpus**, not a 
prompt. It distills 150+ sources into broad and deep references covering 
AI-generated-code anti-patterns. The documents are around 65K and 100K 
tokens respectively, so ingest them into the Context Compiler and retrieve 
only relevant sections. ([GitHub][11])

`redbluepurpleAI`, which you already cloned, is primarily a prompt/workflow 
library. Its public structure contains red, blue, purple and silver helper 
roles; the red material includes recon-oriented prompts and specialist 
security-tool helpers.

So:

```text
arc_pi_taxonomy   → taxonomy
sec-context       → retrieval corpus
redbluepurpleAI   → candidate skills/curriculum seeds
ai-sec-resources  → discovery catalog
P4RS3LT0NGV3      → adversarial mutation transforms
```

P4RS3LT0NGV3 has a large library of text encodings, Unicode transformations 
and steganographic transformations. That is useful as an automated **attack 
mutation primitive** for our isolated AI-redteam environments, rather than 
durable worker knowledge. ([GitHub][12])

Your `/bitt/reference` already contains `ai-sec-resources`, 
`arc_pi_taxonomy`, `redbluepurpleAI`, Hound and `awesome-red-teaming`, so 
there is no reason to keep randomly cloning repos.

## More benchmarks worth stealing

**XBOW Validation Benchmarks** are particularly interesting for CP2. XBOW 
released 104 web vulnerability benchmarks designed to resemble the classes 
encountered in pentesting and bug bounty work; they were held private 
before release specifically to preserve novelty. Now that they're public 
they are no longer SECRET-quality, but they're excellent DEV transfer 
tasks. ([GitHub][13])

[XBOW Validation Benchmarks](
https://github.com/xbow-engineering/validation-benchmarks?utm_source=chatgpt.com
)

**CyBench** gives 40 professional CTF tasks from four competitions, with 
intermediate subtasks for more granular measurement. Good for broad 
capability profiling, less directly economically relevant than BountyBench. 
([GitHub][14])

**CyberGym** is much more serious real-world vulnerability work, but heavy. 
The current dataset is around 240GB, while its complete execution backing 
can be around 10TB; fortunately it publishes a 10-task subset. That's a 
later VPS/storage-heavy frontier rather than CP1. ([GitHub][15])

**AutoPatchBench** is similarly valuable for defensive transfer: real 
fuzzing-discovered C/C++ vulnerabilities with verified fixes. Meta says it 
was introduced with 136 vulnerabilities; the current repository exposes 142 
benchmark cases, with even its small 20-case sample recommending about 
500GB storage. ([Engineering at Meta][16])

**PrimeVul** gives approximately 7,000 vulnerable and 229,000 benign 
functions over 140+ CWEs with de-duplication and chronological splitting. 
Excellent cheap diagnostics, but function classification is too artificial 
to prove our security agent can actually audit systems. ([GitHub][17])

Likewise NIST SARD/Juliet provides tens of thousands of synthetic 
known-flaw cases—for example Juliet C/C++ 1.3 has around 64K cases—but that 
is regression-test material, not the thing we brag about as “learning 
security.” ([NIST][18])

## The crucial implementation change

Create a first-class concept that **doesn't currently exist strongly 
enough**:

```python
SecurityPrimitiveManifest

id
kind:
  WORLD
  EVALUATOR
  TOOL
  PROCESS_SKILL
  CORPUS
  ATTACK_GENERATOR

upstream_repo
upstream_commit
license

school:
  code_audit
  ai_redteam
  adversarial_systems

capability_tags
supported_languages
input_schema
output_schema

sandbox_profile
network_policy

contamination_tier:
  PUBLIC_TRAIN
  PUBLIC_DEV
  SEALED_LOCAL
  LIVE

cost_dimensions
adapter
```

Then:

```text
WorkerVersion
   USED_PROCESS → hound@abc123
   USED_SKILL   → tob/fp-check@456
   USED_TOOL    → slither@...
   USED_CORPUS  → sec-context@...
```

Every receipt records those exact versions.

Now Hydra can eventually answer genuinely useful questions like:

> On smart-contract access-control tasks, Hound + entry-point-analyzer + 
independent fp-check improved sealed recall by 13%, but property fuzzing 
added cost without benefit.

That is learning.

## Don't combine everything immediately

There is a danger that we “cheat” so enthusiastically that we make an 
enormous security harness and can't tell what helped.

The first BitSec experiment should instead have explicit process arms:

| Worker candidate | Process                            |
| ---------------- | ---------------------------------- |
| A                | current Moltwork Scout/Strategist  |
| B                | Hound unchanged                    |
| C                | Cloudflare security-audit skill    |
| D                | Trail of Bits smart-contract stack |
| E                | CGE-generated hybrid               |

Run A–D under equal budgets on DEV.

CGE reads the failures.

Then it proposes E.

CG tests A vs E on sealed tasks.

That's a proper experiment.

And there are several more serious candidate pipelines available after 
that. Google Mantis provides a portable staged security-review toolkit 
designed to find, reproduce and patch vulnerabilities. Visa's VVAH 
implements an 11-stage threat-model → deep-analysis → adversarial 
verification → chaining → remediation architecture. Semgrep's Defending 
Code Harness gives execution-backed C/C++ findings where crashes have to 
reproduce and patches must survive re-testing. ([GitHub][19])

## The SECRET-set problem becomes critical

There's one thing all this reuse makes harder: benchmark contamination.

ScaBench, XBOW, BountyBench, PrimeVul, CyBench, etc. are public.

Therefore:

```text
public dataset ≠ final promotion evidence
```

I would automate a **rolling private Security Holdout** from the Oracle.

When a fresh vulnerability/advisory/audit becomes public:

```text
Oracle sees new disclosure
        ↓
freeze vulnerable commit
        ↓
capture tests/environment
        ↓
store fix/report separately
        ↓
create TaskInstance
        ↓
NO WEB
NO FIX
NO WRITEUP
        ↓
SEALED_LOCAL
```

After evaluation, the label can be revealed.

The GitHub security-advisory feed you've already wired into the Security 
Oracle makes this particularly natural. Your latest Oracle commit already 
added security ingestion and classified BitSec, Immunefi, Cantina, 
Sherlock, Huntr, HackerOne, HackenProof, Intigriti, Google OSS VRP and 
RedTeam SN61 into the same security frontier.

That renewable private set is eventually more valuable than any static 
public benchmark.

## So CP1 changes slightly

The goal isn't:

> make our BitSec prompt better.

It becomes:

> **discover which existing security methods, tools, memories, models and 
workflows actually produce a better `security-01` under controlled 
evaluation.**

Then CP2 becomes even stronger:

```text
CP1
ScaBench / BitSec
→ learn best security process

CP2-A
BountyBench
→ does process transfer to real bug bounty code?

CP2-B
XBOW benchmark
→ does it transfer to web security?

CP2-C
garak/PyRIT/AgentDojo
→ which abstract adversarial skills transfer to AI red teaming?

CP2-D
live Immunefi / Cantina / Sherlock / SN61
→ does measured competence earn externally?
```

And this reveals what the **Security Capability Pool** actually is. It 
isn't a database of security tips. It's an evidence-backed graph saying 
which processes and knowledge transfer between different security worlds.

That's a far more ambitious—and much more defensible—version of the Lab.

[1]: 
https://semgrep.dev/blog/2026/comparing-open-source-ai-code-security-harnesses/ 
"Comparing Open-Source AI Code Security Harnesses | Semgrep"
[2]: https://github.com/EnvCommons/BountyBench?utm_source=chatgpt.com 
"GitHub - EnvCommons/BountyBench · GitHub"
[3]: https://github.com/scabench-org/hound?utm_source=chatgpt.com "GitHub - 
scabench-org/hound: Language-agnostic AI auditor that autonomously builds 
and refines adaptive knowledge graphs for deep, iterative code reasoning. · 
GitHub"
[4]: https://arxiv.org/abs/2510.09633?utm_source=chatgpt.com "Hound: 
Relation-First Knowledge Graphs for Complex-System Reasoning in Security 
Audits"
[5]: https://github.com/cloudflare/security-audit-skill "GitHub - 
cloudflare/security-audit-skill: A coding-agent skill for multi-phase 
security audits with independently verified, machine-readable findings · 
GitHub"
[6]: https://github.com/trailofbits/skills "GitHub - trailofbits/skills: 
Trail of Bits Claude Code skills for security research, vulnerability 
detection, and audit workflows · GitHub"
[7]: https://github.com/NVIDIA/garak/?utm_source=chatgpt.com "GitHub - 
NVIDIA/garak: the LLM vulnerability scanner · GitHub"
[8]: https://microsoft.github.io/PyRIT/latest/code/framework/ "Framework - 
PyRIT Documentation"
[9]: https://github.com/sequrity-ai/agentdojo?utm_source=chatgpt.com 
"GitHub - sequrity-ai/agentdojo: A Dynamic Environment to Evaluate Attacks 
and Defenses for LLM Agents. · GitHub"
[10]: https://github.com/Arcanum-Sec/arc_pi_taxonomy/?utm_source=chatgpt.com 
"GitHub - Arcanum-Sec/arc_pi_taxonomy: The Arcanum Prompt Injection 
Taxonomy · GitHub"
[11]: https://github.com/Arcanum-Sec/sec-context?utm_source=chatgpt.com 
"GitHub - Arcanum-Sec/sec-context: AI Code Security Anti-Patterns distilled 
from 150+ sources to help LLMs generate safer code. · GitHub"
[12]: https://github.com/Arcanum-Sec/P4RS3LT0NGV3?utm_source=chatgpt.com 
"GitHub - Arcanum-Sec/P4RS3LT0NGV3: Parseltongue 3.1 - LLM Payload Crafter 
for AI safety research · GitHub"
[13]: 
https://github.com/xbow-engineering/validation-benchmarks?utm_source=chatgpt.com 
"GitHub - xbow-engineering/validation-benchmarks: XBOW Validation 
Benchmarks · GitHub"
[14]: https://github.com/andyzorigin/cybench?utm_source=chatgpt.com "GitHub 
- andyzorigin/cybench · GitHub"
[15]: https://github.com/sunblaze-ucb/cybergym?utm_source=chatgpt.com 
"GitHub - sunblaze-ucb/cybergym: CyberGym is a large-scale, high-quality 
cybersecurity evaluation framework designed to rigorously assess the 
capabilities of AI agents on real-world vulnerability analysis tasks. · 
GitHub"
[16]: 
https://engineering.fb.com/2025/04/29/ai-research/autopatchbench-benchmark-ai-powered-security-fixes/?utm_source=chatgpt.com 
"Introducing AutoPatchBench: A Benchmark for AI-Powered Security Fixes - 
Engineering at Meta"
[17]: https://github.com/DLVulDet/PrimeVul?utm_source=chatgpt.com "GitHub - 
DLVulDet/PrimeVul: Repository for PrimeVul Vulnerability Detection Dataset 
· GitHub"
[18]: https://samate.nist.gov/SARD/test-suites?utm_source=chatgpt.com "Test 
suites - NIST Software Assurance Reference Dataset"
[19]: https://github.com/google/mantis?utm_source=chatgpt.com "GitHub - 
google/mantis: A modular, stack-agnostic toolkit of security review skills 
for AI coding agents to autonomously find, reproduce, and patch 
vulnerabilities. · GitHub"


On Wed, 2 Sept 2026 at 05:34, Prior Trades <tradesprior@gmail.com> wrote:

> Work for bitt agent 
>
> This email contains the architecture review from the previous response 
> plus the Checkpoint 2 plan.
> CHECKPOINT 1 — BITSEC AS THE FIRST WORLD 
>
> The original *WorkerKit → CGE → CG* plan still makes sense. BitSec does 
> not replace CG/CGE because it has a benchmark; it gives the Security Studio 
> an unusually good *world + native evaluator + live economic venue*.
>
> The clean architecture is:
>
>    - *BitSec / SCA-Bench* — environment and domain-specific scoring. 
>    - *WorkerKit* — executes reproducible episodes and records exactly 
>    what happened. 
>    - *CGE* — learner/scientist that generates curriculum and candidate 
>    changes. 
>    - *CG* — independent referee deciding whether candidate > control. 
>    - *Letta* — persistent worker cognition/memory. 
>    - *Hydra* — derived experience/evidence graph. 
>    - */bitt* — Bittensor intelligence, miner packaging, registration, 
>    submission and emissions. 
>    - *Private Lab / qdw-workbench* — control plane, allocator, 
>    experiments, workers, approvals and budgets. 
>    - *Live Bittensor result* — external outcome / transfer test, not 
>    learning ground truth. 
>
> The universal loop should be:
> TaskInstance ↓ RunSpec ↓ WorkerVersion + BudgetEnvelope + ContextPack ↓ 
> fresh execution episode ↓ artifact/findings ↓ domain evaluator ↓ 
> EvaluationResult ↓ RunReceipt ↓ Hydra projection ↓ failure analysis ↓ 
> LearningProposal ↓ CGE candidate generation ↓ candidate WorkerVersion ↓ CG 
> sealed paired evaluation ├─ FAIL → reject └─ PASS → promote WorkerVersion 
> n+1 What BitSec changes 
>
> BitSec makes Checkpoint 1 easier because we do not need to invent an 
> evaluator. It provides the first security world.
> PRIVATE LAB │ WorkerKit │ security-01 / WorkerVersion v0 │ BitSec 
> StudioAdapter │ TRAIN / DEV / SEALED │ worker executes │ findings.json │ 
> BitSec evaluator │ EvaluationResult │ RunReceipt │ Hydra │ failure clusters 
> │ CGE proposes v1 │ CG compares v0 vs v1 on sealed tasks │ REJECT or 
> PROMOTE │ official BitSec local/Docker evaluation │ Bittensor submission │ 
> rank / score / TAO │ ExternalOutcomeReceipt 
>
> The important granularity is:
> Program → Campaign → Run 
>    
>    - /bitt owns the BitSec program. 
>    - Private Lab coordinates the campaign and worker lineage. 
>    - WorkerKit/MWGym owns individual runs. 
>
> Current /bitt validity problems to fix 
>
> Several current cge/bitsec scripts are useful experiments but should not 
> count as learning evidence.
>
>    1. evolution.py and experiment.py contain simulated analysis paths 
>    that sample from known ground truth. Keep these only as unit simulations. 
>    2. real_eval.py currently supplies expected vulnerability information 
>    to the model. That is label leakage. It is fine for TRAIN teacher 
>    diagnostics, never CG/SECRET evidence. 
>    3. world.py silently falls back to synthetic data when SCA-Bench is 
>    unavailable. Production must fail closed with something like 
>    DATASET_UNAVAILABLE. 
>    4. Homemade approximate scoring should not become authority. Wrap and 
>    pin the official BitSec evaluation path where possible. 
>    5. No mock or heuristic evaluator should be capable of generating a 
>    production CapabilityClaim, promotion or dashboard claim. 
>
> /mw is closer to the correct core 
>
> The earlier WorkerKit plan already had the right success criterion:
>
> real worker → real tasks → real artifacts → real evaluation → real 
> experience → real memory/skill patch → real held-out replay → measurable 
> improvement
>
> Make that literally *Checkpoint 1*.
>
> The ETHOnline cg/evolve.py improvement is important because it introduced 
> an Evaluator protocol and LiveEvaluator, but production should fail if no 
> real domain evaluator is supplied. Do not silently fall back to 
> deterministic hash scoring or response-length heuristics.
> Exact Checkpoint 1 implementation 
>    
>    1. Create one persistent worker: security-01. 
>    2. Freeze immutable security-01/v0 with exact model policy, 
>    prompts/processes, tools, memory revision, context policy, source commits 
>    and evaluator version. 
>    3. Implement a thin BitsecStudioAdapter. 
>    4. Build explicit TRAIN / DEV / VALIDATION / SECRET splits. 
>    5. Run v0 through real WorkerKit runs, not standalone experiment 
>    scripts. 
>    6. Store every run as RunSpec → ContextPack → execution → Artifact → 
>    EvaluationResult → RunReceipt. 
>    7. Let Hydra/CGE consume TRAIN/DEV failures only. 
>    8. CGE proposes one falsifiable mutation at a time. 
>    9. Materialize that as security-01/v1; do not mutate v0 in place. 
>    10. CG performs paired v0 vs v1 evaluation on the same sealed tasks 
>    and budgets. 
>    11. Reject failed changes and preserve the evidence. 
>    12. Promote only successful changes. 
>    13. Then use the official BitSec local/Docker path and optionally 
>    submit through /bitt. 
>    14. Store Bittensor score/rank/TAO as external outcomes, never as 
>    retrospective evaluator truth. 
>
> The first security worker should therefore be *security-01*, not “the 
> BitSec agent.” BitSec is only the first world.
> CHECKPOINT 2 — PROVE SECURITY TRANSFER 
>
> Yes: this is where the project gets substantially more interesting.
>
> *Checkpoint 2 should be: demonstrate that capabilities learned in BitSec 
> transfer to independent security worlds and eventually to live security 
> markets.*
>
> Do not define it as simply “we submitted to a bounty.” A submission alone 
> proves almost nothing. Define it as:
>
> A WorkerVersion promoted using BitSec evidence measurably improves 
> performance on a security task distribution that CGE never trained against, 
> and at least one successful transfer candidate can be packaged and 
> submitted to a real external security venue.
>
> Operationally the Private Lab can now be *security-first*. 
> Architecturally I would still retain one general Private Lab with *Security 
> as its first major capability pool / frontier*, so we do not hard-wire 
> the whole Lab to one industry.
>
> The current Oracle work already points in this direction. The security 
> commit added a Security/Audit family with markets including BitSec, 
> Immunefi, Cantina, Sherlock, Huntr, HackerOne, HackenProof, Intigriti, 
> Google OSS VRP and RedTeam SN61, and organized them into three schools: *code-audit, 
> AI-redteam, adversarial-systems*.
>
> That is a much better way to structure Checkpoint 2 than putting every 
> security task in one bucket.
> The transfer ladder 
>
> Use increasingly distant worlds:
> SOURCE WORLD BitSec / SCA-Bench │ ▼ NEAR TRANSFER historical bug-bounty / 
> audit replay Sherlock / Cantina / Immunefi-style disclosed cases │ ▼ LIVE 
> NEAR TRANSFER real authorized audit / bug-bounty opportunity │ ▼ FAR 
> TRANSFER RedTeam SN61 challenge │ ▼ LIVE FAR TRANSFER SN61 miner submission 
> / other AI red-team market 
>
> This tells us *what* transferred.
>
> If BitSec → Sherlock improves, that may mean smart-contract audit ability 
> transferred.
>
> If BitSec → RedTeam SN61 improves, that is more interesting because SN61 
> is not simply vulnerability-report generation. It currently includes 
> challenges such as automation-framework detection, human-like browser 
> behaviour, anti-detect browser detection, Bot Virus and FlowRadar. Those 
> require adversarial experimentation, false-positive control, environment 
> reproduction and iterative challenge solving rather than Solidity expertise.
>
> That is exactly the sort of *far-transfer test* the capability-pool idea 
> needs.
> Checkpoint 2A — build SecurityPool properly 
>
> Do not store:
> security = 0.82 
>
> That is too vague.
>
> Store empirical capability dimensions such as:
> security/ repo-navigation threat-modeling hypothesis-generation 
> source-code-audit cross-file-reasoning access-control token-flow-analysis 
> oracle-analysis business-logic exploit-reproduction static-analysis fuzzing 
> false-positive-control finding-deduplication severity-estimation 
> report-writing patch-generation regression-testing 
> browser-adversarial-testing bot-detection 
>
> Every capability assertion should be evidence-backed:
> CapabilityEvidence: capability: access-control worker_version: 
> security-01/v7 source_studio: bitsec task_family: smart-contract-audit 
> evaluator_version: ... split: SECRET score: ... n: ... source_run_receipts: 
> [...] evidence_strength: VALIDATED observed_at: ... 
>
> Hydra can then answer something useful:
> security-01/v7 strong: access-control, cross-file reasoning medium: 
> token-flow analysis weak: oracle manipulation unknown: browser bot 
> detection 
>
> This is far better than treating “won BitSec” as a general security 
> capability.
> Checkpoint 2B — independent bug-bounty replay world 
>
> Build a second Studio which is independent from BitSec.
>
> Call it something like:
> studio/security/bugbounty-replay 
>
> Populate it from *resolved/disclosed historical cases only*:
>
>    - vulnerable repository/commit; 
>    - task briefing as it existed before disclosure where reconstructable; 
>    - hidden disclosed finding/report; 
>    - reproducible exploit/test where available; 
>    - patch/regression evidence where available. 
>
> Do not expose the disclosed report to the worker.
>
> Then compare:
> CONTROL A: security worker without validated BitSec transfer context 
> CANDIDATE B: same immutable worker + validated SecurityPool 
> findings/context 
>
> Or, for worker learning:
> security-01/v0 vs security-01/vN promoted in BitSec 
>
> Same tasks. Same budgets. Same model allowances.
>
> The important metric is not “did it say vulnerability.” Use 
> multi-dimensional evaluation:
>
>    - correct vulnerability; 
>    - affected code/location; 
>    - exploitability reasoning; 
>    - false positives; 
>    - severity correctness; 
>    - PoC/reproduction success when applicable; 
>    - patch correctness when requested; 
>    - regression safety; 
>    - cost / model calls / latency. 
>
> This gives us *near-transfer evidence*.
> Checkpoint 2C — test the Capability Pool itself 
>
> This should be an explicit experiment, not just retrieval infrastructure.
>
> Example hypothesis:
>
> A validated BitSec finding that cross-file call-graph investigation 
> improves vulnerability discovery will improve independent bounty replay 
> performance when injected through the SecurityPool Context Compiler.
>
> Test:
> same WorkerVersion same task same budget same model A = no transferred 
> finding B = transferred validated finding 
>
> If B wins on held-out bounty cases:
> Finding ──VALID_IN──> BitSec ──TRANSFERRED_TO──> BugBountyReplay 
>
> Now the finding can move from STUDIO_FINDING to TRANSFER_CLAIM.
>
> If it does not transfer, leave it BitSec-specific.
>
> That is exactly why the evidence tiers in the Private Lab spec matter.
> Checkpoint 2D — RedTeam SN61 as the far-transfer world 
>
> This is an excellent second Bittensor target, but not because it is 
> another subnet. It is useful because it creates a *distribution shift 
> inside security*.
>
> Current RedTeam SN61 miner workflow is highly automatable:
> choose challenge → clone challenge repository → develop solution → local 
> validation/scoring → Docker build → publish image → commit active solution 
> → validator scoring → monitor score/reward 
>
> The current challenge suite includes things such as:
>
>    - AB Sniffer — detect browser automation frameworks while avoiding 
>    human false positives; 
>    - Bot Virus; 
>    - FlowRadar v2; 
>    - Humanize Behaviour — mimic human web interaction; 
>    - Anti-Detect Browser Detection; 
>    - Device Fingerprinter is currently inactive. 
>
> This is therefore a different security school from BitSec.
>
> BitSec mostly trains:
> code comprehension vulnerability hypothesis cross-file reasoning finding 
> validation false-positive suppression security reporting 
>
> RedTeam can test whether the more general processes transfer:
> scientific experimentation adversarial hypothesis generation 
> instrumentation reproduction measurement false-positive minimization 
> iterative improvement Dockerized challenge execution sealed evaluator 
> discipline 
>
> Do *not* expect Solidity-specific memory to help RedTeam. That should 
> stay behind a task-family filter.
>
> The experiment should be something like:
> RedTeam baseline worker vs same worker + globally validated security 
> process findings 
>
> not:
> inject every BitSec lesson into RedTeam 
>
> The Context Compiler is what prevents capability-pool contamination.
> Checkpoint 2E — live bug bounty / audit submissions 
>
> Once near-transfer replay passes, allow the allocator to consider real 
> opportunities from the Oracle.
>
> The Oracle already has the right conceptual structure:
> MarketOracle → Immunefi → Cantina → Sherlock → Huntr → HackerOne → 
> HackenProof → Intigriti → Google OSS VRP → other security programs 
> BittensorIntelligence → BitSec SN60 → RedTeam SN61 
>
> Both feed the same SecurityPool evidence, but venue-specific logic stays 
> inside its module.
>
> A real opportunity gets represented as capability demand:
> opportunity: venue: example requires: source-code-audit: .95 solidity: .90 
> access-control: .80 exploit-reproduction: .70 report-writing: .60 
>
> The Pool Matcher compares this against the empirical worker state.
>
> Then the allocator decides:
> TRAIN MORE SHADOW ATTEMPT SUBMIT HOLD SKIP 
>
> This is where the Oracle becomes useful to the Lab instead of simply being 
> a list of bounties.
> I would make Checkpoint 2 pass criteria very explicit CP2.1 — near 
> transfer 
>
> At least one BitSec-promoted worker/process beats its declared control on 
> a held-out independent bug-bounty/audit replay suite.
> CP2.2 — capability-pool causal test 
>
> At least one STUDIO_FINDING from BitSec is tested with/without retrieval 
> on another Studio and becomes either:
> TRANSFER_CLAIM 
>
> or honestly:
> TRANSFER_REJECTED CP2.3 — far transfer 
>
> The same Lab machinery trains/evaluates a RedTeam SN61 candidate without 
> adding a special second learning system.
> CP2.4 — real venue adapter 
>
> WorkerKit can package and submit to at least one authorized live security 
> venue through a venue adapter and record ExternalSubmissionReceipt + 
> eventual ExternalOutcomeReceipt.
> CP2.5 — no contamination 
>
> BitSec-only observations cannot automatically enter RedTeam/bug-bounty 
> context. Only validated transfer claims or generic Lab doctrine can cross 
> Studio boundaries.
> CP2.6 — economic evidence 
>
> The Lab starts recording whether the transfer is economically useful:
> quality accepted finding rate cash/TAO reward cost per attempt human 
> seconds submission rate expected value 
>
> But money remains separate from CG evaluation quality.
> The Security Lab research program now becomes PRIVATE LAB │ ├── SECURITY 
> POOL │ │ │ ├── School: code-audit │ │ ├── BitSec SN60 │ │ ├── 
> BugBountyReplay │ │ ├── Sherlock │ │ ├── Cantina │ │ ├── Immunefi │ │ ├── 
> Huntr │ │ └── OSS VRPs │ │ │ ├── School: ai-redteam │ │ ├── RedTeam SN61 │ 
> │ └── future model/agent red-team programs │ │ │ └── School: 
> adversarial-systems │ ├── fuzzing │ ├── browser detection │ ├── 
> protocol/incentive attacks │ └── future security worlds │ ├── Worker: 
> security-01 │ └── immutable versions v0 → v1 → v2 ... │ ├── WorkerKit ├── 
> CG ├── CGE ├── Hydra ├── Letta └── Budget allocator 
>
> The key point is that the *Security Pool is not memory*. It is an 
> evidence index over what has been observed and validated. Letta remains the 
> worker’s cognition; Git owns promoted intellectual artifacts; receipts are 
> canonical evidence; Hydra projects the evidence graph.
> Then Checkpoint 3 becomes obvious 
>
> Once CP2 proves transfer, the next milestone is no longer security 
> technique itself. It is *autonomous allocation*:
>
> Given BitSec, RedTeam, Sherlock/Cantina/Immunefi and other security 
> opportunities, can the Lab decide whether to train, evaluate, submit, or 
> hold based on expected capability gain + expected economic value + budget?
>
> That is where the budgeting work becomes real.
>
> The progression is therefore:
> CHECKPOINT 1 Can one worker measurably learn in BitSec? CHECKPOINT 2 Does 
> that learning transfer across security worlds and produce viable external 
> submissions? CHECKPOINT 3 Can the Lab autonomously decide where to spend 
> its next dollar/token/hour to improve capability and/or earn money? 
>
> That is a strong first research program for Moltwork: *Security as the 
> first frontier, BitSec as the first world, but the actual object being 
> built is a general laboratory for measurable autonomous learning and 
> allocation.*
>
