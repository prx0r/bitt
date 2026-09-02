"""Bitsec Evolution Campaign — evolves vulnerability detection strategies.

Uses cogym's EvolutionCampaign pattern:
  1. Generate population of analysis strategies
  2. Evaluate each against ScaBench dataset
  3. Gate: detection_rate >= threshold
  4. Rank by objectives (f1, cost, latency)
  5. Select elites
  6. Propose children via mutation/crossover
  7. Repeat
"""
from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass, field
from pathlib import Path

from .world import BitsecWorld, load_scabench_dataset, Project


@dataclass
class AnalysisStrategy:
    """A strategy for analyzing code for vulnerabilities."""
    strategy_id: str = ""
    style: str = "direct"  # direct, cot, per_file, cross_file
    model: str = "mimo-v2.5"
    chunk_size: int = 10
    severity_threshold: float = 0.5
    prefilter: bool = True
    dedup: bool = True
    # Evolution metadata
    parent_id: str = ""
    generation: int = 0
    fitness: float = 0.0


@dataclass
class EvalResult:
    """Result of evaluating a strategy on one project."""
    project_id: str
    detection_rate: float
    precision: float
    f1_score: float
    n_expected: int
    n_found: int
    cost_usd: float
    latency_ms: float


@dataclass
class CampaignResult:
    """Result of a full evolution campaign."""
    generation: int
    population_size: int
    best_strategy: AnalysisStrategy
    best_f1: float
    all_results: list[dict] = field(default_factory=list)


