# Mutation Strategies — What the Research Says

## From CG Recipes (cogym_kernel/evo/recipes.py)

### Chain Assembly
Evolves the ORDER and COMPOSITION of reasoning-chain steps.
Key insight: "structure beats chatter" — debate +92.8 > chat −51.8
Application: reorder the pipeline phases, add/remove analysis steps.

### Elitist Mutation
Copy elites, resample genes p=0.5.
Application: take winning prompt, randomly modify 50% of instructions.

### Tournament
k=3 tournament by cost → uniform crossover → mutate.
Application: take 3 winning prompts, combine best parts, mutate.

### Champion Lineage
Spawn along Hydra-proven lineages.
Application: track which prompts succeeded on which projects, build ancestry.

## From MulVul (ACL 2026)
Cross-Model Prompt Evolution:
- Generator LLM refines candidate prompts
- Executor LLM validates effectiveness
- Iterative refinement until effectiveness plateaus

## From DeceptPrompt
Genetic algorithm with:
- Sentence-level Crossover: exchange sentences between prompts
- Word-level Substitution: replace words with synonyms
- Oracle-based Mutation: use LLM to paraphrase without changing semantics

## From GAAPO
Combines multiple prompt optimization strategies:
- Lexical mutation (word-level)
- Structural mutation (reorder/add/remove)
- Semantic mutation (LLM paraphrase)

## From EvoPrompt
LLMs into mutation and crossover operations:
- Crossover: combine two prompts
- Mutation: LLM rewrites a prompt section

## From PromptBreeder
Self-referential co-evolution:
- Evolve prompts AND mutation operators together
- The mutation strategy itself evolves

## Concrete Mutation Operations for BitSec

### 1. Prompt Append (Low Risk)
Add a specific instruction to the analysis prompt.
Example: "Also check: does cancelbid clear token approval?"

### 2. Prompt Replace (Medium Risk)
Replace a section of the prompt with a new instruction.
Example: Replace "find common vulnerabilities" with "trace marketplace lifecycle"

### 3. Prompt Crossover (High Risk)
Combine parts of two different prompts.
Example: Take the "marketplace lifecycle" part from one prompt and the "cross-contract" part from another.

### 4. Chain Reorder (Medium Risk)
Change the order of analysis phases.
Example: Do targeted trace BEFORE architecture mapping.

### 5. Focus Narrowing (Low Risk)
Reduce scope to specific vulnerability class.
Example: Only look for business logic bugs, ignore access control.

### 6. Focus Broadening (Medium Risk)
Increase scope to cover more ground.
Example: Analyze ALL functions, not just entry points.

### 7. Evidence Grounding (Low Risk)
Add requirement to cite specific code.
Example: "For each finding, cite the exact file:line"

### 8. Negative Constraints (Low Risk)
Add what NOT to do.
Example: "Do NOT report generic findings like 'missing access control'"

## Fitness Function

```
fitness = detection_rate * (1 - overfitting_penalty)

overfitting_penalty = max(0, (train_dr - test_dr) / train_dr)
```

Where:
- train_dr = DR on the project the prompt was optimized for
- test_dr = DR on held-out projects

This penalizes prompts that overfit to one project.

## Anti-Overfitting via Rubric

Each lesson is a BINARY constraint:
- "Must check marketplace lifecycle state transitions"
- "Must verify approval cleanup on cancel"
- "Must trace payment bypass paths"

New prompts MUST satisfy all rubric lessons.
This prevents regression and forces generalization.
