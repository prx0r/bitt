# IMPORTANT.md — Critical Mistakes to Never Repeat

## Mistake 1: Scaling a Failing Approach

**What I did:**
- Ran 175s test on Superposition → 0 good results (empty arrays)
- Then ran hour-long version of same approach → same 0 results

**Why it was wrong:**
- Never scale up a failing approach
- Fix the approach first, then scale
- 175s test told me everything I needed to know

**What I should have done:**
- Analyze WHY the test failed
- Fix the root cause
- Then run longer test

**Lesson:** If a 2-minute test fails, a 2-hour test will also fail. Fix first.

## Mistake 2: Not Using nohup

**What I did:**
- Ran blocking Python scripts
- Tied up my attention for hours
- User couldn't reach me

**Why it was wrong:**
- Lead agent must NEVER block
- All long tasks must use nohup
- I should always be available to orchestrate

**What I should have done:**
```bash
nohup python3 agent.py > /tmp/agent.log 2>&1 &
```

**Lesson:** Always nohup. Never block.

## Mistake 3: Not Analyzing Results Before Continuing

**What I did:**
- Got 0 results from first test
- Immediately ran another test
- Didn't ask WHY it failed

**Why it was wrong:**
- Results are data, not noise
- 0 results means something is wrong
- Must understand failure before trying again

**What I should have done:**
- Check proxy logs
- Check agent logs
- Understand why findings are empty
- Fix the issue
- Then retest

**Lesson:** Never ignore 0 results. They're telling you something.

## Mistake 4: Running Tests Without Clear Success Criteria

**What I did:**
- Ran "test" without knowing what success looks like
- No target metrics defined
- No comparison baseline

**Why it was wrong:**
- Without success criteria, you can't evaluate
- Without baseline, you can't measure improvement
- "Test" is not a plan

**What I should have done:**
- Define success: "Find >3 high/critical vulns"
- Set baseline: "Official baseline finds X vulns"
- Compare: "mw-audit-v1 finds Y vulns"

**Lesson:** Always define success criteria before testing.

## Mistake 5: Not Checking Proxy Logs During Test

**What I did:**
- Ran agent for 2+ minutes
- Never checked proxy logs
- Didn't know if API calls were working

**Why it was wrong:**
- Proxy logs tell you if inference is working
- Empty responses mean API issues
- 502 errors mean model problems
- Must monitor during test, not after

**What I should have done:**
```bash
# Check logs every 30s during test
docker logs bitsec-proxy 2>&1 | tail -5
```

**Lesson:** Always monitor logs during long runs.

## Mistake 6: Not Documenting Failures

**What I did:**
- Got 0 results
- Moved on to next test
- Didn't document what went wrong

**Why it was wrong:**
- Failures are data
- Documenting failures prevents repeating them
- Future me needs to know what didn't work

**What I should have done:**
- Write failure to IMPORTANT.md
- Update AGENTS.md with lesson
- Prevent future repetition

**Lesson:** Document every failure. It's data, not noise.

## The Pattern

```
WRONG: Test fails → Run longer test → Still fails → Waste time

RIGHT: Test fails → Analyze why → Fix → Retest → Measure improvement
```

## Time is the Scarcest Resource

Every minute spent on a failing approach is a minute not spent on the right one.

**175s test told me the approach was broken.**
**I should have fixed it, not scaled it.**
