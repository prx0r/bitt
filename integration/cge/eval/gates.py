"""Quality gates + lexicographic selection + paired non-inferiority.
Ported verbatim-in-spirit from canonical/core/evaluation.py."""
from __future__ import annotations
import math, random, statistics
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class QualityGate:
    metric: str
    mode: Literal["min", "max", "noninferior"] = "max"
    value: float | None = None
    margin: float = 0.0


def check_gate(gate: QualityGate, metrics: dict,
               baseline: dict | None = None):
    v = metrics.get(gate.metric)
    if v is None:
        return False, f"metric '{gate.metric}' missing"
    if gate.mode == "min":
        return v <= (gate.value if gate.value is not None else math.inf), f"{v}<= {gate.value}"
    if gate.mode == "max":
        return v >= (gate.value if gate.value is not None else -math.inf), f"{v}>={gate.value}"
    b = baseline.get(gate.metric) if baseline else None
    if b is None:
        return False, "baseline missing"
    return v >= b - gate.margin, f"delta {v-b:+.4g} >= -{gate.margin}"


def gates_pass(gates, metrics: dict, baseline: dict | None = None) -> bool:
    return all(ok for ok, _ in (check_gate(g, metrics, baseline) for g in gates))


@dataclass(frozen=True)
class Objective:
    metric: str
    direction: Literal["min", "max"] = "min"
    epsilon: float = 1e-9


def lexicographic_compare(a: dict, a_pass: bool, b: dict, b_pass: bool,
                          objectives=(Objective("cash_cost", "min"),)) -> int:
    """-1 a preferred · +1 b preferred · 0 tie. Gates dominate objectives."""
    if a_pass != b_pass:
        return -1 if a_pass else 1
    for obj in objectives:
        av, bv = a.get(obj.metric), b.get(obj.metric)
        if av is None and bv is None:
            continue
        if av is None:
            return 1
        if bv is None:
            return -1
        better = av < bv if obj.direction == "min" else av > bv
        if abs(av - bv) > obj.epsilon:
            return -1 if better else 1
    return 0


def wilson(k: int, n: int, z: float = 1.959963984540054) -> dict:
    if n <= 0:
        return {"k": k, "n": n, "p": None, "lo": None, "hi": None}
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = (z / denom) * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return {"k": k, "n": n, "p": round(p, 6),
            "lo": round(max(0.0, center - half), 6),
            "hi": round(min(1.0, center + half), 6)}


def bootstrap_ci(deltas: list[float], n_boot: int = 2000, alpha: float = 0.05,
                 seed: int = 7) -> tuple[float, float]:
    rng = random.Random(seed)
    if not deltas:
        return (float("nan"), float("nan"))
    means = sorted(statistics.mean(deltas[rng.randrange(len(deltas))]
                                   for _ in range(len(deltas)))
                   for _ in range(n_boot))
    return (means[int(alpha / 2 * n_boot)],
            means[min(int((1 - alpha / 2) * n_boot), n_boot - 1)])


def non_inferior_paired(baseline: list[float], candidate: list[float],
                        margin: float = 0.005, seed: int = 7) -> dict:
    deltas = [c - b for b, c in zip(baseline, candidate)]
    lo, hi = bootstrap_ci(deltas, seed=seed)
    return {"mean_delta": statistics.mean(deltas), "ci95": [lo, hi], "lcb": lo,
            "margin": margin,
            "non_inferior": lo >= -margin - 1e-12, "n_pairs": len(deltas)}
