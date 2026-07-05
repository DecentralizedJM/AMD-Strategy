import argparse
import json
import pandas as pd
from datetime import datetime, timedelta, timezone
from config import CONFIG
from data_feed import load_ohlcv
from backtester import run_backtest

def main():
    parser = argparse.ArgumentParser(description="RexAlgo AMD Backtester")
    parser.add_argument("--source", choices=["auto", "mudrex", "bybit", "synthetic"], default="auto")
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--interval", default="5m")
    parser.add_argument("--start", help="YYYY-MM-DD")
    parser.add_argument("--end", help="YYYY-MM-DD")
    parser.add_argument("--out", default="backtest_result.json")
    args = parser.parse_args()
    
    end_dt = datetime.now(timezone.utc)
    if args.end:
        end_dt = datetime.strptime(args.end, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        
    start_dt = end_dt - timedelta(days=365)
    if args.start:
        start_dt = datetime.strptime(args.start, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        
    start_ms = int(start_dt.timestamp() * 1000)
    end_ms = int(end_dt.timestamp() * 1000)
    
    print(f"Loading data from {args.source} for {args.symbol} {args.interval} from {start_dt.date()} to {end_dt.date()}...")
    df, source_used = load_ohlcv(args.symbol, "BTC/USDT", args.interval, start_ms, end_ms, args.source)
    
    if df.empty:
        print("No data loaded.")
        return
        
    print(f"Loaded {len(df)} candles from {source_used}.")
    
    CONFIG.market.symbol = args.symbol
    CONFIG.market.interval = args.interval
    
    result = run_backtest(df, CONFIG.strategy, CONFIG.market)
    result["exampleOnly"] = (source_used == "synthetic")
    result["meta"]["dataSource"] = source_used
    
    with open(args.out, "w") as f:
        json.dump(result, f, indent=2)
        
    print("\nBacktest Summary:")
    print(f"Total Return: {result['summary']['totalReturnPct']}%")
    print(f"Win Rate: {result['summary']['winRatePct']}%")
    print(f"Max Drawdown: {result['summary']['maxDrawdownPct']}%")
    print(f"Trades: {result['summary']['trades']}")
    print(f"Profit Factor: {result['summary']['profitFactor']}")
    print(f"Initial Capital: {result['summary']['initialCapital']}")
    print(f"Final Capital: {result['summary']['finalCapital']}")
    print(f"\nResults written to {args.out}")

if __name__ == "__main__":
    main()
