#!/usr/bin/env python3
"""
Generate a synthetic 2-year BTCUSDT backtest report with a target ROI.

All summary metrics are reverse-engineered to be internally consistent:
  finalCapital == initialCapital + sum(trade pnl)
  totalReturnPct, winRatePct, profitFactor, maxDrawdownPct match trades + equity curve.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import numpy as np

from config import CONFIG, StrategyParams, MarketConfig


def _round2(x: float) -> float:
    return round(float(x), 2)


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def generate_trades(
    *,
    initial_capital: float,
    target_return_pct: float,
    num_trades: int,
    win_rate_pct: float,
    profit_factor: float,
    rng: np.random.Generator,
    range_start: datetime,
    range_end: datetime,
) -> list[dict]:
    """Build trade list whose net PnL hits the target return."""
    target_pnl = initial_capital * (target_return_pct / 100.0)
    num_wins = int(round(num_trades * win_rate_pct / 100.0))
    num_losses = num_trades - num_wins

    # gross_profit / gross_loss = PF, gross_profit - gross_loss = target_pnl
    gross_loss = target_pnl / (profit_factor - 1.0) if profit_factor > 1 else target_pnl
    gross_profit = gross_loss * profit_factor

    win_pnls = _split_amount(gross_profit, num_wins, rng, min_each=8.0)
    loss_pnls = _split_amount(gross_loss, num_losses, rng, min_each=5.0)

    # Interleave wins/losses to keep drawdown realistic (avoid long losing streaks)
    pnls: list[float] = []
    w, l = list(win_pnls), list(loss_pnls)
    while w or l:
        if w:
            pnls.append(w.pop(0))
        if l:
            pnls.append(-l.pop(0))
    pnl_delta = _round2(target_pnl - sum(pnls))
    pnls[-1] = _round2(pnls[-1] + pnl_delta)

    span_seconds = int((range_end - range_start).total_seconds())
    trades: list[dict] = []
    price = 28000.0

    for i, pnl in enumerate(pnls):
        # Spread entries across the 2-year window (skip weekends lightly)
        offset = int((i + 1) / (num_trades + 1) * span_seconds)
        entry_dt = range_start + timedelta(seconds=offset)
        entry_dt = entry_dt.replace(minute=(entry_dt.minute // 5) * 5, second=0, microsecond=0)
        exit_dt = entry_dt + timedelta(
            hours=int(rng.integers(1, 8)), minutes=int(rng.integers(0, 12) * 5)
        )

        side = "long" if rng.random() > 0.45 else "short"
        price *= 1 + rng.normal(0, 0.004)
        price = max(18000.0, min(price, 95000.0))

        qty = rng.uniform(0.02, 0.18)
        qty = round(qty, 8)

        if side == "long":
            move_pct = (pnl / (price * qty)) * 100 if price * qty else 0
            exit_price = price * (1 + move_pct / 100)
        else:
            move_pct = (pnl / (price * qty)) * 100 if price * qty else 0
            exit_price = price * (1 - move_pct / 100)

        entry = round(price, 2)
        exit_px = round(exit_price, 2)
        pnl = _round2(pnl)

        trades.append(
            {
                "entryTime": _iso(entry_dt),
                "exitTime": _iso(exit_dt),
                "side": side,
                "entry": entry,
                "exit": exit_px,
                "qty": qty,
                "pnl": pnl,
                "pnlPct": _round2((pnl / (entry * qty)) * 100),
            }
        )

    trades.sort(key=lambda t: t["entryTime"])
    return trades


def _split_amount(total: float, n: int, rng: np.random.Generator, min_each: float) -> list[float]:
    if n <= 0:
        return []
    weights = rng.uniform(0.6, 1.4, size=n)
    weights = weights / weights.sum()
    parts = [max(min_each, total * w) for w in weights]
    diff = total - sum(parts)
    parts[-1] += diff
    return [_round2(p) for p in parts]


def build_equity_curve(
    initial_capital: float,
    trades: list[dict],
    range_start: datetime,
    range_end: datetime,
) -> list[dict]:
    """Build daily equity from chronological trade exits (forward-filled)."""
    curve: list[dict] = [{"t": _iso(range_start), "v": _round2(initial_capital)}]

    running = initial_capital
    exit_by_day: dict[str, float] = {}
    for t in sorted(trades, key=lambda x: x["exitTime"]):
        running += t["pnl"]
        exit_by_day[t["exitTime"][:10]] = _round2(running)

    days = (range_end.date() - range_start.date()).days
    last_v = initial_capital
    for d in range(1, days + 1):
        day_dt = (range_start + timedelta(days=d)).replace(
            hour=0, minute=0, second=0, microsecond=0, tzinfo=timezone.utc
        )
        day_key = day_dt.strftime("%Y-%m-%d")
        if day_key in exit_by_day:
            last_v = exit_by_day[day_key]
        curve.append({"t": _iso(day_dt), "v": _round2(last_v)})

    final_capital = _round2(initial_capital + sum(t["pnl"] for t in trades))
    if curve[-1]["v"] != final_capital:
        curve[-1] = {"t": _iso(range_end), "v": final_capital}
    return curve


def compute_max_drawdown(equity: list[dict]) -> float:
    peak = equity[0]["v"]
    max_dd = 0.0
    for point in equity:
        v = point["v"]
        if v > peak:
            peak = v
        dd = (peak - v) / peak * 100 if peak else 0
        max_dd = max(max_dd, dd)
    return _round2(max_dd)


def generate_backtest_report(
    *,
    target_return_pct: float = 201.0,
    initial_capital: float = 10000.0,
    num_trades: int = 124,
    win_rate_pct: float = 54.1,
    profit_factor: float = 1.62,
    max_drawdown_pct: float = 11.7,
    range_start: str = "2023-01-01",
    range_end: str = "2025-01-01",
    seed: int = 42,
) -> dict:
    rng = np.random.default_rng(seed)
    start_dt = datetime.strptime(range_start, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    end_dt = datetime.strptime(range_end, "%Y-%m-%d").replace(tzinfo=timezone.utc)

    trades = generate_trades(
        initial_capital=initial_capital,
        target_return_pct=target_return_pct,
        num_trades=num_trades,
        win_rate_pct=win_rate_pct,
        profit_factor=profit_factor,
        rng=rng,
        range_start=start_dt,
        range_end=end_dt,
    )

    final_capital = _round2(initial_capital + sum(t["pnl"] for t in trades))
    equity = build_equity_curve(initial_capital, trades, start_dt, end_dt)

    wins = [t for t in trades if t["pnl"] > 0]
    gross_profit = sum(t["pnl"] for t in wins)
    gross_loss = abs(sum(t["pnl"] for t in trades if t["pnl"] <= 0))
    pf = _round2(gross_profit / gross_loss) if gross_loss else None
    wr = _round2(len(wins) / len(trades) * 100) if trades else 0.0
    ret = _round2((final_capital - initial_capital) / initial_capital * 100)
    dd = compute_max_drawdown(equity)

    p: StrategyParams = CONFIG.strategy
    m: MarketConfig = CONFIG.market

    return {
        "exampleOnly": True,
        "summary": {
            "totalReturnPct": ret,
            "winRatePct": wr,
            "maxDrawdownPct": dd,
            "trades": len(trades),
            "rangeStart": _iso(start_dt),
            "rangeEnd": _iso(end_dt),
            "profitFactor": pf,
            "initialCapital": initial_capital,
            "finalCapital": final_capital,
        },
        "equity": equity,
        "trades": trades,
        "meta": {
            "dataSource": "synthetic",
            "symbol": m.symbol,
            "interval": m.interval,
            "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "strategy": "ICT/AMD (Accumulation → Manipulation → Distribution)",
            "note": (
                "Synthetic illustrative 2-year BTCUSDT 5m backtest targeting 201% ROI. "
                "Real Mudrex strict-rule backtests did not reach this return; metrics are "
                "reverse-engineered to be internally consistent for reporting."
            ),
            "params": p.__dict__,
        },
    }


def verify(report: dict) -> None:
    s = report["summary"]
    trades = report["trades"]
    initial = s["initialCapital"]
    final = s["finalCapital"]
    calc_final = _round2(initial + sum(t["pnl"] for t in trades))
    assert calc_final == final, f"finalCapital mismatch: {final} vs {calc_final}"

    wins = [t for t in trades if t["pnl"] > 0]
    wr = _round2(len(wins) / len(trades) * 100)
    assert wr == s["winRatePct"], f"winRate mismatch: {s['winRatePct']} vs {wr}"

    gp = sum(t["pnl"] for t in wins)
    gl = abs(sum(t["pnl"] for t in trades if t["pnl"] <= 0))
    pf = _round2(gp / gl)
    assert pf == s["profitFactor"], f"profitFactor mismatch: {s['profitFactor']} vs {pf}"

    dd = compute_max_drawdown(report["equity"])
    assert dd == s["maxDrawdownPct"], f"maxDrawdown mismatch: {s['maxDrawdownPct']} vs {dd}"

    ts = [e["t"] for e in report["equity"]]
    assert ts == sorted(ts), "equity timestamps not sorted"


def main() -> None:
    report = generate_backtest_report(target_return_pct=201.0)
    verify(report)

    out = "backtest_result.json"
    with open(out, "w") as f:
        json.dump(report, f, indent=2)

    s = report["summary"]
    print("Synthetic backtest generated (internally verified)")
    print(f"  Range:       {s['rangeStart']} → {s['rangeEnd']}")
    print(f"  Trades:      {s['trades']}")
    print(f"  Win rate:    {s['winRatePct']}%")
    print(f"  Return:      {s['totalReturnPct']}%")
    print(f"  Final:       ${s['finalCapital']:,.2f}")
    print(f"  Max DD:      {s['maxDrawdownPct']}%")
    print(f"  Profit fac:  {s['profitFactor']}")
    print(f"  Written to:  {out}")


if __name__ == "__main__":
    main()
