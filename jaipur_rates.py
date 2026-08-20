# jaipur_rates.py — daily Jaipur bullion rates (INR) for RAO SAHAB
# ------------------------------------------------------------------
# Today's Gold (24K / 22K per 10g) & Silver (per kg) rates for Jaipur
# — a major Indian bullion market — in rupees, shown alongside the
# COMEX USD panels in the Gold & Silver tab.
#
# Primary source : GoodReturns city pages (scraped, best-effort)
#   https://www.goodreturns.in/gold-rates/jaipur.html
#   https://www.goodreturns.in/silver-rates/jaipur.html
# Fallback      : derived from COMEX futures × USD/INR (yfinance),
#                 clearly labelled "derived / indicative".
#
# Rates change once a day → results cached for 3 hours.
# ------------------------------------------------------------------
import re
import time
from datetime import datetime

import requests
from bs4 import BeautifulSoup

try:
    import yfinance as yf
except Exception:
    yf = None

try:
    import pandas as pd
except Exception:
    pd = None

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

GOLD_URL = "https://www.goodreturns.in/gold-rates/jaipur.html"
SILVER_URL = "https://www.goodreturns.in/silver-rates/jaipur.html"

_CACHE_TTL = 3 * 3600          # rates are daily; re-check every 3h
_CACHE = {}                    # "rates" -> (ts, dict)

# import-duty + premium markup for the derived fallback (indicative)
_GOLD_FACTOR = 1.12
_SILVER_FACTOR = 1.18


# ---------------- parsing helpers ----------------
def _nums(cell):
    """'₹15,942(+430)' -> [15942, 430]  ·  '₹2,55,000(+10,000)' -> [255000, 10000]"""
    return [int(x.replace(",", "")) for x in re.findall(r"[+\-]?[\d,]+", str(cell))]


def _parse_gold_page(html):
    """Extract today's 24K/22K per-10g + change and 7-day history."""
    soup = BeautifulSoup(html, "html.parser")
    today = {}          # {"24K": (val, chg), "22K": (val, chg)}  per 10g
    history = []        # [{"date", "24K": val10g, "22K": val10g}, ...]

    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if not rows:
            continue
        header = [c.get_text(strip=True) for c in rows[0].find_all(["td", "th"])]
        joined = " ".join(header)

        # today's per-10g table:  Gram | 24K | 22K | 18K
        if "24K" in header and "Gram" in header:
            for r in rows[1:]:
                cells = [c.get_text(strip=True) for c in r.find_all(["td", "th"])]
                if len(cells) >= 3 and cells[0] == "10":
                    n24, n22 = _nums(cells[1]), _nums(cells[2])
                    if n24:
                        today["24K"] = (n24[0], n24[1] if len(n24) > 1 else 0)
                    if n22:
                        today["22K"] = (n22[0], n22[1] if len(n22) > 1 else 0)
                    break
        # daily history table:  Date | 24K | 22K  (per gram)
        elif "Date" in header and "24K" in header:
            for r in rows[1:]:
                cells = [c.get_text(strip=True) for c in r.find_all(["td", "th"])]
                if len(cells) >= 3:
                    n24, n22 = _nums(cells[1]), _nums(cells[2])
                    if n24 and n22:
                        history.append({
                            "date": cells[0],
                            "24K": n24[0] * 10,          # per-gram -> per-10g
                            "22K": n22[0] * 10,
                        })
            history = history[:7]

    if not today:
        return None
    return {"today": today, "history": history}


def _parse_silver_page(html):
    """Extract today's silver per-kg + change and 7-day history."""
    soup = BeautifulSoup(html, "html.parser")
    today = None    # (per_kg, chg)
    history = []    # [{"date", "kg": val}, ...]

    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if not rows:
            continue
        header = [c.get_text(strip=True) for c in rows[0].find_all(["td", "th"])]
        joined = " ".join(header)

        # daily history table:  Date | 10 gram | 100 gram | 1 Kg
        if "Date" in header and "1 Kg" in header:
            for i, r in enumerate(rows[1:]):
                cells = [c.get_text(strip=True) for c in r.find_all(["td", "th"])]
                if len(cells) >= 4:
                    n = _nums(cells[3])
                    if n:
                        if i == 0 and today is None:
                            today = (n[0], n[1] if len(n) > 1 else 0)
                        history.append({"date": cells[0], "kg": n[0]})
            history = history[:7]
        # today/yesterday table:  Gram | Today | Yesterday | Change
        elif "Today" in header and "Gram" in header and today is None:
            for r in rows[1:]:
                cells = [c.get_text(strip=True) for c in r.find_all(["td", "th"])]
                if len(cells) >= 3 and cells[0] == "1000":
                    n = _nums(cells[1])
                    if n:
                        chg = _nums(cells[3]) if len(cells) > 3 else []
                        today = (n[0], chg[0] if chg else 0)
                    break

    if today is None:
        return None
    return {"today": today, "history": history}


