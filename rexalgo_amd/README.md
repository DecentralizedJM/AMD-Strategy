# RexAlgo AMD — BTC 5m

ICT/AMD live signal engine for **BTCUSDT linear, 5-minute candles**.

## Run live

```bash
pip install -r requirements.txt
export REXALGO_SECRET="your_secret"
export REXALGO_DRY_RUN="True"
python3 live_runner.py
```

## Optional backtest (local only, not committed)

```bash
python3 run_backtest.py --source auto --symbol BTCUSDT --interval 5m
```

Output goes to `backtest_result.json` (gitignored).

## WebSocket flow

- **Mudrex**: 1m stream → aggregated to 5m in `CandleAggregator`
- **Bybit fallback**: native `kline.5.BTCUSDT` confirmed candles

Both paths call the same `detect_setup()` logic before sending RexAlgo webhooks.
