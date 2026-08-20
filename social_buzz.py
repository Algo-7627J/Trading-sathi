# social_buzz.py — keyless social-buzz triggers for RAO SAHAB
# ------------------------------------------------------------------
# "What are people saying about this stock right now?" — cheap, fast,
# zero-API-key social chatter that often flags WHY a stock is moving.
#
# Sources (all best-effort, no key required):
#   1. Reddit search across Indian trading subreddits (r/IndianStreetBets,
#      r/IndiaInvestments, r/StockMarketIndia, r/DalalStreetTalks, ...)
#   2. Google News "social" query — headlines where the stock was discussed
#      on twitter / social media ("viral", "trending", "twitter")
#   3. X (Twitter) v2 API — ONLY if X_BEARER_TOKEN is present in Streamlit
#      secrets (optional upgrade path; skipped silently otherwise)
#
# Every source degrades to an empty list instead of raising, and the
# result reports which sources answered, so the UI can say "source
# unavailable" instead of silently showing nothing.
#
# ⏱️ 7-DAY WINDOW: only content from the last 7 days is shown — old news
# is not a trigger for today's move. Enforced three ways:
#   • Reddit search uses t=week
#   • Google News queries carry an `after:` date (last 7 days)
#   • a final hard age-filter drops anything older than _MAX_AGE_DAYS
# ------------------------------------------------------------------
import html as _html
import os
import re
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import requests

try:
    import streamlit as st
except Exception:  # pragma: no cover - module usable standalone
    st = None

IST = timezone(timedelta(hours=5, minutes=30))
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

# ---------------- config ----------------
_REDDIT_SUBS = [
    "IndianStreetBets", "IndiaInvestments", "StockMarketIndia",
    "DalalStreetTalks", "IndianStockMarket", "NSEbets",
]
_PER_SOURCE = 4          # items fetched per source
_CACHE_TTL = 600         # 10 min in-memory cache
_MAX_AGE_DAYS = 7        # show only buzz from the last 7 days (fresh triggers)

# search-phrase aliases: indices & commodities are discussed by name
_ALIAS = {
    "NIFTY50": "Nifty 50",
    "BANKNIFTY": "Bank Nifty",
    "FINNIFTY": "FinNifty",
    "MIDCPNIFTY": "Midcap Nifty",
    "SENSEX": "Sensex",
    "GOLD": "gold price",
    "SILVER": "silver price",
    "CRUDEOIL": "crude oil",
    "NATURALGAS": "natural gas",
    "COPPER": "copper price",
}

# simple lexicon-based sentiment (word-boundary matching, case-insensitive)
_BULL = [
    "bullish", "bull", "breakout", "break out", "rally", "rallies",
    "upgrade", "accumulate", "add", "buy", "bought", "long",
    "target", "gain", "gains", "profit", "beat", "outperform",
    "multibagger", "strong", "surge", "soar", "high", "recovery",
    "🚀", "🤑", "💎",
]
_BEAR = [
    "bearish", "bear", "breakdown", "break down", "crash", "crashes",
    "downgrade", "exit", "avoid", "sell", "sold", "short",
    "loss", "losses", "panic", "dump", "weak", "fall", "falls",
    "falling", "drop", "bubble", "overvalued", "bear trap",
    "📉", "💀",
]


# ---------------- helpers ----------------
def normalize_symbol(symbol):
    """'NSE:TATAMOTORS-EQ' / 'tatamotors.ns' -> 'TATAMOTORS'."""
    s = str(symbol or "").upper().strip()
    s = s.split(":")[-1]                    # drop NSE:/BSE: prefix
    s = re.sub(r"-EQ$|-BE$|\.NS$|\.BO$", "", s)
    return s.strip()


def search_phrase(symbol):
    """Human phrase used to search social sources for this symbol."""
    s = normalize_symbol(symbol)
    return _ALIAS.get(s, s)


