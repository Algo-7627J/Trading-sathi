# momentum.py — RAO SAHAB momentum screens
# ------------------------------------------------------------------
# 1) STRONG DIRECTION  — stocks whose momentum points the SAME way across
#    the 1-Day, 1-Week and 1-Month timeframes (strong directional bias).
# 2) CONSECUTIVE STREAK — stocks that have closed UP (or DOWN) for N
#    consecutive trading days (persistent momentum).
#
# Data: FYERS daily candles first, Yahoo Finance (yfinance) as an
# automatic real-data fallback. A 10-minute in-memory cache avoids
# re-fetching the same symbol across tabs.
# ------------------------------------------------------------------
import time
from datetime import datetime, timedelta, timezone

import pandas as pd
import streamlit as st

try:
    import yfinance as yf
except Exception:
    yf = None

from analysis import to_fyers_symbol
from ui_helpers import (
    GREEN, GREEN_DARK, RED, RED_DARK, MUTED, INK, HEADING,
    BORDER, GREEN_TINT, RED_TINT, GRAY_TINT, NEUT_BAR,
    _fmt_money, _chip, _linkify,
)

IST = timezone(timedelta(hours=5, minutes=30))

# Yahoo Finance ticker for NSE indices (fallback path only)
_YF_INDEX = {"NIFTY50": "^NSEI", "BANKNIFTY": "^NSEBANK", "FINNIFTY": "^NIFTY_FIN_SERVICE", "SENSEX": "^BSESN"}
_YF_NO_LINK = {"GOLD", "SILVER", "CRUDEOIL", "NATURALGAS", "COPPER"}

# ---------------- daily-candle cache (shared across tabs, TTL 10 min) ----------------
_CACHE = {}          # symbol -> (ts, DataFrame or None)
_CACHE_TTL = 600     # seconds


def _yf_daily(symbol, days=800):
    """Yahoo Finance daily OHLCV fallback (real data)."""
    if yf is None:
        return None
    try:
        s = str(symbol).upper().strip()
        if ":" in s or s in _YF_NO_LINK:
            return None
        ticker = _YF_INDEX.get(s, f"{s}.NS")
        df = yf.download(ticker, period="2y", interval="1d", progress=False, auto_adjust=True)
        if df is None or df.empty:
            return None
        # normalise columns (yfinance sometimes returns a MultiIndex)
        df = df.copy()
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
        df.columns = [str(c).strip().lower() for c in df.columns]
        df = df.reset_index()
        date_col = "date" if "date" in df.columns else df.columns[0]
        need = {"open": "o", "high": "h", "low": "l", "close": "c", "volume": "v"}
        out = pd.DataFrame({"date": pd.to_datetime(df[date_col]).dt.date})
        for src, dst in need.items():
            if src in df.columns:
                out[dst] = pd.to_numeric(df[src], errors="coerce")
            else:
                out[dst] = float("nan")
        out = out.dropna(subset=["c"]).reset_index(drop=True)
        return out if len(out) >= 30 else None
    except Exception:
        return None


