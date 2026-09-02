# Phala/dstack Architecture Update — 2026-09-02

## Key Insight

Phala/dstack is not a future integration. It's an **existing architectural dependency** that Treasury/Grant completes.

## The Full Run (Future State)

```
              HUMAN
                │
                ▼
             Mandate
                │
                ▼
             MoltGrant
                │
                ▼
           Run requested
                │
                ▼
       dstack CVM launched
                │
                ▼
       fresh attestation
                │
       ┌────────┴────────┐
       │                 │
       ▼                 ▼
   MoltVault          Treasury
       │                 │
 release API          release scoped
 capabilities         economic capability
       │                 │
       └────────┬────────┘
                ▼
         encrypted Molt
            released
                │
                ▼
            WorkerKit
                │
                ▼
            WorkerRun
                │
       ┌────────┼────────┐
       ▼        ▼        ▼
     work      spend    reward
       │        │        │
       └────────┼────────┘
                ▼
       signed RunReceipt
                │
                ▼
              Hydra
```

## What Phala Protects

Previously: private Worker/Molt configuration + API secrets
Now: private Worker/Molt configuration + API capabilities + economic capabilities

## Grant Becomes Attestation-Bound

```python
Grant(
    worker_version="sha256(...)",
    runtime_measurement="sha256(...)",
    allowed_action=ActionType.REGISTER,
    netuid=62,
    max_tao=0.20,
    required_tee="dstack",
    required_attestation_policy="strict",
)
```

## Receipt Gets TEE Evidence

```python
Receipt(
    plan_id="...",
    tx_hash="0xabc",
    runtime_attestation="attestation_report",
    signer_pubkey="ed25519...",
    signature="...",
)
```

## Molt Marketplace

```
Molt Marketplace
      ↓
CapabilityLease
      ↓
MoltGrant
      ↓
dstack attested invocation
      ↓
WorkerRun
      ↓
Receipt
      ↓
settlement + Hydra
```

## Neither Party Trusts the Other

- **Renter** doesn't trust Molt creator: Molt cannot exceed grant
- **Creator** doesn't trust renter: proprietary worker stays encrypted
- **Moltwork** doesn't trust worker: no treasury root key, no raw credentials
- **Marketplace** doesn't trust self-reported results: signed receipt bound to Molt + runtime + grant + execution + evaluation + economic outcome
