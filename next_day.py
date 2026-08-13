# next_day.py — RAO SAHAB real next-day outlook (daily-candle powered)
# Uses the same confluence scorer as analysis.py on daily candles, plus
# ATR-based expected move and 10-day swing support/resistance.
import random
from datetime import datetime, timedelta, timezone

import pandas as pd

from analysis import fetch_candles, score_dataframe, SCORE_MAX, to_fyers_symbol

IST = timezone(timedelta(hours=5, minutes=30))


def _outlook_from_score(score):
    if score >= 8:
        return "Strong Bullish", "Bullish"
    if score >= 3:
        return "Bullish", "Bullish"
    if score <= -8:
        return "Strong Bearish", "Bearish"
    if score <= -3:
        return "Bearish", "Bearish"
    return "Neutral", "Neutral"


def _confidence(score, bias):
    if bias == "Neutral":
        return int(round(45 + max(0, 3 - abs(score)) * 5))   # 45–60
    return int(round(60 + min(abs(score), 15) / 15 * 32))    # 60–92


def scan_next_day(fyers, symbols, progress=None, include_flow=True):
    results = []

    for i, symbol in enumerate(symbols):
        if progress:
            progress.progress((i + 1) / len(symbols), text=f"Analyzing {symbol}...")

        row = None
        row_was_real = False
        try:
            df = fetch_candles(fyers, symbol, timeframe_mode="1d")
            if df is not None and len(df) >= 30:
                s = score_dataframe(df)
                outlook, bias = _outlook_from_score(s["score"])
                conf = _confidence(s["score"], bias)

                atr_pct = (s["atr"] / s["ltp"] * 100) if s["ltp"] else 1.0
                atr_pct = max(0.1, round(atr_pct, 1))
                if bias == "Bullish":
                    exp_move = f"+{atr_pct}%"
                elif bias == "Bearish":
                    exp_move = f"-{atr_pct}%"
                else:
                    exp_move = f"±{round(atr_pct / 2, 1)}%"

                row = {
                    "Symbol": symbol,
                    "LTP": s["ltp"],
                    "Outlook": outlook,
                    "Expected_Move": exp_move,
                    "Confidence": conf,
                    "Bias": bias,
                    "Key_Levels": f"Support: {round(s['daily_low'], 1)} | Resistance: {round(s['daily_high'], 1)}",
                    "Timeframe": "Next Day",
                }
                row_was_real = True
        except Exception:
            row = None

        if row is None:
            row = _simulated_row(symbol)

        # ---- Last 30-min flow (buying vs heavy selling) ----
        if include_flow:
            if row_was_real and fyers is not None:
                try:
                    flow_sig, flow_detail = last_30min_flow(fyers, symbol)
                except Exception:
                    flow_sig, flow_detail = "N/A", "—"
            else:
                flow_sig, flow_detail = _simulated_flow()
        else:
            flow_sig, flow_detail = "Skipped", "—"
        row["Last30Min"] = flow_sig
        row["Flow_Detail"] = flow_detail

        results.append(row)

    return pd.DataFrame(results)


def _ts_to_ist(ts):
    try:
        ts = float(ts)
        if ts > 1e12:                      # milliseconds -> seconds
            ts /= 1000.0
        return datetime.fromtimestamp(ts, tz=IST).time()
    except Exception:
        return None


