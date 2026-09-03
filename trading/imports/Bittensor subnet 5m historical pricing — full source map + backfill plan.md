# Bittensor subnet 5m historical pricing — full source map + backfill plan

**Date:** Wed, 2 Sep 2026 21:52:36 -0700

---

# Bittensor 5-minute subnet history — deep dive

## Bottom line

We can get what we want. The important discovery is that **there are already at least two indexed sources exposing native 5-minute subnet price data**, so we do NOT need to start by brute-forcing every historical block ourselves.

My recommended architecture for `/bitt` is:

1. **TAOstats TradingView 5m OHLCV** = primary bootstrap dataset.
2. **TAO.app 5m OHLC** = independent second source / cross-check.
3. **Official Bittensor archive node** = canonical verification + missing-point repair + historical pool state.
4. **Start our own collector immediately** so everything from today onward is ours at block-level resolution.
5. Add **TAO/USD 5m** so every alpha price exists both in TAO and USD.
6. Preserve **subnet generations / registration blocks** so a reused netuid is not treated as the same asset across deregistration/re-registration.

This gives Taotoad/Moltwork a genuinely useful research corpus rather than dependence on one dashboard.

---

# 1. TAOstats — strongest immediate source

## Native 5-minute OHLCV

TAOstats exposes the exact TradingView history endpoint behind its charts:

`GET https://api.taostats.io/api/dtao/tradingview/udf/history`

Parameters:

- `symbol=SUB-19`
- `resolution=5`
- `from=<unix timestamp>`
- `to=<unix timestamp>`

Documented resolutions are **1, 5, 15, 60 minutes**, plus 1D / 7D / 30D.

Response is proper OHLCV arrays:

- `t` timestamp
- `o` open
- `h` high
- `l` low
- `c` close
- `v` volume

Docs:
https://docs.taostats.io/reference/trading-view-history

This is the first endpoint I would hit. We should test:

- earliest available timestamp for several old subnets;
- maximum time span allowed per request;
- whether zero-volume 5m candles are emitted or omitted;
- exact meaning/unit of `v`;
- how deregistration/re-registration boundaries are represented.

The docs expose 5m explicitly but do not state the maximum historical retention/range per request. So build the downloader to chunk ranges (7d/30d), resume, hash raw responses, and tolerate missing buckets.

### TAOstats historical pool state

There is also:

`GET https://api.taostats.io/api/dtao/pool/history/v1`

Docs:
https://docs.taostats.io/reference/get-historical-subnet-pools

This is extremely useful because each historical row contains:

- netuid
- block number
- timestamp
- total TAO in pool
- total alpha
- alpha in pool
- alpha staked
- price in TAO
- liquidity
- market cap
- root proportion
- etc.

Frequencies: `by_block`, `by_hour`, `by_day`.

Max 200 rows/page.

I would NOT use by-block for the whole initial OHLC backfill — it would be millions of API calls/rows. Use the TradingView 5m endpoint for candles, then pull pool-history samples for validation and for richer factors such as reserve growth/liquidity.

### TAOstats subnet metadata history

`GET https://api.taostats.io/api/subnet/history/v1`

Docs:
https://docs.taostats.io/reference/get-subnet-history

Important because it includes registration timestamps / registration block information. This should feed our `subnet_generation` identity and prevent survivor/history bugs.

### TAOstats hosted archive RPC

TAOstats Pro exposes:

`wss://api.taostats.io/api/v1/rpc/ws/finney_archive?authorization=API_KEY`

Docs:
https://docs.taostats.io/reference/hosted-rpc-connectivity

Pricing currently shown:

- Free: $0, 5 API calls/min, 10k/month
- Standard: $49, 60/min, 50k/month
- Pro: $199, 240/min, 500k/month + Pro endpoints + RPC archive
- Enterprise: custom

Pricing/API keys:
https://taostats.io/pro/api-keys

For us, I would first see how far the TradingView history endpoint gets us on free/standard. Pro only becomes compelling if we need fast archive reconstruction.

---

# 2. TAO.app — excellent independent second source

TAO.app's OpenAPI is much better than I expected.

Docs:
https://api.tao.app/docs
OpenAPI:
https://api.tao.app/openapi.json

## Paid subnet OHLC endpoint

`GET /api/beta/subnets/ohlc`

Parameters include:

- `netuid`
- `start`
- `end`
- `interval_minutes`

