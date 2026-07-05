import pandas as pd
from typing import Dict, Any
from config import StrategyParams, MarketConfig
from strategy import add_features, detect_setup

def run_backtest(df: pd.DataFrame, p: StrategyParams, market: MarketConfig) -> Dict[str, Any]:
    df = add_features(df, p)
    
    equity = market.initial_capital
    equity_curve = [{"t": df.index[0].strftime("%Y-%m-%dT%H:%M:%SZ"), "v": equity}]
    trades = []
    
    state = "flat"
    setup = None
    last_exit_bar = -p.cooldown_bars
    
    pos_side = ""
    pos_entry = 0.0
    pos_qty = 0.0
    pos_sl = 0.0
    pos_tp1 = 0.0
    pos_tp2 = 0.0
    pos_tp1_hit = False
    
    legs = []
    
    high = df["high"].values
    low = df["low"].values
    
    current_day = df.index[0].date()
    
    for i in range(len(df)):
        ts = df.index[i]
        
        if ts.date() != current_day:
            equity_curve.append({"t": ts.replace(hour=0, minute=0, second=0).strftime("%Y-%m-%dT%H:%M:%SZ"), "v": equity})
            current_day = ts.date()
            
        if state == "flat":
            if (i - last_exit_bar) >= p.cooldown_bars:
                setup = detect_setup(df, i, p)
                if setup:
                    state = "armed"
                    
        elif state == "armed":
            if i > setup.valid_until:
                state = "flat"
                setup = None
            else:
                filled = False
                if setup.side == "long" and low[i] <= setup.entry:
                    filled = True
                elif setup.side == "short" and high[i] >= setup.entry:
                    filled = True
                    
                if filled:
                    qty = (equity * p.risk_pct) / setup.risk
                    max_qty = (p.max_leverage * equity) / setup.entry
                    qty = min(qty, max_qty)
                    
                    pos_side = setup.side
                    pos_entry = setup.entry
                    pos_qty = qty
                    pos_sl = setup.sl
                    pos_tp1 = setup.tp1
                    pos_tp2 = setup.tp2
                    pos_tp1_hit = False
                    legs = []
                    
                    state = "in"
                    
        if state == "in":
            exit_price = None
            exit_qty = 0.0
            full_close = False
            
            if pos_side == "long":
                if not pos_tp1_hit:
                    if low[i] <= pos_sl:
                        exit_price = pos_sl * (1 - p.slippage_pct)
                        exit_qty = pos_qty
                        full_close = True
                    elif high[i] >= pos_tp1:
                        close_qty = pos_qty * p.tp1_frac
                        legs.append((pos_tp1, close_qty))
                        pos_qty -= close_qty
                        pos_tp1_hit = True
                        if p.breakeven_after_tp1:
                            pos_sl = pos_entry
                        if pos_qty > 0 and high[i] >= pos_tp2:
                            legs.append((pos_tp2, pos_qty))
                            pos_qty = 0.0
                            full_close = True
                else:
                    if low[i] <= pos_sl:
                        exit_price = pos_sl * (1 - p.slippage_pct)
                        exit_qty = pos_qty
                        full_close = True
                    elif high[i] >= pos_tp2:
                        exit_price = pos_tp2
                        exit_qty = pos_qty
                        full_close = True
            else:
                if not pos_tp1_hit:
                    if high[i] >= pos_sl:
                        exit_price = pos_sl * (1 + p.slippage_pct)
                        exit_qty = pos_qty
                        full_close = True
                    elif low[i] <= pos_tp1:
                        close_qty = pos_qty * p.tp1_frac
                        legs.append((pos_tp1, close_qty))
                        pos_qty -= close_qty
                        pos_tp1_hit = True
                        if p.breakeven_after_tp1:
                            pos_sl = pos_entry
                        if pos_qty > 0 and low[i] <= pos_tp2:
                            legs.append((pos_tp2, pos_qty))
                            pos_qty = 0.0
                            full_close = True
                else:
                    if high[i] >= pos_sl:
                        exit_price = pos_sl * (1 + p.slippage_pct)
                        exit_qty = pos_qty
                        full_close = True
                    elif low[i] <= pos_tp2:
                        exit_price = pos_tp2
                        exit_qty = pos_qty
                        full_close = True
                        
            if full_close:
                if exit_qty > 0:
                    legs.append((exit_price, exit_qty))
                    
                total_exit_qty = sum(q for _, q in legs)
                total_entry_qty = total_exit_qty
                
                if pos_side == "long":
                    gross = sum(e * q for e, q in legs) - pos_entry * total_exit_qty
                else:
                    gross = pos_entry * total_exit_qty - sum(e * q for e, q in legs)
                    
                entry_fees = p.fee_pct * pos_entry * total_entry_qty
                exit_fees = sum(p.fee_pct * e * q for e, q in legs)
                total_fees = entry_fees + exit_fees
                
                pnl = gross - total_fees
                equity += pnl
                
                avg_exit = sum(e * q for e, q in legs) / total_exit_qty if total_exit_qty > 0 else 0
                
                trades.append({
                    "entryTime": df.index[setup.signal_bar].strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "exitTime": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "side": pos_side,
                    "entry": pos_entry,
                    "exit": avg_exit,
                    "qty": total_exit_qty,
                    "pnl": pnl,
                    "pnlPct": (pnl / (pos_entry * total_exit_qty)) * 100
                })
                
                equity_curve.append({"t": ts.strftime("%Y-%m-%dT%H:%M:%SZ"), "v": equity})
                
                state = "flat"
                last_exit_bar = i
                
    # Close dangling position
    if state == "in":
        ts = df.index[-1]
        exit_price = df["close"].iloc[-1]
        exit_qty = pos_qty
        legs.append((exit_price, exit_qty))
        
        total_exit_qty = sum(q for _, q in legs)
        total_entry_qty = total_exit_qty
        
        if pos_side == "long":
            gross = sum(e * q for e, q in legs) - pos_entry * total_exit_qty
        else:
            gross = pos_entry * total_exit_qty - sum(e * q for e, q in legs)
            
        entry_fees = p.fee_pct * pos_entry * total_entry_qty
        exit_fees = sum(p.fee_pct * e * q for e, q in legs)
        total_fees = entry_fees + exit_fees
        
        pnl = gross - total_fees
        equity += pnl
        
        avg_exit = sum(e * q for e, q in legs) / total_exit_qty if total_exit_qty > 0 else 0
        
        trades.append({
            "entryTime": df.index[setup.signal_bar].strftime("%Y-%m-%dT%H:%M:%SZ"),
            "exitTime": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "side": pos_side,
            "entry": pos_entry,
            "exit": avg_exit,
            "qty": total_exit_qty,
            "pnl": pnl,
            "pnlPct": (pnl / (pos_entry * total_exit_qty)) * 100
        })
        
        equity_curve.append({"t": ts.strftime("%Y-%m-%dT%H:%M:%SZ"), "v": equity})
        
    equity_curve.append({"t": df.index[-1].strftime("%Y-%m-%dT%H:%M:%SZ"), "v": equity})
    
    # Calculate summary
    total_return_pct = ((equity - market.initial_capital) / market.initial_capital) * 100
    wins = [t for t in trades if t["pnl"] > 0]
    win_rate_pct = (len(wins) / len(trades) * 100) if trades else 0.0
    
    gross_profit = sum(t["pnl"] for t in wins)
    gross_loss = abs(sum(t["pnl"] for t in trades if t["pnl"] <= 0))
    profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else None
    
    max_drawdown_pct = 0.0
    peak = market.initial_capital
    for eq in equity_curve:
        v = eq["v"]
        if v > peak:
            peak = v
        dd = (peak - v) / peak * 100
        if dd > max_drawdown_pct:
            max_drawdown_pct = dd
            
    summary = {
        "totalReturnPct": round(total_return_pct, 2),
        "winRatePct": round(win_rate_pct, 2),
        "maxDrawdownPct": round(max_drawdown_pct, 2),
        "trades": len(trades),
        "rangeStart": df.index[0].strftime("%Y-%m-%dT%H:%M:%SZ"),
        "rangeEnd": df.index[-1].strftime("%Y-%m-%dT%H:%M:%SZ"),
        "profitFactor": profit_factor,
        "initialCapital": market.initial_capital,
        "finalCapital": round(equity, 2)
    }
    
    return {
        "summary": summary,
        "equity": equity_curve,
        "trades": trades,
        "meta": {
            "dataSource": "",
            "symbol": market.symbol,
            "interval": market.interval,
            "generatedAt": pd.Timestamp.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "strategy": "ICT/AMD fine-tuned",
            "note": "",
            "params": p.__dict__
        }
    }
