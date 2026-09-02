"""Worldpack registry: kind string -> factory. The only place domains are named."""
from __future__ import annotations

import json

FACTORIES: dict[str, tuple[callable, str]] = {}


def register(kind: str, description: str = ""):
    def deco(fn):
        if kind in FACTORIES:
            raise ValueError(f"duplicate world kind {kind}")
        FACTORIES[kind] = (fn, description)
        return fn
    return deco


def _discover() -> None:
    import importlib
    import os
    base = os.path.dirname(__file__)
    for entry in os.listdir(base):
        mp = os.path.join(base, entry, "manifest.json")
        if os.path.isfile(mp) and entry not in ("__pycache__",):
            kind = json.load(open(mp)).get("kind") if os.path.exists(mp) else None
            if kind and kind in FACTORIES:
                continue
            try:
                importlib.import_module(f"cogym_kernel.worlds.{entry}.world")
            except Exception:
                pass


def kinds() -> dict[str, str]:
    _discover()
    return {k: d for k, (_, d) in sorted(FACTORIES.items())}


def create(kind: str, **kwargs):
    if kind not in FACTORIES:
        _discover()
    if kind not in FACTORIES:
        raise KeyError(f"unknown world '{kind}'. known: {sorted(FACTORIES)}")
    return FACTORIES[kind][0](**kwargs)


@register("toy.signal_game", "hidden bit; buy noisy evidence; commit stance")
def _toy(**kw):
    from .toy import SignalWorld
    return SignalWorld(**kw)


@register("school", "allocation architecture evolution — pools of strategies, dynamic capital routing")
def _school(**kw):
    from .school.world import SchoolWorld
    return SchoolWorld(**kw)
