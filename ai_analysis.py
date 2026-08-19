# ai_analysis.py — "why is this stock moving?" analysis engine
# ------------------------------------------------------------------
# Combines three layers to explain a move:
#   1) Real LLM (OpenAI / Gemini / Anthropic) when an API key is present
#      in Streamlit secrets — one batched call per scan.
#   2) Built-in rule-based narrative (always available) as fallback.
#   3) Latest news headlines (Google News RSS, free) as the "trigger".
#
# Keys are read from Streamlit secrets — nothing is hardcoded:
#   OPENAI_API_KEY   (optional OPENAI_MODEL,   default gpt-4o-mini)
#   GEMINI_API_KEY   (optional GEMINI_MODEL,   default gemini-1.5-flash)
#   ANTHROPIC_API_KEY(optional ANTHROPIC_MODEL,default claude-3-5-haiku-latest)
# ------------------------------------------------------------------
import re
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import requests
import streamlit as st

_NEWS_CACHE = {}     # symbol -> (ts, [headlines])
_NEWS_TTL = 1800     # 30 min


# ====================== NEWS (Google News RSS, free) ======================
def get_news(symbol, limit=3):
    """Top headlines for a symbol from Google News RSS (cached)."""
    s = str(symbol).upper().strip()
    now = time.time()
    hit = _NEWS_CACHE.get(s)
    if hit and (now - hit[0]) < _NEWS_TTL:
        return hit[1]

    out = []
    try:
        q = requests.utils.quote(f"{s} share price NSE")
        url = f"https://news.google.com/rss/search?q={q}&hl=en-IN&gl=IN&ceid=IN:en"
        r = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code == 200:
            root = ET.fromstring(r.text)
            for it in root.findall(".//item")[:limit]:
                title = it.findtext("title") or ""
                title = re.sub(r"\s*-\s*[^-]+$", "", title).strip()   # drop " - source"
                link = it.findtext("link") or ""
                if title:
                    out.append({"title": title, "link": link})
    except Exception:
        pass

    _NEWS_CACHE[s] = (now, out)
    return out


def get_news_bulk(symbols, max_workers=8):
    """Fetch headlines for many symbols in parallel."""
    out = {}
    syms = [str(s).upper().strip() for s in symbols if s]
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        for sym, news in ex.map(lambda s: (s, get_news(s)), syms):
            out[sym] = news
    return out


# ====================== BUILT-IN NARRATIVE (no key needed) ======================
def builtin_analysis(row, news=None, kind="momentum"):
    """Deterministic analyst-style note from the row's own indicators."""
    sym = str(row.get("Symbol", ""))
    parts = []

    if kind == "momentum":
        d1, w1, m1 = row.get("1D %"), row.get("1W %"), row.get("1M %")
        up = "Up" in str(row.get("Direction", ""))
        if d1 is not None and w1 is not None and m1 is not None:
            parts.append(f"{sym} is in a strong {'up' if up else 'down'}trend, aligned across timeframes "
                         f"({d1:+.1f}% today, {w1:+.1f}% this week, {m1:+.1f}% this month).")
        else:
            parts.append(f"{sym} shows aligned {'bullish' if up else 'bearish'} momentum across 1D/1W/1M.")
    else:
        streak = row.get("Streak")
        direction = str(row.get("Direction", ""))
        move = row.get("Streak Move %")
        if streak is not None:
            mv = f" ({move:+.1f}% total)" if move is not None and pd.notna(move) else ""
            parts.append(f"{sym} has closed {direction.lower()} for {streak} consecutive sessions{mv}.")

    dp = row.get("DeliveryPct")
    if dp is not None and pd.notna(dp):
        if dp >= 60:
            parts.append(f"Delivery of {dp:.1f}% signals the move is backed by genuine delivery "
                         f"— conviction buying/selling, not just intraday churn.")
        elif dp >= 30:
            parts.append(f"Delivery at {dp:.1f}% points to moderate conviction behind the move.")
        else:
            parts.append(f"Low delivery ({dp:.1f}%) suggests the move is largely speculative intraday activity.")

    rsi = row.get("RSI")
    if rsi is not None and pd.notna(rsi):
        if rsi >= 70:
            parts.append(f"RSI at {rsi:.0f} is overbought — a pause or pullback is possible.")
        elif rsi <= 30:
            parts.append(f"RSI at {rsi:.0f} is oversold — a technical bounce is possible.")
        elif rsi >= 55:
            parts.append(f"RSI at {rsi:.0f} supports the upward momentum.")
        elif rsi <= 45:
            parts.append(f"RSI at {rsi:.0f} supports the downward pressure.")

    vr = row.get("VolRatio")
    if vr is not None and pd.notna(vr):
        if vr >= 1.5:
            parts.append(f"Volume is {vr:.1f}x its 20-day average — strong participation.")
        elif vr <= 0.7:
            parts.append(f"Volume is only {vr:.1f}x its average — the move lacks participation.")

    if news:
        parts.append(f"Possible trigger: \"{news[0]['title']}\".")

    return " ".join(parts) if parts else f"{sym}: no clear catalyst detected."


# ====================== REAL LLM (batched) ======================
def _get_secret(*names):
    """Robust reader for st.secrets (flat or [section] keys)."""
    try:
        if not (hasattr(st, "secrets") and st.secrets):
            return None
        for name in names:
            # flat keys
            v = st.secrets.get(name)
            if v and isinstance(v, str) and v.strip():
                return v.strip()
            # section keys (case-insensitive)
            for section_name in list(st.secrets.keys()):
                try:
                    sub = st.secrets[section_name]
                    if isinstance(sub, dict):
                        if name in sub and sub[name]:
                            return str(sub[name]).strip()
                    else:
                        val = getattr(sub, name, None)
                        if val:
                            return str(val).strip()
                except Exception:
                    continue
    except Exception:
        pass
    return None