# ---------------- ticker disambiguation ----------------
# Tickers that collide with unrelated things ("ACC" = a US football
# conference + Asian Cricket Council + a Cabinet committee; "IOC" =
# International Olympic Committee; "SAIL" = sailing…). For these we
# search by the company's real name so results stay about the stock.
_COMPANY = {
    "ACC": "ACC Ltd",
    "SAIL": "Steel Authority of India",
    "YES": "Yes Bank",
    "IDEA": "Vodafone Idea",
    "TITAN": "Titan Company",
    "PAGE": "Page Industries",
    "IOC": "Indian Oil",
    "GAIL": "GAIL India",
    "M&M": "Mahindra & Mahindra",
    "LT": "Larsen & Toubro",
    "HAL": "Hindustan Aeronautics",
    "BEL": "Bharat Electronics",
    "BHEL": "Bharat Heavy Electricals",
    "UBL": "United Breweries",
    "PNB": "Punjab National Bank",
    "SBIN": "State Bank of India",
    "NAUKRI": "Info Edge",
    "CONCOR": "Container Corporation of India",
    "AMBER": "Amber Enterprises",
    "RAINBOW": "Rainbow Children's",
    "PEL": "Piramal Enterprises",
    "MRPL": "Mangalore Refinery",
    "SUNTV": "Sun TV Network",
    "NATIONALUM": "National Aluminium Company",
    "CANBK": "Canara Bank",
    "FEDERALBNK": "Federal Bank",
    "PETRONET": "Petronet LNG",
    "LALPATHLAB": "Dr Lal PathLabs",
    "BANKBARODA": "Bank of Baroda",
    "BANKINDIA": "Bank of India",
    "AUBANK": "AU Small Finance Bank",
    "BANDHANBNK": "Bandhan Bank",
    "IDFCFIRSTB": "IDFC First Bank",
    "GODREJCP": "Godrej Consumer Products",
    "GODREJPROP": "Godrej Properties",
    "GODREJIND": "Godrej Industries",
    "INDIAMART": "IndiaMART",
    "MGL": "Mahanagar Gas",
    "IGL": "Indraprastha Gas",
    "JSL": "Jindal Stainless",
    "VEDL": "Vedanta",
    "APOLLOHOSP": "Apollo Hospitals",
    "TVSMOTOR": "TVS Motor",
    "MARUTI": "Maruti Suzuki",
    "TATAPOWER": "Tata Power",
    "ADANIENT": "Adani Enterprises",
    "ADANIPORTS": "Adani Ports",
    "AMBUJACEM": "Ambuja Cements",
    "ULTRACEMCO": "UltraTech Cement",
    "SBICARD": "SBI Card",
    "SBILIFE": "SBI Life",
    "RECLTD": "REC Limited",
}

# extra words to EXCLUDE for the worst offenders when searching by ticker
_EXCLUDE = {
    "SAIL": ["SailPoint"],
    "ACC": ["football", "conference", "cricket"],
    "HAL": ["Halliburton"],
    "IOC": ["Olympic"],
}

# words that signal a stock/business context. Used to filter out
# same-name noise: "ACC football championship" has none of these and
# gets dropped, "ACC Q1 results revenue" passes.
_BUSINESS = {
    "share", "shares", "stock", "stocks", "nse", "bse", "q1", "q2", "q3",
    "q4", "results", "result", "earnings", "profit", "profits", "revenue",
    "net", "crore", "target", "targets", "price", "prices", "rating",
    "ratings", "upgrade", "downgrade", "buy", "sell", "hold", "broker",
    "brokerage", "rally", "rallies", "gains", "gain", "falls", "fall",
    "rises", "rise", "jumps", "jump", "plunges", "plunge", "dividend",
    "merger", "acquisition", "acquire", "acquires", "capex", "order",
    "orders", "ipo", "ofs", "buyback", "stake", "investors", "investor",
    "market", "markets", "trade", "trading", "index", "nifty", "sensex",
    "outlook", "guidance", "margin", "margins", "fy", "quarter", "quarters",
    "quarterly", "annual", "agm", "board", "concall", "debt", "demerger",
    "split", "bonus", "listing", "valuation", "forecast", "prediction",
    "session", "week", "upside", "downside", "bullish", "bearish",
    "outperform", "underperform", "pat", "ebitda", "ltd", "limited",
    "rupees", "announce", "announces", "announced", "launch", "launches",
    "launched", "plant", "plants", "facility", "expansion", "expands",
    "partnership", "deal", "deals", "signed", "bags", "contract",
    "breakout", "breakdown", "support", "resistance", "position",
    "moon", "rocket", "intraday", "swing", "futures", "options", "fno",
}


