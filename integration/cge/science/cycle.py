"""Science cycle stub: findings v2 builder + verification wiring.

Full port of legacy experiments/orchestrator/cycle.py + verify.py.
This stub provides the findings schema builder; LLM review is injected.
"""
from __future__ import annotations
import json, os, time

def build_findings(cycle_id: str, spec: dict, receipt: dict) -> dict:
    from ..eval.gates import wilson
    n = len(receipt.get("winners", []))
    return {
        "schema": "cogym.findings.v2",
        "cycle_id": cycle_id,
        "ts": time.time(),
        "hypothesis": spec.get("hypothesis",""),
        "world_kind": spec.get("world_kind"),
        "quantitative": {"n_winners": n},
        "receipt_path": receipt.get("receipt_path"),
        "raw_receipt": receipt,
        "mode": "PILOT" if receipt.get("n_decided", 0) < 30 else "CONFIRMATORY",
    }

def review_and_seed(findings: dict, spec: dict, cycle_dir: str) -> dict:
    return {"verdict": "INCONCLUSIVE", "rationale": "stub"}

def next_spec(spec: dict, cycle_id: str, parsed: dict) -> dict:
    nxt = dict(spec); nxt["hypothesis"] = parsed.get("sub_hypothesis", spec.get("hypothesis",""))
    return nxt
