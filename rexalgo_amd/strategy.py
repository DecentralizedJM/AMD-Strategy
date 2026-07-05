import numpy as np
import pandas as pd
from dataclasses import dataclass
from config import StrategyParams
from indicators import atr

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
    # Calculate ATR based on Wilder's smoothing (length=14 as per user pseudo code)
    df["atr"] = atr(df["high"], df["low"], df["close"], 14)
    # The trend EMA is added for compatibility with the backtester, but not used in our pure logic
    df["ema_trend"] = np.nan
    return df

def session_ok(ts: pd.Timestamp, p: StrategyParams) -> bool:
    # No session filters in the raw rules
    return True

def detect_setup(df: pd.DataFrame, i: int, p: StrategyParams) -> Setup | None:
    # Needs at least 20 bars for accumulation + 5 bars for MSS
    if i < 25:
        return None
        
    atr_i = df["atr"].iloc[i]
    if not np.isfinite(atr_i) or atr_i <= 0:
        return None
        
    high = df["high"].values
    low = df["low"].values
    close = df["close"].values
    atr_vals = df["atr"].values
    
    # -----------------------------------------------------
    # Step 4: Market Structure Shift (MSS)
    # Sweep के बाद structure break चाहिए।
    # -----------------------------------------------------
    # Bullish MSS: close > max high of previous 5 bars
    prev_5_highs = high[i-5:i]
    is_bull_mss = close[i] > np.max(prev_5_highs)
    
    # Bearish MSS: close < min low of previous 5 bars
    prev_5_lows = low[i-5:i]
    is_bear_mss = close[i] < np.min(prev_5_lows)
    
    if not (is_bull_mss or is_bear_mss):
        return None
        
    # Scan backwards for a sweep that happened recently (e.g. up to 15 bars ago)
    for s in range(i - 1, i - 16, -1):
        if s - 20 < 0:
            continue
            
        # -----------------------------------------------------
        # Step 2: Liquidity Levels
        # Range High और Range Low निकालो। (Rolling 20 before the sweep)
        # -----------------------------------------------------
        box_hi = np.max(high[s-20:s])
        box_lo = np.min(low[s-20:s])
        
        # -----------------------------------------------------
        # Step 1: Accumulation Detection
        # Range size < ATR * 2.5
        # -----------------------------------------------------
        atr_s = atr_vals[s-1] # ATR at the end of accumulation
        if not np.isfinite(atr_s) or atr_s <= 0:
            continue
            
        is_accum = (box_hi - box_lo) < (2.5 * atr_s)
        if not is_accum:
            continue
            
        # -----------------------------------------------------
        # Step 3: Manipulation Detection & Steps 5-7: Entry Logic
        # -----------------------------------------------------
        if is_bull_mss:
            # Bullish AMD: range low के नीचे sweep
            if low[s] < box_lo:
                # We have Accumulation -> Sweep -> MSS!
                sweep_low = np.min(low[s:i+1])
                impulse_high = np.max(high[s:i+1])
                
                # "WAIT pullback" -> Limit order at 50% retracement of the impulse
                entry = sweep_low + 0.5 * (impulse_high - sweep_low)
                
                # Stop Loss = sweep low - atr
                sl = sweep_low - atr_i
                risk = entry - sl
                
                if risk > 0:
                    # Take Profit = 3R
                    tp = entry + 3 * risk
                    return Setup("long", i, s, entry, sl, tp, tp, risk, sweep_low, impulse_high, i + 8)
                    
        if is_bear_mss:
            # Bearish AMD: range high के ऊपर sweep
            if high[s] > box_hi:
                sweep_high = np.max(high[s:i+1])
                impulse_low = np.min(low[s:i+1])
                
                # "WAIT pullback" -> Limit order at 50% retracement
                entry = sweep_high - 0.5 * (sweep_high - impulse_low)
                
                # Stop Loss = sweep high + atr
                sl = sweep_high + atr_i
                risk = sl - entry
                
                if risk > 0:
                    # Take Profit = 3R
                    tp = entry - 3 * risk
                    return Setup("short", i, s, entry, sl, tp, tp, risk, impulse_low, sweep_high, i + 8)
                    
    return None
