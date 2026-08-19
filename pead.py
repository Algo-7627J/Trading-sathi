# pead.py — Post-Earnings Announcement Drift (PEAD) tool
# ------------------------------------------------------------------
# For stocks that have already declared results, this tool combines:
#   • Result QUALITY  — Good / Mixed / Bad, scored from the EPS surprise
#                       vs. estimates plus Revenue & Profit YoY growth
#                       (Yahoo Finance earnings calendar + financials).
#   • Post-result DRIFT (PEAD) — whether the stock is still "running"
#                       (drifting) in the direction of the result after
#                       the announcement, using daily candles.
# ------------------------------------------------------------------
from datetime import datetime, timezone, timedelta

import pandas as pd
import streamlit as st

try:
    import yfinance as yf
except Exception:
    yf = None

from momentum import fetch_daily_history
from ui_helpers import (
    GREEN, GREEN_DARK, RED, RED_DARK, MUTED, INK, HEADING,
    BORDER, GREEN_TINT, RED_TINT, GRAY_TINT, NEUT_BAR,
    _fmt_money, _chip, _linkify,
)

IST = timezone(timedelta(hours=5, minutes=30))

# tickers that are not NSE equities -> skip
_SKIP = {"GOLD", "SILVER", "CRUDEOIL", "NATURALGAS", "COPPER",
         "NIFTY50", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "SENSEX"}


def _yf_symbol(symbol):
    s = str(symbol).upper().strip()
    if not s or s in _SKIP or ":" in s:
        return None
    return f"{s}.NS"


def _yoy_growth(series):
    """YoY growth of the latest quarterly value vs the same quarter last year."""
    try:
        vals = series.astype(float)
        latest_col = series.index[0]
        latest_v = float(vals.iloc[0])
        prev_v = None
        for col, v in vals.items():
            if col.month == latest_col.month and col.year == latest_col.year - 1:
                prev_v = float(v)
                break
        if prev_v is None or prev_v == 0 or pd.isna(prev_v) or pd.isna(latest_v):
            return None
        return round((latest_v / prev_v - 1) * 100, 1)
    except Exception:
        return None


def get_earnings_info(symbol):
    """Fetch the most recent *reported* earnings date, EPS surprise and growth.

    Returns a dict or None when no reported earnings exist for the symbol.
    """
    if yf is None:
        return None
    ysym = _yf_symbol(symbol)
    if not ysym:
        return None

    info = {"Symbol": str(symbol).upper().strip()}
    t = yf.Ticker(ysym)

    # ---- most recent REPORTED earnings (skip future/estimates-only rows) ----
    try:
        ed = t.earnings_dates
        if ed is None or ed.empty:
            return None
        ed = ed[ed.index <= pd.Timestamp.now(tz=IST)]
        ed = ed[ed["Reported EPS"].notna()] if "Reported EPS" in ed.columns else ed
        if ed.empty:
            return None
        latest = ed.sort_index().iloc[-1]
        info["EarningsDate"] = latest.name.date()
        info["EPS_Estimate"] = _num(latest.get("EPS Estimate"))
        info["EPS_Actual"] = _num(latest.get("Reported EPS"))
        info["SurprisePct"] = _num(latest.get("Surprise(%)"))
    except Exception:
        return None

    # ---- revenue & net-income YoY growth (quality inputs) ----
    try:
        fin = t.quarterly_financials
        if fin is not None and not fin.empty:
            rev = fin.loc["Total Revenue"] if "Total Revenue" in fin.index else None
            ni = fin.loc["Net Income"] if "Net Income" in fin.index else None
            info["RevenueYoY"] = _yoy_growth(rev)
            info["ProfitYoY"] = _yoy_growth(ni)
    except Exception:
        pass

    return info


def _num(v):
    try:
        f = float(v)
        return f if pd.notna(f) else None
    except Exception:
        return None