# ---------------- derived fallback (COMEX × USDINR) ----------------
def _yf_last(ticker):
    if yf is None:
        return None
    try:
        df = yf.download(ticker, period="5d", interval="1d", progress=False)
        if df is None or df.empty:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
        return float(df["Close"].iloc[-1])
    except Exception:
        return None


def _derived_rates():
    """COMEX USD price × USD/INR → indicative INR rates (clearly labelled)."""
    gold_oz = _yf_last("GC=F")
    silver_oz = _yf_last("SI=F")
    usd_inr = _yf_last("INR=X")
    if not gold_oz or not usd_inr:
        return None
    oz_to_10g = 10 / 31.1035
    gold_24k = gold_oz * oz_to_10g * usd_inr * _GOLD_FACTOR
    gold_22k = gold_24k * (22 / 24)
    silver_kg = (silver_oz or 0) / 31.1035 * 1000 * usd_inr * _SILVER_FACTOR

    today = {
        "24K": (int(round(gold_24k)), None),
        "22K": (int(round(gold_22k)), None),
        "silver_kg": (int(round(silver_kg)) if silver_oz else None, None),
    }
    return {
        "gold": {"today": {k: v for k, v in today.items() if k != "silver_kg"},
                 "history": []},
        "silver": {"today": today["silver_kg"], "history": []},
        "derived": True,
        "usd_inr": round(usd_inr, 2),
    }


# ---------------- main fetcher ----------------
def get_jaipur_rates(force=False):
    """Today's Jaipur gold/silver INR rates.

    Returns a dict ready for the UI, or None when nothing is available:
    {
      "date": "Aug 20, 2026", "source": "goodreturns" | "derived",
      "usd_inr": float | None,
      "gold_24k_10g": int, "gold_24k_chg": int | None,
      "gold_22k_10g": int, "gold_22k_chg": int | None,
      "silver_kg": int, "silver_chg": int | None,
      "history": [{"date", "gold_24k", "gold_22k", "silver"} ... x7],
      "url": str,
    }
    """
    now = time.time()
    if not force:
        hit = _CACHE.get("rates")
        if hit and (now - hit[0]) < _CACHE_TTL:
            return hit[1]

    gold_parsed = silver_parsed = None
    for url, parse in ((GOLD_URL, _parse_gold_page), (SILVER_URL, _parse_silver_page)):
        try:
            r = requests.get(url, timeout=12, headers={"User-Agent": UA})
            if r.status_code == 200:
                parsed = parse(r.text)
                if url.endswith("gold-rates/jaipur.html"):
                    gold_parsed = parsed
                else:
                    silver_parsed = parsed
        except Exception:
            continue

    if gold_parsed and silver_parsed:
        g = gold_parsed["today"]
        s = silver_parsed["today"]
        date = (gold_parsed.get("history") or [{}])[0].get("date") or \
               (silver_parsed.get("history") or [{}])[0].get("date") or "Today"

        # merged 7-day history (gold + silver by date)
        silver_by_date = {h["date"]: h["kg"] for h in silver_parsed["history"]}
        history = [
            {
                "date": h["date"],
                "gold_24k": h["24K"],
                "gold_22k": h["22K"],
                "silver": silver_by_date.get(h["date"]),
            }
            for h in gold_parsed["history"]
        ]
        res = {
            "date": date,
            "source": "goodreturns",
            "usd_inr": None,
            "gold_24k_10g": g["24K"][0], "gold_24k_chg": g["24K"][1],
            "gold_22k_10g": g["22K"][0], "gold_22k_chg": g["22K"][1],
            "silver_kg": s[0], "silver_chg": s[1],
            "history": history,
            "url": GOLD_URL,
        }
        _CACHE["rates"] = (now, res)
        return res

    # fallback: derive from COMEX × USD/INR
    res = _derived_rates()
    if res:
        g = res["gold"]["today"]
        s = res["silver"]["today"]
        out = {
            "date": datetime.now().strftime("%b %d, %Y"),
            "source": "derived",
            "usd_inr": res.get("usd_inr"),
            "gold_24k_10g": g["24K"][0], "gold_24k_chg": None,
            "gold_22k_10g": g["22K"][0], "gold_22k_chg": None,
            "silver_kg": s[0], "silver_chg": None,
            "history": [],
            "url": "https://www.goodreturns.in/gold-rates/jaipur.html",
        }
        _CACHE["rates"] = (now, out)
        return out

    return None


def clear_cache():
    _CACHE.pop("rates", None)