def _html_to_text(html):
    """Strip tags/entities from Google News <description> HTML."""
    try:
        import html as _h
        txt = re.sub(r"<[^>]+>", " ", str(html or ""))
        return re.sub(r"\s+", " ", _h.unescape(txt)).strip()
    except Exception:
        return ""


def _has_word(text, word):
    """Word-ish match: skips matches glued to letters/digits/hyphens
    ("Self-Reliance" must NOT match the stock RELIANCE)."""
    w = re.escape(str(word or "").lower())
    if not w:
        return False
    return bool(re.search(rf"(?<![a-z0-9-]){w}(?![a-z0-9])", str(text or "").lower()))


def _relevant(title, desc, symbol, ctx):
    """Is this item about the STOCK, not a same-name unrelated thing?

    - company name in the TITLE + a hint of business context → stock
    - name anywhere + strong business language → stock
    - long unique ticker alone in the title → almost always the company
    Casual body-text mentions (e.g. a hospital named after the group)
    without business context get dropped.
    """
    t = str(title or "").lower()
    d = str(desc or "").lower()
    sym = str(symbol).lower()
    c = str(ctx).lower()
    tok = lambda text: sum(
        1 for w in _BUSINESS
        if re.search(rf"(?<![a-z0-9]){re.escape(w)}(?![a-z0-9])", text)
    )
    score = 2 * tok(t) + tok(d)
    name_in_title = _has_word(t, c) or _has_word(t, sym)
    name_in_text = name_in_title or _has_word(d, c) or _has_word(d, sym)

    if name_in_title and score >= 1:
        return True
    if name_in_text and score >= 3:
        return True
    if score >= 4:
        return True
    if len(sym) >= 8 and _has_word(t, sym):
        return True
    return False


def _is_fresh(ts, max_age_days=_MAX_AGE_DAYS):
    """True if `ts` is within the last `max_age_days` (or unknown)."""
    if not ts:
        return True          # no timestamp → keep (best-effort)
    try:
        return (time.time() - float(ts)) <= max_age_days * 86400
    except Exception:
        return True


def _age(ts):
    if not ts:
        return ""
    try:
        dt = datetime.fromtimestamp(float(ts), tz=IST)
        delta = datetime.now(IST) - dt
        secs = max(0, int(delta.total_seconds()))
        if secs < 3600:
            return f"{max(1, secs // 60)}m ago"
        if secs < 86400:
            return f"{secs // 3600}h ago"
        return f"{secs // 86400}d ago"
    except Exception:
        return ""


def _tone(text):
    t = str(text or "").lower()
    bull = sum(1 for w in _BULL if re.search(rf"\b{re.escape(w)}\b", t))
    bear = sum(1 for w in _BEAR if re.search(rf"\b{re.escape(w)}\b", t))
    if bull > bear:
        return "bull"
    if bear > bull:
        return "bear"
    return "neutral"


