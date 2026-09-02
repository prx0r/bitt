"""Evolution recipes registry. Ported from canonical (14 recipes).

Same contract: recipe(ctx, n_children) -> child configs. Recipes never see
evaluators/gates/oracles. See docs/GUIDE.md for the catalog.
"""
from __future__ import annotations
import random
from dataclasses import dataclass, field
from typing import Any, Callable

RECIPES: dict[str, dict] = {}


@dataclass
class EvolutionContext:
    elite_configs: list[dict]
    scorecard: list[dict]          # [{"config":…, "metrics": {name: value}}]
    hydra_leaders: list[dict]
    search_space: dict
    rng: random.Random


def recipe(name: str, family: str, description: str):
    def deco(fn):
        RECIPES[name] = {"fn": fn, "family": family, "description": description}
        return fn
    return deco


def propose_children(name: str, ctx: EvolutionContext, n_children: int) -> list[dict]:
    if name not in RECIPES:
        raise KeyError(f"unknown recipe '{name}'. known: {sorted(RECIPES)}")
    return RECIPES[name]["fn"](ctx, n_children)


def sample_config(space: dict, rng: random.Random) -> dict:
    cfg: dict[str, Any] = {}
    for key, spec in space.items():
        if isinstance(spec, list):
            cfg[key] = rng.choice(spec)
        elif isinstance(spec, dict) and "min" in spec:
            vals = list(range(spec["min"], spec["max"] + 1, spec.get("step", 1)))
            cfg[key] = rng.choice(vals or [spec["min"]])
        else:
            cfg[key] = spec
    return cfg


def mutate_config(cfg: dict, space: dict, rng: random.Random,
                  rate: float = 0.5) -> dict:
    child = dict(cfg)
    for key, spec in space.items():
        if rng.random() < rate:
            child[key] = sample_config({key: spec}, rng)[key]
    return child


def crossover(a: dict, b: dict, rng: random.Random) -> dict:
    keys = set(a) | set(b)
    return {k: (a.get(k, b.get(k)) if rng.random() < 0.5 else b.get(k, a.get(k)))
            for k in keys}


def _random_search(ctx, n):
    return [sample_config(ctx.search_space, ctx.rng) for _ in range(n)]


def _elitist_mutation(ctx, n):
    if not ctx.elite_configs:
        return _random_search(ctx, n)
    return [mutate_config(ctx.elite_configs[i % len(ctx.elite_configs)],
                          ctx.search_space, ctx.rng) for i in range(n)]


recipe("random_search", "standard",
       "Uniform sampling of the declared space. The honest baseline.")(_random_search)
recipe("elitist_mutation", "standard",
       "(mu+lambda): copy elites, resample genes p=0.5.")(_elitist_mutation)


@recipe("tournament", "standard", "Tournament select + crossover + mutate.")
def _tournament(ctx, n):
    scored = [s for s in ctx.scorecard if s.get("config")]
    if len(scored) < 2:
        return _elitist_mutation(ctx, n)
    def pick(k=3):
        pool = [scored[ctx.rng.randrange(len(scored))] for _ in range(min(k, len(scored)))]
        return min(pool, key=lambda s: s["metrics"].get("cash_cost") or 0)
    kids = []
    for _ in range(n):
        a, b = pick(), pick()
        kids.append(mutate_config(crossover(a["config"], b["config"], ctx.rng),
                                  ctx.search_space, ctx.rng))
    return kids


@recipe("successive_halving", "standard",
        "Narrow around top half of scorecard with light mutation.")