`interval_minutes` accepts integers from 1 upward, so **5-minute OHLC is explicitly supported**.

Example conceptual call:

`/api/beta/subnets/ohlc?netuid=19&start=2025-02-13T21:40:00Z&end=2025-03-01T00:00:00Z&interval_minutes=5`

This is marked **Paid**.

Use it as an independent validator of TAOstats candles. If TAOstats and TAO.app disagree, archive-chain state becomes arbiter.

## Free dynamic-info aggregation

`GET /api/beta/analytics/dynamic-info/aggregated`

This is marked **Free** and accepts aggregation intervals including `5min`, with netuid/start/end filters.

Worth testing immediately because it may give us additional 5m pool/network factors without paying for the OHLC endpoint.

## Free alpha price-at-block

`GET /api/beta/accounting/price-at-block`

Marked **Free**. Gives TAO price of an alpha token at a specified block.

Excellent for spot checks of our reconstructed/candle data.

## Free block-by-timestamp

TAO.app also provides block lookup by timestamp. That is useful for converting 5-minute UTC bucket boundaries into canonical Bittensor blocks.

## Free TAO/USD 5-minute history

This is another big find:

`GET /api/beta/historical-price`

Parameters:

- `start`
- optional `end`
- `frequency_min`, **minimum 5**
- pagination, page size up to 10,000

So we may not need a crypto exchange API at all for the initial TAO/USD join.

We should test how far back their 5m retention goes. If it reaches February 2025, it is ideal.

---

# 3. Official Bittensor archive node — canonical source

Official public archive endpoint:

`wss://archive.chain.opentensor.ai:443`

Bittensor docs:
https://www.bittensor.com/docs/guides/running-a-node

The official docs currently say:

- public endpoints are roughly **1 request/sec/IP**;
- lite nodes retain only roughly the latest 300 blocks;
- archive nodes preserve historical state;
- self-hosted archive currently needs **~3.5 TB+ and growing**;
- archive sync takes days.

This should be our **ground truth / repair source**, not necessarily the fastest initial bulk source.

Dynamic TAO/subnet tokens begin at official first dTAO block:

**4,920,351 — February 2025**

Official emissions docs:
https://www.bittensor.com/docs/concepts/emissions

At ~12 seconds/block there are about 25 blocks per 5-minute candle.

As of 3 Sep 2026, dTAO history is only ~4.08 million blocks / ~163k five-minute buckets. That is not actually an enormous time series.

### Important distinction

If we query one historical block every 25 blocks we obtain a **5-minute spot/close series**, NOT true OHLCV.

To reconstruct exact 5m:

- open = first price in bucket
- high = max price observed across all blocks/trades in bucket
- low = min
- close = final price
- volume = aggregate swaps/trading flow in bucket

That means exact OHLC requires processing every price-changing block/trade, not merely 25-block sampling.

For most first-stage factor/backtesting work, 5m close + flow/reserve features may be enough. But if we want execution/slippage studies, use proper OHLCV.

### Current native all-subnet price read

Current Bittensor SDK exposes an `alpha-prices` query backed by runtime API `SwapRuntimeApi.current_alpha_price_all`, returning spot alpha price for every subnet in one read.

Docs:
https://preview.bittensor.com/docs/query/alpha-prices

The Bittensor SDK migration docs explicitly support historical block parameters on subnet reads (e.g. `all_subnets(block=...)`). For archive reconstruction, use runtime/block-pinned queries where possible rather than individually querying 129 storage keys.

### Critical historical-formula warning

Do NOT reconstruct the entire history by applying today's price formula blindly to old reserve values.

Current Bittensor pools are **Balancer-style weighted pools** and current spot price is a weighted TAO-reserve / alpha-reserve ratio. Early dTAO documentation described the simpler constant-product reserve ratio. Runtime mechanics evolved.

Therefore, for canonical historical reconstruction:

- prefer the runtime's price result pinned to that historical block;
- or use spec-version-aware formulas/storage;
- record runtime spec version alongside data.

Official current pricing mechanics:
https://www.bittensor.com/docs/concepts/emissions

---

# 4. Managed archive alternative: OnFinality

Bittensor Finney managed RPC:

https://onfinality.io/en/networks/bittensor-finney

Public HTTP:
`https://bittensor-finney.api.onfinality.io/public`

Public WS:
`wss://bittensor-finney.api.onfinality.io/public-ws`

Their current page says:

