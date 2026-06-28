from __future__ import annotations

import pandas as pd

from config import (
    LOOKBACK_DAYS,
    WEIGHTS,
    STRONG_BUY_THRESHOLD,
    BUY_THRESHOLD,
    SELL_THRESHOLD,
    STRONG_SELL_THRESHOLD,
    NEWS_POSITIVE_KEYWORDS,
    NEWS_NEGATIVE_KEYWORDS,
    TIMEFRAME_OPTIONS,
    CONFIRMATION_BONUS,
    CONFIRMATION_PENALTY,
)
from services import fetch_history, fetch_quote, fetch_news_for_symbol
from patterns import detect_patterns
from storage import should_send_alert


def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    close = df["c"]

    df["EMA20"] = close.ewm(span=20, adjust=False).mean()
    df["EMA50"] = close.ewm(span=50, adjust=False).mean()
    df["EMA200"] = close.ewm(span=200, adjust=False).mean()

    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean().replace(0, 1e-9)
    rs = gain / loss
    df["RSI"] = 100 - (100 / (1 + rs))

    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    df["MACD"] = ema12 - ema26
    df["MACD_SIGNAL"] = df["MACD"].ewm(span=9, adjust=False).mean()
    df["MACD_HIST"] = df["MACD"] - df["MACD_SIGNAL"]

    typical = (df["h"] + df["l"] + df["c"]) / 3
    cum_vol = df["v"].cumsum().replace(0, 1e-9)
    df["VWAP"] = (typical * df["v"]).cumsum() / cum_vol

    tr1 = df["h"] - df["l"]
    tr2 = (df["h"] - df["c"].shift()).abs()
    tr3 = (df["l"] - df["c"].shift()).abs()
    df["TR"] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df["ATR14"] = df["TR"].rolling(14).mean()

    df["VOL_AVG20"] = df["v"].rolling(20).mean()
    df["VOL_RATIO"] = df["v"] / df["VOL_AVG20"].replace(0, 1e-9)
    return df


def analyze_single_timeframe(fyers, sym: str, resolution: str):
    res = fetch_history(fyers, sym, resolution=resolution, days=LOOKBACK_DAYS)
    if not (res and res.get("s") == "ok" and res.get("candles")):
        return None

    df = pd.DataFrame(res["candles"], columns=["ts", "o", "h", "l", "c", "v"])
    if len(df) < 40:
        return None

    df = compute_indicators(df)
    last = df.iloc[-1]

    trend_votes = []
    trend_votes.append(1 if last["c"] > last["EMA20"] else -1)
    trend_votes.append(1 if last["EMA20"] > last["EMA50"] else -1)
    trend_votes.append(1 if last["EMA50"] > last["EMA200"] else -1)
    trend_votes.append(1 if last["c"] > last["VWAP"] else -1)
    trend_score = sum(trend_votes) / len(trend_votes)

    rsi = float(last["RSI"]) if pd.notna(last["RSI"]) else 50.0
    macd_hist = float(last["MACD_HIST"]) if pd.notna(last["MACD_HIST"]) else 0.0

    momentum_votes = [1 if macd_hist > 0 else -1]
    if rsi > 60:
        momentum_votes.append(1)
    elif rsi < 40:
        momentum_votes.append(-1)
    else:
        momentum_votes.append(0)
    momentum_score = sum(momentum_votes) / len(momentum_votes)

    vol_ratio = float(last["VOL_RATIO"]) if pd.notna(last["VOL_RATIO"]) else 1.0
    if vol_ratio >= 1.75:
        volume_score = 1.0
    elif vol_ratio >= 1.25:
        volume_score = 0.5
    elif vol_ratio <= 0.75:
        volume_score = -0.5
    else:
        volume_score = 0.0

    pattern = detect_patterns(df)
    pattern_score = pattern.get("score", 0.0)

    direction_score = trend_score + momentum_score + pattern_score
    if direction_score > 0.3:
        direction = "BULLISH"
    elif direction_score < -0.3:
        direction = "BEARISH"
    else:
        direction = "NEUTRAL"

    note = (
        f"TF={resolution}m, EMA20={last['EMA20']:.2f}, EMA50={last['EMA50']:.2f}, "
        f"RSI={rsi:.1f}, MACD_H={macd_hist:.3f}, VolRatio={vol_ratio:.2f}"
    )

    return {
        "df": df,
        "last": round(float(last["c"]), 2),
        "trend_score": round(trend_score, 2),
        "momentum_score": round(momentum_score, 2),
        "volume_score": round(volume_score, 2),
        "pattern": pattern,
        "pattern_score": round(pattern_score, 2),
        "direction": direction,
        "note": note,
        "resolution": resolution,
    }