def compute_pead(symbol, fyers):
    """Combine quality + post-result drift into one row dict (or None)."""
    info = get_earnings_info(symbol)
    if not info or info.get("EarningsDate") is None:
        return None

    ed = info["EarningsDate"]
    df = fetch_daily_history(fyers, symbol)
    if df is None or len(df) < 5 or "date" not in df.columns:
        return None

    pre = df[df["date"] < ed]
    post = df[df["date"] >= ed]
    if pre.empty or post.empty:
        return None

    pre_close = float(pre["c"].iloc[-1])
    post_first = float(post["c"].iloc[0])
    latest = float(df["c"].iloc[-1])
    if pre_close == 0 or post_first == 0:
        return None

    info["ReactionPct"] = round((post_first / pre_close - 1) * 100, 2)  # immediate reaction
    info["DriftPct"] = round((latest / post_first - 1) * 100, 2)        # PEAD drift since results
    info["LTP"] = round(latest, 2)
    info["DaysSince"] = int((df["date"].iloc[-1] - ed).days)

    # ---- quality score ----
    pts = 0
    parts = []
    s = info.get("SurprisePct")
    if s is not None:
        if s >= 5:
            pts += 2; parts.append(f"EPS beat {s:+.0f}%")
        elif s > 0:
            pts += 1; parts.append(f"EPS slight beat {s:+.0f}%")
        elif s > -5:
            pts -= 1; parts.append(f"EPS miss {s:+.0f}%")
        else:
            pts -= 2; parts.append(f"EPS big miss {s:+.0f}%")
    r = info.get("RevenueYoY")
    p = info.get("ProfitYoY")
    if r is not None:
        pts += 1 if r > 0 else (-1 if r < 0 else 0)
        parts.append(f"Rev {r:+.0f}% YoY")
    if p is not None:
        pts += 1 if p > 0 else (-1 if p < 0 else 0)
        parts.append(f"Profit {p:+.0f}% YoY")

    # ---- quality: EPS surprise is the anchor, growth adds context ----
    if pts >= 2 and s is not None and s >= 0:
        quality = "Good"
    elif pts <= -2:
        quality = "Bad"
    else:
        quality = "Mixed"
    info["Quality"] = quality
    info["QualityPts"] = pts
    info["QualityDetail"] = " · ".join(parts) if parts else "n/a"

    # ---- PEAD classification (drift since results x result quality) ----
    drift = info["DriftPct"]
    th = 0.5  # % drift threshold to call it "running"
    if drift > th:
        if quality == "Good":
            info["PEAD"] = "Running Up (PEAD)"
            info["PEADTone"] = "green"
        elif quality == "Bad":
            info["PEAD"] = "Up drift after bad result"
            info["PEADTone"] = "amber"
        else:
            info["PEAD"] = "Running Up"
            info["PEADTone"] = "green"
    elif drift < -th:
        if quality == "Bad":
            info["PEAD"] = "Drifting Down (PEAD)"
            info["PEADTone"] = "red"
        elif quality == "Good":
            info["PEAD"] = "Down drift after good result"
            info["PEADTone"] = "amber"
        else:
            info["PEAD"] = "Drifting Down"
            info["PEADTone"] = "red"
    else:
        info["PEAD"] = "No Clear Drift"
        info["PEADTone"] = "gray"

    return info


def scan_pead(fyers, symbols, progress=None):
    """Scan a list of symbols for post-earnings drift + result quality."""
    rows = []
    n = max(len(symbols), 1)
    for i, s in enumerate(symbols):
        if progress:
            progress.progress((i + 1) / n, text=f"Checking results {s}…")
        try:
            info = compute_pead(s, fyers)
            if info:
                rows.append(info)
        except Exception:
            continue
    return pd.DataFrame(rows)


# ====================== RENDER (Groww style) ======================
_QUALITY_TONE = {"Good": "green", "Bad": "red", "Mixed": "gray"}
_PEAD_ICON = {
    "Running Up (PEAD)": "🚀", "Running Up": "🚀",
    "Drifting Down (PEAD)": "🔻", "Drifting Down": "🔻",
    "Down drift after good result": "⚠️",
    "Up drift after bad result": "⚠️",
    "No Clear Drift": "➖",
}


def render_pead_card(row):
    symbol = row["Symbol"]
    quality = str(row.get("Quality", "Mixed"))
    q_tone = _QUALITY_TONE.get(quality, "gray")
    drift = row.get("DriftPct")
    reaction = row.get("ReactionPct")
    pead = str(row.get("PEAD", "No Clear Drift"))
    pead_tone = row.get("PEADTone", "gray")
    ltp = _fmt_money(row.get("LTP")) if pd.notna(row.get("LTP")) else ""
    days = row.get("DaysSince")
    detail = row.get("QualityDetail", "")
    ed = row.get("EarningsDate", "")

    d_txt = f"{drift:+.2f}%" if pd.notna(drift) else "—"
    r_txt = f"{reaction:+.2f}%" if pd.notna(reaction) else "—"
    drift_col = GREEN_DARK if (drift or 0) >= 0 else RED_DARK
    react_col = GREEN_DARK if (reaction or 0) >= 0 else RED_DARK

    icon = _PEAD_ICON.get(pead, "➖")

    card = f"""
    <div class="opl-card">
        <div style="display:flex; justify-content:space-between; align-items:center;">
            <div><span class="opl-sym">{symbol}</span><span class="opl-ext">↗</span>
                 <span class="opl-sector">Results {ed}</span></div>
            <div>{_chip(quality, q_tone)}<span class="opl-price" style="margin-left:10px;">{ltp}</span></div>
        </div>
        <div style="display:flex; justify-content:space-between; align-items:center; margin-top:8px;">
            <span style="font-size:12.5px; color:{MUTED};">Reaction <b style="color:{react_col};">{r_txt}</b>
                 &nbsp;·&nbsp; Drift since results <b style="color:{drift_col};">{d_txt}</b>
                 {('· ' + str(days) + 'd ago') if days is not None else ''}</span>
            {_chip(f"{icon} {pead}", pead_tone)}
        </div>
        <div style="font-size:12px; color:{MUTED}; margin-top:7px;">{detail}</div>
    </div>"""
    return _linkify(card, symbol)


def pead_table(df):
    """Table-friendly projection of the PEAD scan."""
    if df is None or df.empty:
        return df
    t = df.copy()
    for c in ["ReactionPct", "DriftPct", "RevenueYoY", "ProfitYoY", "SurprisePct"]:
        if c in t.columns:
            t[c] = t[c].apply(lambda x: f"{x:+.1f}%" if pd.notna(x) else "—")
    cols = [c for c in ["Symbol", "LTP", "EarningsDate", "SurprisePct", "RevenueYoY",
                        "ProfitYoY", "Quality", "ReactionPct", "DriftPct", "PEAD"]
            if c in t.columns]
    return t[cols]