- public: 5 RPS
- authenticated: up to 500 RPS
- archive access supported
- dedicated full/archive/validator nodes available

This may be much cheaper/easier than immediately running a 3.5TB archive box, especially for a one-off historical scan.

I'd benchmark OnFinality vs TAOstats archive before buying hardware.

---

# 5. TAO Public API

TAO has a public Data API:

Docs:
https://docs.tao.com/data/

Base:
`https://api.tao.com/data/v1/...`

Relevant endpoints:

- `GET /data/v1/subnet-pools/latest`
- `GET /data/v1/subnet-pools/history`
- `GET /data/v1/tao/price/latest`
- `GET /data/v1/tao/price/history`

The docs explicitly describe `subnet-pools/history` as **dTAO pool snapshots and historical subnet alpha pricing**.

I could not verify from the indexed docs that it offers native 5-minute resolution or its complete retention, so treat it as a strong additional source to test rather than the primary source yet.

---

# 6. dTAOscan — useful full-history / bulk candidate

API:
https://dtaoscan.io/api

Interesting because it is deliberately machine-native:

- all responses signed with Ed25519 receipts;
- free: 10 req/min, no signup;
- x402: 0.01 USDC/call above free tier;
- Pro: 99 USDC/30d;
- Pro advertises **bulk CSV export + full history**.

The public per-subnet endpoint also includes recent snapshots.

I have not verified that its "full history" is 5-minute granularity, so contact/test before paying. But a one-month Pro pass could potentially be a very cheap way to acquire another complete independent archive/export.

Also philosophically useful for Taotoad because they are already doing signed data + x402 well.

---

# 7. OpenTaoAPI — best open-source scaffold I found

Repo:
https://github.com/RyanMercier/OpenTaoAPI

This is highly relevant to `/bitt` even if we don't use their dataset.

Features include:

- direct Bittensor SDK chain queries;
- historical SQLite storage;
- archive-node backfill scripts;
- OHLC endpoints with `5m`, `15m`, `1h`, `4h`, `1d`;
- live polling;
- SSE stream;
- TAO/USD enrichment using MEXC;
- all-subnet backfill/resume tooling.

Example:

`GET /api/v1/subnet/{netuid}/candles?interval=5m&hours=168`

Important caveat: their historical archive backfill is described as **epoch-resolution snapshots** by default (roughly 30m), then candle generation is derived from stored snapshots. So do not assume their existing historical 5m candles represent genuine historical 5m OHLC.

Still: steal the architecture, not necessarily the data. It is basically a ready-made reference implementation for our collector.

---

# 8. SubQuery — DIY custom indexer option

Bittensor support page:
https://subquery.network/indexer/bittensor

SubQuery explicitly supports Bittensor indexing and can be self-hosted. This is useful if we decide we want a durable custom event/state indexer rather than writing all ingestion from scratch.

Not a ready-made 5m price dataset, but a plausible infrastructure layer for indexing every swap/pool-changing event and building exact OHLCV ourselves.

For now I would keep it secondary: our requirements are simple enough that a Python/Rust collector + Parquet/DuckDB may be cleaner.

---

# 9. Metagraphed — excellent free chain/event corroboration

Docs:
https://metagraph.sh/docs
Repo:
https://github.com/JSONbored/metagraphed

Metagraphed indexes Bittensor chain-direct and exposes:

- blocks
- extrinsics
- chain events
- economics
- account activity
- historical position information
- GraphQL
- RPC/WSS
- MCP

No key is required for the public surface.

Economics docs:
https://metagraph.sh/docs/economics

Blocks:
https://metagraph.sh/docs/blocks

This does not appear to be the cleanest 5m OHLC source, but it is very valuable for explaining *why* a candle moved: stake moves, registrations, extrinsics, events, runtime transitions, etc.

That makes it more useful for Taotoad alpha than another redundant price feed.

---

# 10. Taosis — free sampled OHLC / chart source

Docs:
https://www.taosis.com/api-docs

No API key / signup.

Relevant:

`GET https://taosis.com/api/backend/markets/subnets/{netuid}/ohlc?hours=`

`GET https://taosis.com/api/backend/markets/subnets/{netuid}/chart?hours=`

Their own docs state candles are built from **Taosis's own price sampling** and market rows refresh every few minutes.

Useful as a free third-party corroboration/current collector, but I would not use it as canonical long-history data unless testing establishes its historical coverage and bucket semantics.