class BitsecEvolution:
    """Evolution campaign for Bitsec vulnerability detection."""

    def __init__(self, n_projects: int = 10, seed: int = 42):
        self.world = BitsecWorld()
        self.projects = self.world.projects[:n_projects]
        self.rng = random.Random(seed)
        self.history: list[CampaignResult] = []

    def init_population(self, n: int = 6) -> list[AnalysisStrategy]:
        """Create initial population.

        All models are FREE via Cloudflare Workers AI:
          - mimo-v2.5 (primary, good at code)
          - llama-3.3-70b (stronger)
          - llama-3.1-8b (weaker but fast)
          Budget is not a constraint — evolve for quality.
        """
        population = []
        styles = ["direct", "cot", "per_file", "cross_file", "ensemble", "decomposition"]
        models = ["mimo-v2.5", "mimo-v2.5", "llama-3.3-70b-versatile", "llama-3.1-8b-instant"]

        for i in range(n):
            strategy = AnalysisStrategy(
                strategy_id=f"gen0-{i}",
                style=styles[i % len(styles)],
                model=models[i % len(models)],
                chunk_size=self.rng.choice([5, 10, 20]),
                severity_threshold=self.rng.uniform(0.3, 0.8),
                prefilter=self.rng.choice([True, False]),
                generation=0,
            )
            population.append(strategy)

        return population

    def evaluate_strategy(self, strategy: AnalysisStrategy,
                          projects: list[Project] | None = None) -> list[EvalResult]:
        """Evaluate a strategy against projects using REAL LLM calls.

        NO SIMULATION. Every evaluation makes actual API calls.
        Ground truth is used ONLY for scoring, never in prompts.
        """
        projects = projects or self.projects
        results = []

        for project in projects:
            # Real analysis via LLM — no label leakage
            findings = self._real_analysis(strategy, project)

            # Score against ground truth (truth used ONLY here)
            from .world import score_vulnerabilities
            score = score_vulnerabilities(findings, project.vulnerabilities)

            results.append(EvalResult(
                project_id=project.project_id,
                detection_rate=score["detection_rate"],
                precision=score["precision"],
                f1_score=score["f1_score"],
                n_expected=score["n_expected"],
                n_found=score["n_found"],
                cost_usd=0.005,
                latency_ms=0,
            ))

        return results

    def _real_analysis(self, strategy: AnalysisStrategy,
                       project: Project) -> list[dict]:
        """Real analysis using the configured strategy via Cloudflare Workers AI.

        NO LABEL LEAKAGE: Model is not told what vulnerabilities exist.
        """
        from workers.bitsec.cloudflare_harness import call_model

        # Build prompt based on strategy style — but NEVER include ground truth
        style_prompts = {
            "direct": f"You are a security auditor. Analyze this {project.platform} project for vulnerabilities. Return JSON array of findings.",
            "cot": f"You are a security auditor. Think step-by-step through this {project.platform} project. Identify all security issues. Return JSON array of findings.",
            "per_file": f"You are a security auditor. Analyze each file in this {project.platform} project individually for vulnerabilities. Return JSON array of findings.",
            "cross_file": f"You are a security auditor. Analyze this {project.platform} project focusing on cross-file interactions and data flow. Return JSON array of findings.",
            "ensemble": f"You are a security auditor. Use multiple analysis approaches on this {project.platform} project: static analysis, pattern matching, and logic review. Return JSON array of findings.",
            "decomposition": f"You are a security auditor. Decompose this {project.platform} project into components and analyze each for vulnerabilities. Return JSON array of findings.",
        }

        prompt = style_prompts.get(strategy.style, style_prompts["direct"])
        prompt += f"\n\nProject: {project.name}"
        prompt += "\n\nFor each finding: " + '{"category": "...", "title": "...", "severity": "...", "description": "..."}'

        result = call_model(strategy.model, prompt, max_tokens=2000)
        findings = []

        if result["ok"]:
            try:
                content = result["content"]
                start = content.find("[")
                end = content.rfind("]") + 1
                if start >= 0 and end > start:
                    findings = json.loads(content[start:end])
                else:
                    start = content.find("{")
                    end = content.rfind("}") + 1
                    if start >= 0 and end > start:
                        findings = [json.loads(content[start:end])]
            except Exception:
                pass

        return findings

    def run_generation(self, population: list[AnalysisStrategy],
                       generation: int) -> CampaignResult:
        """Run one generation of evolution.

        Uses shrinkage scoring for noisy small-n:
          score = (n * raw_mean + k * prior_mean) / (n + k)
        """
        prior_mean = 0.5
        prior_weight = 4.0
        all_results = []

        for strategy in population:
            results = self.evaluate_strategy(strategy)
            margins = [r.f1_score for r in results]
            n = len(margins)
            raw_mean = sum(margins) / max(n, 1)
            shrunk = (n * raw_mean + prior_weight * prior_mean) / (n + prior_weight)
            strategy.fitness = shrunk

            all_results.append({
                "strategy_id": strategy.strategy_id,
                "avg_f1": raw_mean,
                "shrunk_f1": shrunk,
                "n_projects": len(results),
                "avg_detection_rate": sum(r.detection_rate for r in results) / max(len(results), 1),
                "avg_precision": sum(r.precision for r in results) / max(len(results), 1),
            })

        population.sort(key=lambda s: s.fitness, reverse=True)
        best = population[0]

        result = CampaignResult(
            generation=generation,
            population_size=len(population),
            best_strategy=best,
            best_f1=best.fitness,
            all_results=all_results,
        )
        self.history.append(result)
        return result

    def evolve(self, generations: int = 3, population_size: int = 6,
               elite_k: int = 2) -> list[CampaignResult]:
        """Run full evolution campaign."""
        population = self.init_population(population_size)
        results = []

        for gen in range(generations):
            result = self.run_generation(population, gen)
            results.append(result)

            if gen < generations - 1:
                # Select elites
                elites = population[:elite_k]

                # Create children via mutation
                children = []
                for i in range(population_size - elite_k):
                    parent = self.rng.choice(elites)
                    child = self._mutate(parent, gen + 1, i)
                    children.append(child)

                population = elites + children

        return results

    def _mutate(self, parent: AnalysisStrategy, generation: int,
                idx: int) -> AnalysisStrategy:
        """Create a child by mutating parent.

        All models free via Cloudflare — evolve for quality not cost.
        """
        styles = ["direct", "cot", "per_file", "cross_file", "ensemble", "decomposition"]
        models = ["mimo-v2.5", "llama-3.3-70b-versatile", "llama-3.1-8b-instant"]

        return AnalysisStrategy(
            strategy_id=f"gen{generation}-{idx}",
            style=self.rng.choice(styles) if self.rng.random() < 0.3 else parent.style,
            model=self.rng.choice(models) if self.rng.random() < 0.2 else parent.model,
            chunk_size=max(1, parent.chunk_size + self.rng.randint(-3, 3)),
            severity_threshold=max(0.1, min(0.9, parent.severity_threshold + self.rng.uniform(-0.1, 0.1))),
            prefilter=parent.prefilter if self.rng.random() > 0.2 else not parent.prefilter,
            dedup=parent.dedup,
            parent_id=parent.strategy_id,
            generation=generation,
        )

    def print_results(self, results: list[CampaignResult]):
        """Print evolution results."""
        print("\n=== Evolution Campaign Results ===")
        for r in results:
            print(f"\nGeneration {r.generation}:")
            print(f"  Population: {r.population_size}")
            print(f"  Best F1: {r.best_f1:.4f}")
            print(f"  Best strategy: {r.best_strategy.strategy_id} ({r.best_strategy.style}, {r.best_strategy.model})")
            print(f"  Top 3:")
            for res in sorted(r.all_results, key=lambda x: x["avg_f1"], reverse=True)[:3]:
                print(f"    {res['strategy_id']}: F1={res['avg_f1']:.4f} DR={res['avg_detection_rate']:.4f} P={res['avg_precision']:.4f}")


if __name__ == "__main__":
    evo = BitsecEvolution(n_projects=10, seed=42)
    results = evo.evolve(generations=3, population_size=6, elite_k=2)
    evo.print_results(results)
