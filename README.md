# Arshe Trading Bot — V2 FINAL

A Deriv public-market analysis bot. **This version does not place live trades.**

## What is fixed

- Correct Python package structure (`bot/...`).
- Correct Render start command: `python -m bot.main`.
- Removes cached `__pycache__` files from the deployment package.
- Uses Deriv's `active_symbols` endpoint before choosing a market.
- Supports the current `underlying_symbol` field and the legacy `symbol` field.
- Defaults to `SYMBOL=AUTO` so the bot does not die just because `1HZ100V` is unavailable.
- Prefers `1HZ100V` when Deriv reports it as usable, then tries other known markets, then other active markets.
- Verifies the chosen symbol with real candle data before analysis.
- Downloads 1m, 5m, 15m and 1h candles.
- Streams live candle updates.
- Keeps a Render health endpoint alive.

## Render

Build command:

```text
pip install -r requirements.txt
```

Start command:

```text
python -m bot.main
```

Health check path:

```text
/health
```

No Deriv token is required for this market-data-only version.

## Optional environment variables

```text
DERIV_WS_URL=wss://ws.binaryws.com/websockets/v3
SYMBOL=AUTO
TIMEFRAMES=60,300,900,3600
HISTORY_COUNT=300
MIN_CONFIDENCE=70
```

For the first deployment, **leave the environment variables empty**. The built-in defaults are intended to work automatically.

## Safety

This V2 release is analysis/demo only. It contains no order placement, buy, sell, account login, or trading-token logic.
