import asyncio
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from bot.analysis.engine import analyze
from bot.config import Settings
from bot.deriv.client import DerivClient


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/", "/health"):
            body = b"Arshe Trading Bot is running"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        return


def start_health_server():
    port = int(os.getenv("PORT", "10000"))
    server = ThreadingHTTPServer(("0.0.0.0", port), HealthHandler)
    print(f"Health server listening on port {port}")
    server.serve_forever()


def print_analysis(symbol, timeframe, result):
    print("\n" + "=" * 64)
    print(f"ARSHE TRADING BOT | {symbol} | {timeframe}s")
    print("=" * 64)
    print(f"BIAS:         {result.bias}")
    print(f"STRUCTURE:    {result.structure}")
    print(f"LIQUIDITY:    {result.liquidity}")
    print(f"FVG:          {result.fvg}")
    print(f"DISPLACEMENT: {'YES' if result.displacement else 'NO'}")
    print(f"CONFLUENCE:   {result.score}/100")
    print(f"SIGNAL:       {result.signal}")
    if result.reasons:
        print("REASONS:")
        for item in result.reasons:
            print(f"  + {item}")
    if result.warnings:
        print("WARNINGS:")
        for item in result.warnings:
            print(f"  ! {item}")


async def main():
    threading.Thread(target=start_health_server, daemon=True).start()
    settings = Settings()
    client = DerivClient(settings.ws_url)

    print("\n" + "=" * 64)
    print("              ARSHE TRADING BOT V2")
    print("=" * 64)
    print(f"Requested symbol: {settings.symbol}")
    print("Timeframes: " + ", ".join(map(str, settings.timeframes)))
    print("Market mode: PUBLIC DATA / ANALYSIS ONLY")
    print("=" * 64)

    try:
        await client.connect()
        symbol = await client.resolve_symbol(settings.symbol)

        snapshots: dict[int, list[dict]] = {}
        for tf in settings.timeframes:
            print(f"\nDownloading {settings.history_count} candles for {symbol} / {tf}s...")
            candles = await client.candles(symbol, tf, settings.history_count)
            if len(candles) < 40:
                print(f"WARNING: only {len(candles)} candles received for {tf}s.")
                continue
            snapshots[tf] = candles
            print_analysis(symbol, tf, analyze(candles, settings.min_confidence))

        if not snapshots:
            raise RuntimeError("Deriv returned no usable candle history for the selected symbol.")

        for tf in snapshots:
            await client.subscribe_candles(symbol, tf)
            print(f"Live candle subscription active: {tf}s")

        print("\nLive stream active. Waiting for Deriv candle updates...\n")

        async for message in client.stream():
            if message.get("error"):
                error = message["error"] or {}
                print(f"Deriv stream error {error.get('code')}: {error.get('message')}")
                continue
            if message.get("msg_type") != "ohlc":
                continue

            o = message.get("ohlc") or {}
            try:
                tf = int(o["granularity"])
                candle = {
                    "epoch": int(o.get("open_time", o.get("epoch"))),
                    "open": float(o["open"]),
                    "high": float(o["high"]),
                    "low": float(o["low"]),
                    "close": float(o["close"]),
                    "granularity": tf,
                }
            except (KeyError, TypeError, ValueError):
                continue

            if tf not in snapshots:
                continue
            candles = snapshots[tf]
            if candles and candles[-1]["epoch"] == candle["epoch"]:
                candles[-1] = candle
            else:
                candles.append(candle)
                if len(candles) > settings.history_count:
                    del candles[:-settings.history_count]

            print_analysis(symbol, tf, analyze(candles, settings.min_confidence))

    finally:
        await client.close()
        print("Deriv connection closed.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped.")
    except Exception as exc:
        print(f"\nERROR: {exc}")
        raise