def _halving(ctx, n):
    scored = sorted([s for s in ctx.scorecard if s.get("config")],
                    key=lambda s: s["metrics"].get("cash_cost")
                    if s["metrics"].get("cash_cost") is not None else 9e9)
    surv = [s["config"] for s in scored[: max(1, len(scored) // 2)]] \
        or _random_search(ctx, n)
    return [mutate_config(surv[i % len(surv)], ctx.search_space, ctx.rng,
                          rate=0.3) for i in range(n)]


@recipe("hydra_adoption", "standard",
        "Children adopt config shapes of graph-known leaders; fallback elites.")
def _hydra_adoption(ctx, n):
    if not ctx.hydra_leaders or not ctx.elite_configs:
        return _elitist_mutation(ctx, n)
    kids = []
    for i in range(n):
        base = ctx.elite_configs[i % len(ctx.elite_configs)]
        kid = mutate_config(base, ctx.search_space, ctx.rng, rate=0.25)
        kid["adopted_from"] = str(
            ctx.hydra_leaders[i % len(ctx.hydra_leaders)]["pk"])
        kids.append(kid)
    return kids


@recipe("champion_lineage", "reasoning",
        "Spawn along Hydra-proven lineages (ancestry via graph traversal).")
def _champion_lineage(ctx, n):
    if not ctx.hydra_leaders:
        return _elitist_mutation(ctx, n)
    kids = []
    for i in range(n):
        leader = ctx.hydra_leaders[i % len(ctx.hydra_leaders)]
        base = (ctx.elite_configs[i % len(ctx.elite_configs)]
                if ctx.elite_configs else {})
        kid = mutate_config(base, ctx.search_space, ctx.rng, rate=0.35)
        kid["lineage_root"] = str(leader["pk"]).split(":")[-1]
        kids.append(kid)
    return kids


DEFAULT_CHAIN_STEPS = ["PACKET", "ANALYZE_SUPPORT", "ANALYZE_REFUTE",
                       "ATTACK_WEAK_POINT", "JUDGE", "COMMIT"]


@recipe("chain_assembly", "reasoning",
        "Evolve reasoning-chain composition: reorder/drop/insert steps and "
        "model routing. Structure beats chatter (E-C2 evidence).")
def _chain_assembly(ctx, n):
    steps_space = ctx.search_space.get("steps") or DEFAULT_CHAIN_STEPS
    bases = ctx.elite_configs or [{"steps": list(steps_space)[:3]}]
    kids = []
    for i in range(n):
        base = dict(bases[i % len(bases)])
        steps = list(base.get("steps") or steps_space[:3])
        op = ctx.rng.choice(["reorder", "drop", "insert", "swap_route", "none"])
        if op == "reorder" and len(steps) > 2:
            a, b = ctx.rng.randrange(len(steps)), ctx.rng.randrange(len(steps))
            steps[a], steps[b] = steps[b], steps[a]
        elif op == "drop" and len(steps) > 2:
            steps.pop(ctx.rng.randrange(len(steps)))
        elif op == "insert":
            cand = [x for x in steps_space if x not in steps]
            if cand:
                steps.insert(ctx.rng.randrange(len(steps) + 1), ctx.rng.choice(cand))
        elif op == "swap_route":
            base["model_routing"] = ctx.rng.choice([{"JUDGE": "STRONG"},
                                                    {"JUDGE": "FAST"}, {}])
        kid = {"steps": steps}
        if ctx.rng.random() < 0.3:
            kid["parallel_first_wave"] = ctx.rng.random() < 0.5
        kid["model_routing"] = base.get("model_routing", {})
        kids.append(kid)
    return kids


@recipe("quality_diversity", "standard",
        "MAP-Elites style archive: bin by (style-family x cost bucket), keep "
        "elite per cell, spawn from DIVERSE elites.")
def _qd(ctx, n):
    cells: dict[tuple, tuple] = {}
    for s in ctx.scorecard:
        cfg = s.get("config") or {}
        style = str(cfg.get("style") or cfg.get("strategy")
                    or cfg.get("policy") or "none")
        cost = s["metrics"].get("cash_cost")
        bucket = 0 if cost is None else min(4, int(cost / 0.02))
        obj = s["metrics"].get("found") or s["metrics"].get("correct") \
            or s["metrics"].get("direction_accuracy") or 0.0
        cell = (style.split("_")[0], bucket)
        if cell not in cells or obj >= cells[cell][0]:
            cells[cell] = (obj, cfg)
    parents = [cfg for (_, cfg) in cells.values()] or ctx.elite_configs
    return [mutate_config(parents[i % len(parents)] if parents else {},
                          ctx.search_space, ctx.rng) for i in range(n)]


__all__ = ["EvolutionContext", "RECIPES", "propose_children", "sample_config",
           "mutate_config", "crossover"]


@recipe("context_seed", "reasoning",
        "Children carry seed_context drawn from Hydra leaders — Reflexion-style "
        "episodic seeding, optional and caller-supplied.")
def _context_seed(ctx, n):
    if not ctx.hydra_leaders:
        return _elitist_mutation(ctx, n)
    kids = []
    for i in range(n):
        base = (ctx.elite_configs[i % len(ctx.elite_configs)]
                if ctx.elite_configs else {})
        leader = ctx.hydra_leaders[i % len(ctx.hydra_leaders)]
        kid = mutate_config(base, ctx.search_space, ctx.rng)
        kid["seed_context"] = (
            f"Best-known on this family: {leader.get('pk')} "
            f"(util={leader.get('util')}, cost={leader.get('cost')}).")
        kids.append(kid)
    return kids


@recipe("style_sweep", "reasoning",
        "Reasoning STYLE as a gene: children sample style ids from the library.")
def _style_sweep(ctx, n):
    from . import reasoning_styles as RS
    styles = ctx.search_space.get("style") or RS.list_styles()
    kids = []
    for i in range(n):
        base = (ctx.elite_configs[i % len(ctx.elite_configs)]
                if ctx.elite_configs else {})
        kid = {k: v for k, v in base.items() if k != "style"}
        kid["style"] = styles[i % len(styles)]
        kids.append(kid)
    return kids