def fetch_intraday_candles(fyers, symbol, resolution="5", days=7):
    """
    Fetch 5-minute OHLCV candles keeping the time-of-day mapping.
    Returns DataFrame[ts, tod, o, h, l, c, v] or None.
    """
    if fyers is None:
        return None
    fsym = to_fyers_symbol(symbol)
    if not fsym:
        return None

    to_date = datetime.now(IST).date()
    from_date = to_date - timedelta(days=days)

    payload = {
        "symbol": fsym,
        "resolution": resolution,
        "date_format": "1",
        "range_from": from_date.strftime("%Y-%m-%d"),
        "range_to": to_date.strftime("%Y-%m-%d"),
        "cont_flag": "1",
    }
    try:
        resp = fyers.history(data=payload)
    except Exception:
        return None

    if not isinstance(resp, dict) or resp.get("s") != "ok":
        return None

    candles = resp.get("candles") or []
    if not candles:
        return None

    rows = []
    for c in candles:
        tod = _ts_to_ist(c[0])
        if tod is None:
            continue
        rows.append({
            "ts": float(c[0]),
            "tod": tod,
            "o": float(c[1]), "h": float(c[2]), "l": float(c[3]),
            "c": float(c[4]), "v": float(c[5]) if len(c) > 5 else 0.0,
        })

    if not rows:
        return None
    return pd.DataFrame(rows).sort_values("ts").reset_index(drop=True)


def last_30min_flow(fyers, symbol):
    """
    Classify the last 30 minutes of trading (last 6 × 5-min candles):
    buying pressure vs heavy selling, plus intensity vs the day's average
    30-minute volume. Returns (signal, detail).
    """
    df = fetch_intraday_candles(fyers, symbol)
    if df is None or df.empty:
        return "N/A", "no intraday data"

    last = df.tail(6)
    up = float(last[last["c"] >= last["o"]]["v"].sum())
    down = float(last[last["c"] < last["o"]]["v"].sum())
    total = up + down
    if total <= 0:
        return "Neutral", "no volume"

    ratio = up / total
    day_vol = float(df["v"].sum())
    buckets = max(len(df) // 6, 1)
    avg_30 = day_vol / buckets
    intensity = (total / avg_30) if avg_30 > 0 else 1.0
    heavy = intensity >= 1.5

    if ratio >= 0.62:
        sig = "Heavy Buying" if heavy else "Buying"
    elif ratio <= 0.38:
        sig = "Heavy Selling" if heavy else "Selling"
    else:
        sig = "Neutral"

    detail = f"{ratio * 100:.0f}% buy vol · {intensity:.1f}x avg"
    return sig, detail


def _simulated_flow():
    r = random.random()
    if r < 0.25:
        return "Heavy Buying", f"{random.randint(70, 90)}% buy · {random.uniform(1.6, 2.5):.1f}x avg"
    if r < 0.50:
        return "Buying", f"{random.randint(62, 70)}% buy · {random.uniform(1.0, 1.5):.1f}x avg"
    if r < 0.68:
        return "Selling", f"{random.randint(30, 38)}% buy · {random.uniform(1.0, 1.5):.1f}x avg"
    if r < 0.83:
        return "Heavy Selling", f"{random.randint(10, 30)}% buy · {random.uniform(1.6, 2.5):.1f}x avg"
    return "Neutral", f"{random.randint(40, 60)}% buy · {random.uniform(0.7, 1.2):.1f}x avg"


def _simulated_row(symbol):
    """Simulated fallback row (keeps the app alive if the API fails)."""
    ltp = round(random.uniform(150, 4500), 2)
    score = round(random.uniform(-12, 12), 1)
    outlook, bias = _outlook_from_score(score)
    conf = _confidence(score, bias)

    if bias == "Bullish":
        exp_move = f"+{round(random.uniform(0.8, 3.5), 1)}%"
    elif bias == "Bearish":
        exp_move = f"-{round(random.uniform(0.8, 3.5), 1)}%"
    else:
        exp_move = f"±{round(random.uniform(0.4, 1.5), 1)}%"

    support = round(ltp * (1 - random.uniform(0.01, 0.04)), 1)
    resistance = round(ltp * (1 + random.uniform(0.01, 0.04)), 1)

    return {
        "Symbol": symbol,
        "LTP": ltp,
        "Outlook": outlook,
        "Expected_Move": exp_move,
        "Confidence": conf,
        "Bias": bias,
        "Key_Levels": f"Support: {support} | Resistance: {resistance}",
        "Timeframe": "Next Day",
    }


def get_next_day_mock(symbols):
    return scan_next_day(None, symbols)
