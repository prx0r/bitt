# Simple Agent — Match Official Baseline Pattern

## Key Insight

The official baseline found 87 vulnerabilities while mw-audit-v1 found 0.

**Why?** The official baseline is simpler:
- Simple system prompt
- Direct tool calls
- Immediate reporting
- No complex analysis

**mw-audit-v1 is too complex:**
- Complex system prompt
- Multi-turn tool calls
- Delayed reporting
- Model gets confused

## The Fix

Create a simpler agent that matches the official baseline pattern:
1. Simple system prompt (like official)
2. Direct tool calls (like official)
3. Immediate reporting (like official)
4. No complex analysis

## Official Baseline Pattern

```python
# System prompt
system = "You are a senior smart contract security auditor. Analyze code for security vulnerabilities. Use tools to explore the project and read files. Report findings using report_vulnerabilities tool."

# Tool loop
for turn in range(max_turns):
    response = inference(messages, tools=TOOL_DEFINITIONS, tool_choice=tool_choice)
    
    if response has tool_calls:
        for tc in tool_calls:
            if tc["function"]["name"] == "report_vulnerabilities":
                # IMMEDIATELY report findings
                findings.extend(tc["function"]["arguments"]["vulnerabilities"])
    else:
        break
```

## What to Change

1. Remove complex analysis phases
2. Use simple system prompt
3. Report findings immediately
4. Don't try to be too smart

## Expected Result

If we match the official baseline pattern, we should get similar results (87 findings).