---

# 11. SubnetStats — rich derived layer, not our raw-price backbone

https://subnetstats.app/pricing

Current plans:

- web Pro: $49.99/mo
- API Starter: $199.99/mo, 100k req, 90 days history
- Growth: $499.99/mo, point-in-time replay
- Scale: $1499.99/mo, bulk exports

It is explicitly a **derived intelligence layer**, not a chain-data mirror, and says it is powered by TAOstats API.

Very interesting later for:

- insider flow
- role-classified wallets
- cost-basis ladders
- exchange flow
- holder concentration

But do not spend this money merely for historical price candles we can get elsewhere.

---

# 12. SubnetRadar / Bittensor.ai / other dashboards

SubnetRadar exposes live market/candle UI and lots of useful derived statistics:
https://subnetradar.com/

Bittensor.ai exposes broad current subnet data:
https://bittensor.ai/subnets

These are useful validation/discovery surfaces but I did not find a clearly documented deep 5-minute historical API comparable to TAOstats or TAO.app.

Treat as corroboration / feature inspiration, not ingestion backbone.

---

# 13. TAO/USD 5-minute history

We need this because subnet price is naturally alpha/TAO. For strategies we will often want both:

`alpha_tao`

and

`alpha_usd = alpha_tao × tao_usd`

## First choice: TAO.app

As above, `/api/beta/historical-price` supports `frequency_min=5` and is marked free. Test full retention.

## MEXC

MEXC listed TAO/USDT on **3 March 2023**, so it comfortably predates dTAO.

Official kline API:

`GET /api/v3/klines`

Supports 5m intervals, start/end time and up to 1000 candles per request.

Docs:
https://mexcdevelop.github.io/apidocs/spot_v3_en/

TAO listing announcement:
https://www.mexc.com/announcements/article/initial-listing-mexc-will-list-bittensor-tao-in-innovation-zone-16101232049689

This is a very good canonical exchange series for the whole dTAO era and OpenTaoAPI already uses MEXC for TAO/USD.

## CoinGecko Enterprise

CoinGecko's range API can explicitly return `interval=5m` for arbitrary historical periods, up to 10 days per request, and says 5m data exists back to February 2018. However historical 5m beyond the immediate 1-day public window is **Enterprise-only**.

Docs:
https://docs.coingecko.com/reference/coins-id-market-chart-range

Probably unnecessary for us given MEXC + TAO.app, but useful as independent cross-validation if access becomes available.

---

# 14. Subnet identity/generation is a MUST

This is easy to get wrong in a trading backtest.

A netuid can represent a subnet that later gets deregistered and then reused by a new registration. Current Bittensor's subnet interface even exposes a registration-generation mechanism specifically so contracts can distinguish a reused netuid.

Also, Bittensor/TAOstats document that when the network is at the subnet cap, new registration can deregister the lowest-priced eligible subnet.

Therefore **never use `netuid` as the permanent asset identity by itself**.

Use something like:

`subnet_instance_id = netuid + registration_block`

or

`(netuid, generation)`.

A price of SN36 before a deregistration and SN36 after a new team registers into that slot must be treated as two distinct assets/time series.

Store at minimum:

- netuid
- registration block
- registration timestamp
- generation
- owner at generation start
- deregistration block/timestamp if applicable

This prevents enormous fake returns around slot recycling.

---

# 15. Recommended canonical schema

For each 5-minute bucket:

```text
bucket_start_utc
netuid
subnet_generation
registration_block
runtime_spec_version

open_alpha_tao
high_alpha_tao
low_alpha_tao
close_alpha_tao
volume_tao
volume_alpha

open_tao_usd
high_tao_usd
low_tao_usd
close_tao_usd
close_alpha_usd

tao_reserve_close
alpha_reserve_close
alpha_outstanding_close
moving_price_close
liquidity_tao_close
market_cap_tao_close
emission_share_close
root_prop_close

source
source_block_open
source_block_close
is_exact_ohlc
quality_flag
raw_payload_hash
```

I would also retain raw vendor responses as compressed JSON/JSONL before normalization. Never overwrite them.

---

# 16. Storage size is trivial

There are only ~163,000 five-minute buckets from dTAO launch to now.

Even if we model ~129 netuids for the entire period (an overestimate because many did not exist throughout), this is ~21 million rows.

That is tiny for Parquet/DuckDB/ClickHouse.

