"""Opportunity Registry — ranks all 129 subnets by cost × reward × lab-fit × learnability.

This is what Hydra should learn next.
"""
import sqlite3
import json
from pathlib import Path


DB_PATH = Path("/root/bitt/market.duckdb")


def get_all_subnets() -> list[dict]:
    """Get all subnets from TAOStats."""
    import http.client, ssl
    from vault import Vault

    v = Vault()
    ctx = ssl.create_default_context()
    api_key = v.get("taostats_api_key")

    conn = http.client.HTTPSConnection("api.taostats.io", context=ctx, timeout=30)
    conn.request("GET", "/api/subnet/latest/v1", headers={
        "Authorization": api_key,
        "accept": "application/json",
    })
    resp = conn.getresponse()
    data = json.loads(resp.read())
    conn.close()
    return data.get("data", [])


def rank_opportunities(subnets: list[dict]) -> list[dict]:
    """Rank all subnets by opportunity score.

    Score = reward × lab_fit × learnability / cost
    """
    ranked = []
    for s in subnets:
        netuid = s.get("netuid", 0)
        emission = s.get("emission", 0)
        validators = s.get("validators", 0)
        active_miners = s.get("active_miners", 0)
        registration_cost = s.get("neuron_registration_cost", 0)

        # Simple scoring
        reward = emission / max(active_miners, 1)  # TAO per miner
        cost = registration_cost / 1e9  # Convert from rao
        competition = active_miners / max(validators * 10, 1)

        # Lab fit (simplified)
        lab_fit = 0.5  # Default
        if netuid in [60, 61, 62, 66, 67, 74, 88]:
            lab_fit = 0.9  # High fit for security/coding/strategy subnets

        # Score
        score = (reward * lab_fit) / max(cost, 0.001) * (1 - competition * 0.5)

        ranked.append({
            "netuid": netuid,
            "name": s.get("name", f"SN{netuid}"),
            "score": score,
            "reward": reward,
            "cost": cost,
            "competition": competition,
            "lab_fit": lab_fit,
            "emission": emission,
            "validators": validators,
            "active_miners": active_miners,
        })

    ranked.sort(key=lambda x: x["score"], reverse=True)
    return ranked


if __name__ == "__main__":
    subnets = get_all_subnets()
    print(f"Subnets: {len(subnets)}")

    ranked = rank_opportunities(subnets)
    print(f"\n=== TOP 10 OPPORTUNITIES ===")
    for r in ranked[:10]:
        print(f"  SN{r['netuid']:3d} {r['name']:20s}: score={r['score']:.3f} reward={r['reward']:.4f} lab_fit={r['lab_fit']:.1f}")
