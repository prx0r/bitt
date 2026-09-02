"""BATS bridge — extend MWGym's BATS router with Bittensor-hosted models.

Bittensor subnets host inference endpoints that can serve as model providers.
This module adds them to BATSRouter.MODELS so the budget-aware router
can select them alongside conventional providers.

Also provides utilities for querying Bittensor inference via the network.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


# ─── Bittensor Model Provider Entries ────────────────────────────────

BITTENSOR_MODELS = {
    # Subnet 1 (Apex) — distributed research inference
    "bittensor.apex.research": {
        "provider": "bittensor-apex",
        "api_url": "",  # queried dynamically from metagraph
        "quality": 0.75,
        "cost_per_1k_in": 0.0002,
        "cost_per_1k_out": 0.0004,
        "free": False,
        "subnet": 1,
        "score_dimension": "research_quality",
    },
    # Subnet 67 (Harnyx) — deep research inference
    "bittensor.harnyx.research": {
        "provider": "bittensor-harnyx",
        "api_url": "",
        "quality": 0.8,
        "cost_per_1k_in": 0.0003,
        "cost_per_1k_out": 0.0006,
        "free": False,
        "subnet": 67,
        "score_dimension": "quality",
    },
    # Subnet 62 (Ridges) — code generation
    "bittensor.ridges.code": {
        "provider": "bittensor-ridges",
        "api_url": "",
        "quality": 0.85,
        "cost_per_1k_in": 0.0004,
        "cost_per_1k_out": 0.0008,
        "free": False,
        "subnet": 62,
        "score_dimension": "test_pass_rate",
    },
    # Free tier via Neurons (text prompting SN1)
    "bittensor.neurons.free": {
        "provider": "bittensor-neurons",
        "api_url": "https://neurons.bittensor.com/api/v1/generate",
        "quality": 0.6,
        "cost_per_1k_in": 0.0,
        "cost_per_1k_out": 0.0,
        "free": True,
        "subnet": 1,
    },
}


def patch_bats_router(router_cls):
    """Monkey-patch BATSRouter to include Bittensor models.

    Usage:
        from bittensor_gym.bats_bridge import patch_bats_router
        from mwgym.harnesses.pydantic_bats import BATSRouter
        patch_bats_router(BATSRouter)
    """
    original_models = getattr(router_cls, 'MODELS', {})
    original_models.update(BITTENSOR_MODELS)
    router_cls.MODELS = original_models


# ─── Bittensor Inference Client ──────────────────────────────────────

@dataclass
class BittensorInferenceResult:
    """Result from querying a Bittensor inference endpoint."""
    ok: bool = False
    content: str = ""
    model: str = ""
    provider: str = ""
    subnet: int = 0
    duration_ms: int = 0
    cost_tao: float = 0.0
    cost_usd: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0
    error: str = ""
    metadata: dict = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class BittensorInferenceClient:
    """Client for querying Bittensor subnet inference endpoints.

    Modes:
      1. DIRECT_AXON — query a specific axon via Bittensor protocol
      2. POOL_API — use a subnet's public API endpoint
      3. EMULATED — use the local cloned code (for development)
    """

    def __init__(self, network: str = "finney"):
        self.network = network
        self._axons: dict[int, list] = {}

    def query_axon(self, netuid: int, messages: list[dict],
                   timeout: int = 30) -> BittensorInferenceResult:
        """Query a subnet axon via Bittensor protocol.

        Requires bittensor package + wallet.
        """
        try:
            import bittensor as bt
        except ImportError:
            return BittensorInferenceResult(
                ok=False,
                error="bittensor not installed",
                subnet=netuid,
            )

        try:
            # Get metagraph
            subtensor = bt.subtensor(network=self.network)
            metagraph = subtensor.metagraph(netuid)

            # Find best axon (highest stake)
            axons = [
                axon for uid, axon in enumerate(metagraph.axons)
                if metagraph.active[uid] > 0
            ]
            if not axons:
                return BittensorInferenceResult(
                    ok=False, error="No active axons", subnet=netuid,
                )

            # Sort by stake, pick top
            axons.sort(key=lambda a: a.stake, reverse=True)
            target = axons[0]

            # Create synapse (subnet-specific)
            from bittensor import Synapse
            synapse = Synapse(
                messages=messages,
            )

            # Query
            t0 = time.time()
            response = target.query(synapse, timeout=timeout)
            duration_ms = int((time.time() - t0) * 1000)

            return BittensorInferenceResult(
                ok=True,
                content=str(response),
                subnet=netuid,
                duration_ms=duration_ms,
            )
        except Exception as e:
            return BittensorInferenceResult(
                ok=False, error=str(e), subnet=netuid,
            )

    def query_pool_api(self, api_url: str, messages: list[dict],
                       timeout: int = 30) -> BittensorInferenceResult:
        """Query a subnet's public pool API endpoint."""
        import http.client
        import ssl
        from urllib.parse import urlparse

        parsed = urlparse(api_url)
        ctx = ssl.create_default_context()
        conn = http.client.HTTPSConnection(parsed.hostname, context=ctx, timeout=timeout)

        payload = json.dumps({"messages": messages})
        headers = {"Content-Type": "application/json"}

        t0 = time.time()
        try:
            conn.request("POST", parsed.path, body=payload, headers=headers)
            resp = conn.getresponse()
            body = resp.read().decode()
            duration_ms = int((time.time() - t0) * 1000)

            if resp.status != 200:
                return BittensorInferenceResult(
                    ok=False, error=f"HTTP {resp.status}: {body[:500]}",
                    duration_ms=duration_ms,
                )

            result = json.loads(body)
            return BittensorInferenceResult(
                ok=True,
                content=result.get("content", ""),
                subnet=0,
                duration_ms=duration_ms,
                tokens_in=result.get("usage", {}).get("prompt_tokens", 0),
                tokens_out=result.get("usage", {}).get("completion_tokens", 0),
            )
        except Exception as e:
            return BittensorInferenceResult(
                ok=False, error=str(e),
                duration_ms=int((time.time() - t0) * 1000),
            )
        finally:
            conn.close()


# ─── Metagraph Utilities ─────────────────────────────────────────────

def fetch_subnet_info(netuid: int) -> dict:
    """Fetch live subnet info from metagraphed API."""
    import http.client
    import ssl

    ctx = ssl.create_default_context()
    conn = http.client.HTTPSConnection("api.metagraph.sh", context=ctx, timeout=15)

    try:
        conn.request("GET", f"/api/v1/subnets/{netuid}")
        resp = conn.getresponse()
        body = resp.read().decode()
        if resp.status == 200:
            return json.loads(body)
    except Exception:
        pass
    finally:
        conn.close()
    return {}


def fetch_taostats_subnet(netuid: int) -> dict:
    """Fetch subnet stats from Taostats API."""
    import http.client
    import ssl

    ctx = ssl.create_default_context()
    conn = http.client.HTTPSConnection("api.taostats.io", context=ctx, timeout=15)

    try:
        conn.request("GET", f"/v1/subnet/{netuid}")
        resp = conn.getresponse()
        body = resp.read().decode()
        if resp.status == 200:
            return json.loads(body)
    except Exception:
        pass
    finally:
        conn.close()
    return {}
