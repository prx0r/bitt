# Bitsec-Scanner Reference Agent

## Source

**Repo:** https://github.com/prx0r/bitsec-scanner
**File:** agents/agent.py (825 lines)

## Architecture

Two-pass Scout/Senior system (inspired by Hound):

```
1. FileManager — discover and read files
2. SolidityParser — regex-based parsing
3. MiniGraph — dict-based call graph
4. ReasoningLoop — Scout/Senior passes
5. BitsecStriker — main agent class
```

## The Flow

1. **Discover files** — find all .sol files
2. **Build call graph** — parse contracts, functions, modifiers
3. **Scout pass** — identify 5-10 high-risk areas
4. **Senior pass** — verify and detail each vulnerability

## Key Components

### Scout Pass
- Scans for: access control, accounting, reentrancy, upgradeability, asset transfers
- Returns: ScoutFinding with area, risk_type, confidence, functions, files, reasoning

### Senior Pass
- Takes Scout findings
- Extracts exact code for relevant functions
- Traces call graph
- Confirms vulnerabilities with detailed descriptions

### MiniGraph
- Dict-based (no networkx dependency)
- Tracks: contracts, functions, call graph
- Finds: public state writers without access control, reentrancy candidates

## What Needs Work

1. **Scout parsing** — LLM returns different field names than expected
2. **Call graph** — regex parser needs improvement
3. **Integration** — needs to work with OpenCode Go API

## Next Steps

1. Fix Scout parsing to handle multiple formats
2. Improve regex parser for better call graph
3. Test on Superposition with real LLM
4. Compare to baseline results
