"""
Next-Day Outlook engine.

Important honesty note (read this before trusting the output):
No model can *reliably* predict tomorrow's stock direction with high
accuracy - markets are influenced by news, global cues, block deals and
randomness that no technical signal can see. What this module does instead
is:

  1. Compute a set of technical signals on DAILY candles that have some
     documented historical edge (trend, ADX/DI trend-strength, RSI/MACD
     momentum, Bollinger Band position, Relative Strength vs Nifty,
     Support/Resistance proximity, Gap behaviour, Volume confirmation).
  2. Combine them into a directional score (like the existing intraday
     scanner), BUT also...
  3. BACKTEST the exact same rule-set against ~1 year of that stock's own
     historical daily candles, so we can report a real, honest
     "this setup has historically been right X% of the time, over N
     occurrences" statistic next to every call, instead of just trusting
     an abstract score.

A "STRONG BULLISH"/"STRONG BEARISH" label is only shown with high
confidence if the backtested hit-rate and sample size clear a minimum bar;
otherwise it's downgraded and flagged as low-confidence.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from config import (
    NIFTY_INDEX_SYMBOL,
    NEXT_DAY_LOOKBACK_DAYS,
    NEXT_DAY_WEIGHTS,
    NEXT_DAY_STRONG_BULLISH,
    NEXT_DAY_BULLISH,
    NEXT_DAY_BEARISH,
    NEXT_DAY_STRONG_BEARISH,
    NEXT_DAY_MIN_SAMPLE_HIGH_CONF,
    NEXT_DAY_MIN_SAMPLE_MED_CONF,
    NEXT_DAY_MIN_HIT_RATE_HIGH_CONF,
    NEXT_DAY_MIN_HIT_RATE_MED_CONF,
)
from services import fetch_history
import streamlit as st


# ---------------------------------------------------------------------------
# Indicator computation (daily candles)
# ---------------------------------------------------------------------------

def compute_daily_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    close = df["c"]
    high = df["h"]
    low = df["l"]

    df["EMA10"] = close.ewm(span=10, adjust=False).mean()
    df["EMA20"] = close.ewm(span=20, adjust=False).mean()
    df["EMA50"] = close.ewm(span=50, adjust=False).mean()

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

    # Bollinger Bands (20, 2)
    df["BB_MID"] = close.rolling(20).mean()
    bb_std = close.rolling(20).std()
    df["BB_UPPER"] = df["BB_MID"] + 2 * bb_std
    df["BB_LOWER"] = df["BB_MID"] - 2 * bb_std
    bb_range = (df["BB_UPPER"] - df["BB_LOWER"]).replace(0, 1e-9)
    df["BB_PCT"] = (close - df["BB_LOWER"]) / bb_range

    # ATR / True Range
    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    df["TR"] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df["ATR14"] = df["TR"].rolling(14).mean()

    # ADX / +DI / -DI (Wilder's smoothing, simplified rolling-mean version)
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    atr_safe = df["ATR14"].replace(0, 1e-9)
    plus_di = 100 * pd.Series(plus_dm, index=df.index).rolling(14).mean() / atr_safe
    minus_di = 100 * pd.Series(minus_dm, index=df.index).rolling(14).mean() / atr_safe
    df["PLUS_DI"] = plus_di
    df["MINUS_DI"] = minus_di
    di_sum = (plus_di + minus_di).replace(0, 1e-9)
    dx = 100 * (plus_di - minus_di).abs() / di_sum
    df["ADX"] = dx.rolling(14).mean()

    # Volume behaviour
    df["VOL_AVG20"] = df["v"].rolling(20).mean()
    df["VOL_RATIO"] = df["v"] / df["VOL_AVG20"].replace(0, 1e-9)

    # Support / Resistance via rolling swing highs/lows (20-day window)
    df["ROLL_HIGH20"] = high.rolling(20).max()
    df["ROLL_LOW20"] = low.rolling(20).min()

    # Gap vs previous close
    df["GAP_PCT"] = (df["o"] - close.shift(1)) / close.shift(1).replace(0, 1e-9) * 100

    return df


# ---------------------------------------------------------------------------
# Rule set: given indicator row(s), produce a directional score in [-1, 1]
# per factor. Same rule-set is used both for "today's live call" and for
# every historical day in the backtest, so the backtest is a faithful replay.
# ---------------------------------------------------------------------------

def _score_trend(row) -> float:
    votes = []
    votes.append(1 if row["c"] > row["EMA20"] else -1)
    votes.append(1 if row["EMA10"] > row["EMA20"] else -1)
    votes.append(1 if row["EMA20"] > row["EMA50"] else -1)
    return sum(votes) / len(votes)


def _score_adx_di(row) -> float:
    adx = row.get("ADX")
    plus_di = row.get("PLUS_DI")
    minus_di = row.get("MINUS_DI")
    if pd.isna(adx) or pd.isna(plus_di) or pd.isna(minus_di):
        return 0.0
    direction = 1 if plus_di > minus_di else -1
    if adx >= 25:
        strength = 1.0
    elif adx >= 20:
        strength = 0.6
    else:
        strength = 0.0  # weak/no trend -> ADX contributes nothing
    return direction * strength


def _score_momentum(row) -> float:
    votes = []
    macd_hist = row.get("MACD_HIST")
    rsi = row.get("RSI")
    if pd.notna(macd_hist):
        votes.append(1 if macd_hist > 0 else -1)
    if pd.notna(rsi):
        if rsi > 60:
            votes.append(1)
        elif rsi < 40:
            votes.append(-1)
        else:
            votes.append(0)
    if not votes:
        return 0.0
    return sum(votes) / len(votes)


def _score_bollinger(row) -> float:
    bb_pct = row.get("BB_PCT")
    if pd.isna(bb_pct):
        return 0.0
    if bb_pct >= 1.0:
        return -0.6  # overbought, riding upper band - mild mean-revert caution
    if bb_pct <= 0.0:
        return 0.6  # oversold, riding lower band - mild bounce bias
    if bb_pct > 0.8:
        return 0.3
    if bb_pct < 0.2:
        return -0.3
    return 0.0


def _score_relative_strength(row) -> float:
    rs = row.get("RS_VS_NIFTY_5D")
    if pd.isna(rs):
        return 0.0
    if rs > 2:
        return 1.0
    if rs > 0.5:
        return 0.5
    if rs < -2:
        return -1.0
    if rs < -0.5:
        return -0.5
    return 0.0


def _score_support_resistance(row) -> float:
    close = row.get("c")
    roll_high = row.get("ROLL_HIGH20")
    roll_low = row.get("ROLL_LOW20")
    if pd.isna(close) or pd.isna(roll_high) or pd.isna(roll_low) or roll_high <= 0:
        return 0.0
    if close >= roll_high * 0.998:
        return 0.7  # breaking out of resistance
    if close <= roll_low * 1.002:
        return -0.7  # breaking down through support
    range_span = roll_high - roll_low
    if range_span <= 0:
        return 0.0
    pos = (close - roll_low) / range_span
    if pos > 0.85:
        return 0.3
    if pos < 0.15:
        return -0.3
    return 0.0


def _score_gap(row) -> float:
    gap = row.get("GAP_PCT")
    if pd.isna(gap):
        return 0.0
    if gap > 1.5:
        return 0.4
    if gap < -1.5:
        return -0.4
    return 0.0


def _score_volume(row) -> float:
    vol_ratio = row.get("VOL_RATIO")
    direction = 1 if row.get("c", 0) >= row.get("o", 0) else -1
    if pd.isna(vol_ratio):
        return 0.0
    if vol_ratio >= 1.5:
        return 0.6 * direction
    if vol_ratio <= 0.6:
        return -0.2 * direction
    return 0.0


FACTOR_SCORERS = {
    "trend": _score_trend,
    "adx_di": _score_adx_di,
    "momentum": _score_momentum,
    "bollinger": _score_bollinger,
    "relative_strength": _score_relative_strength,
    "support_resistance": _score_support_resistance,
    "gap": _score_gap,
    "volume": _score_volume,
}


def compute_row_score(row) -> dict:
    """Return per-factor scores plus a combined weighted score in [-100, 100]."""
    factor_scores = {}
    total_w = 0
    acc = 0.0
    for name, fn in FACTOR_SCORERS.items():
        try:
            s = fn(row)
        except Exception:
            s = 0.0
        factor_scores[name] = round(s, 2)
        w = NEXT_DAY_WEIGHTS.get(name, 0)
        acc += s * w
        total_w += w
    combined = round((acc / total_w) * 100, 1) if total_w else 0.0
    factor_scores["combined"] = combined
    return factor_scores


def score_to_label(score: float) -> str:
    if score >= NEXT_DAY_STRONG_BULLISH:
        return "STRONG BULLISH"
    if score >= NEXT_DAY_BULLISH:
        return "BULLISH"
    if score <= NEXT_DAY_STRONG_BEARISH:
        return "STRONG BEARISH"
    if score <= NEXT_DAY_BEARISH:
        return "BEARISH"
    return "NEUTRAL"


# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------

@st.cache_data(ttl=1800, show_spinner=False)
def _fetch_daily_candles_cached(sym: str, days: int, _fyers):
    """
    Cached fetch of raw daily candles for a symbol. The `_fyers` object is
    excluded from the cache key (Streamlit convention: leading underscore),
    the cache is keyed on (sym, days) alone with a 30-min TTL - daily
    candles don't change intraday so this avoids redundant API calls across
    reruns/auto-refreshes within the same session.
    """
    return fetch_history(_fyers, sym, resolution="1D", days=days)


def get_daily_df(fyers, sym: str, days: int = NEXT_DAY_LOOKBACK_DAYS):
    res = _fetch_daily_candles_cached(sym, days, fyers)
    if not (res and res.get("s") == "ok" and res.get("candles")):
        return None
    df = pd.DataFrame(res["candles"], columns=["ts", "o", "h", "l", "c", "v"])
    if len(df) < 60:
        return None
    return df


def attach_relative_strength(df: pd.DataFrame, nifty_df: pd.DataFrame) -> pd.DataFrame:
    """
    RS_VS_NIFTY_5D = (stock 5-day % change) - (nifty 5-day % change), computed
    for every row so the backtest can replay it faithfully.
    """
    df = df.copy()
    stock_ret5 = df["c"].pct_change(5) * 100
    if nifty_df is not None and len(nifty_df) >= 6:
        nifty_ret5 = nifty_df["c"].pct_change(5) * 100
        # Align by position (both are daily candles fetched over the same window)
        n = min(len(df), len(nifty_ret5))
        rs = pd.Series(index=df.index, dtype=float)
        rs.iloc[-n:] = stock_ret5.iloc[-n:].values - nifty_ret5.iloc[-n:].values
        df["RS_VS_NIFTY_5D"] = rs
    else:
        df["RS_VS_NIFTY_5D"] = np.nan
    return df


# ---------------------------------------------------------------------------
# Backtest: replay the same rule-set on every historical day and check
# whether next-day direction matched the call.
# ---------------------------------------------------------------------------

def backtest_signal(df: pd.DataFrame) -> dict:
    """
    For each historical day (excluding the most recent, since we don't yet
    know its next-day outcome), compute the combined score and compare the
    predicted direction against the ACTUAL next-day close-to-close return.

    Returns hit-rate stats overall and split by BULLISH-tier calls vs
    BEARISH-tier calls, so we can show "when this setup said bullish, it was
    right X% of the time over N occurrences".
    """
    n = len(df)
    if n < 40:
        return {"sample_size": 0, "hit_rate": None, "bullish_hits": None, "bearish_hits": None}

    scores = []
    next_returns = []

    for i in range(30, n - 1):  # need enough history for indicators to warm up
        row = df.iloc[i]
        nxt = df.iloc[i + 1]
        try:
            fs = compute_row_score(row)
        except Exception:
            continue
        combined = fs["combined"]
        cur_close = row["c"]
        nxt_close = nxt["c"]
        if cur_close is None or pd.isna(cur_close) or cur_close == 0:
            continue
        ret = (nxt_close - cur_close) / cur_close * 100
        scores.append(combined)
        next_returns.append(ret)

    if not scores:
        return {"sample_size": 0, "hit_rate": None, "bullish_hits": None, "bearish_hits": None}

    scores = np.array(scores)
    next_returns = np.array(next_returns)

    bullish_mask = scores >= NEXT_DAY_BULLISH
    bearish_mask = scores <= NEXT_DAY_BEARISH

    bullish_n = int(bullish_mask.sum())
    bearish_n = int(bearish_mask.sum())

    bullish_hit_rate = (
        round(float((next_returns[bullish_mask] > 0).mean() * 100), 1) if bullish_n > 0 else None
    )
    bearish_hit_rate = (
        round(float((next_returns[bearish_mask] < 0).mean() * 100), 1) if bearish_n > 0 else None
    )

    directional_mask = bullish_mask | bearish_mask
    directional_n = int(directional_mask.sum())
    if directional_n > 0:
        correct = (
            ((bullish_mask) & (next_returns > 0)) | ((bearish_mask) & (next_returns < 0))
        ).sum()
        overall_hit_rate = round(float(correct / directional_n * 100), 1)
    else:
        overall_hit_rate = None

    return {
        "sample_size": directional_n,
        "hit_rate": overall_hit_rate,
        "bullish_n": bullish_n,
        "bullish_hit_rate": bullish_hit_rate,
        "bearish_n": bearish_n,
        "bearish_hit_rate": bearish_hit_rate,
    }


def confidence_from_backtest(bt: dict, current_label: str) -> str:
    """
    Decide HIGH / MEDIUM / LOW confidence for today's call based on the
    backtested hit-rate & sample size for calls of the SAME direction.
    """
    if not bt or not bt.get("sample_size"):
        return "LOW"

    if "BULLISH" in current_label:
        n = bt.get("bullish_n") or 0
        hr = bt.get("bullish_hit_rate")
    elif "BEARISH" in current_label:
        n = bt.get("bearish_n") or 0
        hr = bt.get("bearish_hit_rate")
    else:
        return "LOW"

    if hr is None or n == 0:
        return "LOW"

    if n >= NEXT_DAY_MIN_SAMPLE_HIGH_CONF and hr >= NEXT_DAY_MIN_HIT_RATE_HIGH_CONF:
        return "HIGH"
    if n >= NEXT_DAY_MIN_SAMPLE_MED_CONF and hr >= NEXT_DAY_MIN_HIT_RATE_MED_CONF:
        return "MEDIUM"
    return "LOW"


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def analyze_next_day(fyers, sym: str, nifty_df_cache: dict) -> dict | None:
    """
    Full pipeline for one symbol: fetch daily candles, compute indicators +
    relative strength vs Nifty, score today's setup, backtest the same
    rule-set on the past year of that stock's own data, and combine into a
    single result with an honest confidence label.
    """
    df = get_daily_df(fyers, sym, days=NEXT_DAY_LOOKBACK_DAYS)
    if df is None:
        return None

    nifty_df = nifty_df_cache.get("df")
    df = attach_relative_strength(df, nifty_df)
    df = compute_daily_indicators(df)

    last = df.iloc[-1]
    factor_scores = compute_row_score(last)
    combined_score = factor_scores["combined"]
    raw_label = score_to_label(combined_score)

    bt = backtest_signal(df)
    confidence = confidence_from_backtest(bt, raw_label)

    # Downgrade a directional call to NEUTRAL-leaning if confidence is LOW,
    # so the UI never shows "STRONG BULLISH" backed by weak/insufficient history.
    display_label = raw_label
    if confidence == "LOW" and raw_label != "NEUTRAL":
        display_label = raw_label.replace("STRONG ", "") + " (Low Confidence)"

    return {
        "symbol": sym,
        "last_close": round(float(last["c"]), 2),
        "score": combined_score,
        "raw_label": raw_label,
        "display_label": display_label,
        "confidence": confidence,
        "factor_scores": {k: v for k, v in factor_scores.items() if k != "combined"},
        "backtest": bt,
        "adx": round(float(last["ADX"]), 1) if pd.notna(last.get("ADX")) else None,
        "rsi": round(float(last["RSI"]), 1) if pd.notna(last.get("RSI")) else None,
        "rs_vs_nifty_5d": round(float(last["RS_VS_NIFTY_5D"]), 2) if pd.notna(last.get("RS_VS_NIFTY_5D")) else None,
    }


def scan_next_day(fyers, symbols: list, progress=None) -> pd.DataFrame:
    nifty_df_cache = {}
    try:
        nifty_df_cache["df"] = get_daily_df(fyers, NIFTY_INDEX_SYMBOL, days=NEXT_DAY_LOOKBACK_DAYS)
    except Exception:
        nifty_df_cache["df"] = None

    rows = []
    n = len(symbols)
    for i, sym in enumerate(symbols):
        result = analyze_next_day(fyers, sym, nifty_df_cache)
        if result is None:
            rows.append({
                "Symbol": sym,
                "LTP": None,
                "Outlook": "NO DATA",
                "Score": None,
                "Confidence": "LOW",
                "Backtest Sample": 0,
                "Backtest Hit Rate %": None,
                "ADX": None,
                "RSI": None,
                "RS vs Nifty (5D)": None,
            })
            continue

        bt = result["backtest"]
        label = result["raw_label"]
        if "BULLISH" in label:
            bt_n = bt.get("bullish_n")
            bt_hr = bt.get("bullish_hit_rate")
        elif "BEARISH" in label:
            bt_n = bt.get("bearish_n")
            bt_hr = bt.get("bearish_hit_rate")
        else:
            bt_n = bt.get("sample_size")
            bt_hr = bt.get("hit_rate")

        rows.append({
            "Symbol": sym,
            "LTP": result["last_close"],
            "Outlook": result["display_label"],
            "Score": result["score"],
            "Confidence": result["confidence"],
            "Backtest Sample": bt_n,
            "Backtest Hit Rate %": bt_hr,
            "ADX": result["adx"],
            "RSI": result["rsi"],
            "RS vs Nifty (5D)": result["rs_vs_nifty_5d"],
        })

        if progress is not None and n > 0:
            progress.progress((i + 1) / n, text=f"Analyzing {i+1}/{n}: {sym}")

    return pd.DataFrame(rows)