def _llm_config():
    key = _get_secret("OPENAI_API_KEY")
    if key:
        return "openai", key, _get_secret("OPENAI_MODEL") or "gpt-4o-mini"
    key = _get_secret("GEMINI_API_KEY")
    if key:
        return "gemini", key, _get_secret("GEMINI_MODEL") or "gemini-1.5-flash"
    key = _get_secret("ANTHROPIC_API_KEY")
    if key:
        return "anthropic", key, _get_secret("ANTHROPIC_MODEL") or "claude-3-5-haiku-latest"
    return None, None, None


def llm_available():
    return _llm_config()[0] is not None


def _fmt(v, suffix="%"):
    if v is None or pd.isna(v):
        return "n/a"
    return f"{float(v):+.1f}{suffix}"


def _row_summary(r, kind):
    sym = r.get("Symbol", "")
    if kind == "momentum":
        s = f"{sym} | {r.get('Direction','')} | LTP {r.get('LTP','')} | 1D {_fmt(r.get('1D %'))} 1W {_fmt(r.get('1W %'))} 1M {_fmt(r.get('1M %'))}"
    else:
        s = f"{sym} | {r.get('Streak','')} days {r.get('Direction','')} | LTP {r.get('LTP','')} | streak move {_fmt(r.get('Streak Move %'))}"
    dp = r.get("DeliveryPct")
    if dp is not None and pd.notna(dp):
        s += f" | Delivery {float(dp):.1f}% ({r.get('Genuineness','')})"
    rsi = r.get("RSI")
    if rsi is not None and pd.notna(rsi):
        s += f" | RSI {float(rsi):.0f}"
    vr = r.get("VolRatio")
    if vr is not None and pd.notna(vr):
        s += f" | Vol {float(vr):.1f}x avg"
    return s


def _llm_call(provider, key, model, prompt):
    headers = {}
    if provider == "openai":
        url = "https://api.openai.com/v1/chat/completions"
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        body = {"model": model, "temperature": 0.4, "max_tokens": 800,
                "messages": [{"role": "user", "content": prompt}]}
    elif provider == "gemini":
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
        headers = {"Content-Type": "application/json"}
        body = {"contents": [{"parts": [{"text": prompt}]}]}
    else:  # anthropic
        url = "https://api.anthropic.com/v1/messages"
        headers = {"x-api-key": key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"}
        body = {"model": model, "max_tokens": 800,
                "messages": [{"role": "user", "content": prompt}]}

    r = requests.post(url, json=body, headers=headers, timeout=45)
    if r.status_code != 200:
        return None
    data = r.json()
    if provider == "openai":
        return data["choices"][0]["message"]["content"]
    if provider == "gemini":
        parts = data["candidates"][0]["content"]["parts"]
        return "".join(p.get("text", "") for p in parts)
    return data["content"][0]["text"]


def _parse_llm(text, symbols):
    out = {}
    for line in str(text).splitlines():
        line = line.strip()
        if not line:
            continue
        if "||" in line:
            sym, rest = line.split("||", 1)
        elif "|" in line:
            sym, rest = line.split("|", 1)
        else:
            parts = line.split(None, 1)
            if len(parts) == 2 and parts[0].upper() in symbols:
                sym, rest = parts
            else:
                continue
        sym = sym.strip().upper().rstrip(":").strip()
        if sym in symbols and rest.strip():
            out[sym] = rest.strip()
    return out


def llm_analysis_batch(rows, news_map):
    """One LLM call to explain all matched stocks. Returns {SYMBOL: text} or None."""
    provider, key, model = _llm_config()
    if not provider:
        return None

    symbols = {str(r.get("Symbol", "")).upper() for r in rows}
    kind = "momentum" if "1D %" in (rows[0] if rows else {}) else "streak"
    lines = []
    for r in rows:
        sym = str(r.get("Symbol", ""))
        news = news_map.get(sym, [])
        hl = "; ".join(n["title"] for n in news[:2]) if news else "none"
        lines.append(f"{_row_summary(r, kind)} || News: {hl}")

    prompt = (
        "You are a concise Indian equity analyst. For each stock below, explain in "
        "2 short sentences the most likely REASON behind its recent move, using the "
        "technicals, delivery conviction and news headlines given. Be factual and "
        "cautious; never give buy/sell advice. Reply with exactly one line per stock "
        "in the format: SYMBOL || explanation\n\n" + "\n".join(lines)
    )

    try:
        text = _llm_call(provider, key, model, prompt)
        if not text:
            return None
        return _parse_llm(text, symbols) or None
    except Exception:
        return None


# ====================== ORCHESTRATOR ======================
def analyze_moves(rows, kind="momentum"):
    """For each matched row -> {'analysis': str, 'news': [headlines]}.

    Uses a batched LLM call when a key is available, else the built-in
    narrative. News headlines are always fetched.
    """
    if not rows:
        return {}
    symbols = [str(r.get("Symbol", "")).upper() for r in rows if r.get("Symbol")]
    news_map = get_news_bulk(symbols)
    llm = llm_analysis_batch(rows, news_map) if llm_available() else None

    out = {}
    for r in rows:
        sym = str(r.get("Symbol", "")).upper()
        news = news_map.get(sym, [])
        text = None
        if llm and sym in llm and str(llm[sym]).strip():
            text = str(llm[sym]).strip()
        if not text:
            text = builtin_analysis(r, news, kind=kind)
        out[sym] = {"analysis": text, "news": news}
    return out
