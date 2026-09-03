# /bitt — 129-subnet miner income oracle: exact 0.1 TAO seat tracking + DB/code handoff

**Date:** Wed, 2 Sep 2026 19:06:48 -0700

---

I completed the first all-network miner-opportunity sweep and packaged the technical handoff.

The key correction is now baked into the design: the oracle does NOT rank subnets by registered miner count or total miner pool. It reconstructs the actual settled payout vector and asks how many accessible non-validator hotkeys are earning at least each threshold:

N_0.01, N_0.05, N_0.1, N_0.25, N_0.5, N_1, N_2, N_5, N_10.

It also stores p10/p25/median/p75/p90 payouts, top-1/top-3 share, HHI, Gini, effective earners, registration burn, and exact threshold-seat membership so we can measure seat persistence over time.

IMPORTANT DATA INTEGRITY NOTE
The attached SQLite file is explicitly marked BOOTSTRAP_ONLY_NOT_LIVE_CHAIN. I did not fabricate a 129×UID exact current payout DB from explorer aggregate data. Your existing /bitt/oracle/chain_scanner.py already has the correct block-pinned metagraph accounting, but currently discards most of the useful detail by retaining only the top 10 emitters. The attached miner_oracle.py persists EVERY non-validator UID and generates the exact income board in one Finney-connected run.

RUN IT

cd /root/bitt
pip install bittensor
python /path/to/miner_oracle.py init --db /root/bitt/miner_oracle.sqlite
python /path/to/miner_oracle.py scan --db /root/bitt/miner_oracle.sqlite

Continuous:

python /path/to/miner_oracle.py daemon --db /root/bitt/miner_oracle.sqlite --network finney --interval 600

The first scan produces exact current values for every subnet. Ten-minute scans then give us historical seat duration/churn; later optimize to scan a subnet only when its epoch changes.

PRIMARY QUERY

SELECT *
FROM latest_income_board
WHERE n_01 > 0
ORDER BY n_01 DESC, p25_tao_day DESC, burn_tao ASC;

This answers: where are the most 0.1 TAO/day seats right now?

Exact current hotkeys earning >=0.1:

SELECT * FROM latest_01_seats;

WHY THIS IS CORRECT
Bittensor settles emission at subnet epochs. The metagraph neuron emission field is the latest settled per-tempo alpha payout. For an accessible non-validator miner:

epochs_per_day = 7200 / tempo
alpha_epoch = neuron.emission / 1e9
alpha_day = alpha_epoch * epochs_per_day
tao_day = alpha_day * alpha_price_tao

Official reference: https://www.bittensor.com/docs/concepts/emissions
TAOStats historical metagraph: https://api.taostats.io/api/metagraph/history/v1
Metagraphed current metagraph: https://api.metagraph.sh/api/v1/subnets/{netuid}/metagraph
Metagraphed economics: https://api.metagraph.sh/api/v1/economics

HISTORICAL
Use TAOStats metagraph/history for full historical per-neuron emission/daily_reward, and Metagraphed neuron history as keyless verification/fallback. Key identities by subnet instance + UID + hotkey + registration block; never join on netuid/UID alone because both can be reused.

SUBMISSION STATS
There is no universal on-chain submission-count field. The correct architecture is:

1. UNIVERSAL CHAIN LAYER — exact payout vector for all 129.
2. MECHANISM ADAPTERS — Harnyx/RedTeam/Ditto/Apex/Synth/etc APIs and repos for submissions, accepted artifacts, score cutoffs, champion age, local evaluator score.
3. FINAL ARBITER — the chain payout vector. If an app says 50 competitors but only three non-validator hotkeys actually receive meaningful emission, it is a three-seat market economically.

Priority adapters:
- Harnyx: champion/latest submissions/batch comparison/artifact results.
- RedTeam: accepted/rejected/decaying submissions, score, similarity.
- Ditto: current artifact/order leaderboard.
- Apex: competition-specific submissions.
- Synth: competition leaderboard.
- Minos/Gradients: current tournament/config leaderboards.

