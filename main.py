import asyncio
from bot.config import Settings
from bot.deriv.client import DerivClient
from bot.analysis.engine import analyze

def print_analysis(symbol, timeframe, result):
    print("\n" + "━" * 64)
    print(f"ARSHE TRADING BOT | {symbol} | {timeframe}s")
    print("━" * 64)
    print(f"BIAS:        {result.bias}")
    print(f"STRUCTURE:   {result.structure}")
    print(f"LIQUIDITY:   {result.liquidity}")
    print(f"FVG:         {result.fvg}")
    print(f"DISPLACEMENT:{' YES' if result.displacement else ' NO'}")
    print(f"CONFLUENCE:  {result.score}/100")
    print(f"SIGNAL:      {result.signal}")
    if result.reasons:
        print("REASONS:")
        for x in result.reasons:
            print(f"  ✓ {x}")
    if result.warnings:
        print("WARNINGS:")
        for x in result.warnings:
            print(f"  ! {x}")

async def main():
    settings = Settings()
    client = DerivClient(settings.ws_url, settings.app_id)

    print("Connecting to Deriv market data...")
    await client.connect()
    print("Connected.")

    # Build initial multi-timeframe snapshots.
    snapshots = {}
    for tf in settings.timeframes:
        candles = await client.candles(
            settings.symbol, tf, settings.history_count
        )
        snapshots[tf] = candles
        result = analyze(candles, settings.min_confidence)
        print_analysis(settings.symbol, tf, result)

    # Subscribe to each timeframe. The v1 bot logs incoming updates.
    for tf in settings.timeframes:
        await client.subscribe_candles(settings.symbol, tf)

    print("\nLive stream active. Press Ctrl+C to stop.\n")

    try:
        async for message in client.stream():
            if message.get("msg_type") != "ohlc":
                continue

            o = message.get("ohlc", {})
            tf = int(o.get("granularity", 0))
            if tf not in snapshots:
                continue

            candle = {
                "epoch": int(o["epoch"]),
                "open": float(o["open"]),
                "high": float(o["high"]),
                "low": float(o["low"]),
                "close": float(o["close"]),
                "granularity": tf,
            }

            candles = snapshots[tf]
            if candles and candles[-1]["epoch"] == candle["epoch"]:
                candles[-1] = candle
            else:
                candles.append(candle)
                del candles[:-settings.history_count]

            # Analyze on each incoming candle update.
            result = analyze(candles, settings.min_confidence)
            print_analysis(settings.symbol, tf, result)

    finally:
        await client.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped.")
    except Exception as exc:
        print(f"\nERROR: {exc}")
        print("If this is a Deriv connection error, paste the exact message here.")
