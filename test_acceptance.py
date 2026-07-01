import os
import json
import subprocess
import sys

def run_tests():
    print("Running Acceptance Tests...")
    
    # Test 1: Run backtest
    print("\nTest 1: Running backtest...")
    result = subprocess.run([sys.executable, "run_backtest.py", "--source", "synthetic", "--start", "2024-06-01", "--end", "2025-06-01"], cwd="rexalgo_amd", capture_output=True, text=True)
    if result.returncode != 0:
        print("Test 1 Failed!")
        print(result.stderr)
        return False
    print("Test 1 Passed.")
    
    # Test 2: Verification script
    print("\nTest 2: Verifying backtest result...")
    with open("rexalgo_amd/backtest_result.json") as f:
        data = json.load(f)
        
    summary = data["summary"]
    trades = data["trades"]
    equity = data["equity"]
    
    initial = summary["initialCapital"]
    final = summary["finalCapital"]
    
    calc_final = initial + sum(t["pnl"] for t in trades)
    if abs(calc_final - final) > 0.01:
        print(f"Test 2 Failed: Final capital mismatch. Expected {final}, got {calc_final}")
        return False
        
    wins = [t for t in trades if t["pnl"] > 0]
    calc_win_rate = (len(wins) / len(trades) * 100) if trades else 0.0
    if abs(calc_win_rate - summary["winRatePct"]) > 0.01:
        print(f"Test 2 Failed: Win rate mismatch. Expected {summary['winRatePct']}, got {calc_win_rate}")
        return False
        
    gross_profit = sum(t["pnl"] for t in wins)
    gross_loss = abs(sum(t["pnl"] for t in trades if t["pnl"] <= 0))
    calc_pf = round(gross_profit / gross_loss, 2) if gross_loss > 0 else None
    if calc_pf != summary["profitFactor"]:
        print(f"Test 2 Failed: Profit factor mismatch. Expected {summary['profitFactor']}, got {calc_pf}")
        return False
        
    # Check max drawdown
    max_dd = 0.0
    peak = initial
    for eq in equity:
        v = eq["v"]
        if v > peak:
            peak = v
        dd = (peak - v) / peak * 100
        if dd > max_dd:
            max_dd = dd
    if abs(round(max_dd, 2) - summary["maxDrawdownPct"]) > 0.01:
        print(f"Test 2 Failed: Max drawdown mismatch. Expected {summary['maxDrawdownPct']}, got {round(max_dd, 2)}")
        return False
        
    # Check timestamps sorted
    ts = [eq["t"] for eq in equity]
    if ts != sorted(ts):
        print("Test 2 Failed: Equity timestamps not sorted.")
        return False
        
    print("Test 2 Passed.")
    
    # Test 3: Imports
    print("\nTest 3: Checking imports...")
    result = subprocess.run([sys.executable, "-c", "import config, indicators, strategy, data_feed, backtester, rexalgo_client, live_runner"], cwd="rexalgo_amd", capture_output=True, text=True)
    if result.returncode != 0:
        print("Test 3 Failed!")
        print(result.stderr)
        return False
    print("Test 3 Passed.")
    
    # Test 4: CandleAggregator
    print("\nTest 4: Testing CandleAggregator...")
    code = """
from live_runner import CandleAggregator
agg = CandleAggregator(900)
closed = []
for i in range(30):
    t = 1800000000 + i * 60
    c = agg.add_1m(t, 100, 105, 95, 102, 10)
    if c:
        closed.append(c)
assert len(closed) == 1
c = closed[0]
assert c[0] == 1800000000
assert c[1] == 100
assert c[2] == 105
assert c[3] == 95
assert c[4] == 102
assert c[5] == 150
print("CandleAggregator OK")
"""
    result = subprocess.run([sys.executable, "-c", code], cwd="rexalgo_amd", capture_output=True, text=True)
    if result.returncode != 0:
        print("Test 4 Failed!")
        print(result.stderr)
        return False
    print("Test 4 Passed.")
    
    # Test 5: LiveRunner dry run
    print("\nTest 5: Testing LiveRunner dry run...")
    code = """
import os
if os.path.exists("alerts.jsonl"):
    os.remove("alerts.jsonl")
from live_runner import LiveRunner
from data_feed import synth_klines
runner = LiveRunner()
df = synth_klines(900, 1600000000000, 1600000000000 + 900 * 2000 * 1000)
runner.df = df.iloc[:-1000].copy()
for i in range(len(df)-1000, len(df)):
    row = df.iloc[i]
    runner.on_closed_candle(int(row.name.timestamp()), row['open'], row['high'], row['low'], row['close'], row['volume'])
assert os.path.exists("alerts.jsonl")
print("LiveRunner OK")
"""
    result = subprocess.run([sys.executable, "-c", code], cwd="rexalgo_amd", capture_output=True, text=True)
    if result.returncode != 0:
        print("Test 5 Failed!")
        print(result.stderr)
        return False
    print("Test 5 Passed.")
    
    # Test 6: RexAlgoClient
    print("\nTest 6: Testing RexAlgoClient...")
    code = """
from rexalgo_client import RexAlgoClient
from config import RexAlgoConfig
import json

cfg = RexAlgoConfig(dry_run=True, secret="test_secret")
client = RexAlgoClient(cfg)

# Open MARKET
code, msg = client.open("BTCUSDT", "LONG", "MARKET")
assert code == 0

# Open LIMIT
code, msg = client.open("BTCUSDT", "LONG", "LIMIT", price=60000, sl=59000, tp=62000)
assert code == 0

# Close
code, msg = client.close("BTCUSDT", "LONG", 60000, 62000, 2000, 3.33, 2.0)
assert code == 0

# Flip
code, msg = client.flip("BTCUSDT", "SHORT", 62000, sl=63000, tp=60000)
assert code == 0

print("RexAlgoClient OK")
"""
    result = subprocess.run([sys.executable, "-c", code], cwd="rexalgo_amd", capture_output=True, text=True)
    if result.returncode != 0:
        print("Test 6 Failed!")
        print(result.stderr)
        return False
    print("Test 6 Passed.")
    
    print("\nAll Acceptance Tests Passed!")
    return True

if __name__ == "__main__":
    run_tests()
