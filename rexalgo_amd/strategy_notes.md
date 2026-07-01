# Strategy Notes

This strategy implements a fine-tuned version of the ICT AMD (Accumulation, Manipulation, Distribution) concept.

## Core Concepts

1. **Accumulation**: A period of consolidation where price ranges within a specific ATR multiple. We look for equal highs/lows to identify liquidity pools.
2. **Manipulation**: A sweep of the liquidity pool (fake-out). The price must wick beyond the accumulation box and ideally close inside it.
3. **Distribution**: A strong impulse leg (displacement) that breaks market structure (MSS) in the opposite direction of the sweep.

## Fine-Tuning Details

- **Real Accumulation**: We require a minimum number of touches (equal highs/lows) within a tolerance to confirm a valid liquidity pool.
- **Fake-out**: The sweep must be a wick that pierces the liquidity pool.
- **Leg-based Displacement**: Displacement is measured from the sweep extreme to the confirming close, not just a single candle body.
- **Pullback Entry**: We use an OTE (Optimal Trade Entry) at 50% or 62% of the impulse leg.
- **Risk Management**: We use a partial take-profit (TP1) and move the stop-loss to break-even after TP1 is hit. Position sizing is based on a fixed percentage of equity.
- **Filters**: We use an EMA trend filter, session killzones, and a cooldown period between trades.

## Tuning Guide

- `lookback`: Length of the accumulation box.
- `box_atr_max`: Maximum height of the accumulation box in ATR multiples.
- `eq_tol_atr`: Tolerance for equal highs/lows in ATR multiples.
- `min_eq_touches`: Minimum number of touches to confirm a liquidity pool.
- `sweep_wick_atr`: Minimum depth of the sweep in ATR multiples.
- `disp_atr`: Minimum displacement in ATR multiples.
- `mss_max_age`: Maximum age of the sweep before MSS is confirmed.
- `entry_mode`: OTE level (50% or 62%).
- `tp1_r`, `tp_final_r`: Risk multiples for TP1 and final TP.