A compact Parquet corpus is likely only a few GB or less depending on fields/compression. There is no reason not to keep everything locally plus R2 backup.

My preference for the lab:

- immutable raw responses in R2
- partitioned Parquet in R2/local disk
- DuckDB for research/backtesting
- optionally ClickHouse only when the live API/query workload justifies it

Do not over-engineer this into a distributed database yet.

---

# 17. Exact ingestion plan I would give the coding agent

## Phase A — prove availability today

For netuids 1, 4, 19, 64 and one recently registered subnet:

1. Query TAOstats TradingView `resolution=5` back to Feb 2025 / registration date.
2. Query TAO.app 5m OHLC for same windows.
3. Compare timestamps/open/high/low/close/volume.
4. Query selected blocks from official archive + TAOstats pool history.
5. Establish what each vendor means by volume.
6. Check deregistration boundaries and missing buckets.

Output a `DATA-AUDIT.md` with discrepancies.

## Phase B — full bootstrap

Backfill every historical subnet generation using TAOstats 5m.

Downloader requirements:

- bounded time chunks;
- pagination/chunk resume state;
- idempotent writes;
- raw-response hashes;
- exponential retry;
- no silent interpolation;
- explicit missing-candle table;
- generation-aware identities.

Then backfill TAO.app as independent comparator where API budget permits.

## Phase C — TAO/USD

Fetch 5m TAO/USD from TAO.app and/or MEXC for entire dTAO era.

Join on UTC bucket.

## Phase D — enrich

Add hourly/by-block pool-state factors:

- TAO reserve
- alpha reserve
- alpha outstanding
- moving price
- emissions
- registration cost
- active miner/validator counts
- liquidity
- stake flows

## Phase E — own data from now forward

Start a collector **right now** against a lite/private RPC, ideally every block.

Store:

- block/time
- all-subnet spot prices
- pool reserves
- moving price
- volume/flow counters
- registration/deregistration events
- relevant swap/stake extrinsics

Aggregate our own exact 1m/5m/15m/1h candles.

From then on, TAOstats/TAO.app become validation sources rather than dependencies.

## Phase F — archive repair

Only after discovering actual gaps should we spend resources reconstructing them from archive state/events.

If public archive is too slow:

- use OnFinality authenticated archive;
- use TAOstats Pro archive;
- temporarily rent/run an archive node;
- or build a custom SubQuery/indexer.

---

# 18. Priority ranking

### S-tier — use immediately

1. **TAOstats TradingView 5m OHLCV** — fastest direct subnet candle source.
2. **TAO.app 5m subnet OHLC** — independent indexed cross-check.
3. **Official Bittensor archive** — canonical arbiter.
4. **TAOstats pool history** — historical reserves/price/features.
5. **TAO.app 5m TAO/USD** / **MEXC 5m TAO/USDT** — fiat normalization.

### A-tier — valuable additional feeds

6. TAO Public API `/subnet-pools/history`.
7. OnFinality archive RPC.
8. dTAOscan full history / bulk CSV.
9. OpenTaoAPI source code/backfill scaffold.
10. Metagraphed events/extrinsics/economics.

### B-tier — supplementary/corroboration

11. Taosis sampled OHLC.
12. SubnetStats derived wallet/flow intelligence.
13. SubnetRadar dashboards/candles.
14. Bittensor.ai current ecosystem data.
15. SubQuery if/when we want our own custom event indexer.
16. CoinGecko Enterprise for alternate TAO/USD 5m.

---

# The key strategic point for Taotoad

The 5m candles themselves are not the moat. They are the substrate.

The valuable corpus becomes:

```text
5m subnet price + liquidity + flow + emissions
+ registrations/deregistrations
+ validator/miner changes
+ code/repo changes
+ social/news events
+ Taotoad calls
+ subsequent realized outcomes
```

Then every Taotoad hypothesis can be evaluated against a precise point-in-time state without lookahead bias.

That is exactly what we need for the "alpha with receipts" thesis: not merely saying SNx looked good, but being able to reconstruct exactly what information existed at 14:35 UTC, what Taotoad predicted, and what happened over the next 5m / 1h / 6h / 24h / 7d.

The immediate dev move is therefore **not** "build a historical indexer from scratch." It is:

> backfill TAOstats 5m + cross-check TAO.app + start our own block collector today + use archive only to verify/repair.

That gets `/bitt` from research into a real backtesting dataset very quickly.
