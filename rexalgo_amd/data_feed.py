import time
import json
import urllib.request
import urllib.parse
import urllib.error
import numpy as np
import pandas as pd
from typing import Tuple

INTERVAL_MAP = {
    "1m": (60, "1m", "1"),
    "3m": (180, "3t", "3"),
    "5m": (300, "5t", "5"),
    "15m": (900, "15t", "15"),
    "30m": (1800, "30t", "30"),
    "1h": (3600, "1h", "60"),
    "4h": (14400, "4h", "240"),
    "1d": (86400, "1d", "D")
}

def fetch_mudrex(asset: str, aggregation: str, start_s: int, end_s: int) -> pd.DataFrame:
    url = f"https://trade.mudrex.com/fapi/v1/price/kline?assets={urllib.parse.quote(asset, safe='/')}&aggregation={aggregation}&start_time={start_s}&end_time={end_s}"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            if not data.get("success", False):
                raise Exception("Mudrex API success=false")
            
            asset_key = asset.lower()
            ticks = data.get("data", {}).get("asset_ticks", {}).get(asset_key, [])
            if not ticks:
                return pd.DataFrame()
                
            df = pd.DataFrame(ticks, columns=["open_time_s", "open", "high", "low", "close", "volume"])
            df["open_time"] = pd.to_datetime(df["open_time_s"], unit="s", utc=True)
            df.set_index("open_time", inplace=True)
            df.drop(columns=["open_time_s"], inplace=True)
            df = df.astype(float)
            return df
    except Exception as e:
        print(f"Mudrex fetch error: {e}")
        return pd.DataFrame()

def fetch_bybit(symbol: str, interval: str, start_ms: int, end_ms: int) -> pd.DataFrame:
    url = f"https://api.bybit.com/v5/market/kline?category=linear&symbol={symbol}&interval={interval}&start={start_ms}&end={end_ms}&limit=1000"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            if str(data.get("retCode")) != "0":
                raise Exception(f"Bybit API error: {data.get('retMsg')}")
                
            ticks = data.get("result", {}).get("list", [])
            if not ticks:
                return pd.DataFrame()
                
            df = pd.DataFrame(ticks, columns=["start_ms", "open", "high", "low", "close", "volume", "turnover"])
            df["open_time"] = pd.to_datetime(pd.to_numeric(df["start_ms"]), unit="ms", utc=True)
            df.set_index("open_time", inplace=True)
            df.drop(columns=["start_ms", "turnover"], inplace=True)
            df = df.astype(float)
            df.sort_index(ascending=True, inplace=True)
            return df
    except Exception as e:
        print(f"Bybit fetch error: {e}")
        return pd.DataFrame()

def synth_klines(interval_s: int, start_ms: int, end_ms: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed=7)
    start_s = start_ms // 1000
    end_s = end_ms // 1000
    times = np.arange(start_s, end_s + 1, interval_s)
    n = len(times)
    if n == 0:
        return pd.DataFrame()
        
    bars_per_year = (365 * 24 * 3600) / interval_s
    sigma = 0.55 / np.sqrt(bars_per_year)
    
    regimes = np.zeros(n)
    current_regime = 0
    for i in range(1, n):
        if rng.random() < 0.05:
            current_regime = rng.choice([0, 1, -1])
        regimes[i] = current_regime
        
    drifts = regimes * (sigma * 0.1)
    returns = rng.normal(loc=drifts, scale=sigma, size=n)
    
    closes = np.zeros(n)
    closes[0] = 60000.0
    for i in range(1, n):
        closes[i] = closes[i-1] * np.exp(returns[i])
        
    opens = np.zeros(n)
    opens[0] = closes[0]
    opens[1:] = closes[:-1]
    
    highs = np.maximum(opens, closes) + rng.exponential(scale=closes*sigma*0.5, size=n)
    lows = np.minimum(opens, closes) - rng.exponential(scale=closes*sigma*0.5, size=n)
    
    sweep_mask = rng.random(size=n) < 0.03
    for i in np.where(sweep_mask)[0]:
        if rng.random() < 0.5:
            highs[i] += closes[i] * sigma * 3
        else:
            lows[i] -= closes[i] * sigma * 3
            
    volumes = rng.lognormal(mean=100, sigma=1, size=n)
    
    df = pd.DataFrame({
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": volumes
    }, index=pd.to_datetime(times, unit="s", utc=True))
    
    return df

def load_ohlcv(symbol: str, mudrex_asset: str, interval: str, start_ms: int, end_ms: int, source: str = "auto") -> Tuple[pd.DataFrame, str]:
    if interval not in INTERVAL_MAP:
        raise ValueError(f"Unsupported interval: {interval}")
        
    interval_s, mudrex_agg, bybit_inv = INTERVAL_MAP[interval]
    start_s = start_ms // 1000
    end_s = end_ms // 1000
    
    if source in ["auto", "mudrex"]:
        dfs = []
        chunk_s = interval_s * 1440
        for chunk_start in range(start_s, end_s + 1, chunk_s):
            chunk_end = min(chunk_start + chunk_s - 1, end_s)
            df = fetch_mudrex(mudrex_asset, mudrex_agg, chunk_start, chunk_end)
            if not df.empty:
                dfs.append(df)
            time.sleep(0.25)
        if dfs:
            df = pd.concat(dfs)
            df = df[~df.index.duplicated(keep='first')].sort_index()
            return df, "mudrex"
            
    if source in ["auto", "bybit"]:
        dfs = []
        chunk_ms = interval_s * 1000 * 1000
        for chunk_start in range(start_ms, end_ms + 1, chunk_ms):
            chunk_end = min(chunk_start + chunk_ms - 1, end_ms)
            df = fetch_bybit(symbol, bybit_inv, chunk_start, chunk_end)
            if not df.empty:
                dfs.append(df)
            time.sleep(0.15)
        if dfs:
            df = pd.concat(dfs)
            df = df[~df.index.duplicated(keep='first')].sort_index()
            return df, "bybit"
            
    if source in ["auto", "synthetic"] or source == "synthetic":
        df = synth_klines(interval_s, start_ms, end_ms)
        return df, "synthetic"
        
    return pd.DataFrame(), "none"
