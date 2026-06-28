import io
import csv
import re
from datetime import datetime, timedelta

import requests
import streamlit as st

from config import (
    TELEGRAM_TOKEN,
    TELEGRAM_CHAT_ID,
    NSE_FO_LIST_URL,
    FYERS_NSE_FO_MASTER,
    FYERS_MCX_MASTER,
    NEWS_API_URL,
    NEWS_API_KEY,
    COMMODITY_BASES,
    INDEX_BASES,
    HEADERS,
    NEWS_LOOKBACK_DAYS,
)


def send_telegram_msg(message: str):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return False
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.get(url, params={"chat_id": TELEGRAM_CHAT_ID, "text": message}, timeout=8)
        return True
    except Exception:
        return False


@st.cache_data(ttl=3600)
def fetch_fo_stock_list():
    try:
        s = requests.Session()
        s.headers.update(HEADERS)
        try:
            s.get("https://www.nseindia.com", timeout=15)
        except Exception:
            pass
        r = s.get(NSE_FO_LIST_URL, timeout=20)
        r.raise_for_status()
        names = r.json()
        if isinstance(names, list) and names:
            return [f"NSE:{n.strip()}-EQ" for n in names if n and isinstance(n, str)]
    except Exception:
        pass
    return []


@st.cache_data(ttl=3600)
def fetch_nearest_futures(master_url, bases):
    out = []
    try:
        r = requests.get(master_url, timeout=25)
        r.raise_for_status()
        rows = list(csv.reader(io.StringIO(r.text)))
        now = datetime.now()
        cand = {b: [] for b in bases}
        for row in rows:
            if len(row) < 14:
                continue
            base = row[13]
            sym = row[9]
            ep = row[8]
            if base in cand and sym.endswith("FUT"):
                try:
                    exp = datetime.fromtimestamp(int(ep))
                except Exception:
                    continue
                cand[base].append((exp, sym))
        for b in bases:
            fut = sorted([c for c in cand[b] if c[0] >= now])
            if fut:
                out.append(fut[0][1])
    except Exception:
        pass
    return out


@st.cache_data(ttl=3600)
def build_universe():
    stocks = fetch_fo_stock_list()
    indices = fetch_nearest_futures(FYERS_NSE_FO_MASTER, INDEX_BASES)
    commodities = fetch_nearest_futures(FYERS_MCX_MASTER, COMMODITY_BASES)
    return {
        "stocks": stocks,
        "indices": indices,
        "commodities": commodities,
        "all": stocks + indices + commodities,
    }


def base_name_from_symbol(sym: str):
    s = sym.split(":")[-1]
    s = s.replace("-EQ", "")
    s = re.sub(r"\d{2}[A-Z]{3}.*FUT$", "", s)
    s = re.sub(r"\d.*$", "", s)
    return s.strip("-").upper()


def fetch_history(fyers, sym, resolution="15", days=20):
    try:
        now = datetime.now()
        data = {
            "symbol": sym.strip(),
            "resolution": resolution,
            "date_format": "1",
            "range_from": (now - timedelta(days=days)).strftime("%Y-%m-%d"),
            "range_to": now.strftime("%Y-%m-%d"),
            "cont_flag": "1",
        }
        res = fyers.history(data)
        return res
    except Exception:
        return None


def fetch_quote(fyers, sym):
    try:
        return fyers.quotes({"symbols": sym})
    except Exception:
        return None


@st.cache_data(ttl=600)
def fetch_news_for_symbol(base: str):
    if not NEWS_API_KEY:
        return []
    try:
        params = {
            "q": base,
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": 5,
            "from": (datetime.now() - timedelta(days=NEWS_LOOKBACK_DAYS)).strftime("%Y-%m-%d"),
            "apiKey": NEWS_API_KEY,
        }
        r = requests.get(NEWS_API_URL, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
        return data.get("articles", [])[:5]
    except Exception:
        return []
