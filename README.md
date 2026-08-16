# Arshe Trading Bot — v1

A Deriv market-analysis bot built from scratch.

## Current scope
- Connects to Deriv public WebSocket market data
- Downloads historical candles
- Streams live candle updates
- Calculates price-action statistics
- Detects basic market structure (swing highs/lows, BOS/CHoCH)
- Detects liquidity sweeps, equal highs/lows, FVGs and displacement
- Produces a confluence score and BUY/SELL/WAIT analysis
- **Analysis/demo only** in v1. No live orders are submitted.

## Quick start

Python 3.11+ recommended.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
python -m bot.main
```

The default symbol is `1HZ100V` and the bot uses 1m, 5m, 15m and 1h candles.

Environment variables are optional; copy `.env.example` to `.env` to customize them.

## Safety
This project deliberately does not contain live order execution in v1. Validate signals with historical replay and demo/paper trading before adding any execution permissions.