def analyze_multi_timeframe(fyers, sym: str, mode_label: str):
    mode = TIMEFRAME_OPTIONS[mode_label]
    primary_res = mode["primary"]
    confirm_res = mode["confirm"]
    tf_label = mode["label"]

    primary = analyze_single_timeframe(fyers, sym, primary_res)
    if primary is None:
        return None

    confirm = None
    mtf_status = "Primary Only"
    adjusted_pattern_score = primary["pattern_score"]

    if confirm_res:
        confirm = analyze_single_timeframe(fyers, sym, confirm_res)
        if confirm:
            if primary["direction"] == confirm["direction"] and primary["direction"] != "NEUTRAL":
                mtf_status = "Confirmed"
                if adjusted_pattern_score >= 0:
                    adjusted_pattern_score += CONFIRMATION_BONUS / 100
                else:
                    adjusted_pattern_score -= CONFIRMATION_BONUS / 100
            elif primary["direction"] != "NEUTRAL" and confirm["direction"] != "NEUTRAL":
                mtf_status = "Conflict"
                if adjusted_pattern_score >= 0:
                    adjusted_pattern_score -= CONFIRMATION_PENALTY / 100
                else:
                    adjusted_pattern_score += CONFIRMATION_PENALTY / 100
            else:
                mtf_status = "Mixed"
        else:
            mtf_status = "No Confirm Data"

    primary["pattern_score"] = round(adjusted_pattern_score, 2)
    primary["confirm"] = confirm
    primary["mtf_status"] = mtf_status
    primary["timeframe_label"] = tf_label
    return primary


def analyze_oi(fyers, sym: str):
    try:
        q = fetch_quote(fyers, sym)
        if not (q and q.get("s") == "ok" and q.get("d")):
            return {"score": None, "note": "oi n/a"}
        v = q["d"][0].get("v", {})
        oi = v.get("oi")
        prev_oi = v.get("pdoi")
        chp = v.get("chp")

        if oi is None or chp is None:
            return {"score": None, "note": "oi n/a"}

        oi_up = (prev_oi is not None and oi > prev_oi)
        price_up = chp > 0

        if price_up and oi_up:
            return {"score": 1.0, "note": "Long buildup"}
        if (not price_up) and oi_up:
            return {"score": -1.0, "note": "Short buildup"}
        if price_up and (not oi_up):
            return {"score": 0.5, "note": "Short covering"}
        if (not price_up) and (not oi_up):
            return {"score": -0.5, "note": "Long unwinding"}
        return {"score": 0.0, "note": "Neutral"}

    except Exception as e:
        return {"score": None, "note": f"err:{e}"}


def analyze_news(base: str):
    articles = fetch_news_for_symbol(base)
    if not articles:
        return {
            "score": None,
            "sentiment": "N/A",
            "strength": "N/A",
            "headline": "No recent news",
            "note": "n/a"
        }

    score = 0
    combined_text = " ".join(
        [((a.get("title") or "") + " " + (a.get("description") or "")) for a in articles]
    ).lower()

    for kw in NEWS_POSITIVE_KEYWORDS:
        if kw in combined_text:
            score += 1
    for kw in NEWS_NEGATIVE_KEYWORDS:
        if kw in combined_text:
            score -= 1

    if score >= 3:
        s = 1.0
        sentiment = "Positive"
        strength = "Strong"
    elif score in [1, 2]:
        s = 0.5
        sentiment = "Positive"
        strength = "Moderate"
    elif score <= -3:
        s = -1.0
        sentiment = "Negative"
        strength = "Strong"
    elif score in [-1, -2]:
        s = -0.5
        sentiment = "Negative"
        strength = "Moderate"
    else:
        s = 0.0
        sentiment = "Neutral"
        strength = "Weak"

    headline = articles[0].get("title") or "No headline"
    return {
        "score": s,
        "sentiment": sentiment,
        "strength": strength,
        "headline": headline,
        "note": headline,
    }


