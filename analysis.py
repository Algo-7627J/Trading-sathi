# analysis.py — RAO SAHAB real FYERS-powered scoring engine
# Pulls live OHLCV from FYERS, computes technical indicators + 16-pattern
# detection (patterns.py), and produces a -17..+17 confluence score.
# Gracefully falls back to simulated data if the API is unavailable.
import random
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

SCORE_MAX = 17.0

try:
    from patterns import detect_patterns
except Exception:
    detect_patterns = None

# ====================== FYERS SYMBOL / RESOLUTION MAPPING ======================
INDEX_SYMBOLS = {
    "NIFTY50": "NSE:NIFTY50-INDEX",
    "BANKNIFTY": "NSE:BANKNIFTY-INDEX",
    "FINNIFTY": "NSE:FINNIFTY-INDEX",
    "MIDCPNIFTY": "NSE:MIDCPNIFTY-INDEX",
    "SENSEX": "BSE:SENSEX-INDEX",
}
# MCX contracts need live expiry mapping — kept as simulated fallback
COMMODITY_SYMBOLS = {"GOLD", "SILVER", "CRUDEOIL", "NATURALGAS", "COPPER"}

# timeframe -> (fyers resolution, days of history to pull)
RESOLUTION_MAP = {
    "1m": ("1", 3),
    "5m": ("5", 7),
    "15m": ("15", 12),
    "1h": ("60", 40),
    "60m": ("60", 40),
    "1d": ("D", 420),
    "1w": ("W", 365 * 4),
    "1M": ("M", 365 * 7),
}


def to_fyers_symbol(symbol):
    s = str(symbol).upper().strip()
    if not s:
        return None
    if s in COMMODITY_SYMBOLS:
        return None                       # simulated fallback
    if s in INDEX_SYMBOLS:
        return INDEX_SYMBOLS[s]
    if ":" in s:                          # already full e.g. NSE:RELIANCE-EQ
        return s
    return f"NSE:{s}-EQ"


def fetch_candles(fyers, symbol, timeframe_mode="15m", resolution=None, days=None):
    """Fetch OHLCV candles from FYERS. Returns DataFrame[o,h,l,c,v] or None."""
    if fyers is None:
        return None
    fsym = to_fyers_symbol(symbol)
    if not fsym:
        return None

    if resolution is None or days is None:
        resolution, days = RESOLUTION_MAP.get(timeframe_mode, ("15", 12))

    to_date = datetime.now().date()
    from_date = to_date - timedelta(days=days)

    payload = {
        "symbol": fsym,
        "resolution": resolution,
        "date_format": "1",
        "range_from": from_date.strftime("%Y-%m-%d"),
        "range_to": to_date.strftime("%Y-%m-%d"),
        "cont_flag": "1",
    }
    resp = fyers.history(data=payload)
    if not isinstance(resp, dict) or resp.get("s") != "ok":
        return None

    candles = resp.get("candles") or []
    if len(candles) < 30:
        return None

    df = pd.DataFrame(candles, columns=["ts", "o", "h", "l", "c", "v"][: len(candles[0])])
    for col in ["o", "h", "l", "c", "v"]:
        if col not in df.columns:
            return None
    return df[["o", "h", "l", "c", "v"]].astype(float).reset_index(drop=True)


# ====================== INDICATORS ======================
def _ema(series, n):
    return series.ewm(span=n, adjust=False).mean()


def _rsi(close, n=14):
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(50.0)


