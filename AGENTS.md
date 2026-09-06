# AGENTS.md — Lead Agent Role

## My Role

I am the lead agent. I NEVER block. I NEVER wait for results.

**I orchestrate. I start nohup jobs. I stay available.**

## Rules

1. **NEVER use Task tool** — it blocks me
2. **ALWAYS use nohup** — jobs run in background
3. **ALWAYS available** — never stuck watching
4. **Start jobs and move on** — don't wait for results
5. **Check results later** — when user asks or when convenient

## Current Jobs

| Job | Status | Log |
|-----|--------|-----|
| Pipeline v2 on Superposition | RUNNING | /tmp/pipeline_run_v2.log |

## How to Check Status

```bash
# Check if job is running
ps aux | grep "pipeline-v1" | grep -v grep

# Check results
cat /root/bitt/data/scabench-repos/PROJECT/agent_report.json | python3 -m json.tool

# Check proxy
docker logs bitsec-proxy 2>&1 | tail -5

# Check pipeline logs
ls /root/bitt/data/pipeline-logs/PROJECT/
```

## Agent Candidates

| Agent | Directory | Status | DR on Superposition |
|-------|-----------|--------|---------------------|
| simple-v1 | `mining/sn60/candidates/simple-v1/` | Working | 0-50% (non-deterministic) |
| scout-senior | `mining/sn60/candidates/scout-senior/` | Working | 0-50% (non-deterministic) |
| pipeline-v1 | `mining/sn60/candidates/pipeline-v1/` | Running v2 | Testing |
| official-baseline | `mining/sn60/candidates/official-baseline/` | Reference | 0% (GPT-5 baseline) |

## Key Files

| File | Purpose |
|------|---------|
| `BUILD-NOTES-2026-09-05.md` | Today's session summary |
| `BUG-REPORT.md` | 4 bugs found and fixed |
| `GOAL.md` | Goal and protocol |
| `EVOLUTION-REFERENCE.md` | Complete reference sheet |
| `WHAT_WE_WERE_DOING_WRONG.md` | Official docs analysis |
| `MULTI-AGENT-RESULTS.md` | Multi-agent experiment results |
| `STATUS-2026-09-05.md` | Overall status |
