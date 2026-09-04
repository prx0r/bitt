# Bittensor subnet trading research — papers, strategy map, and reading order

**Date:** Wed, 2 Sep 2026 22:06:51 -0700

---

# Bittensor subnet trading research — what to read and what to test

I reviewed the current `prx0r/bitt` trading results and searched the Bittensor/AMM/crypto quant literature specifically for strategies that map to what we are already seeing.

## What `/bitt` currently says

The strongest factor in the current comprehensive factor analysis is **7-day price volatility**, with IC ≈ **-0.170**. Low-vol observations subsequently outperform high-vol observations. The separate vol strategy currently has roughly **+2.28% average return for low-vol vs -1.37% for high-vol**, a ~3.65 percentage-point spread. The current `low_vol_active` strategy combines low 7d volatility (weight 3) with active-neuron ratio (weight 1) and holds for 24h.

However, the most honest 42-day analysis says the big portfolio result is **volatility regime switching + one very good SN84 pick**, not a proven timeless static low-vol anomaly. That is important: the research problem should be framed as *forecasting when a subnet is entering/leaving a calm regime* and *separating good volatility from bad volatility*, not just buying the lowest historical standard deviation.

Also, the current signal implementation uses hard volatility bins. Once the 5-minute history is loaded, replace these with cross-sectional ranks / forecast volatility / state probabilities and test them walk-forward.

---

# Tier 0 — compulsory Bittensor-specific papers

## 1. Philip Z. Maymin — Common Risk Factors in Decentralized AI Subnets (arXiv 2603.29751, Mar 2026)
https://arxiv.org/abs/2603.29751

**This is the most important paper for `/bitt`.** It studies daily data on all 128 Bittensor subnet tokens and derives a mechanical size premium from the constant-product AMM. Small-minus-big reportedly earns ~1.01% per day (Newey-West t=3.28). It also explicitly models slippage and finds the strategy only practically implementable at relatively small AUM; around $100K, transaction costs overwhelm gross return.

### Reading instructions
Read in this order:
1. The AMM derivation / size-premium proposition.
2. Exact definition of subnet size and portfolio formation.
3. Cross-sectional tests and robustness.
4. December 2025 halving natural experiment.
5. **Slippage section in full.**

### What we should implement
- Reproduce the paper exactly using our dataset before inventing anything.
- Add `pool_size`, `alpha_reserve`, `tao_reserve`, market cap, implied price impact and AMM slippage as factors.
- Run a 5x5 double sort: **volatility × pool size**.
- Fama–MacBeth / cross-sectional regression: next return ~ low-vol + size + liquidity + price + age + momentum.
- Neutralize low-vol against size and liquidity and see whether our IC survives.
- Test Maymin at 5m/30m/1h/6h/24h horizons rather than only daily.

This is the biggest possible confound in our current result. Our low-vol alpha may be independent, may be the inverse of the small-subnet premium at our horizon, or may be picking up some interaction between pool depth and AMM mechanics. We need to know which.

## 2. Philip Z. Maymin — Mechanical Factor Premia in Automated Market Makers: Evidence from Bittensor Subnet Tokens (SSRN, Jun 2026)
https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6985022

Expanded 52-page version of the same core idea. It argues the return predictability is mechanical: for fixed staked emission, percentage price impact is inversely proportional to pool size, and slippage bounds the arbitrage.

### Reading instructions
Read after #1. Focus on the propositions, implementation/slippage bounds, and any variables we can reproduce at every 5-minute bar. Skip generic literature review on first pass.

## 3. Philip Z. Maymin — Option Pricing on Automated Market Maker Tokens (arXiv 2603.29763)
https://arxiv.org/abs/2603.29763

Very relevant to the low-vol result. It derives a **CEV process** from constant-product AMM price formation and empirically reports a strongly negative relationship between price and realized variance across ~90 Bittensor subnets after controlling for pool depth and flow volatility.

### Reading instructions
Do **not** spend time mastering the option-pricing algebra initially. Read:
1. Price-process derivation.
2. Why AMM mechanics imply a leverage effect / volatility-price relationship.
3. Empirical Bittensor section.

### Test immediately
- `future_vol ~ price + pool_depth + flow_vol`.
- Does our low-vol signal simply identify high-price/deep-pool states predicted mechanically by CEV?
- Compute volatility elasticity to price per subnet and cross-sectionally.
- Add `price_level × pool_depth` interactions.

