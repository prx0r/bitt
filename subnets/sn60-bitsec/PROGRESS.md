# Progress — mw-audit-v1 Testing

## What Works

1. **Proxy setup** — Docker proxy running with OpenCode Go API
2. **Agent logic** — Tool calling works correctly
3. **File discovery** — Finds all contract files
4. **Inference** — Making 91+ calls to the API
5. **Reasoning** — Model is doing detailed analysis

## What's Broken

**The model finds vulnerabilities in reasoning but reports empty arrays.**

Looking at proxy logs:
- Model analyzes code thoroughly
- Identifies real vulnerabilities (inverted check, missing approval reset)
- But then calls `report_vulnerabilities` with `{"vulnerabilities": []}`

This is a prompt/system instruction issue. The model needs clearer instructions to report findings.

## Root Cause

The system prompt says:
```
"Report your findings using the report_vulnerabilities tool before the pass ends"
```

But the model is analyzing code and then reporting empty arrays. The issue is likely:
1. Model is doing deep analysis but not converting to structured findings
2. Or model is confused about when to report

## Fix Needed

Update the system prompt to be more explicit about reporting findings:
```
After analyzing the code, you MUST call report_vulnerabilities with your findings.
Do not report empty arrays. If you found vulnerabilities, report them.
```

## Next Steps

1. Fix the system prompt to ensure findings are reported
2. Re-run on Superposition
3. Measure performance
