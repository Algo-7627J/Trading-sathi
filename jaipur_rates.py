# jaipur_rates.py — daily Indian newspaper bullion rates (INR) for RAO SAHAB
# ------------------------------------------------------------------
# Today's Gold (24K / 22K per 10g) & Silver (per kg) — the same figures
# Indian newspapers print — with vs-yesterday up/down change.
#
# Primary source : GoodReturns city pages (Delhi first — the rate most
#                  North-Indian dailies publish — then Chandigarh, Jaipur)
#   https://www.goodreturns.in/gold-rates/delhi.html
#   https://www.goodreturns.in/silver-rates/delhi.html
# Fallback      : derived from COMEX futures × USD/INR (yfinance),
#                 clearly labelled "derived / indicative".
#
# Change is ALWAYS computed as today − previous newspaper day (history),
# not the (often missing / zero) inline delta on the "today" table.
# Last-seen rates are also persisted so a later fetch can still show Δ.
#
# Rates change once a day → results cached for 3 hours.
# ------------------------------------------------------------------
import json
import re
import time
from datetime import datetime
from pathlib import Path

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

# Newspaper-style city order: Delhi is what most dailies print.
_CITIES = (
    ("delhi", "Delhi"),
    ("chandigarh", "Chandigarh"),
    ("jaipur", "Jaipur"),
)

_CACHE_TTL = 3 * 3600          # rates are daily; re-check every 3h
_CACHE = {}                    # "rates" -> (ts, dict)

# import-duty + premium markup for the derived fallback (indicative)
_GOLD_FACTOR = 1.12
_SILVER_FACTOR = 1.18

_DATA_DIR = Path(__file__).resolve().parent / "data"
_LAST_PATH = _DATA_DIR / "bullion_last.json"


# ---------------- parsing helpers ----------------
def _nums(cell):
    """'₹15,942(+430)' -> [15942, 430]  ·  '₹2,55,000(+10,000)' -> [255000, 10000]"""
    return [int(x.replace(",", "")) for x in re.findall(r"[+\-]?[\d,]+", str(cell))]


def _parse_gold_page(html):
    """Extract today's 24K/22K per-10g + 7-day history (per 10g)."""
    soup = BeautifulSoup(html, "html.parser")
    today = {}          # {"24K": val10g, "22K": val10g}
    history = []        # [{"date", "24K": val10g, "22K": val10g}, ...]

    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if not rows:
            continue
        header = [c.get_text(strip=True) for c in rows[0].find_all(["td", "th"])]

        # today's per-10g table:  Gram | 24K | 22K | 18K
        if "24K" in header and "Gram" in header:
            for r in rows[1:]:
                cells = [c.get_text(strip=True) for c in r.find_all(["td", "th"])]
                if len(cells) >= 3 and cells[0] == "10":
                    n24, n22 = _nums(cells[1]), _nums(cells[2])
                    if n24:
                        today["24K"] = n24[0]
                    if n22:
                        today["22K"] = n22[0]
                    break
        # daily history table:  Date | 24K | 22K  (per gram in newspapers)
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
            history = history[:8]

    if not today and history:
        today = {"24K": history[0]["24K"], "22K": history[0]["22K"]}
    if not today:
        return None
    return {"today": today, "history": history}


def _parse_silver_page(html):
    """Extract today's silver per-kg and 7-day history."""
    soup = BeautifulSoup(html, "html.parser")
    today = None    # per_kg
    history = []    # [{"date", "kg": val}, ...]

    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if not rows:
            continue
        header = [c.get_text(strip=True) for c in rows[0].find_all(["td", "th"])]

        # daily history table:  Date | 10 gram | 100 gram | 1 Kg
        if "Date" in header and "1 Kg" in header:
            for i, r in enumerate(rows[1:]):
                cells = [c.get_text(strip=True) for c in r.find_all(["td", "th"])]
                if len(cells) >= 4:
                    n = _nums(cells[3])
                    if n:
                        if i == 0 and today is None:
                            today = n[0]
                        history.append({"date": cells[0], "kg": n[0]})
            history = history[:8]
        # today/yesterday table:  Gram | Today | Yesterday | Change
        elif "Today" in header and "Gram" in header and today is None:
            for r in rows[1:]:
                cells = [c.get_text(strip=True) for c in r.find_all(["td", "th"])]
                if len(cells) >= 2 and cells[0] in ("1000", "1 Kg", "1Kg", "1 kg"):
                    n = _nums(cells[1])
                    if n:
                        today = n[0]
                    break

    if today is None and history:
        today = history[0]["kg"]
    if today is None:
        return None
    return {"today": today, "history": history}


