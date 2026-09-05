# Multi-Agent BitSec Architecture

## Design Principle

From research and ScaBench analysis, the key insight is:

**Cross-file, cross-contract vulnerabilities require project-level understanding.**

Single-agent per-file analysis fundamentally cannot find:
- Mismatched function signatures between contracts
- Cross-contract state inconsistencies
- Business logic errors spanning multiple files
- Invariants violated by contract interactions

## Architecture

```
Phase 1: MAP (Architecture Understanding)
    ├── Read project structure
    ├── Identify all contracts/interfaces
    ├── Map import relationships
    ├── Identify entry points and external calls
    └── Output: ProjectMap (JSON)

Phase 2: TRACE (Data Flow Analysis)
    ├── For each entry point, trace data flow
    ├── Identify state variables and how they change
    ├── Map cross-contract calls
    ├── Identify trust boundaries
    └── Output: DataFlowGraph (JSON)

Phase 3: HUNT (Targeted Vulnerability Detection)
    ├── For each high-risk area identified in Phase 1-2
    ├── Deep analysis with full context
    ├── Cross-reference with known vulnerability patterns
    ├── Generate specific findings with evidence
    └── Output: VulnerabilityReport (JSON)

Phase 4: VERIFY (Cross-Validation)
    ├── For each finding, verify it's real
    ├── Check for false positives
    ├── Rank by confidence
    └── Output: FinalReport (JSON)
```

## Implementation

### Agent 1: ArchitectureMapper
- Reads all .sol/.rs/.vy files
- Builds dependency graph
- Identifies: contracts, interfaces, libraries, entry points, external calls
- Output: structured JSON with project map

### Agent 2: DataFlowTracer
- Takes ProjectMap as input
- For each state variable, traces reads/writes
- For each external call, traces data flow
- Identifies: trust boundaries, access control points, asset flows
- Output: structured JSON with data flow graph

### Agent 3: VulnerabilityHunter
- Takes ProjectMap + DataFlowGraph as input
- For each high-risk pattern, performs deep analysis
- Has access to read_file for targeted investigation
- Generates specific findings with exact file/line/function
- Output: structured JSON with vulnerability findings

### Agent 4: CrossReferenceVerifier
- Takes raw findings as input
- For each finding, independently verifies it
- Checks: is the vulnerability real? Is it exploitable? What's the impact?
- Filters false positives
- Output: verified vulnerability report

## Why This Works

1. **Phase 1** gives the model a bird's-eye view before diving into details
2. **Phase 2** identifies WHERE to look for bugs (not just scanning everything)
3. **Phase 3** does focused analysis with full context
4. **Phase 4** catches false positives

This mirrors how human auditors work:
1. Read the README and understand what the project does
2. Map the architecture and identify key contracts
3. Trace the money and data flows
4. Deep-dive into suspicious areas
5. Verify findings before reporting

## Token Budget

Each phase makes independent LLM calls:
- Phase 1: ~5-10 calls (map structure)
- Phase 2: ~10-20 calls (trace flows)
- Phase 3: ~20-40 calls (deep analysis)
- Phase 4: ~10-20 calls (verification)
Total: ~50-90 calls per project

At ~5s per call = ~5-8 minutes per project
At 7 projects = ~35-56 minutes total

This is feasible with our proxy and free mimo-v2.5.

## First Test

1. Pick Superposition (we have ground truth)
2. Implement Phase 1 (ArchitectureMapper) only
3. See if the project map helps the model understand the architecture
4. If yes, add Phase 2, then 3, then 4
5. Score after each phase to measure improvement
