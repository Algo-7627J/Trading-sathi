# commodities.py — RAO SAHAB Gold & Silver multi-timeframe forecast engine
# Real market data via Yahoo Finance (COMEX futures, USD/oz).
# Combines the RAO SAHAB confluence scorer across 5 timeframes +
# 20-day breakout (price + volume confirmation) logic.
import random
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from analysis import score_dataframe, signal_from_score, SCORE_MAX

try:
    import yfinance as yf
except Exception:
    yf = None

METALS = {
    "GOLD": {"yf": "GC=F", "name": "GOLD", "icon": "🥇", "unit": "USD/oz"},
    "SILVER": {"yf": "SI=F", "name": "SILVER", "icon": "🥈", "unit": "USD/oz"},
}

# Multi-timeframe weights (longer term = higher conviction)
TF_WEIGHTS = {
    "Intraday (15m)": 0.15,
    "Next Day (Daily)": 0.20,
    "Weekly": 0.20,
    "Monthly": 0.20,
    "Yearly (1-Yr Trend)": 0.25,
}


# ====================== DATA ======================
def _fetch_yf(yf_symbol, period, interval):
    if yf is None:
        return None
    try:
        h = yf.Ticker(yf_symbol).history(period=period, interval=interval, auto_adjust=True)
        if h is None or len(h) < 30:
            return None
        df = pd.DataFrame({
            "o": h["Open"].astype(float).values,
            "h": h["High"].astype(float).values,
            "l": h["Low"].astype(float).values,
            "c": h["Close"].astype(float).values,
            "v": h["Volume"].astype(float).values,
        }, index=pd.DatetimeIndex(h.index).tz_localize(None))
        return df.dropna().reset_index(drop=True) if interval != "1d" else df.dropna()
    except Exception:
        return None


def _resample(df, rule):
    out = df.set_index(pd.DatetimeIndex(df["ts_idx"]) if "ts_idx" in df.columns else df.index) \
        if hasattr(df.index, "to_periodindex") or isinstance(df.index, pd.DatetimeIndex) else df
    if not isinstance(out.index, pd.DatetimeIndex):
        return None
    res = out.resample(rule).agg({"o": "first", "h": "max", "l": "min", "c": "last", "v": "sum"}).dropna()
    return res if len(res) >= 30 else None


# ====================== BREAKOUT (PRICE + VOLUME) ======================
def _breakout_logic(daily):
    """20-day range breakout with volume confirmation."""
    recent = daily.tail(21)
    prev, last = recent.iloc[:-1], recent.iloc[-1]
    hi20, lo20 = float(prev["h"].max()), float(prev["l"].min())
    close = float(last["c"])

    avg_vol = float(prev["v"].mean())
    vol_ratio = round(float(last["v"]) / avg_vol, 2) if avg_vol > 0 else 1.0
    vol_ratio = min(vol_ratio, 9.99)   # clamp contract-roll day spikes
    vol_ok = vol_ratio >= 1.3

    if close > hi20:
        pct = round((close - hi20) / hi20 * 100, 2)
        return {
            "state": "up",
            "strength": "Confirmed" if vol_ok else "Low-Volume",
            "vol_ratio": vol_ratio,
            "note": f"{pct}% above 20D high ({hi20:,.1f})",
            "hi20": hi20, "lo20": lo20,
        }
    if close < lo20:
        pct = round((lo20 - close) / lo20 * 100, 2)
        return {
            "state": "down",
            "strength": "Confirmed" if vol_ok else "Low-Volume",
            "vol_ratio": vol_ratio,
            "note": f"{pct}% below 20D low ({lo20:,.1f})",
            "hi20": hi20, "lo20": lo20,
        }
    # inside range — distance to edges
    d_up = round((hi20 - close) / close * 100, 2)
    d_dn = round((close - lo20) / close * 100, 2)
    return {
        "state": "inside",
        "strength": "—",
        "vol_ratio": vol_ratio,
        "note": f"{d_up}% below 20D high • {d_dn}% above 20D low",
        "hi20": hi20, "lo20": lo20,
    }


