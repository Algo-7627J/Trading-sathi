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
from datetime import datetime

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


# ====================== GOLD & SILVER AI ANALYSIS ======================
def get_metal_news(metal, limit=3):
    """Fresh (≤7 days) headlines for gold/silver — price outlook & macro drivers.

    Same Google News RSS approach as get_news(), but with commodity
    queries and a 7-day freshness filter so the "trigger" is current.
    """
    name = str(metal).upper().strip()
    key = f"METAL_{name}"
    now = time.time()
    hit = _NEWS_CACHE.get(key)
    if hit and (now - hit[0]) < _NEWS_TTL:
        return hit[1]

    q = {"GOLD": "gold price outlook", "SILVER": "silver price outlook"}.get(
        name, "gold price outlook")
    out = []
    try:
        url = (f"https://news.google.com/rss/search?q={requests.utils.quote(q)}"
               f"&hl=en-IN&gl=IN&ceid=IN:en")
        r = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code == 200:
            root = ET.fromstring(r.text)
            for it in root.findall(".//item"):
                title = it.findtext("title") or ""
                title = re.sub(r"\s*-\s*[^-]+$", "", title).strip()
                link = it.findtext("link") or ""
                if not title:
                    continue
                # 7-day freshness (Google ignores date operators on some
                # queries, so enforce it locally; unparseable = keep)
                pub = it.findtext("pubDate") or ""
                try:
                    ts = datetime.strptime(
                        pub, "%a, %d %b %Y %H:%M:%S %Z").timestamp()
                    if time.time() - ts > 7 * 86400:
                        continue
                except Exception:
                    pass
                out.append({"title": title, "link": link})
                if len(out) >= limit:
                    break
    except Exception:
        pass

    _NEWS_CACHE[key] = (now, out)
    return out


def builtin_metal_analysis(rep, news=None):
    """Deterministic analyst-style note from a metal report
    (commodities.get_metal_report) — always available, no key needed."""
    name = str(rep.get("name", "Metal"))
    parts = []

    if rep.get("simulated"):
        parts.append("⚠️ SIMULATED DATA (live feed unavailable):")

    try:
        ltp, chg = rep.get("ltp"), rep.get("change_pct", 0)
        parts.append(f"{name} is trading at ${ltp:,.2f}, "
                     f"{'up' if chg >= 0 else 'down'} {abs(chg):.2f}% today.")
    except (TypeError, ValueError):
        pass

    cd, cons = rep.get("consensus_dir", ""), rep.get("consensus", 0)
    bull, bear = rep.get("bull_count", 0), rep.get("bear_count", 0)
    parts.append(f"Multi-timeframe consensus is {cd} ({cons:+.1f} / 17) — "
                 f"{bull} bullish vs {bear} bearish timeframes.")

    brk = rep.get("breakout") or {}
    st_ = brk.get("state")
    if st_ == "up":
        parts.append(f"🚀 Price has broken above the 20-day range "
                     f"(${brk.get('hi20', 0):,.0f}) on {brk.get('vol_ratio', 1):.1f}x "
                     f"average volume — a volume-backed breakout, continuation favored.")
    elif st_ == "down":
        parts.append(f"⚠️ Price has broken below the 20-day range "
                     f"(${brk.get('lo20', 0):,.0f}) on {brk.get('vol_ratio', 1):.1f}x "
                     f"average volume — weakness may extend.")
    else:
        parts.append(f"⏸️ Price is still inside its 20-day range "
                     f"(${brk.get('lo20', 0):,.0f}–${brk.get('hi20', 0):,.0f}) — "
                     f"wait for a volume-backed break before acting.")

    tf = (rep.get("timeframes") or {}).get("Next Day (Daily)") or {}
    rsi = tf.get("rsi")
    if rsi is not None:
        if rsi >= 70:
            parts.append(f"Daily RSI at {rsi:.0f} is overbought — watch for exhaustion pullbacks.")
        elif rsi <= 30:
            parts.append(f"Daily RSI at {rsi:.0f} is oversold — a technical bounce is possible.")
        elif rsi >= 55:
            parts.append(f"Daily RSI at {rsi:.0f} confirms the upward momentum.")
        elif rsi <= 45:
            parts.append(f"Daily RSI at {rsi:.0f} confirms the downward pressure.")

    atr = rep.get("atr_pct")
    if atr is not None:
        parts.append(f"Daily volatility (ATR) is ±{atr:.1f}% — key levels: support "
                     f"${rep.get('support', 0):,.0f}, resistance ${rep.get('resistance', 0):,.0f}.")

    if news:
        parts.append(f'Possible trigger: "{news[0]["title"]}".')

    return " ".join(parts) if parts else f"{name}: no clear catalyst detected."


def _metal_summary(rep):
    """One-line metal summary for the batched LLM prompt."""
    brk = rep.get("breakout") or {}
    return (f"{rep.get('name', '')} | LTP ${rep.get('ltp', '')} | "
            f"today {_fmt(rep.get('change_pct'))} | "
            f"consensus {rep.get('consensus', '')} ({rep.get('consensus_dir', '')}) | "
            f"breakout {brk.get('state', '')} vol {brk.get('vol_ratio', 1):.1f}x | "
            f"ATR {rep.get('atr_pct', '')}% | "
            f"support {rep.get('support', '')} resistance {rep.get('resistance', '')}")


def llm_metals_batch(reps, news_map):
    """One LLM call for GOLD + SILVER. Returns {NAME: text} or None."""
    provider, key, model = _llm_config()
    if not provider:
        return None

    symbols = {str(r.get("name", "")).upper() for r in reps}
    lines = []
    for r in reps:
        name = str(r.get("name", "")).upper()
        news = news_map.get(name, [])
        hl = "; ".join(n["title"] for n in news[:2]) if news else "none"
        lines.append(f"{_metal_summary(r)} || News: {hl}")

    prompt = (
        "You are a concise commodity market analyst. For each metal below, explain "
        "in 2 short sentences the most likely REASON behind its recent price action, "
        "using the technicals (multi-timeframe consensus, breakout state, RSI, ATR, "
        "support/resistance) and the news headlines given. Be factual and cautious; "
        "never give buy/sell advice. Reply with exactly one line per metal in the "
        "format: METAL || explanation\n\n" + "\n".join(lines)
    )

    try:
        text = _llm_call(provider, key, model, prompt)
        if not text:
            return None
        return _parse_llm(text, symbols) or None
    except Exception:
        return None


def analyze_metals(reps):
    """For each metal report -> {NAME: {'analysis': str, 'news': [headlines]}}.

    One batched LLM call when a key is available, else the built-in
    rule-based narrative. News headlines are always fetched (≤7 days).
    """
    out = {}
    if not reps:
        return out
    names = [str(r.get("name", "")).upper() for r in reps]
    news_map = {n: get_metal_news(n) for n in names}
    llm = llm_metals_batch(reps, news_map) if llm_available() else None
    for r in reps:
        name = str(r.get("name", "")).upper()
        news = news_map.get(name, [])
        text = (llm or {}).get(name)
        if not text or not str(text).strip():
            text = builtin_metal_analysis(r, news)
        out[name] = {"analysis": text, "news": news}
    return out


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