## 4. Gershteyn & Zevelev — Market Microstructure and Emission Policy in Decentralized Incentive Networks: Bittensor (SSRN 2026)
https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6572880

Studies Bittensor emission policy, price/flow smoothing and market correction. Their simulation finds that market microstructure interacts strongly with the protocol’s smoothing rule; high-frequency signals can be attenuated by the emission mechanism.

### What to take from it
Do not treat subnet price as an ordinary crypto price. Explicitly model protocol-induced flows, emissions and smoothing windows as state variables. Test whether return predictability changes around emission-flow regimes.

---

# Tier 1 — papers that directly validate/challenge our low-vol finding

## 5. Pyo & Jang — Revisiting the Low-Volatility Anomaly in Cryptocurrency Markets (Finance Research Letters, 2026)
https://doi.org/10.1016/j.frl.2026.109851

432 Binance spot cryptocurrencies, Jan 2018–Nov 2025. They find **low-volatility portfolios earn higher subsequent returns than high-volatility portfolios**, with the strongest spread using roughly 2–3 month volatility formation and 1-month holding periods. This is unusually close to what we are seeing.

### Reading instructions
Focus on:
- volatility definition;
- formation-vs-holding grid;
- portfolio sorting methodology;
- Fama–MacBeth controls;
- robustness to universe/survivorship choices.

### `/bitt` translation
Run a full horizon surface instead of picking 7d/24h by hand:
- vol lookbacks: 1h, 6h, 24h, 3d, 7d, 14d, 30d;
- forwards: 30m, 1h, 6h, 24h, 3d, 7d;
- Spearman IC + quintile spread + turnover + slippage for every cell.

Do **not** choose the best cell and report it as truth; freeze a hypothesis and validate on held-out time.

## 6. Blitz et al. / Low-volatility strategies for highly liquid cryptocurrencies (Finance Research Letters, 2022)
https://doi.org/10.1016/j.frl.2021.102422

Finds concentrated low-vol crypto portfolios can generate significant excess returns and that a simple stop-loss improves downside risk.

### `/bitt` tests
- low-vol top 1 / 3 / 5 / 10 subnets;
- equal weight vs inverse-vol vs risk-parity;
- stop-loss variants, **including actual AMM execution cost**;
- maximum position as a fraction of pool depth.

Our current result that concentrated calm portfolios outperform is directionally similar, but we need to know if concentration survives many more subnet histories.

## 7. Earlier counter-evidence — Cryptocurrencies and the Low Volatility Anomaly (Finance Research Letters, 2021)
https://doi.org/10.1016/j.frl.2020.101683

Using older 2013–2019 crypto data, this paper found **no conventional low-vol premium / higher-vol coins performed better**. Read this beside the 2026 paper. The contrast is useful because it screams **regime dependence and market maturation**, which fits our Bittensor observation.

---

# Tier 2 — the next strategies I would implement

## 8. Batista & Fernandes — Upside Risk and Return Timing in Bitcoin (SSRN, Aug 2026)
https://papers.ssrn.com/sol3/papers.cfm?abstract_id=7226305

Possibly the highest-value immediate extension. It argues that plain realized volatility incorrectly treats **upside volatility** and **downside volatility** as equivalent. In Bitcoin, upside-driven high-vol states can be associated with positive subsequent returns, so semivolatility timing materially outperforms ordinary volatility management.

### Implement before anything fancy
For each subnet and horizon calculate:
- upside realized variance: sum(r² where r>0);
- downside realized variance: sum(r² where r<0);
- downside/upside ratio;
- signed jump / largest positive and negative moves;
- total RV.

Then test forward returns separately.

Hypothesis: our current `low_vol` strategy is throwing out some of the best bullish volatile states. **“Low bad-vol, allow good-vol” may dominate raw low-vol.**

## 9. Zhang & Zhao — Good Volatility, Bad Volatility, and the Cross Section of Cryptocurrency Returns (IRFA, 2023)
https://doi.org/10.1016/j.irfa.2023.102712

Related realized-semivariance/jump literature. Useful for defining signed volatility and jump factors rigorously.

