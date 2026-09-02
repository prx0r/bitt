"""Bitsec CGE Runner — runs the full evolution loop.

Usage:
    python3 -m cge.bitsec.run --generations 3 --population 6
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

# Add bitt to path
sys.path.insert(0, str(Path("/root/bitt")))

from cge.bitsec.world import BitsecWorld, load_scabench_dataset
from cge.bitsec.evolution import BitsecEvolution, AnalysisStrategy
from cge.bitsec.benchmark import score_findings, format_report as format_scoring_report


def run_full_cge(generations: int = 3, population_size: int = 6,
                  n_projects: int = 10, seed: int = 42):
    """Run the full CGE evolution loop for Bitsec."""
    print("=== Bitsec CGE Evolution ===")
    print(f"Generations: {generations}")
    print(f"Population: {population_size}")
    print(f"Projects: {n_projects}")
    print(f"Seed: {seed}")
    print()

    # Initialize
    evo = BitsecEvolution(n_projects=n_projects, seed=seed)
    print(f"Dataset: {len(evo.projects)} projects")

    # Count total vulnerabilities
    total_vulns = sum(len(p.vulnerabilities) for p in evo.projects)
    print(f"Total ground truth vulns: {total_vulns}")
    print()

    # Run evolution
    results = evo.evolve(
        generations=generations,
        population_size=population_size,
        elite_k=2,
    )

    # Print results
    evo.print_results(results)

    # Detailed scoring of best strategy
    print("\n=== Detailed Scoring of Best Strategy ===")
    best = results[-1].best_strategy
    print(f"Strategy: {best.strategy_id} ({best.style}, {best.model})")

    eval_results = evo.evaluate_strategy(best)
    for r in eval_results[:3]:
        print(f"\n  {r.project_id}:")
        print(f"    Detection Rate: {r.detection_rate:.1%}")
        print(f"    Precision: {r.precision:.1%}")
        print(f"    F1: {r.f1_score:.3f}")
        print(f"    Found: {r.n_found}/{r.n_expected}")

    # Save results
    output = {
        "generations": len(results),
        "best_strategy": {
            "id": best.strategy_id,
            "style": best.style,
            "model": best.model,
            "fitness": best.fitness,
        },
        "history": [
            {
                "generation": r.generation,
                "best_f1": r.best_f1,
                "population": r.population_size,
            }
            for r in results
        ],
    }

    output_path = Path("/root/bitt/data/bitsec_cge_results.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2))
    print(f"\nResults saved to {output_path}")

    return results


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--generations", type=int, default=3)
    parser.add_argument("--population", type=int, default=6)
    parser.add_argument("--projects", type=int, default=10)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    run_full_cge(
        generations=args.generations,
        population_size=args.population,
        n_projects=args.projects,
        seed=args.seed,
    )
