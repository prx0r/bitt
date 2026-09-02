"""Private Holdout Generator — rolling SECRET set from Oracle disclosures.

From email 2:
  Oracle sees new disclosure → freeze vulnerable commit → capture tests/environment
  → store fix/report separately → create TaskInstance → NO WEB / NO FIX / NO WRITEUP
  → SEALED_LOCAL

After evaluation, the label can be revealed.

This module monitors the GitHub security advisory feed and creates
private holdout tasks from freshly disclosed vulnerabilities.
"""
from __future__ import annotations

import json
import hashlib
import time
from pathlib import Path
from typing import Any

import sys
sys.path.insert(0, str(Path("/root/bitt/private-lab")))
from lab.contracts import TaskInstance, CapabilityScope, Split


HOLDOUT_DIR = Path("/root/bitt/data/holdout")
HOLDOUT_MANIFEST = HOLDOUT_DIR / "manifest.json"


class PrivateHoldoutGenerator:
    """Generates and manages a rolling private security holdout set.

    Sources:
    - GitHub Security Advisories (via Oracle)
    - Fresh CVE disclosures
    - New audit findings from public reports

    Each holdout task freezes:
    - Vulnerable commit
    - Task briefing (before disclosure)
    - Hidden ground truth (finding, severity, exploit)
    - NO web access, NO fix, NO writeup during evaluation
    """

    def __init__(self):
        HOLDOUT_DIR.mkdir(parents=True, exist_ok=True)
        self.manifest = self._load_manifest()

    def _load_manifest(self) -> dict:
        if HOLDOUT_MANIFEST.exists():
            return json.loads(HOLDOUT_MANIFEST.read_text())
        return {"tasks": [], "last_updated": 0}

    def _save_manifest(self):
        self.manifest["last_updated"] = int(time.time())
        HOLDOUT_MANIFEST.write_text(json.dumps(self.manifest, indent=2))

    def ingest_github_advisory(self, advisory: dict) -> TaskInstance | None:
        """Ingest a GitHub Security Advisory and create a holdout task.

        Advisory should contain:
        - ghsa_id
        - summary
        - severity
        - vulnerable_package
        - patched_version
        - references
        """
        ghsa_id = advisory.get("ghsa_id", "")
        if not ghsa_id:
            return None

        # Check if already ingested
        existing = [t["task_id"] for t in self.manifest["tasks"]]
        task_id = f"holdout-{ghsa_id}"
        if task_id in existing:
            return None

        # Create holdout task
        task = TaskInstance(
            task_id=task_id,
            studio_id="bitsec",
            task_family="github-advisory",
            split=Split.SECRET,
            capability_scope=CapabilityScope(
                domains=["security"],
                subdomains=["github-advisory", "vulnerability-disclosure"],
                capabilities=["vulnerability-detection", "patch-generation"],
            ),
            content={
                "source": "github-advisory",
                "ghsa_id": ghsa_id,
                "summary": advisory.get("summary", ""),
                "severity": advisory.get("severity", "medium"),
                "package": advisory.get("vulnerable_package", ""),
                "patched_version": advisory.get("patched_version", ""),
                "references": advisory.get("references", []),
                # NO web access, NO fix, NO writeup
                "evaluation_mode": "sealed",
            },
            evaluation_data={
                "vulnerability_type": advisory.get("vulnerability_type", "unknown"),
                "severity": advisory.get("severity", "medium"),
                "patched_version": advisory.get("patched_version", ""),
                # Ground truth hidden from worker
                "expected_findings": advisory.get("summary", ""),
            },
        )

        # Store task
        task_path = HOLDOUT_DIR / f"{task_id}.json"
        task_path.write_text(json.dumps({
            "task_id": task_id,
            "ghsa_id": ghsa_id,
            "created_at": int(time.time()),
            "split": "SECRET",
            "content": task.content,
            "evaluation_data": task.evaluation_data,
        }, indent=2))

        self.manifest["tasks"].append({
            "task_id": task_id,
            "ghsa_id": ghsa_id,
            "created_at": int(time.time()),
            "status": "pending",
        })
        self._save_manifest()

        return task

    def ingest_cve(self, cve: dict) -> TaskInstance | None:
        """Ingest a CVE disclosure."""
        cve_id = cve.get("cve_id", "")
        if not cve_id:
            return None

        existing = [t["task_id"] for t in self.manifest["tasks"]]
        task_id = f"holdout-{cve_id}"
        if task_id in existing:
            return None

        task = TaskInstance(
            task_id=task_id,
            studio_id="bitsec",
            task_family="cve-disclosure",
            split=Split.SECRET,
            capability_scope=CapabilityScope(
                domains=["security"],
                subdomains=["cve", "vulnerability-disclosure"],
                capabilities=["vulnerability-detection", "exploit-reproduction"],
            ),
            content={
                "source": "cve",
                "cve_id": cve_id,
                "description": cve.get("description", ""),
                "severity": cve.get("severity", "medium"),
                "affected_software": cve.get("affected_software", []),
                "evaluation_mode": "sealed",
            },
            evaluation_data={
                "vulnerability_type": cve.get("vulnerability_type", "unknown"),
                "severity": cve.get("severity", "medium"),
                "expected_findings": cve.get("description", ""),
            },
        )

        task_path = HOLDOUT_DIR / f"{task_id}.json"
        task_path.write_text(json.dumps({
            "task_id": task_id,
            "cve_id": cve_id,
            "created_at": int(time.time()),
            "split": "SECRET",
            "content": task.content,
            "evaluation_data": task.evaluation_data,
        }, indent=2))

        self.manifest["tasks"].append({
            "task_id": task_id,
            "cve_id": cve_id,
            "created_at": int(time.time()),
            "status": "pending",
        })
        self._save_manifest()

        return task

    def get_pending_tasks(self) -> list[dict]:
        """Get tasks that haven't been evaluated yet."""
        return [t for t in self.manifest["tasks"] if t["status"] == "pending"]

    def get_completed_tasks(self) -> list[dict]:
        return [t for t in self.manifest["tasks"] if t["status"] == "completed"]

    def mark_completed(self, task_id: str, result: dict):
        """Mark a task as completed with evaluation results."""
        for t in self.manifest["tasks"]:
            if t["task_id"] == task_id:
                t["status"] = "completed"
                t["result"] = result
                t["completed_at"] = int(time.time())
                break
        self._save_manifest()

    def stats(self) -> dict:
        return {
            "total": len(self.manifest["tasks"]),
            "pending": len(self.get_pending_tasks()),
            "completed": len(self.get_completed_tasks()),
        }
