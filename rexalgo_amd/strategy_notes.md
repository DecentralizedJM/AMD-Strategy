# Strategy Notes — BTC 5m AMD

Live configuration: **BTCUSDT linear, 5-minute candles**.

## Rules (pseudo-code implementation)

1. **Accumulation** — last 20 bars: `range_high - range_low < 2.5 × ATR(14)`
2. **Liquidity** — `range_high` / `range_low` from that 20-bar window
3. **Manipulation** — sweep below `range_low` (long) or above `range_high` (short)
4. **MSS** — close breaks prior 5-bar high (bull) or low (bear)
5. **Entry** — limit at 50% retracement of impulse leg
6. **Stop** — sweep extreme ± ATR
7. **Target** — 3R

## Tuning (optional)

Edit `config.py` / `strategy.py`:

- `lookback` (20) — accumulation window length
- ATR multiplier (2.5) — how tight the range must be
- MSS lookback (5) — structure break confirmation
- Retracement (0.5) — pullback entry depth

## Expected frequency (5m, real BTC)

Roughly **~0.2 trades/day** (~6/month) on Mudrex BTCUSDT with current strict rules. Run local backtests via `run_backtest.py` (output gitignored).