## 10. Moreira & Muir — Volatility-Managed Portfolios (Journal of Finance, 2017)
https://doi.org/10.1111/jofi.12513

Canonical volatility timing: reduce exposure when forecast volatility rises. They find improved Sharpe across many factors because expected returns do not rise proportionally with volatility.

### `/bitt` version
Instead of only choosing calm subnets, make **position size a continuous function of forecast variance**. Compare:
- equal-weight low-vol selection;
- inverse-vol sizing;
- inverse-variance sizing / Moreira-Muir style;
- target portfolio volatility;
- hard calm/wild state switch.

This tests whether our alpha is in **selection** or simply **risk scaling**.

## 11. Cederburg et al. — On the Performance of Volatility-Managed Portfolios (JFE, 2020)
https://doi.org/10.1016/j.jfineco.2020.04.015

Mandatory counterweight to #10. Across 103 equity strategies they find volatility management does **not systematically outperform out of sample**, largely due to structural instability.

This paper describes exactly the failure mode we must guard against in `/bitt`: short history + unstable vol relationships + tuning until something looks amazing.

---

# Tier 3 — forecast the calm/wild transition rather than looking backward

## 12. Fulvio Corsi — HAR-RV / A Simple Long Memory Model of Realized Volatility
https://papers.ssrn.com/sol3/papers.cfm?abstract_id=626064

Classic, simple realized-volatility forecasting. It models short/medium/long volatility components together and is ideal for our 5-minute data.

### Implement a tiny version first
Predict next-period realized variance from:
- last 1h RV;
- last 6h RV;
- last 24h RV;
- last 7d RV.

Then rank subnets on **forecast vol**, not backward 7d vol.

If forecast-low-vol beats naive historical-low-vol, we have materially improved the strategy without ML complexity.

## 13. Huang, Wang & Liao — Forecasting Bitcoin Realized Volatility Under Regime Switching and Delayed Mean Reversion (SSRN, Mar 2026)
https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6484648

Finds a persistent low-vol regime plus intermittent high-vol stress regimes and improves OOS forecasts by explicitly modeling regime switching.

### `/bitt` implementation
Start simpler than their full model:
- two-state HMM: CALM / WILD;
- features = log RV, downside RV, return, volume, pool flow;
- retain **posterior probability**, not just hard state;
- calculate transition matrix and expected state duration per subnet;
- trade `P(CALM tomorrow)` rather than `vol_7d`.

This maps almost perfectly to the mechanism our current honest backtest claims to have found.

## 14. Ma et al. — Cryptocurrency Volatility Forecasting: Markov Regime-Switching MIDAS (Journal of Forecasting, 2020)
https://doi.org/10.1002/for.2691

Useful reference for jumps causing persistence in high-vol regimes.

## 15. Ardia, Bluteau & Rüede — Regime Changes in Bitcoin GARCH Volatility Dynamics
https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3180830

Good compact reference showing MS-GARCH beating single-regime GARCH for Bitcoin risk prediction.

## 16. 2026 comparison of GARCH / EGARCH / IGARCH / GJR-GARCH / HAR on 5-minute crypto data
https://doi.org/10.3390/ijfs14040090

Directly useful because the input frequency is exactly the 5-minute history we are now collecting. Do not assume neural nets are needed; benchmark simple HAR/EWMA/GARCH first.

---

# Tier 4 — separate common Bittensor volatility from subnet-specific volatility

## 17. Pham et al. — Good versus Bad COVOL in Cryptocurrency Markets (SSRN, Jan 2026)
https://ssrn.com/abstract=6038623

Separates common volatility shocks associated with positive vs negative market returns and reports improved portfolio outcomes from a Relative COVOL Index.

### `/bitt` translation
Create a Bittensor market volatility factor from all subnet returns, then decompose each subnet into:
- market/common return beta;
- common volatility exposure;
- residual/idiosyncratic volatility;
- good common vol;
- bad common vol.

Then ask: **does low total volatility predict returns, or specifically low idiosyncratic/bad volatility?**

## 18. The Common Risk Drivers of Cryptocurrency Markets (2026)
https://doi.org/10.1016/j.finr.2026.100120

Current work showing a latent common crypto volatility factor. Useful methodology for systemic vs idiosyncratic vol.