# ---------------- sources ----------------
def _reddit_items(query, limit=_PER_SOURCE):
    """Search Indian trading subreddits for `query`. Best-effort.

    Reddit's JSON API blocks some cloud/datacenter IPs (returns the HTML
    app shell instead of JSON). We detect that and return [] — the app
    keeps working, the caller reports "source unavailable".
    """
    q = quote(query)
    subs = "+".join(_REDDIT_SUBS)
    # t=week → only posts from the last 7 days (fresh triggers only)
    urls = [
        f"https://www.reddit.com/search.json?q={q}&subreddit={subs}&sort=new&t=week&limit={limit}",
        f"https://old.reddit.com/search.json?q={q}&subreddit={subs}&sort=new&t=week&limit={limit}",
    ]
    for url in urls:
        try:
            r = requests.get(url, timeout=8,
                             headers={"User-Agent": UA,
                                      "Accept": "application/json"})
            if r.status_code != 200:
                continue
            txt = r.text.lstrip()
            if not txt.startswith("{"):      # HTML shell => blocked
                continue
            data = r.json()
            children = ((data.get("data") or {}).get("children")) or []
            out = []
            for c in children:
                d = (c.get("data") or {})
                title = str(d.get("title") or "").strip()
                if not title:
                    continue
                # drop same-name noise (sailing, football, "yes" as a word…)
                selftext = str(d.get("selftext") or "")
                if not _relevant(title, selftext, query, _COMPANY.get(query, query)):
                    continue
                perm = d.get("permalink") or ""
                url2 = f"https://www.reddit.com{perm}" if perm else \
                    (d.get("url") or "")
                out.append({
                    "source": "reddit",
                    "kind": "post",
                    "title": title,
                    "snippet": re.sub(r"\s+", " ", selftext)[:180],
                    "url": url2,
                    "score": int(d.get("score") or 0),
                    "comments": int(d.get("num_comments") or 0),
                    "ts": float(d.get("created_utc") or 0),
                    "tone": _tone(title + " " + selftext),
                    "meta": str(d.get("subreddit_name_prefixed") or "reddit"),
                })
            return out[:limit]
        except Exception:
            continue
    return []


def _news_social_items(symbol, limit=_PER_SOURCE):
    """Google News items about the STOCK (not same-name unrelated things).

    Query chain (first one that yields enough fresh, relevant items wins):
      1. fresh    — "{company}" after:<7-days-ago>   (date-filtered at source;
                    Google's after: only works on simple queries, so it leads)
      2. social   — "{company}" (twitter OR viral OR "social media" OR trending)
      3. context  — "{company}" (share OR shares OR stock OR NSE OR BSE)
      4. ticker   — "{symbol}" (share OR shares OR stock OR NSE OR BSE) [-excludes]
                    (only when the company name differs from the ticker)

    Every item must pass `_relevant()` (business-context check) and the
    hard 7-day freshness filter — Google's date operators are approximate,
    so the local filter is the real gate.
    """
    s = normalize_symbol(symbol)
    ctx = _COMPANY.get(s, s)
    cutoff = (datetime.now(timezone.utc) - timedelta(days=_MAX_AGE_DAYS)).strftime("%Y-%m-%d")

    def _run(q):
        url = (f"https://news.google.com/rss/search?q={quote(q)}&hl=en-IN&gl=IN"
               f"&ceid=IN:en")
        r = requests.get(url, timeout=10, headers={"User-Agent": UA})
        if r.status_code != 200:
            return []
        try:
            root = ET.fromstring(r.text)
        except Exception:
            return []
        items = []
        for it in root.findall(".//item"):
            title = (it.findtext("title") or "").strip()
            title = re.sub(r"\s*-\s*[^-]+$", "", title).strip()
            if not title:
                continue
            desc = _html_to_text(it.findtext("description") or "")
            pub = it.findtext("pubDate") or ""
            ts = 0
            try:
                ts = datetime.strptime(pub, "%a, %d %b %Y %H:%M:%S %Z").replace(
                    tzinfo=timezone.utc).timestamp()
            except Exception:
                pass
            if not _is_fresh(ts):
                continue
            if not _relevant(title, desc, s, ctx):
                continue
            items.append({
                "source": "news",
                "kind": "headline",
                "title": title,
                "snippet": desc[:200],
                "url": it.findtext("link") or "",
                "score": 0,
                "comments": 0,
                "ts": ts,
                "tone": _tone(title),
                "meta": "Google News",
            })
        return items

    chain = [
        (f'"{ctx}" after:{cutoff}', "Google News · fresh"),
        (f'"{ctx}" (twitter OR viral OR "social media" OR trending)',
         "Google News · social"),
        (f'"{ctx}" (share OR shares OR stock OR NSE OR BSE)',
         "Google News"),
    ]
    if ctx != s:
        neg = " ".join(f'-{w}' for w in _EXCLUDE.get(s, []))
        chain.append(
            (f'"{s}" (share OR shares OR stock OR NSE OR BSE) {neg}'.strip(),
             "Google News")
        )

    out = []
    for q, meta in chain:
        got = _run(q)
        for it in got:
            it["meta"] = meta
            out.append(it)
        if len(out) >= limit:
            break
    return out[:limit]


