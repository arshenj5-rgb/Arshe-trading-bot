# Arshe Trading Bot — v1

Deriv market-analysis bot. It uses public market data only; it does **not** place live trades.

## What was fixed

- Uses Deriv's public market-data WebSocket endpoint.
- Requests `active_symbols` before using the configured symbol.
- Supports Deriv's current `underlying_symbol` response field (and the legacy `symbol` field).
- Verifies `1HZ100V` with a real candle request before running the analysis.
- Downloads 1m, 5m, 15m and 1h candles.
- Streams live candle updates.
- Keeps the Render web process alive with a health endpoint.

## Render

Build command:

```text
pip install -r requirements.txt
```

Start command:

```text
python -m bot.main
```

Environment variables are optional. Defaults are:

```text
DERIV_WS_URL=wss://ws.binaryws.com/websockets/v3
SYMBOL=1HZ100V
TIMEFRAMES=60,300,900,3600
HISTORY_COUNT=300
MIN_CONFIDENCE=70
```

No Deriv token is needed for this market-data-only version.

## Safety

v1 is analysis/demo only. No live order execution is included.