def _atr(df, n=14):
    prev_c = df["c"].shift(1)
    tr = pd.concat([
        df["h"] - df["l"],
        (df["h"] - prev_c).abs(),
        (df["l"] - prev_c).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def _fmt_volume(v):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return "N/A"
    if v >= 1e7:
        return f"{v / 1e7:.1f}Cr"
    if v >= 1e5:
        return f"{v / 1e5:.1f}L"
    if v >= 1e3:
        return f"{v / 1e3:.0f}K"
    return f"{int(v)}"


# ====================== SCORER ======================
def signal_from_score(score):
    if score > 6:
        return "Strong Buy"
    if score > 2:
        return "Buy"
    if score < -6:
        return "Strong Sell"
    if score < -2:
        return "Sell"
    return "Neutral"


def score_dataframe(df):
    """
    Compute the RAO SAHAB confluence score (-17..+17) from OHLCV candles.

    Components (max |points|):
      1. EMA trend structure      ±6
      2. MACD momentum            ±3
      3. RSI momentum/exhaustion  ±3
      4. Volume confirmation      ±2
      5. Chart pattern (16 types) ±3
    """
    close, high, low = df["c"], df["h"], df["l"]
    vol = df["v"]

    ema9, ema21, ema50 = _ema(close, 9), _ema(close, 21), _ema(close, 50)
    macd_line = _ema(close, 12) - _ema(close, 26)
    macd_sig = _ema(macd_line, 9)
    macd_hist = macd_line - macd_sig
    rsi = _rsi(close, 14)
    atr = _atr(df, 14)

    c = float(close.iloc[-1])
    score = 0.0

    # neutral-band helper: tiny moves are neither bullish nor bearish
    EPS = 0.0008  # ~0.08%

    def _sign_pts(pct_gap, pts=1.5):
        if pct_gap > EPS:
            return pts
        if pct_gap < -EPS:
            return -pts
        return 0.0

    # ---- 1. EMA trend structure (±6) ----
    e9, e21, e50 = float(ema9.iloc[-1]), float(ema21.iloc[-1]), float(ema50.iloc[-1])
    score += _sign_pts((c - e21) / e21)            # price vs EMA21
    score += _sign_pts((e9 - e21) / e21)           # EMA9 vs EMA21
    score += _sign_pts((e21 - e50) / e50)          # EMA21 vs EMA50

    e21_now, e21_prv = float(ema21.iloc[-1]), float(ema21.iloc[-6])
    score += _sign_pts((e21_now - e21_prv) / e21_prv)   # EMA21 slope

    # ---- 2. MACD momentum (±3) ----
    h_now, h_prv = float(macd_hist.iloc[-1]), float(macd_hist.iloc[-6])
    eps_a = c * 0.0005                              # ~0.05% of price
    score += 1.5 if h_now > eps_a / 2 else (-1.5 if h_now < -eps_a / 2 else 0.0)
    d_h = h_now - h_prv
    score += 1.5 if d_h > eps_a / 10 else (-1.5 if d_h < -eps_a / 10 else 0.0)

    # ---- 3. RSI momentum / exhaustion (±3) ----
    r = float(rsi.iloc[-1])
    if r > 80:
        score -= 0.5
    elif r > 70:
        score += 1.0
    elif r > 55:
        score += 2.0
    elif r >= 45:
        score += 0.0
    elif r >= 30:
        score -= 2.0
    elif r >= 20:
        score -= 1.0
    else:
        score += 0.5

    # ---- 4. Volume confirmation (±2) ----
    vol_ratio = float(vol.iloc[-1] / vol.tail(21).mean()) if float(vol.tail(21).mean()) > 0 else 1.0
    candle_bull = float(close.iloc[-1]) >= float(df["o"].iloc[-1])
    if vol_ratio >= 1.5:
        score += 2.0 if candle_bull else -2.0
    elif vol_ratio >= 1.2:
        score += 1.0 if candle_bull else -1.0

    # ---- 5. Chart pattern ±3 ----
    pattern_name, pattern_dir, pattern_pts = "None", "NEUTRAL", 0.0
    if detect_patterns is not None:
        try:
            p = detect_patterns(df)
            if p and p.get("pattern") and p["pattern"] != "None":
                pattern_name = p["pattern"]
                pattern_dir = p.get("direction", "NEUTRAL")
                pattern_pts = float(p.get("score", 0.0)) * 3.75   # 0.65–0.8 → ±2.4–3.0
                score += pattern_pts
        except Exception:
            pass

    score = round(max(-SCORE_MAX, min(SCORE_MAX, score)), 1)
    signal = signal_from_score(score)

    # MTF-ish trend label from EMA alignment
    if e9 > e21 > e50:
        mtf = "Bullish"
    elif e9 < e21 < e50:
        mtf = "Bearish"
    else:
        mtf = "Neutral"

    return {
        "score": score,
        "signal": signal,
        "pattern": pattern_name,
        "pattern_dir": pattern_dir,
        "mtf": mtf,
        "ltp": round(c, 2),
        "vol_str": _fmt_volume(vol.iloc[-1]),
        "rsi": round(r, 1),
        "atr": float(atr.iloc[-1]) if len(atr) else 0.0,
        "daily_low": float(low.tail(10).min()),
        "daily_high": float(high.tail(10).max()),
    }


# ====================== MAIN SCAN ======================
def scan_universe(fyers, symbols, timeframe_mode="15m", include_news=True, include_fundamental=False, progress=None):
    """Real FYERS-powered scan. Falls back to simulated data per-symbol on failure."""
    results = []

    for i, symbol in enumerate(symbols):
        if progress:
            progress.progress((i + 1) / len(symbols), text=f"Scanning {symbol}...")

        row = None
        try:
            df = fetch_candles(fyers, symbol, timeframe_mode=timeframe_mode)
            if df is not None and len(df) >= 30:
                s = score_dataframe(df)
                row = {
                    "Symbol": symbol,
                    "LTP": s["ltp"],
                    "Signal": s["signal"],
                    "Score": s["score"],
                    "Pattern": s["pattern"],
                    "MTF Status": s["mtf"],
                    "Volume": s["vol_str"],
                    "Timeframe": timeframe_mode,
                }
        except Exception:
            row = None

        if row is None:
            row = _simulated_row(symbol, timeframe_mode, include_news)

        results.append(row)

    return pd.DataFrame(results)


def _simulated_row(symbol, timeframe_mode, include_news=True):
    """Simulated fallback row (keeps the app alive if the API fails)."""
    ltp = round(random.uniform(150, 4500), 2)
    score = round(random.uniform(-12, 12), 1)
    if include_news and random.random() > 0.6:
        score += 1.5 if score > 0 else -1.5
        score = round(max(-SCORE_MAX, min(SCORE_MAX, score)), 1)
    return {
        "Symbol": symbol,
        "LTP": ltp,
        "Signal": signal_from_score(score),
        "Score": score,
        "Pattern": "Simulated",
        "MTF Status": random.choice(["Bullish", "Bearish", "Neutral"]),
        "Volume": f"{random.randint(1, 45)}M",
        "Timeframe": timeframe_mode,
    }


def get_mock_intraday_data(symbols):
    return scan_universe(None, symbols, timeframe_mode="15m")
