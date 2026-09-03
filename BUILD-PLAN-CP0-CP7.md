# Moltwork Build Plan — CP0 through CP7

## North Star Demo

> Open Moltwork desktop → Oracle shows SN62 opportunity → click "Fund Experiment" → approve a 0.2 TAO / $5 / six-hour grant → coding worker benchmarks itself → proposes registration → exact transaction appears for approval → testnet executes → miner result is measured → complete verified WorkerRun appears with cost/reward → Hydra records the lesson → grant expires and unused capital is swept.

## The Build Sequence

### CP0 — Secure and Correct Foundations
- [ ] Rotate/remove repository credential leakage
- [ ] Repair /bitt historical schema
- [ ] TAOStats historical backfill
- [ ] Correct execution simulator
- [ ] Backtest invariants/tests
- **Exit:** deterministic historical replay produces trustworthy TAO NAV

### CP1 — Moltwork Economic Protocol
- [ ] Mandate, Grant, Intent, Plan, Approval, Receipt, EconomicOutcome
- [ ] Pydantic + append-only event log
- [ ] No blockchain execution
- **Exit:** fake Bittensor registration traverses entire state machine, generates WorkerRun receipt

### CP2 — Bittensor Read-Only Adapter
- [ ] Inspect wallet, positions, proxies, subnet
- [ ] Query registration price, quote staking
- [ ] Convert Oracle opportunity → Moltwork opportunity
- [ ] No signing
- **Exit:** desktop app shows Bittensor treasury + proposed actions

### CP3 — Bittensor Planning
- [ ] Generic intent compiles to Bittensor transaction
- [ ] Calls plan() with exact predicted fee/effects/policy verdict
- [ ] No execution
- **Exit:** every proposal has exact predicted fee/effects/policy verdict

### CP4 — Testnet MoltGrant
- [ ] Testnet treasury wallet
- [ ] Pure proxy + scoped proxy
- [ ] Funded grant
- [ ] One WorkerKit worker executes one testnet action
- **Exit:** WorkerRun proves human mandate → grant → agent intent → authorization → chain execution → receipt

### CP5 — Opportunity-Directed Miner
- [ ] Oracle picks SN62 or SN60
- [ ] Worker develops and benchmarks automatically
- [ ] Registration remains human-approved
- **Exit:** real Bittensor opportunity completes entire learning loop

### CP6 — Rebalancer
- [ ] Use corrected historical engine
- [ ] Shadow allocation first
- [ ] Then Bittensor Staking proxy grant
- **Exit:** same strategy code runs backtest → shadow → bounded execution

### CP7 — Hydra Adaptation
- [ ] Compare opportunity, worker config, grant, attempt, score, cost, reward
- [ ] Promote/demote configurations automatically
- **Exit:** evidence from previous Bittensor runs changes the next run

## Architecture

```
Mandate → Grant → Intent → Plan → Authorization → Execution → Receipt
```

### Protocol Objects (in /mw/protocol/)

| Object | Purpose |
|--------|---------|
| Mandate | What the human authorized conceptually |
| Grant | Exact economic authority |
| Intent | Agent proposal |
| Plan | Deterministically resolved transaction |
| Receipt | What happened |
| EconomicOutcome | Normalized financial results |
| Capability | Non-financial authority (MoltVault) |

### Bittensor Security Model

```
HUMAN TREASURY (coldkey offline)
    ↓ explicit funding
PURE PROXY ACCOUNT (MWGR-00001, 0.20 TAO)
    ↓ Registration scope
AGENT SIGNER
    ↓
Bittensor Runtime (rejects out-of-scope)
```

### Environment Adapter Interface

```python
class EconomicEnvironment:
    def inspect(self): ...
    def opportunities(self): ...
    def plan(self, intent): ...
    def execute(self, plan): ...
    def reconcile(self, receipt): ...
```

### Hydra Economics

```text
EconomicOutcome
  gross_reward
  total_cost
  costs: inference, compute, API, chain, registration, fees, human
  capital_at_risk
  net_profit, ROI, reward_per_hour, reward_per_token
  success, survival, score
  opportunity_cost
```
