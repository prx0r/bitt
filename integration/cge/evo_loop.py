"""Async evolution campaign: population -> evaluate -> project Hydra ->
recipe proposes children -> repeat. Fail-closed under gates (quality first).
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Callable

from ..experience.client import HydraClient
from .recipes import EvolutionContext, propose_children


@dataclass
class CampaignConfig:
    world_kind: str
    suite: list[tuple[str, int]]
    gates_metric: str
    gates_value: float = 1.0
    objectives: tuple = ("cash_cost", "wall_latency_ms")
    generations: int = 3
    population: int = 6
    elite_k: int = 2


@dataclass
class GenerationRecord:
    generation: int
    evaluated: list = field(default_factory=list)


class EvolutionCampaign:
    """Async evolution over any worldpack. Hydra optional; receipts local."""

    def __init__(self, *, world_factory, policy_factory, runner,
                 config: CampaignConfig,
                 hydra_client: HydraClient | None = None,
                 recipe: str = "hydra_adoption",
                 search_space: dict | None = None,
                 seed: int = 7):
        self.world_factory = world_factory
        self.policy_factory = policy_factory
        self.runner = runner
        self.cfg = config
        self.hydra = hydra_client
        self.recipe = recipe
        self.search_space = search_space or {}
        self.rng = random.Random(seed)
        self.archive: list = []
        self.generations: list[GenerationRecord] = []
        self.stats = {"informed": 0, "fallback": 0, "projected": 0}

    # ---- evaluation ----

    async def _evaluate(self, cand) -> dict:
        import asyncio
        world = self.world_factory()
        policy = self.policy_factory(cand)
        tasks = [self.runner.run_episode(world, policy, instance_id=i, seed=s,
                                         candidate=cand)
                 for i, s in self.cfg.suite]
        recs = await asyncio.gather(*tasks)
        agg: dict[str, float] = {}
        for r in recs:
            for m in r.metrics.metrics:
                agg.setdefault(m.name, []).append(m.value)
        metrics = {k: sum(v) / len(v) for k, v in agg.items()}
        # gate: primary quality metric must be perfect on every episode
        gate_ok = all(r.metrics.get(self.cfg.gates_metric) == 1.0
                      for r in recs)
        return {"candidate": cand, "metrics": metrics, "gate_ok": gate_ok,
                "records": recs}

    # ---- hydra projection ----

    async def _project(self, gen_idx: int, evaluated: list) -> None:
        if not self.hydra:
            return
        try:
            from ..experience.client import Edge, NodeRef
            fam = NodeRef("WorldFamily", f"worldfamily:{self.cfg.world_kind}", {})
            await self.hydra.ensure_node(fam)
            for e in evaluated:
                pol = NodeRef("Policy",
                              f"{self.cfg.world_kind}:{e['candidate'].candidate_id[:24]}",
                              {"kind_label": e["candidate"].kind})
                await self.hydra.ensure_node(pol)
                edge = Edge("RAN_ON", pol, fam, {
                    "quality_pass": bool(e["gate_ok"]),
                    **{k: round(v, 4) for k, v in e["metrics"].items()
                       if isinstance(v, (int, float))}}).to_node()
                await self.hydra.ensure_node(edge)
            self.stats["projected"] += 1
        except Exception as exc:  # noqa: BLE001 - derived memory never fatal
            print(f"[evolve] hydra projection failed: {exc}")

    # ---- proposal ----

    async def _leaders(self) -> list[dict]:
        if not self.hydra:
            return []
        try:
            return await self.hydra.query(
                "MATCH (e:REL_RAN_ON {dst_key: $f}) WHERE e.quality_pass = true "
                "RETURN e.src_key AS pk, e.mean_utility_bps AS util, "
                "e.cash_cost AS cost ORDER BY cost ASC LIMIT $n",
                {"f": f"worldfamily:{self.cfg.world_kind}", "n": 5},
                ("pk", "util", "cost"))
        except Exception:
            return []

    def _propose(self, elites: list, n: int, leaders: list[dict] | None = None) -> list:
        leaders = leaders or []
        ctx = EvolutionContext(
            elite_configs=[e.config for e in elites],
            scorecard=self.last_scorecard,
            hydra_leaders=leaders,
            search_space=self.search_space, rng=self.rng)
        from .recipes import propose_children
        kids_cfg = propose_children(self.recipe, ctx, n)
        informed = bool(leaders) and self.recipe in ("hydra_adoption",
                                                     "champion_lineage")
        self.stats["informed" if leaders else "fallback"] += len(kids_cfg)
        out = []
        for i, cfg in enumerate(kids_cfg):
            parent = elites[i % len(elites)] if elites else seeds_artifact(self.cfg)
            out.append(type(parent)(kind=parent.kind,
                                    version=str(int(parent.version) + 1),
                                    config=cfg,
                                    parent_ids=(parent.candidate_id,),
                                    provenance={"recipe": self.recipe,
                                                "hydra_informed": informed}))
        return out

    # ---- main loop ----

    async def run(self, seeds: list) -> list:
        import asyncio
        population = seeds[: self.cfg.population]
        winners: list = []
        for gen in range(self.cfg.generations):
            evaluated = await asyncio.gather(*(self._evaluate(c) for c in population))
            self.generations.append(GenerationRecord(gen, evaluated))
            await self._project(gen, evaluated)

            passing = [e for e in evaluated if e["gate_ok"]]
            if not passing:
                break                                   # fail closed
            ranked = sorted(passing, key=lambda e: tuple(
                (e["metrics"].get(o, 0) if o != "cash_cost"
                 else -(e["metrics"].get("cash_cost") or 0))
                for o in self.cfg.objectives), reverse=True)
            winners = [e["candidate"] for e in ranked[: self.cfg.elite_k]]
            self.archive.extend(w for w in winners if w not in self.archive)
            self.last_scorecard = [
                {"config": e["candidate"].config, "metrics": e["metrics"]}
                for e in evaluated]
            if gen < self.cfg.generations - 1:
                leaders = []
                if self.hydra:
                    try:
                        leaders = await self._leaders()
                    except Exception:  # noqa: BLE001
                        leaders = []
                children = self._propose(winners,
                                         self.cfg.population - len(winners),
                                         leaders=leaders)
                population = winners + children
        return winners


def seeds_artifact(cfg):
    from ..kernel.contracts import CandidateArtifact
    return CandidateArtifact(kind=f"{cfg.world_kind}_policy", version="1", config={})
