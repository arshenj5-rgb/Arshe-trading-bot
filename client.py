import asyncio
import json
import websockets

class DerivClient:
    def __init__(self, url: str, app_id: str = ""):
        self.url = f"{url}?app_id={app_id}" if app_id else url
        self.ws = None
        self.req_id = 0

    async def connect(self):
        self.ws = await websockets.connect(
            self.url,
            ping_interval=20,
            ping_timeout=20,
            close_timeout=5,
        )

    async def close(self):
        if self.ws:
            await self.ws.close()
            self.ws = None

    async def request(self, payload: dict) -> dict:
        if not self.ws:
            raise RuntimeError("WebSocket is not connected")
        self.req_id += 1
        payload = {**payload, "req_id": self.req_id}
        await self.ws.send(json.dumps(payload))
        while True:
            raw = await self.ws.recv()
            msg = json.loads(raw)
            if msg.get("req_id") == self.req_id:
                if "error" in msg:
                    raise RuntimeError(
                        f"Deriv error {msg['error'].get('code')}: "
                        f"{msg['error'].get('message')}"
                    )
                return msg

    async def candles(self, symbol: str, granularity: int, count: int = 300) -> list[dict]:
        response = await self.request({
            "ticks_history": symbol,
            "style": "candles",
            "granularity": granularity,
            "count": count,
            "end": "latest",
        })
        return [
            {
                "epoch": int(c["epoch"]),
                "open": float(c["open"]),
                "high": float(c["high"]),
                "low": float(c["low"]),
                "close": float(c["close"]),
                "granularity": granularity,
            }
            for c in response.get("candles", [])
        ]

    async def subscribe_candles(self, symbol: str, granularity: int):
        if not self.ws:
            raise RuntimeError("WebSocket is not connected")
        self.req_id += 1
        await self.ws.send(json.dumps({
            "ticks_history": symbol,
            "style": "candles",
            "granularity": granularity,
            "count": 1,
            "end": "latest",
            "subscribe": 1,
            "req_id": self.req_id,
        }))
        # First response is the current candle snapshot.
        while True:
            msg = json.loads(await self.ws.recv())
            if msg.get("req_id") == self.req_id:
                if "error" in msg:
                    raise RuntimeError(
                        f"Deriv error {msg['error'].get('code')}: "
                        f"{msg['error'].get('message')}"
                    )
                break

    async def stream(self):
        if not self.ws:
            raise RuntimeError("WebSocket is not connected")
        while True:
            yield json.loads(await self.ws.recv())
