from dataclasses import dataclass, field
from typing import List, Tuple

@dataclass
class StrategyParams:
    lookback: int = 24
    atr_len: int = 14
    box_atr_max: float = 6.0
    eq_tol_atr: float = 0.18
    min_eq_touches: int = 2
    accum_max_age: int = 6
    require_close_inside: bool = True
    sweep_wick_atr: float = 0.10
    swing_len: int = 3
    disp_atr: float = 1.5
    mss_max_age: int = 8
    entry_mode: str = "ote50"
    entry_valid_bars: int = 8
    min_stop_atr: float = 0.5
    sl_atr: float = 0.5
    tp1_r: float = 1.5
    tp1_frac: float = 1.0
    breakeven_after_tp1: bool = False
    tp_final_r: float = 3.0
    trend_filter: str = "none"
    trend_ema: int = 200
    session_filter: bool = False
    killzones_utc: List[Tuple[int, int]] = field(default_factory=lambda: [(7, 10), (12, 15)])
    cooldown_bars: int = 4
    risk_pct: float = 0.01
    fee_pct: float = 0.00055
    slippage_pct: float = 0.0002
    max_leverage: float = 10.0

@dataclass
class MarketConfig:
    symbol: str = "BTCUSDT"
    mudrex_asset: str = "BTC/USDT"
    interval: str = "5m"
    initial_capital: float = 10000.0

import os

@dataclass
class RexAlgoConfig:
    webhook_url: str = os.environ.get("REXALGO_WEBHOOK_URL", "https://rexalgo-production.up.railway.app/api/webhooks/strategy")
    secret: str = os.environ.get("REXALGO_SECRET", "PASTE_WEBHOOK_SECRET_FROM_STRATEGY_STUDIO")
    strategy_id: str = os.environ.get("REXALGO_STRATEGY_ID", "PASTE_STRATEGY_ID")
    dry_run: bool = os.environ.get("REXALGO_DRY_RUN", "True").lower() in ("true", "1", "yes")

@dataclass
class AppConfig:
    strategy: StrategyParams = field(default_factory=StrategyParams)
    market: MarketConfig = field(default_factory=MarketConfig)
    rexalgo: RexAlgoConfig = field(default_factory=RexAlgoConfig)

CONFIG = AppConfig()
