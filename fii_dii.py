# fii_dii.py — FII & DII net buy/sell (official NSE daily data)
# ------------------------------------------------------------------
# Foreign Institutional Investors (FII) and Domestic Institutional
# Investors (DII) net flows are published by NSE after market close.
# A net FII inflow is generally bullish for the next session; when FIIs
# sell and DIIs buy, DIIs are "absorbing" the selling (resilience).
# ------------------------------------------------------------------
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests

from storage import DATA_DIR

FII_DII_FILE = DATA_DIR / "fii_dii.csv"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/",
}

URL = "https://www.nseindia.com/api/fiidiiTradeReact"


def _to_float(v):
    try:
        return float(str(v).replace(",", ""))
    except Exception:
        return 0.0


def fetch_fii_dii(timeout: int = 12):
    """
    Fetch the latest available FII & DII net buy/sell (₹ Cr) from NSE.
    Returns a dict, or None on failure.
    """
    session = requests.Session()
    session.headers.update(HEADERS)
    try:
        session.get("https://www.nseindia.com/", timeout=timeout)
        time.sleep(0.4)
        resp = session.get(URL, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return None

    if not isinstance(data, list) or not data:
        return None

    fii = dii = None
    date_str = None
    for item in data:
        cat = str(item.get("category", "")).upper()
        if date_str is None:
            date_str = str(item.get("date", ""))
        if "FII" in cat and fii is None:
            fii = item
        elif "DII" in cat and dii is None:
            dii = item

    if fii is None and dii is None:
        return None

    fii_net = _to_float(fii.get("netValue")) if fii else 0.0
    dii_net = _to_float(dii.get("netValue")) if dii else 0.0
    net_total = round(fii_net + dii_net, 2)

    # Next-day lean
    if fii_net > 0 and dii_net > 0:
        lean = "FII & DII both buying — strongly bullish setup"
        tone = "green"
    elif fii_net > 0:
        lean = "FII buying, DII selling — bullish bias"
        tone = "green"
    elif fii_net < 0 and dii_net > 0:
        lean = "FII selling, DII absorbing — mixed / resilient"
        tone = "gray"
    elif fii_net < 0 and dii_net < 0:
        lean = "FII & DII both selling — bearish pressure"
        tone = "red"
    else:
        lean = "Flat institutional flow"
        tone = "gray"

    return {
        "date": date_str,
        "fii_buy": _to_float(fii.get("buyValue")) if fii else 0.0,
        "fii_sell": _to_float(fii.get("sellValue")) if fii else 0.0,
        "fii_net": fii_net,
        "dii_buy": _to_float(dii.get("buyValue")) if dii else 0.0,
        "dii_sell": _to_float(dii.get("sellValue")) if dii else 0.0,
        "dii_net": dii_net,
        "net_total": net_total,
        "lean": lean,
        "tone": tone,
    }


def log_fii_dii(fd: dict):
    """Append today's FII/DII snapshot to data/fii_dii.csv (dedupe by date)."""
    if not fd or not fd.get("date"):
        return
    DATA_DIR.mkdir(exist_ok=True)
    cols = ["Date", "FII_Net", "DII_Net", "Net_Total", "Lean"]
    new_row = pd.DataFrame([{
        "Date": fd["date"],
        "FII_Net": fd["fii_net"],
        "DII_Net": fd["dii_net"],
        "Net_Total": fd["net_total"],
        "Lean": fd["lean"],
    }])
    try:
        old = pd.read_csv(FII_DII_FILE)
    except Exception:
        old = pd.DataFrame(columns=cols)
    if not old.empty and "Date" in old.columns:
        old = old[old["Date"].astype(str) != str(fd["date"])]
    if old.empty:
        merged = new_row
    else:
        merged = pd.concat([old, new_row], ignore_index=True)
    merged[[c for c in cols if c in merged.columns]].to_csv(FII_DII_FILE, index=False)


def load_fii_dii_history() -> pd.DataFrame:
    """Load the FII/DII history log (most recent first)."""
    try:
        df = pd.read_csv(FII_DII_FILE)
        return df.sort_values("Date", ascending=False).reset_index(drop=True)
    except Exception:
        return pd.DataFrame(columns=["Date", "FII_Net", "DII_Net", "Net_Total", "Lean"])