def _fyers_daily_with_dates(fyers, symbol, days=800):
    """FYERS daily candles WITH a date column (needed for PEAD/streak)."""
    fsym = to_fyers_symbol(symbol)
    if not fsym:
        return None
    to_date = datetime.now().date()
    from_date = to_date - timedelta(days=days)
    payload = {
        "symbol": fsym, "resolution": "D", "date_format": "1",
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
    if len(candles) < 30:
        return None
    rows = []
    for c in candles:
        try:
            ts = float(c[0])
            if ts > 1e12:
                ts /= 1000.0
            d = datetime.fromtimestamp(ts, tz=IST).date()
            rows.append({"date": d, "o": float(c[1]), "h": float(c[2]),
                         "l": float(c[3]), "c": float(c[4]), "v": float(c[5])})
        except Exception:
            continue
    if len(rows) < 30:
        return None
    return (
        pd.DataFrame(rows)
        .sort_values("date")
        .drop_duplicates("date")
        .reset_index(drop=True)
    )


def fetch_daily_history(fyers, symbol):
    """Daily OHLCV DataFrame with a 'date' column (FYERS first, yfinance fallback).

    Returns None when neither source yields enough history.
    """
    now = time.time()
    hit = _CACHE.get(symbol)
    if hit and (now - hit[0]) < _CACHE_TTL:
        return hit[1]

    df = None
    if fyers is not None:
        try:
            df = _fyers_daily_with_dates(fyers, symbol)
        except Exception:
            df = None
    if (df is None or len(df) < 30) and yf is not None:
        df = _yf_daily(symbol)
    if df is None or len(df) < 30:
        df = None

    _CACHE[symbol] = (now, df)
    return df


# ====================== MOMENTUM / STREAK MATHS ======================
def _pct_change(df, days_back):
    """% change from `days_back` sessions ago to the latest close."""
    if df is None or len(df) <= days_back:
        return None
    base = float(df["c"].iloc[-(days_back + 1)])
    cur = float(df["c"].iloc[-1])
    if base == 0:
        return None
    return (cur / base - 1) * 100.0


def _direction(v, eps=0.2):
    if v is None:
        return "flat"
    if v > eps:
        return "up"
    if v < -eps:
        return "down"
    return "flat"


def timeframes_momentum(df):
    return {
        "d1": _pct_change(df, 1),   # 1 day
        "w1": _pct_change(df, 5),   # 1 week (5 sessions)
        "m1": _pct_change(df, 21),  # 1 month (~21 sessions)
    }


def compute_streak(df):
    """Return (streak_len, direction) of consecutive same-direction closes.

    direction is 'up' | 'down' | 'flat'. A 'flat' close resets the streak.
    """
    if df is None or len(df) < 2:
        return 0, "flat"
    closes = df["c"].astype(float)
    diffs = closes.diff()
    dirs = [("up" if d > 0 else ("down" if d < 0 else "flat"))
            for d in diffs.tolist()[1:]]
    if not dirs:
        return 0, "flat"
    first = dirs[-1]
    if first == "flat":
        return 0, "flat"
    streak = 0
    for d in reversed(dirs):
        if d == first:
            streak += 1
        else:
            break
    return streak, first


# ====================== SCANS ======================
def scan_strong_direction(fyers, symbols, min_move=0.5, progress=None):
    """Stocks whose 1D / 1W / 1M momentum all point the same way."""
    rows = []
    n = max(len(symbols), 1)
    for i, s in enumerate(symbols):
        if progress:
            progress.progress((i + 1) / n, text=f"Checking {s}…")
        try:
            df = fetch_daily_history(fyers, s)
            if df is None or len(df) < 30:
                continue
            mom = timeframes_momentum(df)
            d1, w1, m1 = mom["d1"], mom["w1"], mom["m1"]
            if d1 is None or w1 is None or m1 is None:
                continue
            dirs = [_direction(d1), _direction(w1), _direction(m1)]
            if dirs == ["up", "up", "up"]:
                if min(d1, w1, m1) < min_move:
                    continue
                direction = "Strong Up"
            elif dirs == ["down", "down", "down"]:
                if max(d1, w1, m1) > -min_move:
                    continue
                direction = "Strong Down"
            else:
                continue
            rows.append({
                "Symbol": s,
                "LTP": round(float(df["c"].iloc[-1]), 2),
                "1D %": round(d1, 2),
                "1W %": round(w1, 2),
                "1M %": round(m1, 2),
                "Avg %": round((d1 + w1 + m1) / 3, 2),
                "Direction": direction,
            })
        except Exception:
            continue
    return pd.DataFrame(rows)


def scan_consecutive(fyers, symbols, min_streak=5, progress=None):
    """Stocks that closed up (or down) for >= min_streak consecutive days."""
    rows = []
    n = max(len(symbols), 1)
    for i, s in enumerate(symbols):
        if progress:
            progress.progress((i + 1) / n, text=f"Checking {s}…")
        try:
            df = fetch_daily_history(fyers, s)
            if df is None or len(df) < 30:
                continue
            streak, direction = compute_streak(df)
            if streak < min_streak or direction == "flat":
                continue
            closes = df["c"].astype(float)
            start = float(closes.iloc[-1 - streak])
            end = float(closes.iloc[-1])
            move = (end / start - 1) * 100 if start else None
            rows.append({
                "Symbol": s,
                "LTP": round(end, 2),
                "Streak": streak,
                "Direction": "Up" if direction == "up" else "Down",
                "Streak Move %": round(move, 2) if move is not None else None,
                "As Of": str(df["date"].iloc[-1]) if "date" in df.columns else "",
            })
        except Exception:
            continue
    return pd.DataFrame(rows)


# ====================== RENDER HELPERS (Groww style) ======================
def _pct_cell(v, label):
    c = GREEN_DARK if v >= 0 else RED_DARK
    return (
        f'<div style="flex:1; text-align:center; background:{GRAY_TINT}; border-radius:8px; padding:6px 4px;">'
        f'<div style="font-size:11px; color:{MUTED};">{label}</div>'
        f'<div style="font-size:15px; font-weight:700; color:{c};">{v:+.2f}%</div></div>'
    )


def render_momentum_card(row):
    symbol = row["Symbol"]
    d1, w1, m1 = row["1D %"], row["1W %"], row["1M %"]
    direction = str(row["Direction"])
    is_up = "Up" in direction
    tone = "green" if is_up else "red"
    side = "bull" if is_up else "bear"
    ltp = _fmt_money(row.get("LTP")) if pd.notna(row.get("LTP")) else ""

    card = f"""
    <div class="opl-card {side}">
        <div style="display:flex; justify-content:space-between; align-items:center;">
            <div><span class="opl-sym">{symbol}</span><span class="opl-ext">↗</span></div>
            <div>{_chip(direction, tone)}<span class="opl-price" style="margin-left:10px;">{ltp}</span></div>
        </div>
        <div style="display:flex; gap:8px; margin-top:10px;">
            {_pct_cell(d1, "1 Day")}{_pct_cell(w1, "1 Week")}{_pct_cell(m1, "1 Month")}
        </div>
    </div>"""
    return _linkify(card, symbol)


def render_streak_card(row):
    symbol = row["Symbol"]
    streak = int(row["Streak"])
    direction = str(row["Direction"])
    is_up = direction == "Up"
    tone = "green" if is_up else "red"
    side = "bull" if is_up else "bear"
    move = row.get("Streak Move %")
    move_txt = f"{move:+.2f}%" if pd.notna(move) else "—"
    ltp = _fmt_money(row.get("LTP")) if pd.notna(row.get("LTP")) else ""
    asof = row.get("As Of", "")

    card = f"""
    <div class="opl-card {side}">
        <div style="display:flex; justify-content:space-between; align-items:center;">
            <div><span class="opl-sym">{symbol}</span><span class="opl-ext">↗</span></div>
            <div>{_chip(f"{streak} days {direction}", tone)}<span class="opl-price" style="margin-left:10px;">{ltp}</span></div>
        </div>
        <div style="display:flex; justify-content:space-between; align-items:center; margin-top:9px;">
            <span style="font-size:12.5px; color:{MUTED};">{streak} consecutive {direction.lower()} closes{' · ' + asof if asof else ''}</span>
            <span style="font-size:14px; font-weight:700; color:{GREEN_DARK if is_up else RED_DARK};">{move_txt}</span>
        </div>
    </div>"""
    return _linkify(card, symbol)
