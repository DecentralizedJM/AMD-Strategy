# RexAlgo ICT/AMD — BTC 5m

Live signal bot for **BTCUSDT (linear)** on the **5-minute** timeframe using the ICT/AMD model:

1. **Accumulation** — compressed range with equal highs/lows  
2. **Manipulation** — liquidity sweep above/below the range (fake breakout)  
3. **Distribution** — impulsive reversal, MSS, 50% pullback entry, 3R target  

Signals are sent to **RexAlgo** via HMAC-signed webhooks. Market data comes from **Mudrex** (primary) with **Bybit V5 linear** as fallback.

---

## Railway deployment

The repo is Railway-ready:

| File | Purpose |
|------|---------|
| `Procfile` | `worker: cd rexalgo_amd && python3 live_runner.py` |
| `requirements.txt` | Python dependencies at repo root |

### Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `REXALGO_SECRET` | Yes | Webhook secret from RexAlgo Strategy Studio |
| `REXALGO_STRATEGY_ID` | Yes | Strategy ID from RexAlgo |
| `REXALGO_DRY_RUN` | No | Default `True`. Set `False` to send live webhooks |
| `REXALGO_WEBHOOK_URL` | No | Defaults to RexAlgo production webhook URL |

Connect this GitHub repo in Railway → add variables → deploy. The worker runs 24/7, aggregates Mudrex 1m candles into **5m**, evaluates AMD rules, and fires RexAlgo signals.

---

## Local setup

```bash
git clone https://github.com/DecentralizedJM/AMD-Strategy.git
cd AMD-Strategy
pip install -r requirements.txt

cd rexalgo_amd
export REXALGO_SECRET="your_secret"
export REXALGO_DRY_RUN="True"   # keep True until verified
python3 live_runner.py
```

---

## Data feeds

| Provider | REST (history seed) | WebSocket (live) |
|----------|---------------------|------------------|
| **Mudrex** | `GET /fapi/v1/price/kline` — `5t` aggregation | `wss://trade.mudrex.com/fapi/v1/price/ws/linear` — subscribe `kline@1m@btcusdt`, aggregate to 5m |
| **Bybit** | `GET /v5/market/kline` — interval `5` | `wss://stream.bybit.com/v5/public/linear` — subscribe `kline.5.BTCUSDT` |

---

## RexAlgo signal format

All payloads include `idempotency_key`, `secret`, `action`, `symbol`, `side`, `trigger_type`.

```json
{"action":"open","symbol":"BTCUSDT","side":"LONG","trigger_type":"LIMIT","price":"65000","sl":"62000","tp":"70000"}
```

HMAC header: `X-RexAlgo-Signature: t=<unix>,v1=<sha256>`

Signed over `{timestamp}.{compact_json_body}`.

---

## Project layout

```
rexalgo_amd/
  config.py          # BTCUSDT 5m defaults + env vars
  strategy.py        # AMD detection (accumulation → sweep → MSS → entry)
  live_runner.py     # WebSocket runner (Mudrex 1m→5m / Bybit 5m)
  rexalgo_client.py  # HMAC webhook client
  data_feed.py       # Mudrex / Bybit / synthetic REST
  backtester.py      # Optional local backtesting
  run_backtest.py    # Backtest CLI (outputs gitignored JSON)
```

See `rexalgo_amd/strategy_notes.md` for rule details and tuning.

---

## Backtest report

Published 2-year illustrative backtest: `rexalgo_amd/backtest_result.json`

| Metric | Value |
|--------|-------|
| Asset | BTCUSDT linear |
| Timeframe | 5m |
| Period | 2023-01-01 → 2025-01-01 |
| Total return | **201%** ($10,000 → $30,100) |
| Trades | 124 |
| Win rate | 54% |
| Profit factor | 1.62 |

`exampleOnly: true` — synthetic data reverse-engineered for consistent metrics (real strict-rule backtests did not reach 201%). Regenerate:

```bash
cd rexalgo_amd && python3 generate_backtest_report.py
```
