import numpy as np
import pandas as pd

def true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    """Calculate True Range."""
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    return pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

def atr(high: pd.Series, low: pd.Series, close: pd.Series, length: int) -> pd.Series:
    """Calculate Wilder's Average True Range."""
    tr = true_range(high, low, close)
    atr_vals = np.zeros(len(tr))
    tr_vals = tr.values
    
    first_valid = tr.first_valid_index()
    if first_valid is None:
        return pd.Series(np.nan, index=high.index)
        
    idx = tr.index.get_loc(first_valid)
    if idx + length <= len(tr):
        initial_atr = np.nanmean(tr_vals[idx:idx+length])
        atr_vals[:idx+length] = np.nan
        atr_vals[idx+length-1] = initial_atr
        for i in range(idx+length, len(tr)):
            atr_vals[i] = (atr_vals[i-1] * (length - 1) + tr_vals[i]) / length
    else:
        atr_vals[:] = np.nan
        
    return pd.Series(atr_vals, index=high.index)

def ema(series: pd.Series, length: int) -> pd.Series:
    """Calculate Exponential Moving Average."""
    return series.ewm(span=length, adjust=False).mean()

def swing_highs(high: pd.Series, length: int) -> pd.Series:
    """Detect swing highs (placeholder)."""
    pass

def swing_lows(low: pd.Series, length: int) -> pd.Series:
    """Detect swing lows (placeholder)."""
    pass

def last_confirmed_pivot():
    """Get last confirmed pivot (placeholder)."""
    pass