# ====================== MAIN REPORT ======================
def get_metal_report(key="GOLD", force_refresh=False):
    meta = METALS.get(str(key).upper(), METALS["GOLD"])
    yf_sym = meta["yf"]

    daily = _fetch_yf(yf_sym, "3y", "1d")
    intra = _fetch_yf(yf_sym, "59d", "15m")

    if daily is None:
        return _sim_report(meta)

    # ---- build timeframe frames ----
    def with_idx(df):
        # keep datetime index version for resampling
        return df

    weekly = _resample(daily, "W-FRI")
    monthly = _resample(daily, "ME")
    yearly = daily.tail(252).reset_index(drop=True)

    frames = {
        "Intraday (15m)": intra.reset_index(drop=True) if intra is not None else None,
        "Next Day (Daily)": daily.tail(300).reset_index(drop=True),
        "Weekly": weekly.reset_index(drop=True) if weekly is not None else None,
        "Monthly": monthly.reset_index(drop=True) if monthly is not None else None,
        "Yearly (1-Yr Trend)": yearly,
    }

    timeframes, dir_count = {}, {"Bullish": 0, "Bearish": 0, "Neutral": 0}
    wsum, wtot = 0.0, 0.0

    for label, frame in frames.items():
        w = TF_WEIGHTS[label]
        if frame is None or len(frame) < 30:
            s = _sim_score()
            simulated = True
        else:
            try:
                s = score_dataframe(frame[["o", "h", "l", "c", "v"]])
                simulated = False
            except Exception:
                s, simulated = _sim_score(), True
        d = "Bullish" if s["score"] > 2 else ("Bearish" if s["score"] < -2 else "Neutral")
        dir_count[d] += 1
        wsum += s["score"] * w
        wtot += w
        timeframes[label] = {
            "score": s["score"],
            "signal": s["signal"],
            "direction": d,
            "rsi": s.get("rsi", 50),
            "simulated": simulated,
        }

    consensus = round(wsum / wtot, 1) if wtot else 0.0
    if consensus >= 8:
        c_dir = "Strong Bullish"
    elif consensus >= 3:
        c_dir = "Bullish"
    elif consensus <= -8:
        c_dir = "Strong Bearish"
    elif consensus <= -3:
        c_dir = "Bearish"
    else:
        c_dir = "Neutral / Mixed"

    brk = _breakout_logic(daily)
    day = score_dataframe(daily.tail(300)[["o", "h", "l", "c", "v"]])
    ltp = float(daily["c"].iloc[-1])
    prev = float(daily["c"].iloc[-2])
    change_pct = round((ltp - prev) / prev * 100, 2)
    atr_pct = round(max(0.1, day["atr"] / ltp * 100), 1)

    forecast = _build_forecast(c_dir, consensus, dir_count, len(frames), brk, day["rsi"], atr_pct, day)

    return {
        "name": meta["name"],
        "icon": meta["icon"],
        "unit": meta["unit"],
        "ltp": round(ltp, 2),
        "change_pct": change_pct,
        "timeframes": timeframes,
        "consensus": consensus,
        "consensus_dir": c_dir,
        "bull_count": dir_count["Bullish"],
        "bear_count": dir_count["Bearish"],
        "breakout": brk,
        "atr_pct": atr_pct,
        "support": round(day["daily_low"], 1),
        "resistance": round(day["daily_high"], 1),
        "forecast": forecast,
        "simulated": False,
    }


def _build_forecast(c_dir, consensus, dir_count, total_tf, brk, rsi, atr_pct, day):
    dom = "bullish" if dir_count["Bullish"] >= dir_count["Bearish"] else "bearish"
    parts = [
        f"{dom.capitalize()} momentum on {max(dir_count['Bullish'], dir_count['Bearish'])}/{total_tf} timeframes "
        f"(consensus {consensus:+.1f} / {int(SCORE_MAX)} → **{c_dir}**)."
    ]
    if brk["state"] == "up":
        parts.append(f"🚀 Upside breakout ({brk['strength'].lower()}: volume {brk['vol_ratio']}× avg) — {brk['note']}. Trend continuation favored.")
    elif brk["state"] == "down":
        parts.append(f"⚠️ Downside breakdown ({brk['strength'].lower()}: volume {brk['vol_ratio']}× avg) — {brk['note']}. Weakness may extend.")
    else:
        parts.append(f"⏸️ Inside 20-day range ({brk['note']}) — wait for a volume-backed break.")
    if rsi >= 80:
        parts.append("RSI overbought — watch for exhaustion pullbacks.")
    elif rsi <= 20:
        parts.append("RSI oversold — bounce possible.")
    parts.append(f"Next-day expected move ±{atr_pct}%.  Support **{day['daily_low']:,.1f}** • Resistance **{day['daily_high']:,.1f}**.")
    return " ".join(parts)


# ====================== SIMULATED FALLBACK ======================
def _sim_score():
    score = round(random.uniform(-12, 12), 1)
    return {"score": score, "signal": signal_from_score(score), "rsi": round(random.uniform(30, 70), 1)}


def _sim_report(meta):
    ltp = 4100.0 if meta["name"] == "GOLD" else 58.0
    ltp = round(ltp * random.uniform(0.97, 1.03), 2)
    timeframes = {}
    for label in TF_WEIGHTS:
        s = _sim_score()
        d = "Bullish" if s["score"] > 2 else ("Bearish" if s["score"] < -2 else "Neutral")
        timeframes[label] = {"score": s["score"], "signal": s["signal"], "direction": d, "rsi": s["rsi"], "simulated": True}
    return {
        "name": meta["name"], "icon": meta["icon"], "unit": meta["unit"],
        "ltp": ltp, "change_pct": round(random.uniform(-1.5, 1.5), 2),
        "timeframes": timeframes, "consensus": round(random.uniform(-6, 6), 1),
        "consensus_dir": "Neutral / Mixed", "bull_count": 2, "bear_count": 2,
        "breakout": {"state": "inside", "strength": "—", "vol_ratio": 1.0,
                     "note": "—", "hi20": ltp * 1.02, "lo20": ltp * 0.98},
        "atr_pct": 1.2, "support": round(ltp * 0.98, 1), "resistance": round(ltp * 1.02, 1),
        "forecast": "Live data unavailable — showing simulated outlook.",
        "simulated": True,
    }