## 19. Is Idiosyncratic Volatility Priced in Cryptocurrency Markets? (2020)
https://doi.org/10.1016/j.ribaf.2020.101252

Finds a positive IVOL premium in its crypto sample. Important because this can conflict with raw low-vol results.

## 20. Ahmad et al. — Is Idiosyncratic Risk Diversifiable in a Cryptocurrency Market? (SSRN, 2026)
https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6110597

Finds IVOL pricing differs by size: positive in microcaps, negative in non-micro coins, with downside IVOL especially important in smaller assets. This sounds highly relevant to shallow Bittensor pools.

### Required experiment
Double/triple sorts:
- size × total vol;
- size × idiosyncratic vol;
- pool depth × downside vol;
- age × vol.

---

# Tier 5 — trend/momentum combined with volatility

## 21. Fieberg et al. — A Trend Factor for the Cross Section of Cryptocurrency Returns (JFQA, 2025)
https://doi.org/10.1017/S0022109024000747

Open-access paper using price + volume information across several horizons to construct a crypto trend factor that survives transaction costs and multiple market states.

Our current factor table is interesting here: `momentum_7d` is weakly positive while `1d lookback` is negative. That suggests **short-horizon reversal + longer-horizon trend** may coexist.

### Build a simple CTREND-lite before ML
For every subnet:
- returns: 1h, 6h, 24h, 3d, 7d, 14d;
- volume changes over same horizons;
- distance from rolling high/low;
- sign consistency / trend quality;
- combine cross-sectional ranks.

Then test `trend × low_bad_vol`.

## 22. Barroso & Santa-Clara — Momentum Has Its Moments (JFE 2015)
https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2041429

Momentum risk is predictable; volatility scaling nearly doubles Sharpe in their setting.

## 23. Daniel & Moskowitz — Momentum Crashes (JFE 2016)
https://www.nber.org/papers/w20439

Momentum crashes are partly forecastable in high-vol/panic states. Useful if we add subnet momentum: **never test momentum without conditioning on volatility state.**

---

# Tier 6 — liquidity and AMM capacity

## 24. Dong et al. — Liquidity in the Cryptocurrency Market and Commonalities Across Anomalies (IRFA 2022)
https://doi.org/10.1016/j.irfa.2022.102097

Many crypto anomalies are stronger in lower-liquidity assets—but lower liquidity also means worse implementability. This distinction is absolutely central for Bittensor.

### Add to every factor result
Report both:
1. raw return / IC;
2. **capacity-adjusted net return after exact AMM slippage**.

Build Amihud-style illiquidity, reserve depth, price impact for 0.1 / 1 / 10 TAO, turnover, and recent flow as factors.

## 25. Tolusic — The Dealer Atom: A Universal Intraday Timescale in Volatility and Its Installation in Cryptocurrency Markets (SSRN, Jul 2026)
https://papers.ssrn.com/sol3/papers.cfm?abstract_id=7135098

Interesting high-frequency paper: absolute-return autocorrelation contains a fast 1–5h component, modal ~2.4h, in professionally market-made markets.

### `/bitt` test
With 5m data, compute ACF of |returns| / RV and estimate volatility half-life per subnet. If Bittensor has a stable hours-scale persistence window, **rebalance cadence should be learned from that** rather than arbitrarily daily.

---

# Backtest hygiene — mandatory before believing a +50% result

## 26. Bailey & López de Prado — The Deflated Sharpe Ratio
https://doi.org/10.3905/jpm.2014.40.5.094

Corrects Sharpe for selection bias, multiple testing and non-normal returns.

## 27. Bailey, Borwein, López de Prado & Zhu — The Probability of Backtest Overfitting
https://doi.org/10.21314/JCF.2016.322

Use CSCV/PBO to estimate how likely our chosen strategy is simply the winner of many attempted variants.

## 28. Harvey & Liu — False (and Missed) Discoveries in Financial Economics
https://arxiv.org/abs/2006.04269

Multiple-testing / false-discovery framework for factor research.

### `/bitt` research protocol from now on
Every candidate factor should log:
- hypothesis before test;
- exact factor definition;
- universe rules;
- lookback + horizon;
- number of variants tried;
- Spearman IC / ICIR;
- Newey-West t-stat where appropriate;
- quintile/top-bottom spread;
- turnover;
- exact AMM slippage;
- drawdown / tail loss;
- walk-forward OOS result;
- result by subnet-age cohort;
- result by pool-size cohort;
- result by global market regime;
- Deflated Sharpe / multiple-testing-adjusted evidence where useful.

