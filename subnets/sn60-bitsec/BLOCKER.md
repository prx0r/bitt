# Blocker — API Usage Limit

## Problem

OpenCode Go API monthly limit reached:
```
Monthly usage limit reached. Resets in 15 days.
```

## Impact

- Cannot run any LLM inference
- Cannot test agents
- Cannot submit to BitSec

## Options

1. **Wait 15 days** — quota resets
2. **Use different API key** — if available
3. **Use different provider** — Chutes, OpenRouter, etc.
4. **Use local model** — if GPU available

## What's Ready

- Agent code (824 lines, Scout/Senior architecture)
- Wrapper for BitSec format
- Ground truth for 4 projects
- All documentation

## What's Blocked

- LLM inference
- Agent testing
- BitSec submission

## Next Steps

1. Get a working API key
2. Test agent on Superposition
3. Optimize based on results
4. Submit to BitSec