def _fetch(url):
    r = requests.get(url, timeout=12, headers={"User-Agent": UA})
    r.raise_for_status()
    return r.text


def _prev_from_history(history, today_val, key):
    """Previous newspaper-day value (skip rows that equal 'today' on the same date)."""
    if not history:
        return None
    for h in history[1:]:
        v = h.get(key)
        if v is None:
            continue
        return int(v)
    return None


def _chg(today, prev):
    if today is None or prev is None:
        return None
    return int(today) - int(prev)


def _chg_pct(today, prev):
    if today is None or prev in (None, 0):
        return None
    return round((int(today) - int(prev)) / int(prev) * 100.0, 2)


# ---------------- persisted last-seen rates ----------------
def _load_last():
    try:
        if _LAST_PATH.exists():
            return json.loads(_LAST_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    return None


def _save_last(res):
    try:
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        payload = {
            "date": res.get("date"),
            "gold_24k_10g": res.get("gold_24k_10g"),
            "gold_22k_10g": res.get("gold_22k_10g"),
            "silver_kg": res.get("silver_kg"),
            "saved_at": datetime.now().isoformat(timespec="seconds"),
        }
        _LAST_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except Exception:
        pass


def _fill_change_from_last(res):
    """If history didn't give a previous day, compare against last persisted snapshot."""
    last = _load_last()
    if not last:
        return res
    last_date = str(last.get("date") or "")
    if last_date and last_date == str(res.get("date") or ""):
        # same newspaper day — keep existing change
        return res
    if res.get("gold_24k_chg") is None and last.get("gold_24k_10g"):
        res["gold_24k_prev"] = last["gold_24k_10g"]
        res["gold_24k_chg"] = _chg(res.get("gold_24k_10g"), last["gold_24k_10g"])
        res["gold_24k_chg_pct"] = _chg_pct(res.get("gold_24k_10g"), last["gold_24k_10g"])
    if res.get("gold_22k_chg") is None and last.get("gold_22k_10g"):
        res["gold_22k_prev"] = last["gold_22k_10g"]
        res["gold_22k_chg"] = _chg(res.get("gold_22k_10g"), last["gold_22k_10g"])
        res["gold_22k_chg_pct"] = _chg_pct(res.get("gold_22k_10g"), last["gold_22k_10g"])
    if res.get("silver_chg") is None and last.get("silver_kg"):
        res["silver_prev"] = last["silver_kg"]
        res["silver_chg"] = _chg(res.get("silver_kg"), last["silver_kg"])
        res["silver_chg_pct"] = _chg_pct(res.get("silver_kg"), last["silver_kg"])
    return res


# ---------------- derived fallback (COMEX × USDINR) ----------------
def _yf_closes(ticker, n=3):
    if yf is None:
        return []
    try:
        df = yf.download(ticker, period="10d", interval="1d", progress=False)
        if df is None or df.empty:
            return []
        if pd is not None and isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
        closes = [float(x) for x in df["Close"].dropna().tolist()]
        return closes[-n:]
    except Exception:
        return []


def _derived_rates():
    """COMEX USD price × USD/INR → indicative INR rates (clearly labelled)."""
    gold = _yf_closes("GC=F", 3)
    silver = _yf_closes("SI=F", 3)
    usd = _yf_closes("INR=X", 3)
    if len(gold) < 1 or len(usd) < 1:
        return None
    gold_oz, usd_inr = gold[-1], usd[-1]
    silver_oz = silver[-1] if silver else None
    oz_to_10g = 10 / 31.1035
    gold_24k = gold_oz * oz_to_10g * usd_inr * _GOLD_FACTOR
    gold_22k = gold_24k * (22 / 24)
    silver_kg = (silver_oz / 31.1035 * 1000 * usd_inr * _SILVER_FACTOR) if silver_oz else None

    def pair(today, prev_raw, conv):
        t = int(round(today)) if today is not None else None
        p = int(round(conv(prev_raw))) if prev_raw else None
        return t, p, _chg(t, p), _chg_pct(t, p)

    g24_prev = gold[-2] * oz_to_10g * (usd[-2] if len(usd) > 1 else usd_inr) * _GOLD_FACTOR if len(gold) > 1 else None
    g24, g24p, g24c, g24pct = pair(gold_24k, g24_prev, lambda x: x)
    g22, g22p, g22c, g22pct = pair(gold_22k, (g24_prev * 22 / 24) if g24_prev else None, lambda x: x)
    s_prev = None
    if silver_kg is not None and len(silver) > 1:
        s_prev = silver[-2] / 31.1035 * 1000 * (usd[-2] if len(usd) > 1 else usd_inr) * _SILVER_FACTOR
    s, sp, sc, spct = pair(silver_kg, s_prev, lambda x: x)

    return {
        "date": datetime.now().strftime("%b %d, %Y"),
        "source": "derived",
        "city": "India (indicative)",
        "usd_inr": round(usd_inr, 2),
        "gold_24k_10g": g24, "gold_24k_prev": g24p, "gold_24k_chg": g24c, "gold_24k_chg_pct": g24pct,
        "gold_22k_10g": g22, "gold_22k_prev": g22p, "gold_22k_chg": g22c, "gold_22k_chg_pct": g22pct,
        "silver_kg": s, "silver_prev": sp, "silver_chg": sc, "silver_chg_pct": spct,
        "history": [],
        "url": "https://www.goodreturns.in/gold-rates/delhi.html",
    }


# ---------------- main fetcher ----------------
def get_jaipur_rates(force=False):
    """Today's newspaper-style gold/silver INR rates.

    Returns a dict ready for the UI, or None when nothing is available:
    {
      "date": "Sep 06, 2026", "source": "goodreturns" | "derived",
      "city": "Delhi", "usd_inr": float | None,
      "gold_24k_10g": int, "gold_24k_prev": int | None,
      "gold_24k_chg": int | None, "gold_24k_chg_pct": float | None,
      ... same for 22K and silver_kg,
      "history": [{"date", "gold_24k", "gold_22k", "silver"} ...],
      "url": str,
    }
    """
    now = time.time()
    if not force:
        hit = _CACHE.get("rates")
        if hit and (now - hit[0]) < _CACHE_TTL:
            return hit[1]

    gold_parsed = silver_parsed = None
    city_used = url_used = None

    for slug, city in _CITIES:
        gold_url = f"https://www.goodreturns.in/gold-rates/{slug}.html"
        silver_url = f"https://www.goodreturns.in/silver-rates/{slug}.html"
        try:
            ghtml = _fetch(gold_url)
            gold_parsed = _parse_gold_page(ghtml)
        except Exception:
            gold_parsed = None
        try:
            shtml = _fetch(silver_url)
            silver_parsed = _parse_silver_page(shtml)
        except Exception:
            silver_parsed = None
        if gold_parsed and silver_parsed:
            city_used, url_used = city, gold_url
            break

    if gold_parsed and silver_parsed:
        g = gold_parsed["today"]
        s = silver_parsed["today"]
        g_hist = gold_parsed.get("history") or []
        s_hist = silver_parsed.get("history") or []
        date = (g_hist[0].get("date") if g_hist else None) or \
               (s_hist[0].get("date") if s_hist else None) or \
               datetime.now().strftime("%b %d, %Y")

        g24 = int(g["24K"])
        g22 = int(g["22K"])
        sil = int(s)

        g24_prev = _prev_from_history(g_hist, g24, "24K")
        g22_prev = _prev_from_history(g_hist, g22, "22K")
        sil_prev = _prev_from_history(s_hist, sil, "kg")

        silver_by_date = {h["date"]: h["kg"] for h in s_hist}
        history = [
            {
                "date": h["date"],
                "gold_24k": h["24K"],
                "gold_22k": h["22K"],
                "silver": silver_by_date.get(h["date"]),
            }
            for h in g_hist
        ]
        res = {
            "date": date,
            "source": "goodreturns",
            "city": city_used or "Delhi",
            "usd_inr": None,
            "gold_24k_10g": g24, "gold_24k_prev": g24_prev,
            "gold_24k_chg": _chg(g24, g24_prev), "gold_24k_chg_pct": _chg_pct(g24, g24_prev),
            "gold_22k_10g": g22, "gold_22k_prev": g22_prev,
            "gold_22k_chg": _chg(g22, g22_prev), "gold_22k_chg_pct": _chg_pct(g22, g22_prev),
            "silver_kg": sil, "silver_prev": sil_prev,
            "silver_chg": _chg(sil, sil_prev), "silver_chg_pct": _chg_pct(sil, sil_prev),
            "history": history,
            "url": url_used or "https://www.goodreturns.in/gold-rates/delhi.html",
        }
        res = _fill_change_from_last(res)
        _save_last(res)
        _CACHE["rates"] = (now, res)
        return res

    # fallback: derive from COMEX × USD/INR
    res = _derived_rates()
    if res:
        res = _fill_change_from_last(res)
        _save_last(res)
        _CACHE["rates"] = (now, res)
        return res

    return None


def clear_cache():
    _CACHE.pop("rates", None)