SEAT STABILITY
After a week, calculate Jaccard continuity and consecutive time above threshold. I care about 0.1/0.25/0.5/1 TAO separately. A market with 8 stable 0.1 seats is better recurring income than one with 25 seats that completely rotate every epoch.

INITIAL ALL-NETWORK SCREEN
The current 129-subnet directory and live subnet pages identify several places that deserve exact payout-vector interrogation first. This is screening only; the attached scanner replaces these aggregate estimates with exact seats.

INCOME / BROAD-PAYOUT PRIORITY
1. SN61 RedTeam — ~26.44 TAO/day miner pool in the recent live screen; no GPU; accepted submissions can earn and decay rather than one permanent winner.
2. SN67 Harnyx — 19.79 TAO/day miner pool today; explicit participant tiers + novelty; no GPU; current aggregate est ~0.152 TAO/day per listed miner equivalent.
3. SN88 Investing — 12.34 TAO/day; no GPU; aggregate sits near the 0.1/day threshold, so exact tail is important.
4. SN79 MVTRX — large miner population; recent aggregate around 0.1/day neighborhood; inspect actual tail.
5. SN13 Data Universe — broad service mining; very large miner population; likely tail worth measuring.
6. SN50 Synth — multiple competitions/softmax-style allocation; exact tail matters more than average.
7. SN41 Almanac — 15.56 TAO/day miner pool today; CPU/no GPU; eligibility and payout tail need exact scan.
8. SN74 Gittensor — 12.74 TAO/day today; aggregate est ~1.42 TAO/day from the displayed per-epoch figure if evenly representative, but exact distribution is what matters.
9. SN96 Verathos — 29.58 TAO/day; 4090+ requirement; contribution-based inference scoring.
10. SN53 engy — 95.08 TAO/day; high reward but substantial GPU requirement.
11. SN102 ConnitoAI — 32.20 TAO/day; very high nominal per-miner aggregate, GPU, concentration unknown.
12. SN12 Compute Horde — 15.52 TAO/day; A6000 infrastructure.
13. SN77 Liquidity — 18.32 TAO/day but this is capital/LP mining, not ordinary software mining.
14. SN82 Compelle — 12.81 TAO/day, young/no GPU, but the aggregate currently looks suspiciously like one effective seat; verify before spending.
15. SN118 Ditto — ~34.15 TAO/day, no GPU, but mechanism-specific competition risk.

JACKPOT / CONCENTRATED
- SN56 Gradients: ~50.78 TAO/day but tournament concentration.
- SN97 Albedo: winner gets 100% of miner emission.
- Ridges: current winner-take-all mechanism.
- Poker44 / Thirty Spokes / similar duel/champion markets: separate jackpot queue.

ALERTS TO BUILD
- N_0.1 rises >=3 seats or >=20% in 24h while burn stays low.
- N_0.1 >=5 AND p25 >=0.1 AND 7d seat survival >=60%.
- Miner pool rises + N_0.1 rises but registrations have not risen yet: this is especially interesting because reward breadth expanded before competition reacted.
- Local benchmark crosses estimated paid cutoff.

The ZIP contains:
- miner_oracle.py — runnable all-129 Finney scanner/daemon
- miner_oracle_schema.sql
- miner_oracle_bootstrap.sqlite
- README.md — full coding instructions and acceptance criteria
- queries.sql
- initial_sweep_candidates.json
- initial_129_sweep_skeleton.json

Recommended immediate implementation: merge the payout persistence logic into /bitt/oracle/chain_scanner.py, run it continuously for 7 days, and build Harnyx + RedTeam submission adapters in parallel. After the FIRST live scan, sort by N_0.1 and inspect the top 20 mechanisms. That becomes the actual low-hanging-TAO queue.
