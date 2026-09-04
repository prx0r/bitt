# SN Miners — Proper Assessment

## What I Learned

### Bittensor Mining is Complex

1. **Registration Flow**:
   - Create wallet (coldkey + hotkey)
   - Fund wallet with TAO (0.05-1 TAO per subnet)
   - Register hotkey on subnet via `btcli subnet register`
   - Get UID (unique identifier on that subnet)
   - Post IP via fiber for validator discovery

2. **Mining Flow**:
   - Run miner software that responds to validator queries
   - Validators score your work based on subnet-specific criteria
   - Emissions distributed proportionally to scores
   - Must maintain uptime or get deregistered

3. **Per-Subnet Requirements**:
   - Each subnet has its own mechanism, scoring, and requirements
   - Hardware varies (CPU vs GPU, RAM, storage)
   - Some require specific software stacks

### What We Actually Have (Bitsec)

**Working Components**:
- CG World (bitsec.scabench) — registered, deterministic reset
- WorkerKit (PydanticBATS) — real LLM calls via CF Workers AI
- Ledger — append-only, chain-hashed, immutable
- HydraDB — derived projection, live
- Learning loop — propose → evaluate → reject
- Pool knowledge — doctrine + skills

**What's Broken**:
- Replay returns 0% (schema corruption)
- Backtest needs more data
- Non-deterministic LLM output
- Wallet has no TAO (can't register)
- No Git lineage tracking

### Actual Subnet Requirements

**SN62 Ridges** (SWE Agent):
- Submit `agent.py` with `agent_main(input) -> str`
- Use OpenRouter/Targon/Chutes for inference
- Return unified diff patches
- Tested via `ridges miner run-local`
- Upload requires OpenRouter API + management keys
- Cost: ~$5-20 per submission

**SN19 Blockmachine** (RPC Marketplace):
- Run full Bittensor node
- Serve RPC requests
- Bid on pricing per epoch
- Hardware: 32GB RAM, 500GB NVMe SSD

**SN44 TurboVision** (Computer Vision):
- Deploy model to Chutes
- Commit metadata on-chain
- p95 latency ≤100ms per frame on 2 vCPU

**SN91 Cascade** (Time Series):
- Generate synthetic time series data
- Submit generator to Hippius Hub
- Duel-only rounds

### What Needs to Happen

1. **Wallet Setup**:
   - Create coldkey + hotkey
   - Fund with TAO
   - Register on target subnets

2. **Per-Subnet Setup**:
   - Clone official repo
   - Follow subnet-specific setup guide
   - Configure inference providers
   - Test locally before submitting

3. **Actual Mining**:
   - Run miner software
   - Monitor performance
   - Iterate based on feedback
   - Maintain uptime

### Key Insight

The bitsec learning loop is about **improving** an existing miner, not creating one from scratch. The flow is:

1. Clone existing subnet miner
2. Get it working locally
3. Register on subnet
4. Deploy and start earning
5. Use learning loop to improve

### Next Steps (Proper)

1. **Pick one subnet** (SN62 Ridges is most accessible)
2. **Set up wallet** with TAO
3. **Clone and configure** the official miner
4. **Test locally** with `ridges miner run-local`
5. **Register** on subnet
6. **Upload** agent
7. **Monitor** and iterate

### What I Should NOT Do

- Create oversimplified miners that don't actually work
- Ignore the actual subnet mechanisms
- Skip wallet setup and registration
- Assume LLM calls are the only requirement
