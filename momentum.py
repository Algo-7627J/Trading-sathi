# momentum.py — RAO SAHAB momentum screens
# ------------------------------------------------------------------
# 1) STRONG DIRECTION  — stocks whose momentum points the SAME way across
#    the 1-Day, 1-Week and 1-Month timeframes (strong directional bias).
# 2) CONSECUTIVE STREAK — stocks that have closed UP (or DOWN) for N
#    consecutive trading days (persistent momentum).
#
# Each result now also carries:
#   • Delivery % (NSE security-wise delivery) → "genuineness" of the move
#   • RSI + volume ratio → overbought/oversold & participation context
#   (these feed the AI-style analysis shown on the cards)
#
# Data: FYERS daily candles first, Yahoo Finance (yfinance) as an
# automatic real-data fallback. A 10-minute in-memory cache avoids
# re-fetching the same symbol across tabs.
# ------------------------------------------------------------------
import html as _html
import time
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

try:
    import yfinance as yf
except Exception:
    yf = None

from analysis import to_fyers_symbol
from delivery import fetch_delivery_frame, delivery_map, delivery_date
from social_buzz import buzz_section_html
from ui_helpers import (
    GREEN, GREEN_DARK, RED, RED_DARK, MUTED, INK,
    GRAY_TINT, GREEN_TINT, NEUT_BAR, BORDER,
    _fmt_money, _chip,
    genuineness_chip, delivery_line,
    fyers_wrap, news_links, gemini_ai_link,
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
    """Daily OHLCV DataFrame with a 'date' column (FYERS first, yfinance fallback)."""
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
    """Return (streak_len, direction) of consecutive same-direction closes."""
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


# ====================== CONTEXT INDICATORS ======================
def _rsi_series(close, n=14):
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(50.0)


def _vol_ratio(df):
    v = df["v"].astype(float)
    last = float(v.iloc[-1])
    avg = float(v.tail(21).mean())
    return round(last / avg, 2) if avg > 0 else None


def genuineness_label(pct):
    """Conviction label from delivery % (direction-agnostic)."""
    try:
        p = float(pct)
    except (TypeError, ValueError):
        return ""
    if pd.isna(p):
        return ""
    if p >= 60:
        return "Genuine Move"
    if p >= 30:
        return "Moderate Conviction"
    return "Speculative"


def _delivery_lookup():
    """Fetch NSE delivery data once -> {SYMBOL: {...}} + latest date."""
    try:
        ddf = fetch_delivery_frame(force_refresh=False)
        if ddf is None or ddf.empty:
            return {}, ""
        return delivery_map(ddf), delivery_date(ddf)
    except Exception:
        return {}, ""


# ====================== SCANS ======================
def scan_strong_direction(fyers, symbols, min_move=0.5, progress=None):
    """Stocks whose 1D / 1W / 1M momentum all point the same way.

    Extra columns: DeliveryPct, QtyTraded, DeliverableQty, Genuineness, RSI, VolRatio.
    """
    dmap, _ = _delivery_lookup()
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
            info = dmap.get(s, {})
            dp = info.get("pct")
            rsi = float(_rsi_series(df["c"].astype(float)).iloc[-1])
            vr = _vol_ratio(df)
            rows.append({
                "Symbol": s,
                "LTP": round(float(df["c"].iloc[-1]), 2),
                "1D %": round(d1, 2),
                "1W %": round(w1, 2),
                "1M %": round(m1, 2),
                "Avg %": round((d1 + w1 + m1) / 3, 2),
                "Direction": direction,
                "DeliveryPct": dp,
                "QtyTraded": info.get("qty"),
                "DeliverableQty": info.get("delv"),
                "Genuineness": genuineness_label(dp) if dp is not None else "",
                "RSI": round(rsi, 1),
                "VolRatio": vr,
            })
        except Exception:
            continue
    return pd.DataFrame(rows)


def scan_consecutive(fyers, symbols, min_streak=5, progress=None):
    """Stocks that closed up (or down) for >= min_streak consecutive days.

    Extra columns: DeliveryPct, QtyTraded, DeliverableQty, Genuineness, RSI, VolRatio.
    """
    dmap, _ = _delivery_lookup()
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
            info = dmap.get(s, {})
            dp = info.get("pct")
            rsi = float(_rsi_series(closes).iloc[-1])
            vr = _vol_ratio(df)
            rows.append({
                "Symbol": s,
                "LTP": round(end, 2),
                "Streak": streak,
                "Direction": "Up" if direction == "up" else "Down",
                "Streak Move %": round(move, 2) if move is not None else None,
                "As Of": str(df["date"].iloc[-1]) if "date" in df.columns else "",
                "DeliveryPct": dp,
                "QtyTraded": info.get("qty"),
                "DeliverableQty": info.get("delv"),
                "Genuineness": genuineness_label(dp) if dp is not None else "",
                "RSI": round(rsi, 1),
                "VolRatio": vr,
            })
        except Exception:
            continue
    return pd.DataFrame(rows)


# ====================== RENDER HELPERS (single-line HTML, Groww style) ======================
def _pct_cell(v, label):
    c = GREEN_DARK if v >= 0 else RED_DARK
    return (f'<div style="flex:1;text-align:center;background:{GRAY_TINT};border-radius:8px;padding:6px 4px;">'
            f'<div style="font-size:11px;color:{MUTED};">{label}</div>'
            f'<div style="font-size:15px;font-weight:700;color:{c};">{v:+.2f}%</div></div>')


def _analysis_box(text):
    if not text:
        return ""
    return (f'<div style="margin-top:9px;background:{GRAY_TINT};border-radius:8px;padding:8px 11px;'
            f'font-size:12.5px;color:{INK};line-height:1.55;">\U0001F4A1 {_html.escape(str(text))}</div>')


def _meta_line(dp, genuineness):
    dl = delivery_line(dp)
    gc = genuineness_chip(genuineness) if genuineness else ""
    if not dl and not gc:
        return ""
    return f'<div style="display:flex;align-items:center;gap:8px;margin-top:9px;flex-wrap:wrap;">{dl}{gc}</div>'


def render_momentum_card(row, analysis=None, news=None, buzz=None):
    symbol = row["Symbol"]
    d1, w1, m1 = row["1D %"], row["1W %"], row["1M %"]
    direction = str(row["Direction"])
    is_up = "Up" in direction
    tone = "green" if is_up else "red"
    side = "bull" if is_up else "bear"
    ltp = _fmt_money(row.get("LTP")) if pd.notna(row.get("LTP")) else ""

    main = (f'<div style="display:flex;justify-content:space-between;align-items:center;">'
            f'<div><span class="opl-sym">{symbol}</span><span class="opl-ext">\u2197</span></div>'
            f'<div style="display:flex;align-items:center;gap:8px;">{_chip(direction, tone)}'
            f'<span class="opl-price">{ltp}</span></div></div>'
            f'<div style="display:flex;gap:8px;margin-top:10px;">'
            f'{_pct_cell(d1, "1 Day")}{_pct_cell(w1, "1 Week")}{_pct_cell(m1, "1 Month")}</div>'
            f'{_meta_line(row.get("DeliveryPct"), row.get("Genuineness", ""))}'
            f'{_analysis_box(analysis)}')

    card = (f'<div class="opl-card {side}">{fyers_wrap(symbol, main)}'
            f'{news_links(news)}{buzz_section_html(buzz)}{gemini_ai_link(symbol)}</div>')
    return card


def render_streak_card(row, analysis=None, news=None, buzz=None):
    symbol = row["Symbol"]
    streak = int(row["Streak"])
    direction = str(row["Direction"])
    is_up = direction == "Up"
    tone = "green" if is_up else "red"
    side = "bull" if is_up else "bear"
    move = row.get("Streak Move %")
    move_txt = f"{move:+.2f}%" if pd.notna(move) else "\u2014"
    ltp = _fmt_money(row.get("LTP")) if pd.notna(row.get("LTP")) else ""
    asof = row.get("As Of", "")

    main = (f'<div style="display:flex;justify-content:space-between;align-items:center;">'
            f'<div><span class="opl-sym">{symbol}</span><span class="opl-ext">\u2197</span></div>'
            f'<div style="display:flex;align-items:center;gap:8px;">{_chip(f"{streak}d {direction}", tone)}'
            f'<span class="opl-price">{ltp}</span></div></div>'
            f'<div style="display:flex;justify-content:space-between;align-items:center;margin-top:9px;">'
            f'<span style="font-size:12.5px;color:{MUTED};">{streak} consecutive {direction.lower()} closes'
            f'{" · " + asof if asof else ""}</span>'
            f'<span style="font-size:14px;font-weight:700;color:{GREEN_DARK if is_up else RED_DARK};">{move_txt}</span></div>'
            f'{_meta_line(row.get("DeliveryPct"), row.get("Genuineness", ""))}'
            f'{_analysis_box(analysis)}')

    card = (f'<div class="opl-card {side}">{fyers_wrap(symbol, main)}'
            f'{news_links(news)}{buzz_section_html(buzz)}{gemini_ai_link(symbol)}</div>')
    return card
