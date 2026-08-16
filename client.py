import asyncio
import json
import websockets


class DerivClient:

    def __init__(self, url: str, app_id: str = ""):
        self.base_url = url
        self.app_id = app_id

        if app_id:
            separator = "&" if "?" in url else "?"
            self.full_url = f"{url}{separator}app_id={app_id}"
        else:
            self.full_url = url

        self.ws = None
        self.req_id = 0
        self.active_symbols = []
        self.selected_symbol = None

    # ---------------------------------------------------------
    # CONNECTION
    # ---------------------------------------------------------

    async def connect(self):
        self.ws = await websockets.connect(
            self.full_url,
            ping_interval=20,
            ping_timeout=20,
            close_timeout=5
        )

        print("Connected to Deriv WebSocket.")
        print(f"Endpoint: {self.full_url}")

    async def close(self):
        if self.ws:
            await self.ws.close()
            self.ws = None

    # ---------------------------------------------------------
    # GENERIC REQUEST
    # ---------------------------------------------------------

    async def request(self, payload: dict) -> dict:

        if not self.ws:
            raise RuntimeError("WebSocket is not connected")

        self.req_id += 1

        request = {
            **payload,
            "req_id": self.req_id
        }

        await self.ws.send(json.dumps(request))

        while True:

            raw = await self.ws.recv()

            message = json.loads(raw)

            # Ignore unrelated subscription messages.
            if message.get("req_id") != self.req_id:
                continue

            if "error" in message:
                error = message["error"]

                raise RuntimeError(
                    f"Deriv error "
                    f"{error.get('code')}: "
                    f"{error.get('message')}"
                )

            return message

    # ---------------------------------------------------------
    # ACTIVE SYMBOLS
    # ---------------------------------------------------------

    async def get_active_symbols(self):

        response = await self.request({
            "active_symbols": "brief"
        })

        symbols = response.get("active_symbols", [])

        self.active_symbols = symbols

        print()
        print("========================================")
        print("DERIV ACTIVE SYMBOLS")
        print("========================================")
        print(f"Received {len(symbols)} active symbols.")

        return symbols

    # ---------------------------------------------------------
    # SYMBOL RESOLUTION
    # ---------------------------------------------------------

    async def resolve_symbol(self, requested_symbol: str):

        symbols = await self.get_active_symbols()

        if not symbols:
            raise RuntimeError(
                "Deriv returned no active symbols."
            )

        # Build a lookup using the CURRENT Deriv API field.
        lookup = {}

        for item in symbols:

            symbol = item.get("underlying_symbol")

            if symbol:
                lookup[symbol.upper()] = item

        requested = requested_symbol.upper()

        # -----------------------------------------------------
        # 1. Requested symbol is available
        # -----------------------------------------------------

        if requested in lookup:

            selected = requested

            print()
            print(f"Requested symbol is ACTIVE: {selected}")

            self.selected_symbol = selected

            return selected

        # -----------------------------------------------------
        # 2. Try common Volatility symbols
        # -----------------------------------------------------

        preferred_symbols = [
            "1HZ10V",
            "1HZ25V",
            "1HZ50V",
            "1HZ75V",
            "1HZ100V",
            "1HZ150V",
            "1HZ200V",
            "R_10",
            "R_25",
            "R_50",
            "R_75",
            "R_100",
        ]

        for candidate in preferred_symbols:

            if candidate in lookup:

                print()
                print(
                    f"Requested symbol {requested_symbol} "
                    f"is unavailable."
                )

                print(
                    f"Automatically switching to: {candidate}"
                )

                self.selected_symbol = candidate

                return candidate

        # -----------------------------------------------------
        # 3. Search synthetic / volatility markets
        # -----------------------------------------------------

        candidates = []

        for item in symbols:

            symbol = item.get("underlying_symbol", "")
            name = item.get("underlying_symbol_name", "")
            market = item.get("market", "")
            subgroup = item.get("subgroup", "")

            text = (
                f"{symbol} "
                f"{name} "
                f"{market} "
                f"{subgroup}"
            ).lower()

            if (
                "synthetic" in text
                or "volatility" in text
                or symbol.startswith("1HZ")
                or symbol.startswith("R_")
            ):
                candidates.append(item)

        if candidates:

            selected_item = candidates[0]

            selected = selected_item.get(
                "underlying_symbol"
            )

            print()
            print(
                f"Automatically selected available "
                f"synthetic symbol: {selected}"
            )

            self.selected_symbol = selected

            return selected

        # -----------------------------------------------------
        # 4. Nothing suitable found
        # -----------------------------------------------------

        sample = list(lookup.keys())[:20]

        raise RuntimeError(
            "Could not find a suitable active Deriv symbol. "
            f"Available symbols include: {sample}"
        )

    # ---------------------------------------------------------
    # CANDLES
    # ---------------------------------------------------------

    async def candles(
        self,
        symbol: str,
        granularity: int,
        count: int = 300
    ):

        # Automatically resolve unavailable symbols.
        symbol = await self.resolve_symbol(symbol)

        response = await self.request({
            "ticks_history": symbol,
            "style": "candles",
            "granularity": granularity,
            "count": count,
            "end": "latest",
            "subscribe": 0
        })

        candles = response.get("candles", [])

        return [
            {
                "epoch": int(c["epoch"]),
                "open": float(c["open"]),
                "high": float(c["high"]),
                "low": float(c["low"]),
                "close": float(c["close"]),
                "granularity": granularity
            }
            for c in candles
        ]

    # ---------------------------------------------------------
    # LIVE CANDLE SUBSCRIPTION
    # ---------------------------------------------------------

    async def subscribe_candles(
        self,
        symbol: str,
        granularity: int
    ):

        symbol = await self.resolve_symbol(symbol)

        if not self.ws:
            raise RuntimeError(
                "WebSocket is not connected"
            )

        self.req_id += 1

        request = {
            "ticks_history": symbol,
            "style": "candles",
            "granularity": granularity,
            "count": 1,
            "end": "latest",
            "subscribe": 1,
            "req_id": self.req_id
        }

        await self.ws.send(
            json.dumps(request)
        )

        # First response is the current candle snapshot.
        while True:

            raw = await self.ws.recv()

            message = json.loads(raw)

            if message.get("req_id") != self.req_id:
                continue

            if "error" in message:

                error = message["error"]

                raise RuntimeError(
                    f"Deriv error "
                    f"{error.get('code')}: "
                    f"{error.get('message')}"
                )

            break

        print(
            f"Live candle stream started: "
            f"{symbol} / {granularity}s"
        )

    # ---------------------------------------------------------
    # RAW LIVE STREAM
    # ---------------------------------------------------------

    async def stream(self):

        if not self.ws:
            raise RuntimeError(
                "WebSocket is not connected"
            )

        while True:

            raw = await self.ws.recv()

            yield json.loads(raw)
