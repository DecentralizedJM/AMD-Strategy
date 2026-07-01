import numpy as np
import pandas as pd
from dataclasses import dataclass
from config import StrategyParams
from indicators import atr, ema

@dataclass
class Setup:
    side: str
    signal_bar: int
    sweep_bar: int
    entry: float
    sl: float
    tp1: float
    tp2: float
    risk: float
    impulse_low: float
    impulse_high: float
    valid_until: int

def add_features(df: pd.DataFrame, p: StrategyParams) -> pd.DataFrame:
    df = df.copy()
    df["atr"] = atr(df["high"], df["low"], df["close"], p.atr_len)
    if p.trend_filter == "ema":
        df["ema_trend"] = ema(df["close"], p.trend_ema)
    else:
        df["ema_trend"] = np.nan
    return df

def session_ok(ts: pd.Timestamp, p: StrategyParams) -> bool:
    if not p.session_filter:
        return True
    hour = ts.hour
    for start, end in p.killzones_utc:
        if start <= hour < end:
            return True
    return False

def detect_setup(df: pd.DataFrame, i: int, p: StrategyParams) -> Setup | None:
    # Design note: displacement is the impulse LEG (sweep extreme -> confirming close),
    # NOT a single-candle body — a single-candle body threshold removes ~98% of valid setups.
    
    if i < p.lookback + p.mss_max_age + 2:
        return None
        
    atr_i = df["atr"].iloc[i]
    if not np.isfinite(atr_i) or atr_i <= 0:
        return None
        
    ts_i = df.index[i]
    if not session_ok(ts_i, p):
        return None
        
    retr = 0.62 if p.entry_mode == "ote62" else 0.50
    
    high = df["high"].values
    low = df["low"].values
    close = df["close"].values
    atr_vals = df["atr"].values
    
    if p.trend_filter == "ema":
        ema_vals = df["ema_trend"].values
    else:
        ema_vals = np.full(len(df), np.nan)
        
    # Scan candidate sweep bars s from i-2 down to i-p.mss_max_age (inclusive)
    for s in range(i - 2, i - p.mss_max_age - 1, -1):
        if s - p.lookback < 0:
            continue
            
        atr_s = atr_vals[s]
        if not np.isfinite(atr_s) or atr_s <= 0:
            continue
            
        # Accumulation "box" over the lookback bars ENDING JUST BEFORE the sweep
        box_highs = high[s-p.lookback:s]
        box_lows = low[s-p.lookback:s]
        
        box_hi = np.max(box_highs)
        box_lo = np.min(box_lows)
        
        if (box_hi - box_lo) > p.box_atr_max * atr_s:
            continue
            
        eq_low_touches = np.sum(box_lows <= box_lo + p.eq_tol_atr * atr_s)
        eq_high_touches = np.sum(box_highs >= box_hi - p.eq_tol_atr * atr_s)
        
        # BULLISH
        swept_low = low[s] < box_lo - p.sweep_wick_atr * atr_s
        closed_inside_bull = (close[s] > box_lo) if p.require_close_inside else True
        
        if swept_low and closed_inside_bull and eq_low_touches >= p.min_eq_touches:
            impulse_low = np.min(low[s:i+1])
            impulse_high = np.max(high[s:i+1])
            
            if i - (s + 1) >= 1:
                internal_high = np.max(high[s+1:i])
            else:
                internal_high = high[s]
                
            disp_ok = (close[i] - impulse_low) >= p.disp_atr * atr_i
            mss_up = disp_ok and close[i] > internal_high and close[i] > box_lo
            
            trend_ok = True if p.trend_filter == "none" else (np.isfinite(ema_vals[i]) and close[i] > ema_vals[i])
            
            if mss_up and trend_ok:
                rng = impulse_high - impulse_low
                if rng > 0:
                    entry = impulse_high - retr * rng
                    sl = impulse_low - p.sl_atr * atr_i
                    risk = entry - sl
                    
                    if risk < p.min_stop_atr * atr_i:
                        sl = entry - p.min_stop_atr * atr_i
                        risk = entry - sl
                        
                    if risk > 0:
                        return Setup("long", i, s, entry, sl, entry + p.tp1_r * risk, entry + p.tp_final_r * risk,
                                     risk, impulse_low, impulse_high, i + p.entry_valid_bars)
                                     
        # BEARISH
        swept_high = high[s] > box_hi + p.sweep_wick_atr * atr_s
        closed_inside_bear = (close[s] < box_hi) if p.require_close_inside else True
        
        if swept_high and closed_inside_bear and eq_high_touches >= p.min_eq_touches:
            impulse_high = np.max(high[s:i+1])
            impulse_low = np.min(low[s:i+1])
            
            if i - (s + 1) >= 1:
                internal_low = np.min(low[s+1:i])
            else:
                internal_low = low[s]
                
            disp_ok = (impulse_high - close[i]) >= p.disp_atr * atr_i
            mss_dn = disp_ok and close[i] < internal_low and close[i] < box_hi
            
            trend_ok = True if p.trend_filter == "none" else (np.isfinite(ema_vals[i]) and close[i] < ema_vals[i])
            
            if mss_dn and trend_ok:
                rng = impulse_high - impulse_low
                if rng > 0:
                    entry = impulse_low + retr * rng
                    sl = impulse_high + p.sl_atr * atr_i
                    risk = sl - entry
                    
                    if risk < p.min_stop_atr * atr_i:
                        sl = entry + p.min_stop_atr * atr_i
                        risk = sl - entry
                        
                    if risk > 0:
                        return Setup("short", i, s, entry, sl, entry - p.tp1_r * risk, entry - p.tp_final_r * risk,
                                     risk, impulse_low, impulse_high, i + p.entry_valid_bars)
                                     
    return None