def analyze_fundamental_optional(base: str, enabled: bool = False):
    if not enabled:
        return {"score": None, "note": "disabled"}
    return {"score": None, "note": "optional placeholder"}


def analyze_results_optional(base: str, enabled: bool = False):
    if not enabled:
        return {"score": None, "note": "disabled"}
    return {"score": None, "note": "optional placeholder"}


def combine_scores(tech, oi, news, fund=None, result=None):
    parts = [
        ("technical", tech.get("trend_score") if tech else None),
        ("momentum", tech.get("momentum_score") if tech else None),
        ("volume", tech.get("volume_score") if tech else None),
        ("pattern", tech.get("pattern_score") if tech else None),
        ("oi", oi.get("score") if oi else None),
        ("news", news.get("score") if news else None),
        ("fundamental", fund.get("score") if fund else None),
        ("results", result.get("score") if result else None),
    ]

    total_w = 0
    acc = 0.0
    for key, sc in parts:
        if sc is not None:
            w = WEIGHTS[key]
            acc += sc * w
            total_w += w

    if total_w == 0:
        return None

    return round((acc / total_w) * 100, 1)


def score_to_signal(score):
    if score is None:
        return "NO DATA"
    if score >= STRONG_BUY_THRESHOLD:
        return "STRONG BUY"
    if score >= BUY_THRESHOLD:
        return "BUY"
    if score <= STRONG_SELL_THRESHOLD:
        return "STRONG SELL"
    if score <= SELL_THRESHOLD:
        return "SELL"
    return "HOLD"


def score_to_probabilities(score):
    if score is None:
        return None, None

    bullish = round((score + 100) / 2, 1)
    bullish = max(0.0, min(100.0, bullish))
    bearish = round(100.0 - bullish, 1)
    return bullish, bearish


def build_reason(tech, oi, news, signal):
    chunks = [signal]

    if tech:
        chunks.append(f"TF Mode: {tech.get('timeframe_label')}")
        chunks.append(f"MTF: {tech.get('mtf_status')}")

        patt = tech.get("pattern", {})
        if patt.get("pattern") and patt.get("pattern") != "None":
            chunks.append(
                f"Pattern: {patt.get('pattern')} on {tech.get('resolution')}m ({patt.get('confidence')})"
            )

        confirm = tech.get("confirm")
        if confirm:
            chunks.append(
                f"Confirm TF: {confirm.get('resolution')}m / {confirm.get('direction')}"
            )

        chunks.append(
            f"Tech: trend {tech.get('trend_score')}, momentum {tech.get('momentum_score')}, volume {tech.get('volume_score')}"
        )

    if oi and oi.get("note"):
        chunks.append(f"OI: {oi.get('note')}")

    if news and news.get("sentiment") not in (None, "N/A"):
        chunks.append(f"News: {news.get('sentiment')} / {news.get('strength')}")

    return " | ".join(chunks)


