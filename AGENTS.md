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

## The Pattern

```bash
# WRONG — blocks me
task(subagent_type="general", description="do work", prompt="...")

# RIGHT — starts job, I stay free
nohup bash -c '
export INFERENCE_API=http://localhost:8087
export INFERENCE_API_KEY=$(python3 -c "import sys; sys.path.insert(0, \"/root/bitt\"); from vault import Vault; print(Vault().get(\"opencode_go_api_key\"))")
cd /root/bitt/subnets/sn60-bitsec/sandbox-v2
python3 /root/bitt/mining/sn60/candidates/simple-v1/agent.py /root/bitt/data/scabench-repos/PROJECT
' > /tmp/PROJECT.log 2>&1 &
echo "Started: $!"
```

## What I Do

- Start nohup jobs
- Tell user what I started
- Stay free to talk
- Check results when asked

## What I Do NOT Do

- Use Task tool (blocks me)
- Wait for results
- Sleep
- Run long tasks directly

## Current Jobs

| Job | Status | Log |
|-----|--------|-----|
| (none) | - | - |

## How to Check Status

```bash
# Check if job is running
ps aux | grep "simple-v1" | grep -v grep

# Check results
cat /root/bitt/data/scabench-repos/PROJECT/agent_report.json | python3 -m json.tool

# Check proxy
docker logs bitsec-proxy 2>&1 | tail -5
```
