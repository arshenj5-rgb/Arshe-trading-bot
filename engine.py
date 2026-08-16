from dataclasses import dataclass


@dataclass
class Analysis:
    bias: str
    score: int
    reasons: list[str]
    warnings: list[str]
    structure: str
    liquidity: str
    fvg: str
    displacement: bool
    signal: str


def _swing_points(candles, left=2, right=2):
    highs, lows = [], []
    for i in range(left, len(candles) - right):
        h = candles[i]["high"]
        l = candles[i]["low"]
        if all(h > candles[j]["high"] for j in range(i - left, i)) and all(
            h >= candles[j]["high"] for j in range(i + 1, i + right + 1)
        ):
            highs.append((i, h))
        if all(l < candles[j]["low"] for j in range(i - left, i)) and all(
            l <= candles[j]["low"] for j in range(i + 1, i + right + 1)
        ):
            lows.append((i, l))
    return highs, lows


def analyze(candles: list[dict], min_confidence: int = 70) -> Analysis:
    if len(candles) < 40:
        return Analysis(
            "UNKNOWN", 0, [], ["Not enough candles"], "UNKNOWN",
            "UNKNOWN", "UNKNOWN", False, "WAIT"
        )

    recent = candles[-30:]
    highs, lows = _swing_points(recent)
    reasons, warnings = [], []
    score = 50

    structure = "RANGE"
    if len(highs) >= 2 and len(lows) >= 2:
        hh = highs[-1][1] > highs[-2][1]
        hl = lows[-1][1] > lows[-2][1]
        lh = highs[-1][1] < highs[-2][1]
        ll = lows[-1][1] < lows[-2][1]
        if hh and hl:
            structure = "BULLISH"
            score += 20
            reasons.append("Higher-high / higher-low structure")
        elif lh and ll:
            structure = "BEARISH"
            score += 20
            reasons.append("Lower-high / lower-low structure")
        else:
            warnings.append("Structure is mixed")

    last = recent[-1]
    rng = max(last["high"] - last["low"], 1e-12)
    body = abs(last["close"] - last["open"])
    avg_range = sum(c["high"] - c["low"] for c in recent[-10:-1]) / 9
    displacement = body / rng >= 0.70 and rng > avg_range * 1.35
    if displacement:
        score += 10
        reasons.append("Displacement candle detected")

    prior_high = max(c["high"] for c in recent[-8:-1])
    prior_low = min(c["low"] for c in recent[-8:-1])
    sweep = "NONE"
    if last["high"] > prior_high and last["close"] < prior_high:
        sweep = "BUY-SIDE SWEEP"
        score += 10
        reasons.append("Buy-side liquidity sweep")
    elif last["low"] < prior_low and last["close"] > prior_low:
        sweep = "SELL-SIDE SWEEP"
        score += 10
        reasons.append("Sell-side liquidity sweep")

    fvg = "NONE"
    if len(recent) >= 3:
        a, _, c = recent[-3:]
        if a["high"] < c["low"]:
            fvg = "BULLISH FVG"
            score += 5
            reasons.append("Bullish fair-value gap")
        elif a["low"] > c["high"]:
            fvg = "BEARISH FVG"
            score += 5
            reasons.append("Bearish fair-value gap")

    bias = structure
    if structure == "RANGE":
        score = min(score, 59)
        warnings.append("No clear directional structure")

    score = max(0, min(100, score))
    if score >= min_confidence:
        signal = "BUY" if bias == "BULLISH" else "SELL" if bias == "BEARISH" else "WAIT"
    else:
        signal = "WAIT"

    if signal == "WAIT" and not warnings:
        warnings.append("Confluence below trade threshold")

    return Analysis(
        bias=bias,
        score=score,
        reasons=reasons,
        warnings=warnings,
        structure=structure,
        liquidity=sweep,
        fvg=fvg,
        displacement=displacement,
        signal=signal,
    )
