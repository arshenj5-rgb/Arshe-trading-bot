import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Settings:
    ws_url: str = os.getenv("DERIV_WS_URL", "wss://ws.derivws.com/websockets/v3")
    app_id: str = os.getenv("DERIV_APP_ID", "")
    symbol: str = os.getenv("SYMBOL", "1HZ100V")
    timeframes: tuple[int, ...] = tuple(
        int(x.strip()) for x in os.getenv("TIMEFRAMES", "60,300,900,3600").split(",") if x.strip()
    )
    history_count: int = int(os.getenv("HISTORY_COUNT", "300"))
    min_confidence: int = int(os.getenv("MIN_CONFIDENCE", "70"))
