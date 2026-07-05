import time
import json
import threading
from datetime import datetime, timezone
import pandas as pd
from config import CONFIG
from data_feed import INTERVAL_MAP, load_ohlcv
from strategy import add_features, detect_setup
from rexalgo_client import RexAlgoClient

try:
    import websocket
except ImportError:
    websocket = None


def interval_seconds(interval: str) -> int:
    """Return candle length in seconds for a supported interval string."""
    if interval not in INTERVAL_MAP:
        raise ValueError(f"Unsupported interval: {interval}")
    return INTERVAL_MAP[interval][0]


def bybit_kline_topic(symbol: str, interval: str) -> str:
    """Build Bybit linear kline subscription topic, e.g. kline.5.BTCUSDT."""
    bybit_interval = INTERVAL_MAP[interval][2]
    return f"kline.{bybit_interval}.{symbol}"


class CandleAggregator:
    def __init__(self, tf_seconds: int):
        self.tf_seconds = tf_seconds
        self.current_bucket = None
        self.o = self.h = self.l = self.c = self.v = 0.0

    def add_1m(self, t: int, o: float, h: float, l: float, c: float, v: float):
        bucket = (t // self.tf_seconds) * self.tf_seconds

        closed_candle = None
        if self.current_bucket is not None and bucket > self.current_bucket:
            closed_candle = (self.current_bucket, self.o, self.h, self.l, self.c, self.v)
            self.current_bucket = bucket
            self.o = o
            self.h = h
            self.l = l
            self.c = c
            self.v = v
        elif self.current_bucket is None:
            self.current_bucket = bucket
            self.o = o
            self.h = h
            self.l = l
            self.c = c
            self.v = v
        else:
            self.h = max(self.h, h)
            self.l = min(self.l, l)
            self.c = c
            self.v += v

        return closed_candle


class LiveRunner:
    def __init__(self):
        self.p = CONFIG.strategy
        self.m = CONFIG.market
        self.client = RexAlgoClient(CONFIG.rexalgo)

        self.df = pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
        self.pos_side = None
        self.pos_entry = 0.0
        self.pos_sl = 0.0
        self.pos_tp = 0.0
        self.pos_risk = 0.0
        self.cooldown_until = 0
        self.last_signal_ts = None

        self.tf_seconds = interval_seconds(self.m.interval)
        self.agg = CandleAggregator(self.tf_seconds)

    def seed_history(self):
        print(f"Seeding history for {self.m.symbol} {self.m.interval}...")
        end_ms = int(time.time() * 1000)
        start_ms = end_ms - (self.p.trend_ema + self.p.lookback + 120) * self.tf_seconds * 1000

        df, src = load_ohlcv(
            self.m.symbol, self.m.mudrex_asset, self.m.interval, start_ms, end_ms, "auto"
        )
        if df.empty:
            raise Exception("Failed to seed history")
        self.df = df
        print(f"Seeded {len(self.df)} candles from {src}")

    def _log(self, msg: dict):
        msg["ts"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        print(json.dumps(msg))
        with open("alerts.jsonl", "a") as f:
            f.write(json.dumps(msg) + "\n")

    def on_closed_candle(self, t: int, o: float, h: float, l: float, c: float, v: float):
        ts = pd.to_datetime(t, unit="s", utc=True)
        self.df.loc[ts] = [o, h, l, c, v]

        df_feat = add_features(self.df, self.p)
        i = len(df_feat) - 1

        if self.pos_side:
            hit_sl = (self.pos_side == "long" and l <= self.pos_sl) or (
                self.pos_side == "short" and h >= self.pos_sl
            )
            hit_tp = (self.pos_side == "long" and h >= self.pos_tp) or (
                self.pos_side == "short" and l <= self.pos_tp
            )

            if hit_sl or hit_tp:
                exit_price = self.pos_sl if hit_sl else self.pos_tp
                pnl = (exit_price - self.pos_entry) if self.pos_side == "long" else (
                    self.pos_entry - exit_price
                )
                roi_pct = (pnl / self.pos_entry) * 100
                rr = pnl / self.pos_risk if self.pos_risk > 0 else 0

                self.client.close(
                    self.m.symbol, self.pos_side, self.pos_entry, exit_price, pnl, roi_pct, rr
                )
                self._log({"event": "close", "side": self.pos_side, "pnl": pnl})

                self.pos_side = None
                self.cooldown_until = i + self.p.cooldown_bars

        if i >= self.cooldown_until:
            setup = detect_setup(df_feat, i, self.p)
            if setup and df_feat.index[setup.signal_bar] != self.last_signal_ts:
                self.last_signal_ts = df_feat.index[setup.signal_bar]

                if not self.pos_side:
                    self.client.open(
                        self.m.symbol, setup.side, "LIMIT", setup.entry, setup.sl, setup.tp2
                    )
                    self._log({"event": "open", "side": setup.side, "entry": setup.entry})
                    self.pos_side = setup.side
                    self.pos_entry = setup.entry
                    self.pos_sl = setup.sl
                    self.pos_tp = setup.tp2
                    self.pos_risk = setup.risk
                elif self.pos_side != setup.side:
                    self.client.flip(
                        self.m.symbol, setup.side, setup.entry, setup.sl, setup.tp2
                    )
                    self._log({"event": "flip", "side": setup.side, "entry": setup.entry})
                    self.pos_side = setup.side
                    self.pos_entry = setup.entry
                    self.pos_sl = setup.sl
                    self.pos_tp = setup.tp2
                    self.pos_risk = setup.risk

    def run_mudrex(self):
        if not websocket:
            print("websocket-client not installed")
            return

        url = "wss://trade.mudrex.com/fapi/v1/price/ws/linear"

        def on_message(ws, message):
            data = json.loads(message)
            if "data" in data and "stream" in data and "1m" in data["stream"]:
                d = data["data"]
                closed = self.agg.add_1m(d["t"], d["o"], d["h"], d["l"], d["c"], d["v"])
                if closed:
                    self.on_closed_candle(*closed)

        def on_open(ws):
            print(f"Mudrex WS connected — aggregating 1m → {self.m.interval}")
            ws.send(json.dumps({"method": "SUBSCRIBE", "params": ["kline@1m@btcusdt"], "id": 1}))

            def keepalive():
                while ws.keep_running:
                    time.sleep(20)
                    try:
                        ws.send(json.dumps({"method": "LIST_SUBSCRIPTIONS", "id": 2}))
                    except Exception:
                        break

            threading.Thread(target=keepalive, daemon=True).start()

        ws = websocket.WebSocketApp(url, on_message=on_message, on_open=on_open)
        ws.run_forever()

    def run_bybit(self):
        if not websocket:
            return

        url = "wss://stream.bybit.com/v5/public/linear"
        topic = bybit_kline_topic(self.m.symbol, self.m.interval)

        def on_message(ws, message):
            data = json.loads(message)
            if "topic" in data and "kline" in data["topic"]:
                for k in data.get("data", []):
                    if k.get("confirm"):
                        self.on_closed_candle(
                            int(k["start"]) // 1000,
                            float(k["open"]),
                            float(k["high"]),
                            float(k["low"]),
                            float(k["close"]),
                            float(k["volume"]),
                        )

        def on_open(ws):
            print(f"Bybit WS connected — {topic}")
            ws.send(json.dumps({"op": "subscribe", "args": [topic]}))

            def keepalive():
                while ws.keep_running:
                    time.sleep(20)
                    try:
                        ws.send(json.dumps({"op": "ping"}))
                    except Exception:
                        break

            threading.Thread(target=keepalive, daemon=True).start()

        ws = websocket.WebSocketApp(url, on_message=on_message, on_open=on_open)
        ws.run_forever()

    def run(self):
        self.seed_history()
        while True:
            try:
                print("Starting Mudrex WS...")
                self.run_mudrex()
            except Exception as e:
                print(f"Mudrex WS error: {e}")

            try:
                print("Falling back to Bybit WS...")
                self.run_bybit()
            except Exception as e:
                print(f"Bybit WS error: {e}")

            print("Reconnecting in 10s...")
            time.sleep(10)


if __name__ == "__main__":
    LiveRunner().run()
