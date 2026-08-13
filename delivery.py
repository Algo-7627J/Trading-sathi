# delivery.py — NSE Security-wise Delivery Position (bulk MTO archive)
# ------------------------------------------------------------------
# Delivery % = shares actually delivered to buyers vs total traded.
# High delivery % + a bullish scan signal = conviction buying (investors
# taking delivery, not just intraday speculation). Low delivery = mostly
# intraday/square-off activity.
#
# Data source: NSE's official daily MTO archive (published after market
# close). One bulk file covers every listed security — far cheaper than
# per-symbol API calls.
# ------------------------------------------------------------------
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import requests

from storage import DATA_DIR

DELIVERY_FILE = DATA_DIR / "delivery.csv"

IST = timezone(timedelta(hours=5, minutes=30))

ARCHIVE_URL = "https://archives.nseindia.com/archives/equities/mto/MTO_{d}.DAT"

COLUMNS = ["Date", "Symbol", "QtyTraded", "DeliverableQty", "DeliveryPct"]


def _fetch_mto(d: str) -> str | None:
    """Download the MTO delivery-position file for date DDMMYYYY. None on fail."""
    try:
        r = requests.get(
            ARCHIVE_URL.format(d=d),
            timeout=20,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        if r.status_code == 200 and "Security Wise Delivery" in r.text[:80]:
            return r.text
    except Exception:
        pass
    return None


def _parse_mto(text: str, date_iso: str) -> pd.DataFrame:
    """Parse the MTO delivery-position text into a per-symbol DataFrame."""
    rows = []
    for line in text.splitlines():
        parts = [p.strip() for p in line.split(",")]
        # delivery-position rows: 20,SrNo,Symbol,SERIES,QtyTraded,DeliverableQty,%Del
        if len(parts) < 7 or parts[0] != "20":
            continue
        if parts[3] != "EQ":            # equities only (skip debt/ETF/bonds)
            continue
        symbol = parts[2].strip()
        if not symbol:
            continue
        try:
            qty = int(float(parts[4]))
            delv = int(float(parts[5]))
            pct = float(parts[6])
        except (ValueError, IndexError):
            continue
        rows.append({
            "Date": date_iso,
            "Symbol": symbol,
            "QtyTraded": qty,
            "DeliverableQty": delv,
            "DeliveryPct": round(pct, 2),
        })
    return pd.DataFrame(rows, columns=COLUMNS)


def load_cached_delivery() -> pd.DataFrame:
    try:
        df = pd.read_csv(DELIVERY_FILE)
        return df
    except Exception:
        return pd.DataFrame(columns=COLUMNS)


def _save_delivery(df: pd.DataFrame):
    DATA_DIR.mkdir(exist_ok=True)
    try:
        df[COLUMNS].to_csv(DELIVERY_FILE, index=False)
    except Exception:
        pass


def fetch_delivery_frame(force_refresh: bool = False, max_back: int = 10) -> pd.DataFrame:
    """
    Get the latest available security-wise delivery data as a DataFrame
    [Date, Symbol, QtyTraded, DeliverableQty, DeliveryPct].
    Walks back from today until a published MTO file is found. Cached.
    """
    cached = load_cached_delivery()

    # Reuse cache only if it's fresh enough (latest available date is
    # naturally "yesterday" during market hours).
    if not force_refresh and not cached.empty:
        return cached

    today = datetime.now(IST).date()
    for back in range(max_back):
        d = today - timedelta(days=back)
        ds = d.strftime("%d%m%Y")
        text = _fetch_mto(ds)
        if not text:
            continue
        df = _parse_mto(text, d.strftime("%Y-%m-%d"))
        if not df.empty:
            _save_delivery(df)
            return df

    # No fresh file — fall back to whatever we had cached.
    return cached


def delivery_map(df: pd.DataFrame) -> dict:
    """{SYMBOL: {'pct':.., 'qty':.., 'delv':.., 'date':..}} from a delivery frame."""
    out = {}
    for _, r in df.iterrows():
        out[str(r["Symbol"]).upper()] = {
            "pct": float(r["DeliveryPct"]),
            "qty": int(r["QtyTraded"]),
            "delv": int(r["DeliverableQty"]),
            "date": str(r["Date"]),
        }
    return out


def delivery_date(df: pd.DataFrame) -> str:
    if df is None or df.empty:
        return ""
    return str(df["Date"].iloc[0])


# ------------------------------------------------------------------
# Combine scan results with delivery data
# ------------------------------------------------------------------
def _direction(row) -> str:
    """Bullish / Bearish / Neutral from an intraday or next-day scan row."""
    def _clean(v):
        if pd.isna(v):
            return ""
        return str(v).strip()

    bias = _clean(row.get("Bias", ""))
    if bias:
        b = bias.lower()
        if "bull" in b:
            return "Bullish"
        if "bear" in b:
            return "Bearish"
        return "Neutral"
    signal = _clean(row.get("Signal", ""))
    if signal:
        s = signal.lower()
        if "buy" in s:
            return "Bullish"
        if "sell" in s:
            return "Bearish"
        return "Neutral"
    # fall back to score sign
    try:
        score = float(row.get("Score", 0))
        if pd.notna(score):
            if score > 2:
                return "Bullish"
            if score < -2:
                return "Bearish"
    except (TypeError, ValueError):
        pass
    return "Neutral"


def combine_with_delivery(scan_df: pd.DataFrame, delivery_df: pd.DataFrame) -> pd.DataFrame:
    """
    Merge scan results with delivery data and add a Direction column.
    Returns a DataFrame with, at minimum:
      Symbol, Direction, DeliveryPct, QtyTraded, DeliverableQty
    plus original signal columns where present (Signal/Bias/Outlook/LTP/Score).
    """
    if scan_df is None or scan_df.empty or delivery_df is None or delivery_df.empty:
        return pd.DataFrame()

    dmap = delivery_map(delivery_df)

    rows = []
    for _, r in scan_df.iterrows():
        symbol = str(r.get("Symbol", "")).upper().strip()
        if not symbol:
            continue
        info = dmap.get(symbol)
        if not info:
            continue                      # no delivery data for this symbol
        row = {
            "Symbol": symbol,
            "Direction": _direction(r),
            "DeliveryPct": info["pct"],
            "QtyTraded": info["qty"],
            "DeliverableQty": info["delv"],
        }
        for col in ("Signal", "Bias", "Outlook", "LTP", "Score", "Confidence",
                    "Last30Min", "Expected_Move"):
            if col in r.index:
                row[col] = r[col]
        rows.append(row)

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    order = ["Symbol", "Direction", "DeliveryPct", "QtyTraded", "DeliverableQty",
             "Signal", "Bias", "Outlook", "LTP", "Score", "Confidence",
             "Last30Min", "Expected_Move"]
    df = df[[c for c in order if c in df.columns]]
    return df.sort_values("DeliveryPct", ascending=False).reset_index(drop=True)


# ------------------------------------------------------------------
# Live session verification
# ------------------------------------------------------------------
def live_session_move(fyers, merged_df: pd.DataFrame, progress=None) -> pd.DataFrame:
    """
    For each delivery-combo stock, fetch today's live move (vs previous
    close) and check whether it's behaving as its combo direction predicts.

    Bullish combo -> "on track" if rising today; Bearish combo -> "on track"
    if falling today. Returns DataFrame with:
      Symbol, Direction, DeliveryPct, PrevClose, LTP, MovePct,
      Status, Tone, Correct
    """
    from analysis import fetch_candles

    if merged_df is None or merged_df.empty or fyers is None:
        return pd.DataFrame()

    rows = []
    total = len(merged_df)
    for i, (_, r) in enumerate(merged_df.iterrows()):
        symbol = str(r["Symbol"])
        direction = str(r.get("Direction", "Neutral"))
        delivery_pct = r.get("DeliveryPct")
        if progress and (i + 1) % 10 == 0:
            progress.progress((i + 1) / total, text=f"Checking {symbol}…")

        base = {
            "Symbol": symbol,
            "Direction": direction,
            "DeliveryPct": delivery_pct,
            "PrevClose": None,
            "LTP": None,
            "MovePct": None,
            "Status": "No data",
            "Tone": "gray",
            "Correct": None,
        }
        try:
            df = fetch_candles(fyers, symbol, timeframe_mode="1d")
            if df is not None and len(df) >= 2:
                prev_close = float(df["c"].iloc[-2])
                ltp = float(df["c"].iloc[-1])
                move_pct = (ltp - prev_close) / prev_close * 100.0 if prev_close else None
                base["PrevClose"] = round(prev_close, 2)
                base["LTP"] = round(ltp, 2)
                base["MovePct"] = round(move_pct, 3) if move_pct is not None else None

                if move_pct is None:
                    base["Status"] = "No move"
                    base["Tone"] = "gray"
                elif direction == "Bullish":
                    if move_pct > 0:
                        base["Status"], base["Tone"], base["Correct"] = "✓ Rising", "green", True
                    elif move_pct < 0:
                        base["Status"], base["Tone"], base["Correct"] = "✗ Falling", "red", False
                    else:
                        base["Status"], base["Tone"] = "• Flat", "gray"
                elif direction == "Bearish":
                    if move_pct < 0:
                        base["Status"], base["Tone"], base["Correct"] = "✓ Falling", "green", True
                    elif move_pct > 0:
                        base["Status"], base["Tone"], base["Correct"] = "✗ Rising", "red", False
                    else:
                        base["Status"], base["Tone"] = "• Flat", "gray"
                else:  # neutral
                    base["Status"] = "• Flat" if abs(move_pct) < 0.3 else ("Rising" if move_pct > 0 else "Falling")
                    base["Tone"] = "gray"
        except Exception:
            pass

        rows.append(base)

    return pd.DataFrame(rows)


def live_accuracy(df: pd.DataFrame) -> dict:
    """Summarise on-track vs against for a live-session check frame."""
    if df is None or df.empty or "Correct" not in df.columns:
        return {"total": 0, "correct": 0, "wrong": 0, "accuracy": None}
    correct = int((df["Correct"] == True).sum())
    wrong = int((df["Correct"] == False).sum())
    decided = correct + wrong
    accuracy = (correct / decided * 100.0) if decided else None
    return {"total": len(df), "correct": correct, "wrong": wrong, "accuracy": accuracy}
