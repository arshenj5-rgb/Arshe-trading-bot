import asyncio
import traceback

from config import settings
from client import DerivClient


async def run():
    print("=" * 60)
    print("ARSHE TRADING BOT")
    print("Deriv market-analysis engine")
    print("=" * 60)

    print(f"WebSocket: {settings.deriv_ws_url}")
    print(f"Requested symbol: {settings.symbol}")
    print(f"Timeframes: {settings.timeframes}")
    print(f"History count: {settings.history_count}")
    print(f"Minimum confidence: {settings.min_confidence}")
    print()

    client = DerivClient(
        settings.deriv_ws_url,
        settings.deriv_app_id,
    )

    try:
        # ---------------------------------------------------------
        # 1. CONNECT
        # ---------------------------------------------------------
        print("Connecting to Deriv market data...")

        await client.connect()

        print("Connected to Deriv WebSocket.")
        print()

        # ---------------------------------------------------------
        # 2. GET ACTIVE SYMBOLS
        # ---------------------------------------------------------
        print("Checking Deriv active symbols...")

        symbols = await client.active_symbols()

        print(
            f"Received {len(symbols)} active symbols."
        )

        if symbols:
            print("Sample active symbols:")

            shown = 0

            for item in symbols:
                symbol = (
                    item.get("underlying_symbol")
                    or item.get("symbol")
                    or ""
                )

                name = (
                    item.get("underlying_symbol_name")
                    or item.get("display_name")
                    or ""
                )

                if symbol:
                    print(
                        f"  {symbol}"
                        + (f" - {name}" if name else "")
                    )

                    shown += 1

                    if shown >= 10:
                        break

        print()

        # ---------------------------------------------------------
        # 3. RESOLVE SYMBOL
        # ---------------------------------------------------------
        symbol = await client.resolve_symbol(
            settings.symbol
        )

        print()
        print(f"Using symbol: {symbol}")
        print()

        # ---------------------------------------------------------
        # 4. TEST TICK DATA
        # ---------------------------------------------------------
        print("Testing live tick data...")

        async with asyncio.timeout(15):
            async for message in client.stream_ticks(symbol):

                if message.get("msg_type") == "tick":
                    tick = message.get("tick", {})

                    quote = tick.get("quote")
                    epoch = tick.get("epoch")

                    print(
                        f"Live tick: {quote} "
                        f"(epoch={epoch})"
                    )

                    break

        print("Live tick stream is working.")
        print()

        # ---------------------------------------------------------
        # 5. GET HISTORICAL CANDLES
        # ---------------------------------------------------------
        print("Downloading historical candles...")

        for timeframe in settings.timeframes:

            print(
                f"Fetching {timeframe}-second candles..."
            )

            candles = await client.candles(
                symbol=symbol,
                granularity=timeframe,
                count=settings.history_count,
            )

            print(
                f"Received {len(candles)} candles "
                f"for {timeframe}s timeframe."
            )

            if candles:
                latest = candles[-1]

                print(
                    f"Latest candle: "
                    f"O={latest['open']} "
                    f"H={latest['high']} "
                    f"L={latest['low']} "
                    f"C={latest['close']}"
                )

            print()

        # ---------------------------------------------------------
        # 6. BOT STATUS
        # ---------------------------------------------------------
        print("=" * 60)
        print("DERIV CONNECTION TEST PASSED")
        print("=" * 60)
        print()
        print(f"Symbol: {symbol}")
        print("WebSocket: OK")
        print("Active symbols: OK")
        print("Ticks: OK")
        print("Historical candles: OK")
        print()
        print(
            "The market-data engine is ready."
        )
        print(
            "No live orders are submitted by this version."
        )
        print()

        # Keep Render worker alive.
        print("Bot is staying online...")

        while True:
            await asyncio.sleep(60)

    except asyncio.TimeoutError:
        print()
        print(
            "ERROR: Timed out waiting for Deriv tick data."
        )

        raise

    except Exception as exc:
        print()
        print(
            f"ERROR: {exc}"
        )

        print()
        print("Full traceback:")
        traceback.print_exc()

        raise

    finally:
        await client.close()
        print("Deriv WebSocket closed.")


if __name__ == "__main__":
    asyncio.run(run())
