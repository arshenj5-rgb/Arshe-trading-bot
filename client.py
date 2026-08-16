import asyncio
import json
from typing import Any

import websockets


class DerivClient:
    def __init__(self, url: str, app_id: str = ""):
        self.url = url

        # Keep compatibility with old deployments.
        if app_id and "app_id=" not in url:
            self.url = f"{url}?app_id={app_id}"

        self.ws = None
        self.req_id = 0

    async def connect(self):
        if self.ws is not None:
            return

        self.ws = await websockets.connect(
            self.url,
            ping_interval=20,
            ping_timeout=20,
            close_timeout=5,
            max_size=10 * 1024 * 1024,
        )

    async def close(self):
        if self.ws is not None:
            try:
                await self.ws.close()
            finally:
                self.ws = None

    async def request(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self.ws is None:
            raise RuntimeError("WebSocket is not connected")

        self.req_id += 1

        request = dict(payload)
        request["req_id"] = self.req_id

        await self.ws.send(json.dumps(request))

        while True:
            raw = await self.ws.recv()
            msg = json.loads(raw)

            # Ignore unrelated subscription messages.
            if msg.get("req_id") != self.req_id:
                continue

            if "error" in msg:
                error = msg["error"]
                code = error.get("code", "UnknownError")
                message = error.get("message", "Unknown Deriv error")

                raise RuntimeError(
                    f"Deriv error {code}: {message}"
                )

            return msg

    async def active_symbols(self) -> list[dict[str, Any]]:
        """
        Get all active Deriv symbols.

        Current Deriv API returns:
            underlying_symbol

        Older API versions returned:
            symbol
        """

        response = await self.request({
            "active_symbols": "brief"
        })

        symbols = response.get("active_symbols", [])

        if not isinstance(symbols, list):
            raise RuntimeError(
                "Deriv returned an invalid active_symbols response."
            )

        return symbols

    async def resolve_symbol(self, requested_symbol: str) -> str:
        """
        Resolve a symbol against Deriv's current active-symbol list.

        Supports both:
            underlying_symbol  (new API)
            symbol             (legacy API)
        """

        requested = requested_symbol.strip().upper()

        symbols = await self.active_symbols()

        print(f"Deriv returned {len(symbols)} active symbols.")

        # First look for an exact match.
        for item in symbols:
            symbol = (
                item.get("underlying_symbol")
                or item.get("symbol")
                or ""
            )

            if str(symbol).upper() == requested:
                print(
                    f"Confirmed active symbol: {symbol}"
                )
                return str(symbol)

        # If the symbol isn't in active_symbols, don't immediately
        # kill the bot. Try the symbol directly with ticks_history.
        print(
            f"Symbol {requested} was not found in active_symbols."
        )
        print(
            "Testing the requested symbol directly with ticks_history..."
        )

        try:
            await self.request({
                "ticks_history": requested,
                "count": 1,
                "end": "latest",
                "style": "ticks",
            })

            print(
                f"Confirmed symbol is usable: {requested}"
            )

            return requested

        except Exception as exc:
            raise RuntimeError(
                f"Deriv could not validate symbol '{requested}'. "
                f"Original error: {exc}"
            ) from exc

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

        candles = response.get("candles", [])

        if not isinstance(candles, list):
            raise RuntimeError(
                "Deriv returned an invalid candles response."
            )

        return [
            {
                "epoch": int(c["epoch"]),
                "open": float(c["open"]),
                "high": float(c["high"]),
                "low": float(c["low"]),
                "close": float(c["close"]),
            }
            for c in candles
        ]

    async def subscribe_candles(
        self,
        symbol: str,
        granularity: int,
    ):
        if self.ws is None:
            raise RuntimeError("WebSocket is not connected")

        self.req_id += 1

        request = {
            "ticks_history": symbol,
            "style": "candles",
            "granularity": granularity,
            "count": 1,
            "end": "latest",
            "subscribe": 1,
            "req_id": self.req_id,
        }

        await self.ws.send(json.dumps(request))

        while True:
            raw = await self.ws.recv()
            msg = json.loads(raw)

            if msg.get("error"):
                error = msg["error"]

                raise RuntimeError(
                    f"Deriv error "
                    f"{error.get('code', 'Unknown')}: "
                    f"{error.get('message', 'Unknown error')}"
                )

            yield msg

    async def stream_ticks(self, symbol: str):
        if self.ws is None:
            raise RuntimeError("WebSocket is not connected")

        self.req_id += 1

        request = {
            "ticks": symbol,
            "subscribe": 1,
            "req_id": self.req_id,
        }

        await self.ws.send(json.dumps(request))

        while True:
            raw = await self.ws.recv()
            msg = json.loads(raw)

            if msg.get("error"):
                error = msg["error"]

                raise RuntimeError(
                    f"Deriv error "
                    f"{error.get('code', 'Unknown')}: "
                    f"{error.get('message', 'Unknown error')}"
                )

            yield msg
