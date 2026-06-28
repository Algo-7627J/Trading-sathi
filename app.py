"""
Trading Sathi - F&O + Commodity Multi-Factor Scanner
=====================================================
Yeh app symbols hardcode NAHI karta. Yeh:
  1. NSE se LIVE F&O stock list uthata hai (211+ stocks, auto-updated).
  2. FYERS se Nifty50 / index derivatives + commodity (Gold/Silver/Crude) symbols
     auto-fetch karta hai.
  3. Har symbol par 4 cheezein analyse karta hai aur WEIGHTED score banata hai:
        - Technical Analysis (EMA, RSI, MACD, trend)
        - Open Interest (OI) Analysis  [FYERS live]
        - Fundamental Analysis         [screener.in - free]
        - Latest Results / growth      [screener.in - free]
  4. Combined score se BUY / SELL / HOLD signal deta hai.

NOTE: Free public sources (NSE / screener.in) kabhi block ho sakte hain. Har
module try/except mein hai - ek source fail ho to woh factor "N/A" ho jaata hai,
baaki scoring chalti rehti hai. App kabhi crash nahi karta.
"""

import io
import csv
import re
import time
import requests
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta

try:
    from fyers_apiv3 import fyersModel
except Exception:
    fyersModel = None  # allow UI to load even if lib missing

# ---------------- CONFIG ----------------
APP_ID = st.secrets.get("FYERS_APP_ID", "")
SECRET_KEY = st.secrets.get("FYERS_SECRET_KEY", "")
REDIRECT_URL = st.secrets.get("FYERS_REDIRECT_URL", "")
TELEGRAM_TOKEN = st.secrets.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = st.secrets.get("TELEGRAM_CHAT_ID", "")

NSE_FO_LIST_URL = "https://www.nseindia.com/api/master-quote"
FYERS_NSE_FO_MASTER = "https://public.fyers.in/sym_details/NSE_FO.csv"
FYERS_MCX_MASTER = "https://public.fyers.in/sym_details/MCX_COM.csv"

COMMODITY_BASES = ["GOLD", "GOLDM", "SILVER", "SILVERM", "CRUDEOIL", "CRUDEOILM"]
INDEX_BASES = ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

# Scoring weights (total = 100)
WEIGHTS = {
    "technical": 40,
    "oi": 20,
    "fundamental": 25,
    "results": 15,
}


