import asyncio
import json
from typing import Any

import websockets


class DerivClient:
    """Small Deriv public-market WebSocket client.

    This client deliberately uses the public market-data endpoint only.
    No login token or account credentials are needed for market data.
    """

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
        message = {**payload, "req_id": request_id}

        await self.ws.send(json.dumps(message))

        while True:
            raw = await asyncio.wait_for(self.ws.recv(), timeout=timeout)
            msg = json.loads(raw)

            # Only consume the response belonging to this request.
            if msg.get("req_id") != request_id:
                continue

            if "error" in msg:
                error = msg["error"]
                raise RuntimeError(
                    f"Deriv error {error.get('code', 'Unknown')}: "
                    f"{error.get('message', 'Unknown error')}"
                )

            return msg

    async def active_symbols(self) -> list[dict[str, Any]]:
        response = await self.request({"active_symbols": "brief"})
        symbols = response.get("active_symbols", [])
        return symbols if isinstance(symbols, list) else []

    @staticmethod
    def symbol_code(item: dict[str, Any]) -> str:
        # Current Deriv API: underlying_symbol
        # Legacy Deriv API: symbol
        return str(
            item.get("underlying_symbol")
            or item.get("symbol")
            or ""
        ).strip()

    async def resolve_symbol(self, requested: str) -> str:
        """Resolve a requested symbol against Deriv's current active-symbol list.

        The bot does not blindly assume that a symbol is active. It first asks
        Deriv for the current list, supports the current underlying_symbol field,
        and then verifies the requested symbol with a small candle request.
        """
        requested = requested.strip()
        symbols = await self.active_symbols()

        available = [
            self.symbol_code(item)
            for item in symbols
            if self.symbol_code(item)
        ]
        available_set = set(available)

        print(f"Deriv returned {len(available_set)} active symbols.")

        if requested not in available_set:
            sample = ", ".join(sorted(available_set)[:20])
            raise RuntimeError(
                f"Requested symbol '{requested}' is not active on Deriv right now. "
                f"Sample active symbols: {sample or 'none'}"
            )

        # Verify the exact symbol through market data before doing all timeframes.
        response = await self.request({
            "ticks_history": requested,
            "style": "candles",
            "granularity": 60,
            "count": 2,
            "end": "latest",
        })

        candles = response.get("candles", [])
        if not candles:
            raise RuntimeError(
                f"Deriv accepted symbol '{requested}' but returned no candles."
            )

        print(f"Confirmed active symbol: {requested}")
        return requested

    async def candles(
        self,
        symbol: str,
        granularity: int,
        count: int = 300,
    ) -> list[dict[str, Any]]:
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

        # Consume the acknowledgement/current candle for this subscription.
        while True:
            raw = await asyncio.wait_for(self.ws.recv(), timeout=20)
            msg = json.loads(raw)
            if msg.get("req_id") != request_id:
                continue
            if "error" in msg:
                error = msg["error"]
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
