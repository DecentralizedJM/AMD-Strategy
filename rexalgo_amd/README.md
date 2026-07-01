# RexAlgo AMD Strategy

A complete, runnable Python project that implements a fine-tuned ICT / AMD (Accumulation → Manipulation → Distribution) trading strategy for BTCUSDT on the 15m timeframe.

## Project Structure

- `config.py`: Configuration dataclasses (StrategyParams, MarketConfig, RexAlgoConfig).
- `indicators.py`: Technical indicators (ATR, EMA, True Range).
- `strategy.py`: Core strategy logic (accumulation, sweep, displacement).
- `data_feed.py`: Data fetching from Mudrex, Bybit, and synthetic generator.
- `backtester.py`: Event-driven backtester.
- `run_backtest.py`: CLI for running backtests.
- `rexalgo_client.py`: Webhook client for RexAlgo.
- `live_runner.py`: Live trading runner with websocket feeds.

## Installation

```bash
pip install -r requirements.txt
```

## Running Backtest

```bash
python run_backtest.py --source synthetic --start 2024-06-01 --end 2025-06-01
```

## Running Live

```python
from live_runner import LiveRunner
runner = LiveRunner()
runner.run()
```

## Provider Cheatsheet

- **Mudrex**: Primary data source. REST API for historical data, WebSocket for live 1m candles (aggregated to 15m).
- **Bybit**: Fallback data source. REST API for historical data, WebSocket for live 15m candles.
- **Synthetic**: Offline regime-switching OHLCV generator for testing.

## Signal/HMAC Format

Signals are sent as JSON payloads to the configured webhook URL.
Headers include:
- `Content-Type: application/json`
- `X-RexAlgo-Signature: t=<timestamp>,v1=<hmac_sha256>`

The HMAC is calculated using the secret key over the string `{timestamp}.{raw_json_body}`.
