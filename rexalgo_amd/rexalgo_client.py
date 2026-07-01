import json
import time
import hmac
import hashlib
import urllib.request
import urllib.error
import uuid
from config import RexAlgoConfig

class RexAlgoClient:
    def __init__(self, cfg: RexAlgoConfig):
        self.cfg = cfg
        
    def _send(self, body: dict) -> tuple[int, str]:
        body["idempotency_key"] = str(uuid.uuid4())
        body["secret"] = self.cfg.secret
        
        raw = json.dumps(body, separators=(",", ":"))
        
        if self.cfg.dry_run:
            print(f"[DRY-RUN] would POST {raw}")
            return (0, "dry-run")
            
        ts = str(int(time.time()))
        sig = hmac.new(self.cfg.secret.encode(), f"{ts}.{raw}".encode(), hashlib.sha256).hexdigest()
        
        req = urllib.request.Request(self.cfg.webhook_url, data=raw.encode(), headers={
            "X-RexAlgo-Signature": f"t={ts},v1={sig}",
            "Content-Type": "application/json"
        })
        
        try:
            with urllib.request.urlopen(req) as response:
                return response.getcode(), response.read().decode()
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode()
        except Exception as e:
            return 500, str(e)

    def open(self, symbol: str, side: str, trigger_type: str = "MARKET", price: float = None, sl: float = None, tp: float = None) -> tuple[int, str]:
        body = {
            "action": "open",
            "symbol": symbol,
            "side": side.upper(),
            "trigger_type": trigger_type.upper()
        }
        if trigger_type.upper() == "LIMIT" and price is not None:
            body["price"] = str(price)
        if sl is not None:
            body["sl"] = str(sl)
        if tp is not None:
            body["tp"] = str(tp)
        return self._send(body)
        
    def close(self, symbol: str, side: str, entry_price: float, exit_price: float, pnl: float, roi_pct: float, risk_reward: float, trigger_type: str = "MARKET") -> tuple[int, str]:
        body = {
            "action": "close",
            "symbol": symbol,
            "side": side.upper(),
            "trigger_type": trigger_type.upper(),
            "entry_price": str(entry_price),
            "exit_price": str(exit_price),
            "pnl": str(pnl),
            "roi_pct": str(roi_pct),
            "risk_reward": str(risk_reward)
        }
        return self._send(body)
        
    def flip(self, symbol: str, side: str, entry_price: float, sl: float = None, tp: float = None, trigger_type: str = "MARKET") -> tuple[int, str]:
        body = {
            "action": "flip",
            "symbol": symbol,
            "side": side.upper(),
            "trigger_type": trigger_type.upper(),
            "entry_price": str(entry_price)
        }
        if sl is not None:
            body["sl"] = str(sl)
        if tp is not None:
            body["tp"] = str(tp)
        return self._send(body)
