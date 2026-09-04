# Bitsec SN60 — Intel Collection

## Official Links

| Resource | URL | Purpose |
|----------|-----|---------|
| Main site | https://bitsec.ai | Platform homepage |
| Leaderboard | https://bitsec.ai/leaderboard | Current top agents |
| Agent status | https://bitsec.ai/agents-status | All submitted agents |
| Docs | https://docs.bitsec.ai | Official documentation |
| Miner guide | https://docs.bitsec.ai/miner | How to build miners |
| GitHub | https://github.com/Bitsec-AI | Organization repos |
| Sandbox repo | https://github.com/Bitsec-AI/sandbox | Official miner template |
| ScaBench | https://github.com/Bitsec-AI/scabench | Evaluation benchmark |
| Subnet repo | https://github.com/Bitsec-AI/subnet | Bittensor subnet code |
| Twitter | https://twitter.com/bitsecai | Updates and announcements |

## Key Findings from Docs

### Agent Structure
- Entry point: `agent_main()` with no args
- Returns: dict with `vulnerabilities` list
- Each vulnerability: title, description, severity, confidence, location, file

### Inference
- Uses proxy at `http://bitsec_proxy:8000/inference`
- Headers: `x-inference-api-key`, `x-agent-id`, `x-job-run-id`, `x-request-phase`
- Model: configurable, default is `qwen/qwen3.6-35b-a3b`

### Screening
1. Code check: valid Python, `agent_main` exists
2. LLM security check: no malicious code
3. Hard-steering check: not memorized answers
4. Duplicate check: not exact copy of existing agent

### Submission
```bash
# Register
uv run ./bitsec.py miner create email@example.com "Name" --wallet my_wallet

# Submit
uv run ./bitsec.py miner submit --wallet my_wallet
```

### Testing
```bash
# Local without Docker
uv run ./bitsec.py miner run-no-docker

# Local with Docker
uv run ./bitsec.py miner run
```

## Winning Agent Analysis

From leaderboard:
- Score: 83.3%
- Projects passed: 15
- True positives: 254
- Runtime: ~13 minutes per project
- 3 validators, all scoring similarly

## Competition Landscape

- 256 miners registered
- Top agents use tool calling
- Most use OpenRouter for inference
- Runtime matters (under 30 min timeout)

## Intel from Discord/Community

- Hard-steering detection catches memorized answers
- Novel approaches score higher
- Consistency across validators matters
- False positives hurt score significantly
