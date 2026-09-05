# Bug Report — Why We're at 1% DR

## Bug 1: Wrong Baseline Comparison (CRITICAL)

**The ScaBench baseline uses GPT-5, not MiniMax.**

From the official ScaBench README:
> "Pre-computed baseline results from analyzing each individual file with GPT-5"

We've been comparing mimo-v2.5 against a GPT-5 baseline and wondering why we underperform. That's not a fair comparison. GPT-5 is significantly more capable than mimo-v2.5 for deep code reasoning.

**Impact:** Our 1% DR is expected when comparing a free model against GPT-5. The question isn't "why are we at 1%" — it's "what can mimo-v2.5 actually achieve?"

## Bug 2: Single-Agent Per-File Architecture (CRITICAL)

Our agent analyzes each file independently (3 turns per file). This CANNOT find:
- Cross-contract vulnerabilities
- Cross-file data flow bugs
- Architecture-level design flaws
- Business logic errors

The ground truth contains exactly these types of bugs (e.g., "createPoolD650E2D0 mismatch between Solidity and Stylus").

**Research shows multi-agent systems consistently outperform single-agent approaches:**
- LLM-SmartAudit (IEEE TSE 2025): multi-agent with buffer-of-thought → 98% on common vulns
- VulTrial (ICSE 2026): mock-court approach → 2× performance over single-agent
- CodeSpeak (JSS 2026): domain-specific prompts mimicking expert audit practices

**Impact:** No amount of prompt mutation will fix this. The architecture needs to change.

## Bug 3: Official Scorer Requires Python 3.12+ (BLOCKING)

The Nethermind AuditAgent scorer (`pip install scoring-algo`) requires Python >= 3.12. We have 3.11.2.

**Impact:** Can't run official scoring locally. Options:
- Install Python 3.12 in a venv
- Use the scorer remotely
- Build our own scorer that matches the official algorithm

## Bug 4: Our Scorer Is Approximate (MEDIUM)

Our LLM-based scorer uses a different model and prompt than the official AuditAgent scorer. Results may differ significantly.

**Impact:** Our 1% score may not reflect actual official score. Need official scorer to validate.

---

## What Actually Needs to Change

### NOT: More mutations of the current approach
The per-file single-agent architecture is fundamentally limited.

### YES: Multi-agent architecture
1. **Architecture Mapper** — reads project structure, identifies key contracts and their relationships
2. **Data Flow Analyst** — traces how data moves between functions/contracts
3. **Vulnerability Hunter** — uses architectural understanding to find specific bugs
4. **Cross-Reference Checker** — compares findings against known vulnerability patterns

### YES: Project-level analysis
Instead of analyzing each file independently:
1. First pass: read all files, build project map
2. Second pass: analyze cross-file interactions
3. Third pass: targeted deep-dive on high-risk areas

### YES: Official scorer
Need Python 3.12 or remote scoring to validate properly.

---

## Immediate Next Steps

1. Set up Python 3.12 venv for official scorer
2. Design multi-agent architecture
3. Test on 1 project with multi-agent approach
4. Score with official scorer
5. Compare to baseline

## The Honest Assessment

mimo-v2.5 may be "better than minimax" (per user), but:
- It needs the RIGHT architecture to succeed
- Per-file analysis is the wrong approach for cross-file bugs
- Multi-agent systems are the proven path forward
- The 1% score is an architecture problem, not a model problem