def _x_bearer_token():
    """X API v2 bearer token from Streamlit secrets, if any.

    st.secrets raises when no secrets file exists at all, so every
    access is wrapped in try/except.
    """
    if st is None:
        return None
    try:
        sec = st.secrets
    except Exception:
        return None
    for key in ("X_BEARER_TOKEN", "TWITTER_BEARER_TOKEN"):
        try:
            for section in list(sec.keys()):
                sub = sec[section]
                if hasattr(sub, "get") and sub.get(key):
                    return str(sub[key]).strip()
        except Exception:
            continue
        try:
            if isinstance(sec.get(key), str) and sec[key].strip():
                return str(sec[key]).strip()
        except Exception:
            continue
    return None


def _x_items(symbol, limit=_PER_SOURCE):
    """Real tweet search via the X API — only if a bearer token is set."""
    tok = _x_bearer_token()
    if not tok:
        return []
    phrase = search_phrase(symbol)
    q = quote(f"{phrase} lang:en -is:retweet")
    url = ("https://api.twitter.com/2/tweets/search/recent"
           f"?query={q}&max_results={min(limit, 10)}"
           "&tweet.fields=created_at,public_metrics")
    try:
        r = requests.get(url, timeout=10,
                         headers={"Authorization": f"Bearer {tok}"})
        if r.status_code != 200:
            return []
        data = r.json()
        out = []
        for t in (data.get("data") or []):
            title = re.sub(r"\s+", " ", t.get("text") or "").strip()[:160]
            if not title:
                continue
            ts = 0
            try:
                ts = datetime.fromisoformat(
                    t["created_at"].replace("Z", "+00:00")).timestamp()
            except Exception:
                pass
            metrics = t.get("public_metrics") or {}
            out.append({
                "source": "x",
                "kind": "tweet",
                "title": title,
                "snippet": "",
                "url": f"https://x.com/i/status/{t.get('id')}",
                "score": int(metrics.get("like_count") or 0),
                "comments": int(metrics.get("reply_count") or 0),
                "ts": ts,
                "tone": _tone(title),
                "meta": "@author on X",
            })
        return out
    except Exception:
        return []


def reddit_hot(subreddit="IndianStreetBets", limit=8):
    """What's hot right now on a trading subreddit (best-effort).

    No symbol filter — this is the "what is everyone talking about today"
    view. Returns a list of items shaped like the other sources.
    """
    url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit={limit}"
    try:
        r = requests.get(url, timeout=8,
                         headers={"User-Agent": UA, "Accept": "application/json"})
        if r.status_code != 200:
            return []
        txt = r.text.lstrip()
        if not txt.startswith("{"):          # HTML shell => blocked
            return []
        data = r.json()
        out = []
        for c in ((data.get("data") or {}).get("children") or []):
            d = c.get("data") or {}
            title = str(d.get("title") or "").strip()
            if not title:
                continue
            perm = d.get("permalink") or ""
            out.append({
                "source": "reddit",
                "kind": "post",
                "title": title,
                "snippet": re.sub(r"\s+", " ", str(d.get("selftext") or ""))[:180],
                "url": f"https://www.reddit.com{perm}" if perm else (d.get("url") or ""),
                "score": int(d.get("score") or 0),
                "comments": int(d.get("num_comments") or 0),
                "ts": float(d.get("created_utc") or 0),
                "tone": _tone(title),
                "meta": f"r/{subreddit}",
            })
        # hot feed only — keep posts from the last 7 days
        return [i for i in out if _is_fresh(i.get("ts"))][:limit]
    except Exception:
        return []


