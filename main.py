import asyncio
import traceback

from config import settings
from client import DerivClient


def get_symbol(item):
    return (
        item.get("underlying_symbol")
        or item.get("symbol")
        or ""
    )


async def run():
    print("=" * 60)
    print("ARSHE TRADING BOT - DERIV MARKET DATA TEST")
    print("=" * 60)

    client = DerivClient(
        settings.deriv_ws_url,
        settings.deriv_app_id,
    )

    try:
        print("Connecting to Deriv market data...")

        await client.connect()

        print("Connected to Deriv WebSocket.")
        print()

        # ---------------------------------------------------------
        # GET ACTIVE SYMBOLS
        # ---------------------------------------------------------

        print("Requesting active symbols...")

        response = await client.request({
            "active_symbols": "brief",
            "product_type": "basic",
        })

        symbols = response.get("active_symbols", [])

        print(
            f"Deriv returned {len(symbols)} active symbols."
        )
        print()

        if not symbols:
            raise RuntimeError(
                "Deriv returned zero active symbols."
            )

        # ---------------------------------------------------------
        # PRINT EVERY SYMBOL
        # ---------------------------------------------------------

        print("=" * 60)
        print("AVAILABLE DERIV SYMBOLS")
        print("=" * 60)

        valid_symbols = []

        for item in symbols:
            symbol = get_symbol(item)

            if not symbol:
                continue

            name = (
                item.get("underlying_symbol_name")
                or item.get("display_name")
                or ""
            )

            market = item.get("market", "")
            subgroup = item.get("subgroup", "")

            print(
                f"{symbol}"
                f" | {name}"
                f" | market={market}"
                f" | subgroup={subgroup}"
            )

            valid_symbols.append({
                "symbol": symbol,
                "name": name,
                "market": market,
                "subgroup": subgroup,
            })

        print("=" * 60)
        print()

        # ---------------------------------------------------------
        # FIND VOLATILITY / SYNTHETIC SYMBOLS
        # ---------------------------------------------------------

        volatility = []

        for item in valid_symbols:
            text = (
                f"{item['symbol']} "
                f"{item['name']} "
                f"{item['market']} "
                f"{item['subgroup']}"
            ).lower()

            if (
                "volatility" in text
                or item["symbol"].startswith("1HZ")
                or item["symbol"].startswith("R_")
            ):
                volatility.append(item)

        print("=" * 60)
        print("VOLATILITY / SYNTHETIC CANDIDATES")
        print("=" * 60)

        for item in volatility:
            print(
                f"{item['symbol']} - {item['name']}"
            )

        print("=" * 60)
        print()

        # ---------------------------------------------------------
        # SELECT SYMBOL
        # ---------------------------------------------------------

        requested = settings.symbol.upper()

        selected = None

        # First: exact requested symbol.
        for item in valid_symbols:
            if item["symbol"].upper() == requested:
                selected = item
                break

        # If requested symbol is unavailable, choose a volatility
        # symbol returned by Deriv.
        if selected is None and volatility:
            selected = volatility[0]

        # Otherwise use the first valid market.
        if selected is None:
            selected = valid_symbols[0]

        symbol = selected["symbol"]

        print(
            f"SELECTED SYMBOL: {symbol}"
        )

        print(
            f"NAME: {selected['name']}"
        )

        print()

        # ---------------------------------------------------------
        # TEST TICKS
        # ---------------------------------------------------------

        print(
            f"Testing live ticks for {symbol}..."
        )

        self_req_id = 9001

        await client.ws.send(
            __import__("json").dumps({
                "ticks": symbol,
                "subscribe": 1,
                "req_id": self_req_id,
            })
        )

        while True:
            raw = await asyncio.wait_for(
                client.ws.recv(),
                timeout=15
            )

            msg = __import__("json").loads(raw)

            if msg.get("req_id") != self_req_id:
                continue

            if "error" in msg:
                error = msg["error"]

                raise RuntimeError(
                    f"Deriv rejected symbol {symbol}: "
                    f"{error.get('code')}: "
                    f"{error.get('message')}"
                )

            if msg.get("msg_type") == "tick":
                tick = msg.get("tick", {})

                print()
                print("=" * 60)
                print("LIVE MARKET DATA WORKING")
                print("=" * 60)
                print(
                    f"Symbol: {tick.get('symbol', symbol)}"
                )
                print(
                    f"Quote: {tick.get('quote')}"
                )
                print(
                    f"Epoch: {tick.get('epoch')}"
                )
                print("=" * 60)

                break

        # ---------------------------------------------------------
        # TEST HISTORICAL DATA
        # ---------------------------------------------------------

        print()
        print(
            f"Downloading candles for {symbol}..."
        )

        candles = await client.candles(
            symbol=symbol,
            granularity=60,
            count=100,
        )

        print(
            f"Received {len(candles)} candles."
        )

        if candles:
            print(
                "Latest candle:"
            )

            print(
                candles[-1]
            )

        print()
        print("=" * 60)
        print("DERIV MARKET DATA TEST PASSED")
        print("=" * 60)
        print()
        print(
            f"Using actual active symbol: {symbol}"
        )
        print(
            "Ticks: OK"
        )
        print(
            "Candles: OK"
        )
        print()

        # Keep Render worker alive.
        while True:
            await asyncio.sleep(60)

    except Exception as exc:
        print()
        print("=" * 60)
        print("ERROR")
        print("=" * 60)
        print(exc)
        print()
        traceback.print_exc()

        raise

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(run())
