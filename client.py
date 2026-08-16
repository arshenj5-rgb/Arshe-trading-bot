import asyncio
import json
from typing import Any

import websockets


class DerivClient:
    """Small Deriv public market-data WebSocket client.

    This version deliberately uses public market data only. No login token
    or account credentials are required for active_symbols or candle data.
    """

    # Preferred markets. AUTO mode only uses one of these if Deriv reports it
    # as currently active and it successfully returns candle data.
    PREFERRED_SYMBOLS = (
        "1HZ100V",
        "R_100",
        "R_75",
        "R_50",
        "R_25",
        "frxEURUSD",
        "frxGBPUSD",
        "frxUSDJPY",
    )

    def __init__(self, url: str):
        self.url = url
        self.ws = None
        self.req_id = 0

    async def connect(self):
        print(f"Connecting to Deriv market data: {self.url}")
        self.ws = await websockets.connect(
            self.url,
            ping_interval=20,
            ping_timeout=20,
            close_timeout=5,
            open_timeout=20,
        )
        print("Connected to Deriv WebSocket.")

    async def close(self):
        if self.ws is not None:
            try:
                await self.ws.close()
            finally:
                self.ws = None

    async def request(self, payload: dict[str, Any], timeout: float = 20) -> dict[str, Any]:
        if self.ws is None:
            raise RuntimeError("WebSocket is not connected")

        self.req_id += 1
        request_id = self.req_id
        await self.ws.send(json.dumps({**payload, "req_id": request_id}))

        while True:
            raw = await asyncio.wait_for(self.ws.recv(), timeout=timeout)
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            if msg.get("req_id") != request_id:
                continue

            if "error" in msg:
                error = msg["error"] or {}
                raise RuntimeError(
                    f"Deriv error {error.get('code', 'Unknown')}: "
                    f"{error.get('message', 'Unknown error')}"
                )
            return msg

    @staticmethod
    def symbol_code(item: dict[str, Any]) -> str:
        # Current API field is underlying_symbol; legacy API used symbol.
        return str(item.get("underlying_symbol") or item.get("symbol") or "").strip()

    async def active_symbols(self) -> list[dict[str, Any]]:
        """Fetch active symbols using the current API shape, with a fallback."""
        response = await self.request({"active_symbols": "brief"})
        symbols = response.get("active_symbols")
        if isinstance(symbols, list) and symbols:
            return symbols

        # Compatibility fallback for older gateway behaviour.
        response = await self.request({"active_symbols": "full"})
        symbols = response.get("active_symbols")
        return symbols if isinstance(symbols, list) else []

    @staticmethod
    def _is_usable_symbol(item: dict[str, Any]) -> bool:
        code = DerivClient.symbol_code(item)
        if not code:
            return False
        # If these flags are supplied, don't choose a suspended/closed market.
        if str(item.get("is_trading_suspended", "0")) == "1":
            return False
        if "exchange_is_open" in item and str(item.get("exchange_is_open")) == "0":
            # Synthetic/24h markets may not expose this flag; only reject an
            # explicitly closed symbol when another suitable symbol exists.
            return False
        return True

    async def _verify_symbol(self, symbol: str) -> bool:
        try:
            response = await self.request({
                "ticks_history": symbol,
                "style": "candles",
                "granularity": 60,
                "count": 5,
                "end": "latest",
            })
            candles = response.get("candles")
            return isinstance(candles, list) and len(candles) >= 2
        except Exception as exc:
            print(f"  {symbol}: candle check failed ({exc})")
            return False

    async def resolve_symbol(self, requested: str) -> str:
        """Choose a currently usable Deriv symbol and verify it with candles."""
        requested = (requested or "AUTO").strip()
        symbols = await self.active_symbols()
        records = [s for s in symbols if isinstance(s, dict) and self.symbol_code(s)]
        available = {self.symbol_code(s): s for s in records}
        print(f"Deriv returned {len(available)} active symbols.")

        if not available:
            raise RuntimeError(
                "Deriv returned zero active symbols. The WebSocket connected, "
                "but the active_symbols response contained no usable symbols."
            )

        if requested.upper() != "AUTO":
            candidates = [requested]
        else:
            # Prefer configured/default markets, then fall back to whatever
            # Deriv actually reported as active.
            candidates = [s for s in self.PREFERRED_SYMBOLS if s in available]
            candidates += [s for s in sorted(available) if s not in candidates]

        # First pass: usable/open-looking records.
        usable = [s for s in candidates if self._is_usable_symbol(available[s])]
        if usable:
            candidates = usable + [s for s in candidates if s not in usable]

        for symbol in candidates:
            print(f"Checking Deriv symbol: {symbol}")
            if await self._verify_symbol(symbol):
                print(f"Confirmed usable active symbol: {symbol}")
                return symbol

        sample = ", ".join(candidates[:20])
        raise RuntimeError(
            "Deriv reported active symbols, but none returned candle data. "
            f"Sample checked symbols: {sample or 'none'}"
        )

    async def candles(self, symbol: str, granularity: int, count: int = 300) -> list[dict[str, Any]]:
        response = await self.request({
            "ticks_history": symbol,
            "style": "candles",
            "granularity": granularity,
            "count": count,
            "end": "latest",
        })

        raw_candles = response.get("candles", [])
        if not isinstance(raw_candles, list):
            return []

        result = []
        for c in raw_candles:
            try:
                result.append({
                    "epoch": int(c["epoch"]),
                    "open": float(c["open"]),
                    "high": float(c["high"]),
                    "low": float(c["low"]),
                    "close": float(c["close"]),
                    "granularity": granularity,
                })
            except (KeyError, TypeError, ValueError):
                continue
        return result

    async def subscribe_candles(self, symbol: str, granularity: int) -> int:
        if self.ws is None:
            raise RuntimeError("WebSocket is not connected")

        self.req_id += 1
        request_id = self.req_id
        await self.ws.send(json.dumps({
            "ticks_history": symbol,
            "style": "candles",
            "granularity": granularity,
            "count": 1,
            "end": "latest",
            "subscribe": 1,
            "req_id": request_id,
        }))

        while True:
            raw = await asyncio.wait_for(self.ws.recv(), timeout=20)
            msg = json.loads(raw)
            if msg.get("req_id") != request_id:
                continue
            if "error" in msg:
                error = msg["error"] or {}
                raise RuntimeError(
                    f"Deriv error {error.get('code', 'Unknown')}: "
                    f"{error.get('message', 'Unknown error')}"
                )
            return request_id

    async def stream(self):
        if self.ws is None:
            raise RuntimeError("WebSocket is not connected")
        while True:
            raw = await self.ws.recv()
            yield json.loads(raw)
