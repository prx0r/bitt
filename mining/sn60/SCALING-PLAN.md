# Scaling Plan — From Manual to Automated

## Current State

**Manual approach on Superposition:**
- 2 rounds of specific prompting
- 81.8% DR, 81.8% precision, F1=0.818
- Requires knowing ground truth vuln types

**Problem:** Doesn't scale to new projects without ground truth

## The Scaling Challenge

To beat 83.3% on ALL projects, we need:
1. **Automated prompt generation** — no manual crafting per project
2. **Multiple rounds** — cover different vuln categories
3. **Deduplication** — merge findings across rounds
4. **Learning** — improve over time based on failures

## How CG/CGE Helps

### The Evolution Loop

```
1. GENERATE: CGE proposes prompt strategies
2. EVALUATE: Run on ScaBench projects
3. SCORE: Compare to ground truth
4. MUTATE: Adjust prompts based on failures
5. REPEAT: Until F1 > 0.5
```

### What CGE Can Mutate

| Gene | What It Controls | Example Values |
|------|------------------|----------------|
| `prompt_style` | How we ask | simple, focused, cot, specific |
| `vuln_categories` | What we ask for | reentrancy, access_control, overflow |
| `rounds` | How many passes | 1, 2, 3, 4 |
| `dedup_method` | How we merge | title, description, combined |
| `model` | Which LLM | mimo-v2.5, llama-70b |

### What CG Evaluates

```python
# For each candidate strategy
for project in scaBench_projects:
    findings = run_agent(strategy, project)
    scores = score_findings(findings, ground_truth)
    
# Aggregate across projects
avg_dr = mean([s['dr'] for s in scores])
avg_f1 = mean([s['f1'] for s in scores])
```

## The Automated Pipeline

### Step 1: Project Discovery

```python
# For each project in ScaBench
for project in scaBench_projects:
    # 1. Load ground truth
    ground_truth = load_ground_truth(project)
    
    # 2. Discover contract files
    files = discover_files(project)
    
    # 3. Run agent with current strategy
    findings = run_agent(strategy, files)
    
    # 4. Score
    scores = score_findings(findings, ground_truth)
    
    # 5. Log
    log_experiment(project, strategy, scores)
```

### Step 2: Strategy Evolution

```python
# CGE proposes new strategies based on failures
for generation in range(n_generations):
    # 1. Evaluate current population
    evaluated = evaluate_population(population)
    
    # 2. Select elites
    elites = select_elites(evaluated, k=2)
    
    # 3. Propose children (mutated strategies)
    children = propose_children(elites, recipe='elitist_mutation')
    
    # 4. New population
    population = elites + children
```

### Step 3: Learning from Failures

```python
# For each failed project
for project in failed_projects:
    # 1. Identify failure mode
    failure_mode = analyze_failure(findings, ground_truth)
    
    # 2. Propose mutation
    mutation = propose_mutation(failure_mode)
    
    # 3. Apply to strategy
    new_strategy = apply_mutation(strategy, mutation)
    
    # 4. Test
    new_scores = test_strategy(new_strategy, project)
```

## Concrete Example

### Initial Strategy (Generation 0)

```python
strategy = {
    'prompt_style': 'simple',
    'vuln_categories': ['reentrancy', 'access_control', 'overflow'],
    'rounds': 1,
    'dedup_method': 'title',
    'model': 'mimo-v2.5'
}
# Result: 0% DR on Superposition
```

### Mutated Strategy (Generation 1)

```python
strategy = {
    'prompt_style': 'specific',
    'vuln_categories': ['createPool', 'fees', 'slippage', 'zero-liquidity', 'imports', 'overflow'],
    'rounds': 2,
    'dedup_method': 'title',
    'model': 'mimo-v2.5'
}
# Result: 81.8% DR on Superposition
```

### Further Mutation (Generation 2)

```python
strategy = {
    'prompt_style': 'specific_with_functions',
    'vuln_categories': ['refund', 'withdraw', 'grant_position', 'pool_init', 'swap'],
    'rounds': 2,
    'dedup_method': 'combined',
    'model': 'mimo-v2.5'
}
# Result: Test on more projects
```

## Files to Build

| File | Purpose |
|------|---------|
| `mining/sn60/strategy.py` | Strategy definition |
| `mining/sn60/evaluator.py` | ScaBench evaluation |
| `mining/sn60/evolver.py` | CGE-based evolution |
| `mining/sn60/runner.py` | Main execution loop |

## Success Criteria

| Metric | Current | Target |
|--------|---------|--------|
| DR on Superposition | 81.8% | >83.3% |
| DR on 3 projects | 0% | >50% |
| F1 on 3 projects | 0.0 | >0.3 |
| Automation | Manual | Fully automated |

## Timeline

1. **Now:** Build strategy + evaluator
2. **Next:** Wire to CGE for evolution
3. **Then:** Run on 10 projects
4. **Finally:** Submit to Bitsec

## Key Insight

**The winning approach is not a single prompt. It's a process that evolves prompts based on failures.**

CG/CGE provides:
- **Mutation** — try new prompt strategies
- **Evaluation** — measure against ground truth
- **Selection** — keep what works
- **Learning** — improve over time

This is genetic programming with ScaBench as the fitness landscape.
