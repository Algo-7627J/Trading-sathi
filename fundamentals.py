"""
Real fundamentals + quarterly results data, scraped best-effort from
Screener.in (public, unofficial - no API key required).

This is intentionally defensive: Screener can change its HTML layout or
block scraping at any time, so every parse step is wrapped in try/except
and returns sensible "N/A" defaults instead of raising.
"""
from __future__ import annotations

import re
import requests
import streamlit as st

try:
    from bs4 import BeautifulSoup
except Exception:
    BeautifulSoup = None

from config import HEADERS

SCREENER_BASE = "https://www.screener.in/company"


def _clean_number(text: str):
    if text is None:
        return None
    t = text.replace(",", "").replace("₹", "").replace("%", "").strip()
    t = t.replace("Cr.", "").strip()
    if t in ("", "-", "N/A"):
        return None
    try:
        return float(t)
    except Exception:
        return None


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def fetch_screener_page(base_symbol: str):
    """Fetch and parse Screener.in company page. Tries consolidated then standalone."""
    if BeautifulSoup is None:
        return None

    for url in (
        f"{SCREENER_BASE}/{base_symbol}/consolidated/",
        f"{SCREENER_BASE}/{base_symbol}/",
    ):
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            if r.status_code != 200:
                continue
            return r.text
        except Exception:
            continue
    return None


def _parse_top_ratios(soup):
    out = {}
    try:
        top = soup.select_one("#top-ratios")
        if not top:
            return out
        for li in top.select("li"):
            name_el = li.select_one(".name")
            value_el = li.select_one(".number")
            if name_el and value_el:
                name = name_el.get_text(strip=True)
                value = value_el.get_text(strip=True)
                out[name] = value
    except Exception:
        pass
    return out


def _parse_sector_breadcrumb(soup):
    try:
        peers = soup.select_one("#peers")
        if not peers:
            return None, None
        links = peers.select("a")
        broad_sector = links[0].get_text(strip=True) if len(links) > 0 else None
        sector = links[1].get_text(strip=True) if len(links) > 1 else None
        return broad_sector, sector
    except Exception:
        return None, None


def _parse_quarterly_table(soup):
    try:
        q = soup.select_one("#quarters")
        if not q:
            return {}, []
        table = q.select_one("table")
        if not table:
            return {}, []
        headers = [th.get_text(strip=True) for th in table.select("thead th")][1:]
        rows = {}
        for tr in table.select("tbody tr"):
            cells = [td.get_text(strip=True) for td in tr.select("td")]
            if not cells:
                continue
            key = cells[0].replace("+", "").strip()
            rows[key] = cells[1:]
        return rows, headers
    except Exception:
        return {}, []


def analyze_fundamental_and_results(base_symbol: str, enabled: bool = True):
    """
    Returns two dicts: fundamental (valuation snapshot) and results
    (quarterly performance / beat-miss style signal).

    fundamental: {score, pe, roe, roce, market_cap, div_yield, note}
    results: {score, sales_qoq, profit_qoq, note}
    """
    fundamental = {"score": None, "note": "disabled"}
    results = {"score": None, "note": "disabled"}

    if not enabled:
        return fundamental, results

    html = fetch_screener_page(base_symbol)
    if not html or BeautifulSoup is None:
        fundamental = {"score": None, "note": "fundamental data n/a"}
        results = {"score": None, "note": "results data n/a"}
        return fundamental, results

    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception:
        try:
            soup = BeautifulSoup(html, "html.parser")
        except Exception:
            fundamental = {"score": None, "note": "parse error"}
            results = {"score": None, "note": "parse error"}
            return fundamental, results

    ratios = _parse_top_ratios(soup)
    broad_sector, sector = _parse_sector_breadcrumb(soup)

    pe = _clean_number(ratios.get("Stock P/E", ""))
    roe = _clean_number(ratios.get("ROE", ""))
    roce = _clean_number(ratios.get("ROCE", ""))
    market_cap = _clean_number(ratios.get("Market Cap", ""))
    div_yield = _clean_number(ratios.get("Dividend Yield", ""))

    # --- Fundamental score: simple quality/valuation heuristic ---
    f_votes = []
    if roe is not None:
        f_votes.append(1 if roe >= 15 else (-1 if roe < 8 else 0))
    if roce is not None:
        f_votes.append(1 if roce >= 15 else (-1 if roce < 8 else 0))
    if pe is not None and pe > 0:
        f_votes.append(1 if pe < 25 else (-1 if pe > 60 else 0))

    if f_votes:
        f_score = sum(f_votes) / len(f_votes)
        note_bits = []
        if pe is not None:
            note_bits.append(f"P/E {pe:g}")
        if roe is not None:
            note_bits.append(f"ROE {roe:g}%")
        if roce is not None:
            note_bits.append(f"ROCE {roce:g}%")
        fundamental = {
            "score": round(f_score, 2),
            "pe": pe,
            "roe": roe,
            "roce": roce,
            "market_cap": market_cap,
            "div_yield": div_yield,
            "sector": sector or broad_sector,
            "note": ", ".join(note_bits) if note_bits else "n/a",
        }
    else:
        fundamental = {"score": None, "note": "ratios n/a"}

    # --- Results score: latest quarter Sales/Profit QoQ growth (beat/miss proxy) ---
    q_rows, q_headers = _parse_quarterly_table(soup)
    sales_row = q_rows.get("Sales")
    profit_row = q_rows.get("Net Profit")

    r_votes = []
    sales_qoq = None
    profit_qoq = None
    latest_q_label = q_headers[-1] if q_headers else None

    try:
        if sales_row and len(sales_row) >= 2:
            latest = _clean_number(sales_row[-1])
            prev = _clean_number(sales_row[-2])
            if latest is not None and prev not in (None, 0):
                sales_qoq = round(((latest - prev) / abs(prev)) * 100, 1)
                r_votes.append(1 if sales_qoq > 5 else (-1 if sales_qoq < -5 else 0))
    except Exception:
        pass

    try:
        if profit_row and len(profit_row) >= 2:
            latest = _clean_number(profit_row[-1])
            prev = _clean_number(profit_row[-2])
            if latest is not None and prev not in (None, 0):
                profit_qoq = round(((latest - prev) / abs(prev)) * 100, 1)
                r_votes.append(1 if profit_qoq > 5 else (-1 if profit_qoq < -5 else 0))
    except Exception:
        pass

    if r_votes:
        r_score = sum(r_votes) / len(r_votes)
        note_bits = [f"Qtr: {latest_q_label}" if latest_q_label else "Latest Qtr"]
        if sales_qoq is not None:
            note_bits.append(f"Sales QoQ {sales_qoq:+.1f}%")
        if profit_qoq is not None:
            note_bits.append(f"Profit QoQ {profit_qoq:+.1f}%")
        results = {
            "score": round(r_score, 2),
            "sales_qoq": sales_qoq,
            "profit_qoq": profit_qoq,
            "quarter": latest_q_label,
            "note": ", ".join(note_bits),
        }
    else:
        results = {"score": None, "note": "quarterly data n/a"}

    return fundamental, results