# ---------------- cache + aggregate ----------------
_CACHE = {}   # symbol -> (ts, result)


def fetch_buzz(symbol, per_source=_PER_SOURCE, force=False):
    """Aggregated social buzz for one symbol.

    Returns dict: {symbol, items, counts, tone, engagement, sources_ok}
    """
    s = normalize_symbol(symbol)
    now = time.time()
    hit = _CACHE.get(s)
    if not force and hit and (now - hit[0]) < _CACHE_TTL:
        return hit[1]

    items = []
    ok = {"reddit": False, "news": False, "x": False}

    red = _reddit_items(s, per_source)
    ok["reddit"] = len(red) > 0
    items += red

    news = _news_social_items(s, per_source)
    ok["news"] = len(news) > 0
    items += news

    x = _x_items(s, per_source)
    ok["x"] = len(x) > 0
    items += x

    # dedupe by url, newest first
    seen, dedup = set(), []
    for it in sorted(items, key=lambda d: -(d.get("ts") or 0)):
        key = it.get("url") or it.get("title")
        if key in seen:
            continue
        seen.add(key)
        dedup.append(it)
    # HARD 7-DAY WINDOW: anything older than a week is not a fresh trigger
    items = [i for i in dedup if _is_fresh(i.get("ts"))]

    bull = sum(1 for i in items if i["tone"] == "bull")
    bear = sum(1 for i in items if i["tone"] == "bear")
    neutral = len(items) - bull - bear
    tone = "bull" if bull > bear else "bear" if bear > bull else "neutral"
    engagement = sum(i.get("score", 0) + i.get("comments", 0) for i in items)

    res = {
        "symbol": s,
        "items": items,
        "counts": {"total": len(items), "bull": bull, "bear": bear,
                   "neutral": neutral},
        "tone": tone,
        "engagement": engagement,
        "sources_ok": ok,
        "window_days": _MAX_AGE_DAYS,
        "updated": now,
    }
    _CACHE[s] = (now, res)
    return res


def fetch_buzz_bulk(symbols, per_source=_PER_SOURCE, max_workers=6):
    """Buzz for many symbols in parallel (used for card widgets)."""
    out = {}
    syms = [str(s).strip() for s in symbols if str(s).strip()]
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        for sym, buzz in ex.map(lambda s: (s, fetch_buzz(s, per_source)), syms):
            out[normalize_symbol(sym)] = buzz
    return out


# ---------------- HTML rendering ----------------
_TONE_CHIP = {
    "bull": '<span class="chip chip-green">Bullish</span>',
    "bear": '<span class="chip chip-red">Bearish</span>',
    "neutral": '<span class="chip chip-gray">Neutral</span>',
}
_SOURCE_ICON = {"reddit": "💬", "news": "📰", "x": "🐦"}


