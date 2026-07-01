# RexAlgo ICT/AMD Trading Strategy

A complete, runnable Python project that implements a fine-tuned **ICT / AMD (Accumulation → Manipulation → Distribution)** trading strategy for **BTCUSDT on the 15m timeframe**. 

This repository includes an event-driven backtester and a live trading runner that streams WebSocket market data (from Mudrex or Bybit) and triggers HMAC-signed webhook signals to the RexAlgo platform.

---

## 📈 Backtest Results

A synthetic backtest run simulated the strategy over a 1-year period (June 2024 - June 2025) to verify the strategy engine's mechanics without needing network access. The synthetic data generates randomized regimes (trend up/down, ranging, liquidity sweeps).

**Synthetic Backtest Overview:**
* **Total Trades**: 32
* **Win Rate**: 37.5%
* **Total Return**: -4.69% (Initial Capital: $10,000 → Final Capital: $9,530.71)
* **Max Drawdown**: 9.63%
* **Profit Factor**: 0.78

*(Note: Because this is synthetic, regime-switching data, the numbers reflect random simulation rather than real market profitability. Run `python run_backtest.py --source auto` locally to backtest against real Mudrex/Bybit BTCUSDT data).*

---

## 🚀 Railway Deployment Guide

This repository is **fully ready** to be hosted on Railway. The `Procfile` and `requirements.txt` are configured at the repository root, so Railway's Python builder will detect and deploy it automatically.

### Railway Environment Variables

To connect the live runner to your specific RexAlgo account, add the following variables in your Railway project settings:

* `REXALGO_WEBHOOK_URL` (Optional): The webhook URL. Defaults to `https://rexalgo-production.up.railway.app/api/webhooks/strategy`.
* `REXALGO_SECRET` (**Required**): Your strategy's secret token from the RexAlgo Strategy Studio.
* `REXALGO_STRATEGY_ID` (**Required**): Your strategy ID from RexAlgo.
* `REXALGO_DRY_RUN`: Set to `False` (or `0`) to actually fire live signals. By default, it is set to `True` so the bot will only print `[DRY-RUN]` logs to stdout without sending HTTP requests.

### How Railway Runs the App
Railway uses the `Procfile` command:
`worker: cd rexalgo_amd && python live_runner.py`

This will spin up a background worker that aggregates WebSocket data and executes the strategy logic 24/7. Check your Railway logs to see the live feed updates and triggered signal logs!

---

## 🛠 Project Structure

* **`rexalgo_amd/config.py`**: Configuration dataclasses (Strategy, Market, RexAlgo settings, env variables).
* **`rexalgo_amd/indicators.py`**: Causal technical indicators (ATR, EMA, True Range) with 0 look-ahead bias.
* **`rexalgo_amd/strategy.py`**: Core strategy logic detecting Accumulation (box), Manipulation (sweeps), and Distribution (MSS + pullback entries).
* **`rexalgo_amd/data_feed.py`**: Data fetching from Mudrex (primary), Bybit (fallback), and synthetic generation.
* **`rexalgo_amd/backtester.py`**: Event-driven backtester supporting partial TP, break-even stops, limit entries.
* **`rexalgo_amd/run_backtest.py`**: CLI tool for running backtests. Outputs `backtest_result.json`.
* **`rexalgo_amd/rexalgo_client.py`**: Webhook client mapping orders to RexAlgo payload specs with HMAC signing.
* **`rexalgo_amd/live_runner.py`**: Live bot process that handles the 1m → 15m candle aggregation and triggers webhooks.

---

## 💻 Local Development

### 1. Installation

```bash
git clone https://github.com/DecentralizedJM/AMD-Strategy.git
cd AMD-Strategy
pip install -r requirements.txt
```

### 2. Running a Backtest Locally

To run the backtest with actual market data for the last 365 days:
```bash
cd rexalgo_amd
python run_backtest.py --source auto --symbol BTCUSDT --interval 15m
```
This writes a schema-compliant `backtest_result.json` file.

### 3. Running Live Locally

```bash
cd rexalgo_amd
export REXALGO_SECRET="your_secret_here"
export REXALGO_DRY_RUN="False"
python live_runner.py
```