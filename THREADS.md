# Threads — Interesting Ideas, Unfinished Work, Future Directions

**Last updated:** 2026-09-03

## Active Threads

### 1. x402 Paid Reports (HIGH PRIORITY)
- Create API serving daily mining/rebalancing reports
- Charge 0.001 TAO per report via x402
- Reports: mining opportunities, rebalancing signals, subnet analysis
- Internal scores that can't be copied (the moat)
- Need: x402 integration, report generation, payment flow
- Status: IDEA — not started

### 2. X/Twitter Bot (MEDIUM)
- Auto-post daily mining opportunities
- Post rebalancing signals
- Generate charts from data
- Need: Twitter API, chart generation, scheduling
- Status: IDEA — not started

### 3. 60+ Report Ideas (from emails)
- Mining landscape daily
- Subnet type analysis
- Rebalancing signals
- SN88 performance tracking
- Security audit opportunities
- Child subnet prediction
- Regime detection alerts
- Whale movement tracking
- And 50+ more
- Status: CATALOGED in hypothesis_library.py

### 4. Child Subnet Prediction (UNFINISHED)
- Can we predict which subnets will succeed at birth?
- Early signals: low vol + positive trajectory + low activity
- Need: more historical data, lifecycle analysis
- Status: PARTIAL — formula exists, needs validation

### 5. Regime Detection (UNFINISHED)
- HMM CALM/WILD states
- Trade P(CALM tomorrow) not vol_7d
- Need: state model, transition matrix
- Status: IDEA — not implemented

### 6. HAR-RV Volatility Forecast (UNFINISHED)
- Forecast volatility instead of lagging it
- Use 1h + 6h + 24h + 7d components
- Status: TESTED (+1.18%), needs more validation

### 7. Pair Trading (UNFINISHED)
- Correlated subnets mean-revert spread
- Need: correlation matrix, spread z-scores
- Status: UNTESTED

### 8. SN88 Integration (PARTIAL)
- Can submit strategies via CSV
- Need: hotkey, strategy format
- Status: FORMAT READY, not submitted

### 9. Whale Movement Tracking (IDEA)
- Track large stake movements
- Predict price impact
- Status: IDEA — not started

### 10. Security Audit Opportunities (IDEA)
- SN61 RedTeam overlap
- BitSec integration
- Bounty hunting
- Status: IDEA — not started

## Monetization Ideas

### x402 Reports
- Daily mining report: 0.001 TAO
- Weekly rebalancing signal: 0.005 TAO
- Monthly subnet analysis: 0.01 TAO
- Custom analysis: 0.05 TAO

### X Bot
- Free tier: daily top 3 mining opportunities
- Paid tier: full analysis + rebalancing signals
- Premium: custom alerts + portfolio tracking

### Data API
- Query historical subnet data
- Factor scores
- Backtesting results
- Strategy performance

## Research Threads

### From Imported Emails
- Maymin SMB (AMM size premium)
- HAR-RV volatility forecasting
- Upside/downside semivolatility
- HMM regime detection
- Pair mean reversion
- Whale inflow detection

### From Our Backtesting
- Support bounce is strongest signal (+2.48%)
- Child composite works (+1.72%)
- Low vol confirmed but smaller than claimed
- 5 positions = sweet spot
- 24h rebalance = optimal

### From Mining Analysis
- Broad distribution > high yield
- Median > average (always)
- Top1 > 40% = jackpot (avoid)
- Registration cost same for all

## What We Learned (Lessons)

1. **Small samples lie** — test on full universe
2. **Average lies** — always use median
3. **Cached data lies** — always verify against live chain
4. **Simple beats complex** — support bounce > 10-factor model
5. **Mining > trading** — for TAO accumulation
6. **Holding TAO > trading** — our edge is too small
7. **Broad distribution > high yield** — predictable income wins
8. **Registration cost is same for all** — not a differentiator