def buzz_item_html(item):
    """One clickable buzz row (used in the Social Buzz tab)."""
    src = item.get("source", "reddit")
    icon = _SOURCE_ICON.get(src, "💬")
    title = _html.escape(str(item.get("title") or ""))
    snippet = _html.escape(str(item.get("snippet") or "")[:200])
    url = _html.escape(str(item.get("url") or ""), quote=True)
    meta = _html.escape(str(item.get("meta") or ""))
    age = _age(item.get("ts"))
    score = item.get("score") or 0
    comments = item.get("comments") or 0
    stats = []
    if score:
        stats.append(f"▲ {score}")
    if comments:
        stats.append(f"💬 {comments}")
    stats_txt = _html.escape(" · ".join(stats))
    chip = _TONE_CHIP.get(item.get("tone"), _TONE_CHIP["neutral"])

    inner = (
        f'<div style="display:flex;justify-content:space-between;align-items:baseline;gap:8px;">'
        f'<span style="font-size:14px;font-weight:700;color:var(--heading);">{icon} {title}</span>'
        f'{chip}</div>'
    )
    if snippet:
        inner += (f'<div style="font-size:12.5px;color:var(--muted);margin-top:5px;'
                  f'line-height:1.5;">{snippet}</div>')
    inner += (
        f'<div style="display:flex;justify-content:space-between;align-items:center;'
        f'margin-top:7px;flex-wrap:wrap;gap:4px;">'
        f'<span style="font-size:11.5px;color:var(--muted);">{meta}'
        f'{(" · " + stats_txt) if stats_txt else ""}'
        f'{(" · " + age) if age else ""}</span>'
        f'<span style="font-size:11.5px;font-weight:700;color:#00875F;">Open ↗</span></div>'
    )
    card = (f'<div class="opl-card" style="padding:11px 13px;margin-bottom:8px;">{inner}</div>')
    if url:
        return (f'<a href="{url}" target="_blank" rel="noopener noreferrer" '
                f'class="opl-link">{card}</a>')
    return card


def buzz_section_html(buzz, max_items=2):
    """Compact buzz strip embedded inside momentum/streak cards.

    Shows the top social items as clickable trigger links + a bullish/
    bearish tally. Returns '' when there is nothing to show.
    """
    if not buzz:
        return ""
    items = (buzz.get("items") or [])[:max_items]
    if not items:
        return ""
    c = buzz.get("counts") or {}
    bull, bear = c.get("bull", 0), c.get("bear", 0)
    tally = []
    if bull:
        tally.append(f'<span style="color:#00875F;font-weight:800;">▲ {bull} bullish</span>')
    if bear:
        tally.append(f'<span style="color:#C93A20;font-weight:800;">▼ {bear} bearish</span>')
    if not tally:
        tally.append(f'<span style="color:var(--muted);font-weight:700;">{c.get("total", 0)} mentions</span>')
    tally_html = " · ".join(tally)

    rows = ""
    for it in items:
        icon = _SOURCE_ICON.get(it.get("source", "reddit"), "💬")
        title = _html.escape(str(it.get("title") or "")[:90])
        url = _html.escape(str(it.get("url") or ""), quote=True)
        age = _age(it.get("ts"))
        chip = _TONE_CHIP.get(it.get("tone"), _TONE_CHIP["neutral"])
        age_html = (f'<span style="color:var(--muted);"> · {_html.escape(age)}</span>'
                    if age else "")
        line = (f'<div style="display:flex;align-items:center;gap:6px;margin-top:6px;'
                f'justify-content:space-between;">'
                f'<span style="font-size:12px;color:var(--ink);line-height:1.4;">'
                f'{icon} {title}{age_html}</span>{chip}</div>')
        rows += (f'<a href="{url}" target="_blank" rel="noopener noreferrer" '
                 f'class="opl-link" style="display:block;">{line}</a>')

    window = buzz.get("window_days", 7)
    return (
        f'<div style="margin-top:10px;padding-top:9px;border-top:1px dashed var(--border);">'
        f'<div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:4px;">'
        f'<span style="font-size:11px;font-weight:800;letter-spacing:.6px;color:var(--muted);">'
        f'💬 SOCIAL BUZZ · LAST {window}D</span>'
        f'<span style="font-size:11px;">{tally_html}</span></div>'
        f'{rows}</div>'
    )


def buzz_sources_note(buzz):
    """Small hint when some sources were unreachable (e.g. Reddit blocks)."""
    if not buzz:
        return ""
    ok = buzz.get("sources_ok") or {}
    dead = []
    if not ok.get("reddit"):
        dead.append("Reddit")
    if not ok.get("news"):
        dead.append("Google News")
    if not ok.get("x"):
        dead.append("X")
    if not dead:
        return ""
    return ("ℹ️ No results from: " + ", ".join(dead) +
            " (source unreachable or no mentions found — try again later)")