Never overwrite failed tests. They become Hydra/Moltwork evidence and protect Taotoad from rediscovering false edges.

---

# Exact experiment queue I would give the coding agent

## P0 — establish whether low-vol is real
1. Expand to full available subnet histories / 5m bars.
2. Build horizon grid for realized volatility and forward returns.
3. Walk-forward cross-sectional IC; no random train/test split.
4. Low-vs-high quintile portfolios with exact execution/slippage.
5. Control for pool size, liquidity, price, subnet age and TAO market return.
6. 5x5 volatility × size double sort.
7. Repeat excluding SN84 and excluding each subnet one-at-a-time. If the result dies under leave-one-out, we do not call it an edge.

## P1 — improve volatility definition
8. Upside vs downside semivolatility.
9. Jump measures / max positive and max negative 5m return.
10. EWMA forecast volatility.
11. HAR-RV forecast volatility.
12. Two-state HMM CALM/WILD posterior.
13. Volatility-of-volatility and regime transition speed.

## P2 — Bittensor mechanics
14. Reproduce Maymin SMB exactly.
15. Pool depth / reserve / price-impact factors.
16. Emission flow and stake-flow momentum.
17. Price elasticity of realized variance / CEV test.
18. Slippage-adjusted capacity curve for every strategy at 0.1, 1, 5, 10, 50, 100 TAO.

## P3 — combinations
19. `low downside-vol + positive trend`.
20. `low forecast-vol + high active ratio` (our current idea, but forecasted).
21. `low bad-vol + stake inflow`.
22. `small/subnet-size factor + volatility neutralization`.
23. `support bounce × calm regime`.
24. `squeeze → breakout`, conditioned on direction/flow rather than blindly buying compression.
25. momentum conditioned on calm/wild state.

## P4 — portfolio layer
26. Top-1/3/5/10 equal weight.
27. Inverse-vol sizing.
28. Inverse-variance / volatility-managed sizing.
29. Minimum-variance covariance portfolio with shrinkage.
30. Risk caps as fraction of AMM pool depth.
31. TAO cash allocation when no subnet clears an OOS confidence hurdle.

## P5 — anti-overfit
32. Frozen monthly model versions.
33. One-bar execution delay.
34. Purged/embargoed walk-forward where overlapping labels matter.
35. Deflated Sharpe + PBO.
36. Paper-trade every signal and resolve predictions immutably for Taotoad.

---

# Recommended reading order if you only spend a few hours

**First hour**
1. Maymin — Common Risk Factors in Decentralized AI Subnets.
2. Maymin — Option Pricing on AMM Tokens, empirical/CEV sections only.
3. Pyo & Jang — 2026 low-vol crypto paper.

**Second hour**
4. Batista & Fernandes — Upside Risk and Return Timing in Bitcoin.
5. Moreira & Muir — Volatility-Managed Portfolios.
6. Cederburg et al. — read the critique immediately after Moreira/Muir.

**Third hour**
7. Corsi HAR-RV.
8. Huang/Wang/Liao regime-switching volatility.
9. CTREND crypto factor.

**Before trusting or deploying anything**
10. Deflated Sharpe Ratio.
11. Probability of Backtest Overfitting.

---

# My current hypothesis

The promising research direction is **not simply “buy low-vol subnets.”** A better candidate is:

> Bittensor subnet returns have mechanically structured AMM/size effects, while volatility is persistent but state-dependent. The best risk-adjusted allocations may come from identifying subnets transitioning into persistent low-*downside*-volatility regimes, while retaining positive trend/flow, and sizing positions by forecast risk and actual pool capacity.

That hypothesis directly combines:
- our strongest current empirical factor (low vol);
- our observed regime switching;
- the 2026 crypto low-vol literature;
- upside/downside semivolatility evidence;
- HAR/HMM volatility forecasting;
- Maymin’s Bittensor AMM size mechanics;
- exact slippage/capacity constraints.

If it survives full historical 5m data and walk-forward tests, it is much more credible than a hand-tuned trading rule—and every resolved experiment becomes Taotoad evidence.
