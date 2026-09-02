"""Three-tier verification (ported): deterministic → binary criteria → review.
Final statuses: SUPPORTED / REFUTED / PROVISIONAL / DISPUTED / BLOCKED."""
from __future__ import annotations
import json
import os
from typing import Callable


def deterministic_checks(findings: dict, receipt_path: str | None = None) -> dict:
    checks = []

    def add(name, ok, detail=""):
        checks.append({"check": name, "pass": bool(ok), "detail": detail})

    add("schema_v1", findings.get("schema") == "cogym.findings.v2",
        f"schema={findings.get('schema')}")
    add("hypothesis_present", bool(findings.get("hypothesis")))
    q = findings.get("quantitative", {})
    raw = findings.get("raw_receipt") or {}
    add("winners_consistent",
        q.get("n_winners") == len(raw.get("winners", [])))
    if receipt_path and os.path.exists(receipt_path):
        disk = json.load(open(receipt_path))
        add("receipt_file_matches",
            json.dumps(disk.get("configs"), sort_keys=True)
            == json.dumps(raw.get("configs"), sort_keys=True))
    failed = [c for c in checks if not c["pass"]]
    return {"tier": "deterministic", "pass": not failed, "checks": checks}


def binary_criteria_check(findings: dict, spec: dict,
                          llm_fn: Callable[[str], str] | None = None) -> dict:
    criteria = spec.get("success_criteria")
    if not llm_fn:
        return {"tier": "binary", "outcome": "ABSTAIN",
                "criteria": [], "mode": "abstained"}
    user = json.dumps({"hypothesis": findings.get("hypothesis"),
                       "success_criteria": criteria,
                       "quantitative_findings": findings.get("quantitative"),
                       "instruction": 'For EACH criterion answer YES/NO/'
                       'UNCERTAIN with <=25-word evidence. Reply ONLY JSON '
                       '{"criteria":[{"criterion","answer","evidence"}],'
                       '"overall":"SUPPORTED|REFUTED|ABSTAIN"}'})
    raw = llm_fn(user)
    try:
        s, e = raw.find("{"), raw.rfind("}")
        parsed = json.loads(raw[s:e + 1])
        overall = str(parsed.get("overall", "ABSTAIN")).upper()
        return {"tier": "binary", "mode": "llm",
                "criteria": parsed.get("criteria", []),
                "outcome": overall if overall in ("SUPPORTED", "REFUTED",
                                                  "ABSTAIN") else "ABSTAIN"}
    except (json.JSONDecodeError, ValueError, AttributeError):
        return {"tier": "binary", "outcome": "ABSTAIN", "mode": "abstained"}


def reconcile(det: dict, binary: dict, review_verdict: str | None) -> dict:
    if not det["pass"]:
        return {"status": "BLOCKED", "reason": "deterministic failure"}
    if binary["outcome"] == "ABSTAIN":
        return {"status": "PROVISIONAL", "reason": "verifier abstained"}
    if review_verdict and binary["outcome"] != review_verdict:
        return {"status": "DISPUTED",
                "reason": f"binary={binary['outcome']} vs review={review_verdict}"}
    return {"status": binary["outcome"], "reason": "tiers agree"}

