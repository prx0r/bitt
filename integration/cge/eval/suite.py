"""Layered dev/validation/secret suites + successive halving.

Secret instances come from OS entropy AT EVALUATION TIME; proposers never
see them (evolution_lab P0-1 rule). Objective is MAXIMIZED throughout;
cost-minimizing worlds emit objective=-cash_cost.
"""
from __future__ import annotations
import secrets as _secrets
from dataclasses import dataclass, field

Instance = tuple[str, int]


@dataclass
class LayeredSuite:
    dev: tuple[Instance, ...]
    validation: tuple[Instance, ...] = ()
    n_secret: int = 8
    secret_instance_fn: callable | None = None
    secret_space_start: int = 10_000
    halve_fraction: float = 0.5
    history: list = field(default_factory=list)

    def __post_init__(self):
        if not self.dev:
            raise ValueError("dev layer required")
        if not (0 < self.halve_fraction <= 1):
            raise ValueError("halve_fraction in (0,1]")

    def dev_layer(self):
        self.history.append(("dev", len(self.dev))); return self.dev

    def validation_layer(self):
        self.history.append(("validation", len(self.validation)))
        return self.validation

    def secret_layer(self):
        fn = self.secret_instance_fn or (lambda s: (f"secret-{s}", s))
        layer = []
        for _ in range(self.n_secret):
            seed = self.secret_space_start + _secrets.randbelow(1_000_000)
            inst, base = fn(seed)
            layer.append((str(inst), int(base)))
        self.history.append(("secret", len(layer)))
        return tuple(layer)

    def halve(self, ranked: list) -> list:
        keep = max(1, int(len(ranked) * self.halve_fraction))
        return ranked[:keep]


def run_layered_campaign(candidates, evaluate_fn, suite: LayeredSuite,
                         gates_pass_fn, promote_margin: float = 0.0) -> dict:
    """objective MAXIMIZED. Gates dominate. Fail-closed at every phase."""
    passing = [(c, m) for c in candidates
               if gates_pass_fn(m := evaluate_fn(c, suite.dev_layer()))]
    if not passing:
        return {"promoted": [], "status": "EXTINCT", "layer": "dev"}
    ranked = sorted(passing, key=lambda cm: -cm[1]["objective"])
    while len(ranked) > 2:
        ranked = suite.halve(ranked)
        re_eval = [(c, evaluate_fn(c, suite.dev_layer())) for c, _ in ranked]
        ranked = [cm for cm in sorted(
            re_eval, key=lambda cm: -cm[1]["objective"]) if gates_pass_fn(cm[1])]
        if not ranked:
            return {"promoted": [], "status": "EXTINCT", "layer": "halving"}
        ranked = ranked[:max(1, len(ranked))]
    champion = ranked[0][0]
    val_scores = [(c, evaluate_fn(c, suite.validation_layer() or suite.dev_layer()))
                  for c, _ in ranked]
    best_val = max(val_scores, key=lambda cm: cm[1]["objective"])[0]
    secret = suite.secret_layer()
    champ_secret = evaluate_fn(champion, secret)
    others = [evaluate_fn(c, secret)["objective"] for c, _ in ranked[1:]]
    delta = champ_secret["objective"] - (max(others) if others
                                         else champ_secret["objective"])
    promoted = delta >= promote_margin
    return {"promoted": [champion] if promoted else [],
            "status": "PROMOTED" if promoted else "NOT_PROMOTED",
            "champion": champion, "secret_delta": round(delta, 6),
            "validation_best": best_val}