# ===================================================================
#  TELEGRAM
# ===================================================================
def send_telegram_msg(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.get(url, params={"chat_id": TELEGRAM_CHAT_ID, "text": message}, timeout=5)
    except Exception:
        pass


# ===================================================================
#  SYMBOL UNIVERSE  (no hardcoding)
# ===================================================================
@st.cache_data(ttl=3600)
def fetch_fo_stock_list():
    """Live F&O stock list from NSE. Returns list of FYERS eq symbols."""
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
    """Generic: nearest active FUT contract per base, from a FYERS master CSV."""
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
    """Combine: F&O stocks (NSE) + index futures + commodity futures."""
    stocks = fetch_fo_stock_list()
    indices = fetch_nearest_futures(FYERS_NSE_FO_MASTER, INDEX_BASES)
    commodities = fetch_nearest_futures(FYERS_MCX_MASTER, COMMODITY_BASES)
    return {
        "stocks": stocks,
        "indices": indices,
        "commodities": commodities,
        "all": stocks + indices + commodities,
    }


def base_name_from_symbol(sym):
    """NSE:RELIANCE-EQ -> RELIANCE ; MCX:GOLD26AUGFUT -> GOLD"""
    s = sym.split(":")[-1]
    s = s.replace("-EQ", "")
    s = re.sub(r"\d{2}[A-Z]{3}.*FUT$", "", s)   # strip futures expiry
    s = re.sub(r"\d.*$", "", s)                  # strip any trailing digits
    return s.strip("-").upper()


# ===================================================================
#  1) TECHNICAL ANALYSIS  (FYERS candles)
# ===================================================================
def analyze_technical(fyers, sym):
    """Returns dict: score(-1..+1), notes. EMA + RSI + MACD trend."""
    try:
        now = datetime.now()
        data = {
            "symbol": sym.strip(),
            "resolution": "15",
            "date_format": "1",
            "range_from": (now - timedelta(days=10)).strftime("%Y-%m-%d"),
            "range_to": now.strftime("%Y-%m-%d"),
            "cont_flag": "1",
        }
        res = fyers.history(data)
        if not (res and res.get("s") == "ok" and res.get("candles")):
            return {"score": None, "note": "no data", "last": None}

        df = pd.DataFrame(res["candles"], columns=["ts", "o", "h", "l", "c", "v"])
        if len(df) < 30:
            return {"score": None, "note": "few candles", "last": None}

        close = df["c"]
        ema20 = close.ewm(span=20, adjust=False).mean()
        ema50 = close.ewm(span=50, adjust=False).mean()

        # RSI(14)
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        rs = gain / loss.replace(0, 1e-9)
        rsi = 100 - (100 / (1 + rs))

        # MACD
        macd = close.ewm(span=12, adjust=False).mean() - close.ewm(span=26, adjust=False).mean()
        signal_line = macd.ewm(span=9, adjust=False).mean()

        last = float(close.iloc[-1])
        e20 = float(ema20.iloc[-1])
        e50 = float(ema50.iloc[-1])
        r = float(rsi.iloc[-1]) if pd.notna(rsi.iloc[-1]) else 50.0
        macd_hist = float(macd.iloc[-1] - signal_line.iloc[-1])

        votes = []
        votes.append(1 if last > e20 else -1)          # price vs EMA20
        votes.append(1 if e20 > e50 else -1)           # EMA trend
        votes.append(1 if macd_hist > 0 else -1)       # MACD momentum
        if r > 60:
            votes.append(1)
        elif r < 40:
            votes.append(-1)
        else:
            votes.append(0)

        score = sum(votes) / len(votes)                # -1 .. +1
        note = f"P>{'EMA20' if last>e20 else 'EMA20-'}, RSI={r:.0f}, MACD={'+' if macd_hist>0 else '-'}"
        return {"score": round(score, 2), "note": note, "last": round(last, 2)}
    except Exception as e:
        return {"score": None, "note": f"err:{e}", "last": None}


# ===================================================================
#  2) OPEN INTEREST ANALYSIS  (FYERS quotes)
# ===================================================================
def analyze_oi(fyers, sym):
    """Compares OI change vs price direction (price up + OI up = long buildup)."""
    try:
        q = fyers.quotes({"symbols": sym})
        if not (q and q.get("s") == "ok" and q.get("d")):
            return {"score": None, "note": "no oi"}
        v = q["d"][0].get("v", {})
        oi = v.get("oi")
        prev_oi = v.get("pdoi") or v.get("oipChange")
        chp = v.get("chp")  # percent change in price
        if oi is None or chp is None:
            return {"score": None, "note": "oi n/a"}

        oi_up = (prev_oi is not None and oi > prev_oi)
        price_up = chp > 0

        if price_up and oi_up:
            return {"score": 1.0, "note": "Long buildup"}
        if (not price_up) and oi_up:
            return {"score": -1.0, "note": "Short buildup"}
        if price_up and (not oi_up):
            return {"score": 0.5, "note": "Short covering"}
        if (not price_up) and (not oi_up):
            return {"score": -0.5, "note": "Long unwinding"}
        return {"score": 0.0, "note": "neutral"}
    except Exception as e:
        return {"score": None, "note": f"err:{e}"}


# ===================================================================
#  3) FUNDAMENTAL ANALYSIS  (screener.in - free)
# ===================================================================
@st.cache_data(ttl=21600)  # 6h cache, screener data changes slowly
def fetch_screener(base):
    """Scrape top ratios + recent profit growth from screener.in."""
    out = {"pe": None, "roce": None, "roe": None,
           "profit_growth": None, "sales_growth": None, "ok": False}
    try:
        s = requests.Session()
        s.headers.update(HEADERS)
        html = None
        for path in (f"{base}/consolidated/", f"{base}/"):
            try:
                r = s.get(f"https://www.screener.in/company/{path}", timeout=20)
                if r.status_code == 200 and "Stock P/E" in r.text:
                    html = r.text
                    break
            except Exception:
                continue
        if not html:
            return out

        # top ratio chips
        items = re.findall(r"<li[^>]*>(.*?)</li>", html, re.S)
        ratios = {}
        for it in items:
            name = re.search(r'class="name">\s*(.*?)\s*<', it, re.S)
            val = re.search(r'class="(?:number|value)"[^>]*>\s*([\d,\.\-]+)', it, re.S)
            if name and val:
                key = re.sub(r"\s+", " ", name.group(1)).strip()
                try:
                    ratios[key] = float(val.group(1).replace(",", ""))
                except Exception:
                    pass
        out["pe"] = ratios.get("Stock P/E")
        out["roce"] = ratios.get("ROCE")
        out["roe"] = ratios.get("ROE")

        # Compounded profit growth (TTM/1yr) from "Compounded Profit Growth" table
        mp = re.search(r"Compounded Profit Growth.*?</table>", html, re.S)
        if mp:
            pcts = re.findall(r">([\-\d]+)%<", mp.group(0))
            if pcts:
                out["profit_growth"] = float(pcts[-1])  # latest (1yr) value
        ms = re.search(r"Compounded Sales Growth.*?</table>", html, re.S)
        if ms:
            pcts = re.findall(r">([\-\d]+)%<", ms.group(0))
            if pcts:
                out["sales_growth"] = float(pcts[-1])

        out["ok"] = True
        return out
    except Exception:
        return out


def analyze_fundamental(base):
    """Score fundamentals: ROE/ROCE good + reasonable P/E = bullish."""
    f = fetch_screener(base)
    if not f["ok"]:
        return {"score": None, "note": "n/a", "data": f}
    votes = []
    if f["roe"] is not None:
        votes.append(1 if f["roe"] >= 15 else (-1 if f["roe"] < 8 else 0))
    if f["roce"] is not None:
        votes.append(1 if f["roce"] >= 15 else (-1 if f["roce"] < 8 else 0))
    if f["pe"] is not None:
        # very high PE = expensive (slightly bearish), moderate = ok
        votes.append(-1 if f["pe"] > 60 else (1 if f["pe"] < 25 else 0))
    if not votes:
        return {"score": None, "note": "n/a", "data": f}
    score = sum(votes) / len(votes)
    note = f"PE={f['pe']}, ROE={f['roe']}, ROCE={f['roce']}"
    return {"score": round(score, 2), "note": note, "data": f}


# ===================================================================
#  4) RESULTS / GROWTH ANALYSIS  (from same screener data)
# ===================================================================
def analyze_results(base):
    f = fetch_screener(base)
    if not f["ok"]:
        return {"score": None, "note": "n/a"}
    votes = []
    if f["profit_growth"] is not None:
        votes.append(1 if f["profit_growth"] > 10 else (-1 if f["profit_growth"] < 0 else 0))
    if f["sales_growth"] is not None:
        votes.append(1 if f["sales_growth"] > 10 else (-1 if f["sales_growth"] < 0 else 0))
    if not votes:
        return {"score": None, "note": "growth n/a"}
    score = sum(votes) / len(votes)
    note = f"ProfitGr={f['profit_growth']}%, SalesGr={f['sales_growth']}%"
    return {"score": round(score, 2), "note": note}


# ===================================================================
#  COMBINED WEIGHTED SCORING
# ===================================================================
def combine_scores(tech, oi, fund, result):
    """Weighted blend of available factors -> final score (-100..+100)."""
    parts = [
        ("technical", tech.get("score")),
        ("oi", oi.get("score")),
        ("fundamental", fund.get("score")),
        ("results", result.get("score")),
    ]
    total_w = 0
    acc = 0.0
    for key, sc in parts:
        if sc is not None:
            w = WEIGHTS[key]
            acc += sc * w
            total_w += w
    if total_w == 0:
        return None
    final = (acc / total_w) * 100  # normalize to -100..100 using available weights
    return round(final, 1)


def score_to_signal(score):
    if score is None:
        return "NO DATA"
    if score >= 35:
        return "STRONG BUY"
    if score >= 15:
        return "BUY"
    if score <= -35:
        return "STRONG SELL"
    if score <= -15:
        return "SELL"
    return "HOLD"


def scan_universe(fyers, symbols, do_fundamental=True, progress=None):
    rows = []
    n = len(symbols)
    for i, sym in enumerate(symbols):
        base = base_name_from_symbol(sym)
        is_commodity = sym.startswith("MCX:")
        is_index = any(b in base for b in INDEX_BASES)

        tech = analyze_technical(fyers, sym)
        oi = analyze_oi(fyers, sym)

        # Fundamentals/results only for equities (not index/commodity)
        if do_fundamental and not is_commodity and not is_index:
            fund = analyze_fundamental(base)
            result = analyze_results(base)
            time.sleep(0.15)  # be polite to screener.in
        else:
            fund = {"score": None, "note": "skip"}
            result = {"score": None, "note": "skip"}

        score = combine_scores(tech, oi, fund, result)
        signal = score_to_signal(score)

        if signal in ("STRONG BUY", "BUY"):
            send_telegram_msg(f"\U0001F680 {signal}: {sym} | score {score} | LTP {tech.get('last')}")
        elif signal in ("STRONG SELL", "SELL"):
            send_telegram_msg(f"\U0001F4C9 {signal}: {sym} | score {score} | LTP {tech.get('last')}")

        rows.append({
            "Symbol": sym,
            "LTP": tech.get("last"),
            "Tech": tech.get("score"),
            "OI": oi.get("score"),
            "Fund": fund.get("score"),
            "Results": result.get("score"),
            "Score": score,
            "Signal": signal,
            "Notes": f"{tech.get('note')} | OI:{oi.get('note')} | {fund.get('note')} | {result.get('note')}",
        })

        if progress is not None:
            progress.progress((i + 1) / n, text=f"Scanned {i+1}/{n}: {sym}")

    return pd.DataFrame(rows)


# ===================================================================
#  STREAMLIT UI
# ===================================================================
st.set_page_config(page_title="Trading Sathi", layout="wide")
st.title("\U0001F916 Trading Sathi - Multi-Factor F&O Scanner")
st.caption("Technical + OI + Fundamental + Results -> Weighted Score. "
           "Symbols auto-fetched live from NSE & FYERS (no hardcoding).")

for k, v in [("fyers", None), ("access_token", None), ("run_scan", False)]:
    if k not in st.session_state:
        st.session_state[k] = v


# ---------- LOGIN ----------
if st.session_state.fyers is None:
    st.info("Step 1: Login to FYERS and get auth code")
    if fyersModel is None:
        st.error("fyers_apiv3 library not installed. Run: pip install fyers-apiv3")
    elif not APP_ID or not SECRET_KEY or not REDIRECT_URL:
        st.error("Set FYERS_APP_ID, FYERS_SECRET_KEY and FYERS_REDIRECT_URL in Streamlit secrets.")
    else:
        try:
            session = fyersModel.SessionModel(
                client_id=APP_ID, secret_key=SECRET_KEY, redirect_uri=REDIRECT_URL,
                response_type="code", grant_type="authorization_code")
            login_url = session.generate_authcode()
            st.markdown(f"**[\U0001F449 Click here to Login to FYERS]({login_url})**")
        except Exception as e:
            st.error(f"Unable to generate FYERS login URL: {e}")

    auth_code = st.text_input("Step 2: Paste the auth_code here:")
    if st.button("Generate Access Token"):
        if not auth_code:
            st.error("Please paste the auth_code first.")
        else:
            try:
                session = fyersModel.SessionModel(
                    client_id=APP_ID, secret_key=SECRET_KEY, redirect_uri=REDIRECT_URL,
                    response_type="code", grant_type="authorization_code")
                session.set_token(auth_code)
                response = session.generate_token()
                if "access_token" in response:
                    token = response["access_token"]
                    st.session_state.access_token = token
                    st.session_state.fyers = fyersModel.FyersModel(
                        client_id=APP_ID, token=token, log_path="")
                    st.success("Login Successful!")
                    st.rerun()
                else:
                    st.error(f"Token generation failed: {response}")
            except Exception as e:
                st.error(f"Login failed: {e}")


# ---------- DASHBOARD ----------
else:
    st.success("\u2705 Connected to FYERS")

    with st.spinner("Loading symbol universe from NSE & FYERS..."):
        uni = build_universe()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("F&O Stocks", len(uni["stocks"]))
    c2.metric("Index Futures", len(uni["indices"]))
    c3.metric("Commodities", len(uni["commodities"]))
    c4.metric("Total", len(uni["all"]))

    if not uni["stocks"]:
        st.warning("Could not fetch live F&O list from NSE (may be temporarily blocked). "
                   "You can still paste symbols manually below.")

    st.subheader("Scan Settings")
    colA, colB, colC = st.columns(3)
    with colA:
        scope = st.selectbox(
            "Universe to scan",
            ["Everything (Stocks + Index + Commodity)", "Only F&O Stocks",
             "Only Index Futures", "Only Commodities"])
    with colB:
        do_fund = st.checkbox("Include Fundamental + Results (slower)", value=True)
    with colC:
        limit = st.number_input("Max symbols (0 = all)", min_value=0, value=25, step=5)

    if scope == "Only F&O Stocks":
        chosen = uni["stocks"]
    elif scope == "Only Index Futures":
        chosen = uni["indices"]
    elif scope == "Only Commodities":
        chosen = uni["commodities"]
    else:
        chosen = uni["all"]

    st.subheader("Editable Symbol List")
    txt = st.text_area("One symbol per line (auto-filled, you can edit)",
                       value="\n".join(chosen), height=260)
    symbols = [s.strip() for s in txt.split("\n") if s.strip()]
    if limit and limit > 0:
        symbols = symbols[:limit]
    st.write(f"Symbols queued for scan: **{len(symbols)}**")

    cscan, clog = st.columns(2)
    with cscan:
        if st.button("\U0001F50D Run Multi-Factor Scan", type="primary"):
            st.session_state.run_scan = True
    with clog:
        if st.button("Logout"):
            for k in ("fyers", "access_token", "run_scan"):
                st.session_state[k] = None if k != "run_scan" else False
            st.rerun()

    if st.session_state.run_scan:
        st.session_state.run_scan = False
        if not symbols:
            st.error("No symbols to scan.")
        else:
            prog = st.progress(0.0, text="Starting scan...")
            df = scan_universe(st.session_state.fyers, symbols,
                               do_fundamental=do_fund, progress=prog)
            prog.empty()

            st.subheader("Scan Results (sorted by score)")
            if not df.empty:
                df_sorted = df.sort_values("Score", ascending=False, na_position="last")
                st.dataframe(df_sorted, use_container_width=True, hide_index=True)

                buy = df_sorted[df_sorted["Signal"].isin(["STRONG BUY", "BUY"])]
                sell = df_sorted[df_sorted["Signal"].isin(["STRONG SELL", "SELL"])]
                colb, cols = st.columns(2)
                with colb:
                    st.subheader(f"\U0001F7E2 BUY ({len(buy)})")
                    st.dataframe(buy, use_container_width=True, hide_index=True)
                with cols:
                    st.subheader(f"\U0001F534 SELL ({len(sell)})")
                    st.dataframe(sell, use_container_width=True, hide_index=True)

                st.download_button("Download results CSV",
                                   df_sorted.to_csv(index=False).encode(),
                                   "scan_results.csv", "text/csv")
            else:
                st.warning("No results returned.")

    with st.expander("\u2139\ufe0f How the signal works (scoring logic)"):
        st.markdown(f"""
Each factor produces a score from **-1 (bearish)** to **+1 (bullish)**, then they
are blended using these weights (only available factors count):

| Factor | Weight | What it checks |
|---|---|---|
| **Technical** | {WEIGHTS['technical']}% | Price vs EMA20/EMA50, RSI(14), MACD momentum |
| **Open Interest** | {WEIGHTS['oi']}% | Long buildup / Short buildup / Covering / Unwinding |
| **Fundamental** | {WEIGHTS['fundamental']}% | ROE, ROCE, P/E (screener.in) |
| **Results/Growth** | {WEIGHTS['results']}% | Profit & Sales growth (screener.in) |

Final score is normalized to **-100 .. +100**:
- **>= 35** -> STRONG BUY  &nbsp; | &nbsp; **15 to 35** -> BUY
- **-15 to 15** -> HOLD
- **-35 to -15** -> SELL &nbsp; | &nbsp; **<= -35** -> STRONG SELL

Index & commodity rows skip Fundamental/Results (not applicable) and score on
Technical + OI only.
        """)
