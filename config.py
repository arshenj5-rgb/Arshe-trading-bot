import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


def _timeframes(value: str) -> tuple[int, ...]:
    values = []
    for item in value.split(","):
        item = item.strip()
        if not item:
            continue
        try:
            n = int(item)
        except ValueError:
            continue
        if n in {60, 120, 180, 300, 600, 900, 1800, 3600, 7200, 14400, 28800, 86400}:
            values.append(n)
    return tuple(dict.fromkeys(values)) or (60, 300, 900, 3600)


@dataclass(frozen=True)
class Settings:
    # Public Deriv market-data WebSocket. No token is required for market data.
    ws_url: str = os.getenv(
        "DERIV_WS_URL",
        "wss://ws.binaryws.com/websockets/v3",
    ).strip()
    # AUTO means: ask Deriv what is active and choose a usable market.
    symbol: str = os.getenv("SYMBOL", "AUTO").strip() or "AUTO"
    timeframes: tuple[int, ...] = _timeframes(
        os.getenv("TIMEFRAMES", "60,300,900,3600")
    )
    history_count: int = max(40, min(1000, int(os.getenv("HISTORY_COUNT", "300"))))
    min_confidence: int = max(0, min(100, int(os.getenv("MIN_CONFIDENCE", "70"))))