def scan_universe(fyers, symbols, timeframe_mode="15 min + 1 hr", include_news=True, include_fundamental=False, progress=None):
    rows = []
    n = len(symbols)

    from services import base_name_from_symbol, send_telegram_msg

    for i, sym in enumerate(symbols):
        base = base_name_from_symbol(sym)

        tech = analyze_multi_timeframe(fyers, sym, timeframe_mode)
        oi = analyze_oi(fyers, sym)
        news = analyze_news(base) if include_news else {
            "score": None,
            "sentiment": "N/A",
            "strength": "N/A",
            "headline": "disabled",
            "note": "disabled"
        }

        fund = analyze_fundamental_optional(base, enabled=include_fundamental)
        result = analyze_results_optional(base, enabled=include_fundamental)

        score = combine_scores(tech, oi, news, fund, result)
        signal = score_to_signal(score)
        bull, bear = score_to_probabilities(score)
        reason = build_reason(tech, oi, news, signal)

        if tech is None:
            row = {
                "Symbol": sym,
                "Timeframe Mode": timeframe_mode,
                "Primary TF": "",
                "Confirm TF": "",
                "MTF Status": "No Data",
                "LTP": None,
                "Pattern": "None",
                "Pattern TF": "",
                "Pattern Direction": "NEUTRAL",
                "Pattern Confidence": "LOW",
                "TrendScore": None,
                "MomentumScore": None,
                "VolumeScore": None,
                "OI": oi.get("score"),
                "OI Note": oi.get("note"),
                "News Sentiment": news.get("sentiment"),
                "News Strength": news.get("strength"),
                "Top Headline": news.get("headline"),
                "Score": score,
                "Bullish %": bull,
                "Bearish %": bear,
                "Signal": signal,
                "Reason": "No technical data",
            }
            rows.append(row)
            continue

        pattern = tech.get("pattern", {})
        confirm = tech.get("confirm")

        row = {
            "Symbol": sym,
            "Timeframe Mode": timeframe_mode,
            "Primary TF": f"{tech.get('resolution')}m",
            "Confirm TF": f"{confirm.get('resolution')}m" if confirm else "-",
            "MTF Status": tech.get("mtf_status"),
            "LTP": tech.get("last"),
            "Pattern": pattern.get("pattern"),
            "Pattern TF": f"{tech.get('resolution')}m",
            "Pattern Direction": pattern.get("direction"),
            "Pattern Confidence": pattern.get("confidence"),
            "TrendScore": tech.get("trend_score"),
            "MomentumScore": tech.get("momentum_score"),
            "VolumeScore": tech.get("volume_score"),
            "OI": oi.get("score"),
            "OI Note": oi.get("note"),
            "News Sentiment": news.get("sentiment"),
            "News Strength": news.get("strength"),
            "Top Headline": news.get("headline"),
            "Score": score,
            "Bullish %": bull,
            "Bearish %": bear,
            "Signal": signal,
            "Reason": reason,
        }
        rows.append(row)

        if signal in ("STRONG BUY", "BUY", "STRONG SELL", "SELL"):
            if should_send_alert(sym, signal, score):
                msg = (
                    f"{'🚀' if 'BUY' in signal else '📉'} {signal}\n"
                    f"Symbol: {sym}\n"
                    f"Timeframe Mode: {timeframe_mode}\n"
                    f"Primary TF: {tech.get('resolution')}m\n"
                    f"Confirm TF: {confirm.get('resolution')}m\n" if confirm else
                    f"{'🚀' if 'BUY' in signal else '📉'} {signal}\n"
                    f"Symbol: {sym}\n"
                    f"Timeframe Mode: {timeframe_mode}\n"
                    f"Primary TF: {tech.get('resolution')}m\n"
                )

                if confirm:
                    msg += f"MTF Status: {tech.get('mtf_status')}\n"
                else:
                    msg += "MTF Status: Primary Only\n"

                msg += (
                    f"LTP: {tech.get('last')}\n"
                    f"Score: {score}\n"
                    f"Bullish: {bull}% | Bearish: {bear}%\n"
                    f"Pattern: {pattern.get('pattern')}\n"
                    f"Pattern TF: {tech.get('resolution')}m\n"
                    f"Pattern Confidence: {pattern.get('confidence')}\n"
                    f"OI: {oi.get('note')}\n"
                    f"News: {news.get('sentiment')} / {news.get('strength')}\n"
                    f"Headline: {news.get('headline')}\n"
                    f"Reason: {reason}"
                )
                send_telegram_msg(msg)

        if progress is not None and n > 0:
            progress.progress((i + 1) / n, text=f"Scanned {i+1}/{n}: {sym}")

    return pd.DataFrame(rows)
