import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    # Public Deriv market-data WebSocket.
    deriv_ws_url: str = os.getenv(
        "DERIV_WS_URL",
        "wss://ws.binaryws.com/websockets/v3"
    )

    # App ID is NOT required for public market data.
    deriv_app_id: str = os.getenv("DERIV_APP_ID", "")

    # Default market.
    symbol: str = os.getenv("SYMBOL", "")

    # Timeframes in seconds.
    timeframes: tuple[int, ...] = tuple(
        int(x.strip())
        for x in os.getenv("TIMEFRAMES", "60,300,900,3600").split(",")
        if x.strip()
    )

    history_count: int = int(os.getenv("HISTORY_COUNT", "300"))

    min_confidence: int = int(
        os.getenv("MIN_CONFIDENCE", "70")
    )


settings = Settings()
