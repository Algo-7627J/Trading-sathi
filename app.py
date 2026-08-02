import streamlit as st
import pandas as pd

try:
    from fyers_apiv3 import fyersModel
except Exception:
    fyersModel = None

# ====================== BULLETPROOF CONFIG + SECRETS LOADING (FIXED FOR CLOUD) ======================
# This block guarantees the variables ALWAYS exist, even if everything fails.

import os

# === SAFE DEFAULTS (will be overwritten by secrets) ===
APP_ID = "YOUR_FYERS_APP_ID"
SECRET_KEY = "YOUR_FYERS_SECRET_KEY"
REDIRECT_URL = "https://your-redirect-url.com"

TIMEFRAME_OPTIONS = {
    "1m": "1m", "5m": "5m", "15m": "15m",
    "1h": "60m", "1d": "1d", "1w": "1w", "1M": "1M"
}
SECTOR_TIMEFRAMES = {
    "1D (Intraday)": "1d",
    "1W": "1w",
    "2W": "2w",
    "1 Month": "1M"
}

# 1. Load from config.py (only if real values)
try:
    from config import (
        APP_ID as _a, SECRET_KEY as _s, REDIRECT_URL as _r,
        TIMEFRAME_OPTIONS as _t, SECTOR_TIMEFRAMES as _se
    )
    if _a and "YOUR_FYERS" not in str(_a).upper(): APP_ID = _a
    if _s and "YOUR_FYERS" not in str(_s).upper(): SECRET_KEY = _s
    if _r and "your-redirect" not in str(_r).lower(): REDIRECT_URL = _r
    if _t: TIMEFRAME_OPTIONS = _t
    if _se: SECTOR_TIMEFRAMES = _se
except Exception:
    pass

# 2. Load from Streamlit Secrets - FINAL ULTRA-ROBUST LOADER (catches all formats)
_secrets_source = "defaults"

def _clean_secret_url(v):
    """'[https://x](https://x)' -> 'https://x' — people paste markdown links into secrets."""
    v = str(v).strip()
    if v.startswith("[") and "](" in v and v.endswith(")"):
        return v.split("](", 1)[1][:-1]
    return v

def _load_from_secrets():
    global APP_ID, SECRET_KEY, REDIRECT_URL
    if not (hasattr(st, "secrets") and st.secrets):
        return "no_secrets_object"

    sec = st.secrets
    source = "defaults"

    # Case-insensitive, section-agnostic, FYERS_-prefix-tolerant secret reader.
    # Accepts [fyers]/[FYERS], APP_ID/app_id/FYERS_APP_ID etc.
    def get_val(key):
        kn = str(key).strip().upper().replace("-", "_")

        def norm(s):
            s = str(s).strip().upper().replace("-", "_")
            return s[6:] if s.startswith("FYERS_") else s

        # 1) search ALL sections (any name, any case)
        try:
            for section_name in list(sec.keys()):
                try:
                    sub = sec[section_name]
                except Exception:
                    continue
                try:
                    for k2 in list(sub.keys()):
                        if norm(k2) == kn and sub[k2]:
                            return str(sub[k2]).strip(), f"[{section_name}].{k2}"
                except Exception:
                    pass
                try:
                    for a in dir(sub):
                        if not a.startswith("_") and norm(a) == kn:
                            v = getattr(sub, a, None)
                            if v:
                                return str(v).strip(), f"[{section_name}].{a}"
                except Exception:
                    pass
        except Exception:
            pass

        # 2) flat top-level keys (string values only, skip section dicts)
        try:
            for k2 in list(sec.keys()):
                v = sec[k2]
                if norm(k2) == kn and isinstance(v, str) and v:
                    return v.strip(), f"flat.{k2}"
        except Exception:
            pass

        return None, None

    val, src = get_val("APP_ID")
    if val and "YOUR" not in val.upper() and "PLACEHOLDER" not in val.upper():
        APP_ID = val
        source = src

    val, src = get_val("SECRET_KEY")
    if val and "YOUR" not in val.upper() and "PLACEHOLDER" not in val.upper():
        SECRET_KEY = val
        source = src

    val, src = get_val("REDIRECT_URL")
    if val:
        val = _clean_secret_url(val)
    if val and "your-redirect" not in val.lower() and "PLACEHOLDER" not in val.upper():
        REDIRECT_URL = val
        source = src

    return source

try:
    _secrets_source = _load_from_secrets()
except Exception:
    _secrets_source = "error"
# ====================== END BULLETPROOF CONFIG ======================

import time as _time
from services import build_universe
from analysis import scan_universe
from next_day import scan_next_day
from commodities import get_metal_report
from storage import ensure_data_files, save_latest_scan, append_signal_history, load_watchlist
from ui_helpers import (
    inject_custom_css, render_title, section_label, render_stat_row,
    render_watchlist_manager, render_next_day_results,
    sort_by_priority, render_compact_table_view, render_compact_cards_view,
    render_sector_card, render_bull_bear_sections, render_count_tile,
    render_sector_stock_row, render_footer, render_commodity_panel
)
from sectors import add_sector_column, get_sector_timeframe_stats, get_top_stocks_by_sector

st.set_page_config(page_title="RAO SAHAB", layout="wide", page_icon="📈")
inject_custom_css()
ensure_data_files()


# ====================== SESSION STATE ======================
defaults = {
    "fyers": None,
    "access_token": None,
    "run_scan": False,
    "last_scan_df": None,
    "run_next_day_scan": False,
    "next_day_df": None,
    "show_strong_buy": False,
    "show_strong_sell": False,
    "selected_bullish_sector": None,
    "selected_bearish_sector": None,
    "sector_timeframe": "1D (Intraday)",
    "watchlist": [],
}

for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

df = st.session_state.get("last_scan_df")

render_title("RAO SAHAB", "Intraday &amp; Next-Day Scanner", connected=st.session_state.fyers is not None)

# ====================== LOGIN SECTION ======================
if st.session_state.fyers is None:
    _sp1, _mid, _sp2 = st.columns([1, 1.6, 1])
    with _mid:
        with st.container(border=True):
            st.markdown("### 🔐 Connect to FYERS")
            st.caption("Login with your FYERS account to unlock live intraday & next-day scans.")

            if fyersModel is None:
                st.error("`fyers_apiv3` not installed. Add it to requirements.txt")
            else:
                try:
                    session = fyersModel.SessionModel(
                        client_id=APP_ID,
                        secret_key=SECRET_KEY,
                        redirect_uri=REDIRECT_URL,
                        response_type="code",
                        grant_type="authorization_code"
                    )
                    login_url = session.generate_authcode()
                    st.link_button("🚀 Login to FYERS", login_url, type="primary", use_container_width=True)
                except Exception as e:
                    st.error(f"Error generating login URL: {e}")

            auth_code = st.text_input("Paste auth_code here", label_visibility="collapsed", placeholder="Paste your auth_code…")

            if st.button("Generate Access Token", type="primary", use_container_width=True):
                if not auth_code:
                    st.error("Please paste the auth_code first.")
                else:
                    try:
                        session = fyersModel.SessionModel(
                            client_id=APP_ID,
                            secret_key=SECRET_KEY,
                            redirect_uri=REDIRECT_URL,
                            response_type="code",
                            grant_type="authorization_code"
                        )
                        session.set_token(auth_code)
                        response = session.generate_token()

                        if response and isinstance(response, dict) and "access_token" in response:
                            token = response["access_token"]
                            st.session_state.fyers = fyersModel.FyersModel(client_id=APP_ID, token=token, log_path="")
                            st.success("Login successful!")
                            st.rerun()
                        else:
                            if isinstance(response, dict):
                                code = response.get("code")
                                msg = response.get("message", "").lower()
                                if "invalid app id hash" in msg or code == -5:
                                    st.error("❌ **Invalid App ID Hash (Code: -5)** — check APP_ID / SECRET_KEY in Secrets, and confirm the Redirect URL exactly matches your FYERS app settings.")
                                else:
                                    st.error(f"Token generation failed. Code: {code}")
                                    st.write("Response:", response)
                            else:
                                st.error("Token generation failed. Unexpected response.")
                                st.write("Response:", response)
                    except Exception as e:
                        st.error(f"Login failed: {str(e)}")

        # ---- hidden diagnostics (only when user needs help) ----
        with st.expander("🛠️ Login not working? → Diagnostics & Fix"):
            def _loaded(val, min_len):
                v = str(val or "")
                return len(v) >= min_len and "YOUR" not in v.upper() and "PLACEHOLDER" not in v.upper() and "your-redirect" not in v.lower()

            id_ok = _loaded(APP_ID, 5)
            sk_ok = _loaded(SECRET_KEY, 10)
            ru_ok = _loaded(REDIRECT_URL, 10)

            _aid = (str(APP_ID)[:4] + "…" + str(APP_ID)[-4:] + f"  ({len(str(APP_ID))} chars)") if id_ok else "❌ NOT LOADED"
            _sk = f"✅ Loaded ({len(str(SECRET_KEY))} chars)" if sk_ok else "❌ NOT LOADED"
            _ru = (REDIRECT_URL + f"  ({len(str(REDIRECT_URL))} chars)") if ru_ok else "❌ NOT LOADED"

            st.markdown("**What the app currently sees:**")
            st.write(f"1️⃣ APP_ID → `{_aid}`")
            st.write(f"2️⃣ SECRET_KEY → {_sk}")
            st.write(f"3️⃣ REDIRECT_URL → `{_ru}`")
            st.divider()

            if not (id_ok and sk_ok and ru_ok):
                st.error("Secrets are NOT being read. Almost always one of these:")
                st.markdown("""
                **A) App was not rebooted after saving Secrets** → Manage app → **⋮ (top-right) → Reboot app**
                **B) TOML format issue** — in Manage app → Settings → **Secrets**, paste EXACTLY this (with your real values):
                """)
                st.code("""[fyers]
APP_ID = "ABCD1234-100"
SECRET_KEY = "xxxxxx"
REDIRECT_URL = "https://trading-sathi-o6qgdjpsf6rcfuapptyzzt4.streamlit.app\"""", language="toml")
                st.markdown("""
                - Keys must be **UPPERCASE** exactly: `APP_ID`, `SECRET_KEY`, `REDIRECT_URL`
                - Values in **normal double quotes** `" "` — not smart quotes `“ ”` (typing straight in the box is safe)
                - First line must be exactly `[fyers]`
                - No spaces inside the App ID / Secret Key
                **C) REDIRECT_URL must match your FYERS app settings letter-for-letter** (myapi.fyers.in → your app → Redirect URL)
                """)
            else:
                st.success("✅ All 3 secrets loaded correctly!")
                st.markdown("""
                If login STILL fails with **-5**, the values themselves are wrong:
                - Re-copy **App ID** & **Secret Key** from [myapi.fyers.in](https://myapi.fyers.in/) (check for extra spaces)
                - Confirm the FYERS app **Status = Active**
                - Confirm **Redirect URL** in FYERS = the one shown in line 3️⃣ above
                - Use a **fresh auth_code** (Login → paste → Generate immediately; codes die in seconds)
                """)

# ====================== MAIN APP ======================
else:
    try:
        with st.sidebar:
            st.markdown("### ⚙️ Settings")

            # ====================== UNIVERSE SETTINGS ======================
            use_live = st.checkbox("🚀 Use Live NSE F&O", value=True, key="use_live_universe")

            if st.button("🔄 Refresh Universe", use_container_width=True):
                st.session_state.force_refresh_universe = True

            uni = build_universe(use_live=use_live, force_refresh=st.session_state.get("force_refresh_universe", False))

            if st.session_state.get("force_refresh_universe"):
                st.session_state.force_refresh_universe = False

            source = uni.get("source", "unknown")
            count = uni.get("count", len(uni["stocks"]))

            if "live" in source.lower():
                st.success(f"✅ Live NSE: {count} F&O stocks")
            elif "cached" in source.lower():
                st.info(f"📦 Cached Live: {count} stocks")
            else:
                st.warning(f"📋 Hardcoded: {count} stocks")

            st.caption(f"Source: {source}")

            st.divider()
            render_watchlist_manager(uni["all"])
            st.divider()

            if st.button("Logout", use_container_width=True):
                st.session_state.fyers = None
                st.rerun()

        render_stat_row([
            {"label": "F&O Stocks", "value": len(uni["stocks"])},
            {"label": "Index", "value": len(uni["indices"])},
            {"label": "Commodities", "value": len(uni["commodities"])},
            {"label": "Total Universe", "value": len(uni["all"])},
        ])

        watchlist = load_watchlist()
        tab1, tab2, tab3, tab4 = st.tabs(["⚡ Intraday Scanner", "📅 Next-Day Outlook", "🏭 Sector Trend", "🥇 Gold & Silver"])

        # ==================== TAB 1: INTRADAY ====================
        with tab1:
            section_label("Scan Settings")
            c1, c2, c3, c4, c5 = st.columns(5)
            with c1:
                scope = st.selectbox("Universe", ["Everything", "Only F&O Stocks", "Only Index", "Only Commodities", "Only Watchlist"])
            with c2:
                timeframe_mode = st.selectbox("Timeframe", list(TIMEFRAME_OPTIONS.keys()), index=2)
            with c3:
                include_news = st.checkbox("News", value=True)
            with c4:
                include_fund = st.checkbox("Fundamentals", value=False)
            with c5:
                limit = st.number_input("Max symbols (0 = All)", min_value=0, value=0, step=5)

            if scope == "Only F&O Stocks":
                chosen = uni["stocks"]
            elif scope == "Only Index":
                chosen = uni["indices"]
            elif scope == "Only Commodities":
                chosen = uni["commodities"]
            elif scope == "Only Watchlist":
                chosen = watchlist if watchlist else uni["all"]
            else:
                chosen = uni["all"]

            with st.expander("✏️ Edit Symbols"):
                txt = st.text_area("Symbols", value="\n".join(chosen), height=160, label_visibility="collapsed")
            symbols = [s.strip() for s in txt.split("\n") if s.strip()]
            if limit > 0:
                symbols = symbols[:limit]

            if st.button("⚡ Run Scan", type="primary", use_container_width=True):
                st.session_state.run_scan = True

            if st.session_state.run_scan:
                st.session_state.run_scan = False
                if symbols:
                    prog = st.progress(0.0, text="Scanning…")
                    result = scan_universe(
                        st.session_state.fyers,
                        symbols,
                        timeframe_mode=timeframe_mode,
                        include_news=include_news,
                        include_fundamental=include_fund,
                        progress=prog
                    )
                    prog.empty()
                    save_latest_scan(result)
                    append_signal_history(result)
                    st.session_state.last_scan_df = result
                    df = result

            if df is not None and not df.empty:
                df_sorted = add_sector_column(df)
                section_label("📊 Scan Results")
                st.caption("💡 Click any stock card to open its live chart on FYERS ↗")

                strong_buy = df_sorted[df_sorted["Signal"].str.contains("Buy", case=False, na=False)]
                strong_sell = df_sorted[df_sorted["Signal"].str.contains("Sell", case=False, na=False)]
                neutral = df_sorted[~df_sorted["Signal"].str.contains("Buy|Sell", case=False, na=False)]

                t1, t2, t3c = st.columns(3)
                with t1:
                    render_count_tile("BULLISH SIGNALS", len(strong_buy), "green", "🟢")
                    if st.button("View List ▸", key="view_buy", use_container_width=True):
                        st.session_state.show_strong_buy = True
                        st.session_state.show_strong_sell = False
                with t2:
                    render_count_tile("BEARISH SIGNALS", len(strong_sell), "red", "🔴")
                    if st.button("View List ▸", key="view_sell", use_container_width=True):
                        st.session_state.show_strong_sell = True
                        st.session_state.show_strong_buy = False
                with t3c:
                    render_count_tile("NEUTRAL", len(neutral), "gray", "⚪")

                if st.session_state.show_strong_buy or st.session_state.show_strong_sell:
                    selected = strong_buy if st.session_state.show_strong_buy else strong_sell
                    head = "🟢 All Bullish Signals" if st.session_state.show_strong_buy else "🔴 All Bearish Signals"
                    section_label(head)
                    render_compact_cards_view(selected)
                    if st.button("← Back to Overview", use_container_width=True):
                        st.session_state.show_strong_buy = False
                        st.session_state.show_strong_sell = False
                        st.rerun()
                else:
                    # ===== 🟢 MOST BULLISH / 🔴 MOST BEARISH (CARD VIEW) =====
                    render_bull_bear_sections(df_sorted, top_n=6, key_prefix="id")

                    st.divider()
                    section_label("All Results")
                    view = st.radio("View Mode", ["Table", "Cards"], horizontal=True, key="intraday_view", label_visibility="collapsed")
                    if view == "Table":
                        render_compact_table_view(df_sorted)
                    else:
                        render_compact_cards_view(df_sorted)

                    st.download_button(
                        "⬇️ Download CSV",
                        df_sorted.to_csv(index=False).encode(),
                        "intraday_results.csv",
                        "text/csv"
                    )

        # ==================== TAB 2: NEXT-DAY OUTLOOK ====================
        with tab2:
            section_label("Next-Day Outlook Settings")
            nd1, nd2 = st.columns([2, 1])
            with nd1:
                nd_scope = st.selectbox(
                    "Universe",
                    ["Everything", "Only F&O Stocks", "Only Index", "Only Commodities", "Only Watchlist"],
                    key="nd_scope"
                )
            with nd2:
                nd_limit = st.number_input("Max symbols (0 = All)", min_value=0, value=0, step=5, key="nd_limit")

            if nd_scope == "Only F&O Stocks":
                nd_chosen = uni["stocks"]
            elif nd_scope == "Only Index":
                nd_chosen = uni["indices"]
            elif nd_scope == "Only Commodities":
                nd_chosen = uni["commodities"]
            elif nd_scope == "Only Watchlist":
                nd_chosen = watchlist if watchlist else uni["all"]
            else:
                nd_chosen = uni["all"]

            with st.expander("✏️ Edit Symbols"):
                nd_txt = st.text_area(
                    "Symbols",
                    value="\n".join(nd_chosen),
                    height=160,
                    label_visibility="collapsed",
                    key="nd_symbols"
                )
            nd_symbols = [s.strip() for s in nd_txt.split("\n") if s.strip()]
            if nd_limit > 0:
                nd_symbols = nd_symbols[:nd_limit]

            if st.button("📅 Run Next-Day Analysis", type="primary", use_container_width=True, key="run_next_day"):
                st.session_state.run_next_day_scan = True

            if st.session_state.run_next_day_scan:
                st.session_state.run_next_day_scan = False
                if nd_symbols:
                    prog = st.progress(0.0, text="Analyzing next-day outlook…")
                    nd_result = scan_next_day(st.session_state.fyers, nd_symbols, progress=prog)
                    prog.empty()
                    st.session_state.next_day_df = nd_result

            nd_df = st.session_state.get("next_day_df")
            if nd_df is not None and not nd_df.empty:
                nd_df = add_sector_column(nd_df)
                section_label("📅 Next-Day Results")
                st.caption("💡 Click any stock card to open its live chart on FYERS ↗")

                bias_col = "Bias" if "Bias" in nd_df.columns else "Outlook"
                nd_bull = nd_df[nd_df[bias_col].astype(str).str.contains("Bullish", case=False, na=False)]
                nd_bear = nd_df[nd_df[bias_col].astype(str).str.contains("Bearish", case=False, na=False)]
                nd_neu = nd_df[~nd_df[bias_col].astype(str).str.contains("Bullish|Bearish", case=False, na=False)]

                n1, n2, n3 = st.columns(3)
                with n1:
                    render_count_tile("BULLISH TOMORROW", len(nd_bull), "green", "🟢")
                with n2:
                    render_count_tile("BEARISH TOMORROW", len(nd_bear), "red", "🔴")
                with n3:
                    render_count_tile("NEUTRAL", len(nd_neu), "gray", "⚪")

                # ===== 🟢 MOST BULLISH / 🔴 MOST BEARISH (CARD VIEW) =====
                render_bull_bear_sections(nd_df, top_n=6, key_prefix="nd")

                st.divider()
                section_label("All Next-Day Results")
                render_next_day_results(nd_df)
                st.download_button(
                    "⬇️ Download Next-Day CSV",
                    nd_df.to_csv(index=False).encode(),
                    "next_day_results.csv",
                    "text/csv"
                )
            elif nd_df is not None:
                st.info("No results found.")

        # ==================== TAB 3: SECTOR TREND ====================
        with tab3:
            section_label("Sector Trend Analysis")

            col_tf, col_info = st.columns([1, 2])
            with col_tf:
                selected_tf = st.selectbox(
                    "Select Timeframe",
                    list(SECTOR_TIMEFRAMES.keys()),
                    index=0,
                    key="sector_tf_select"
                )
                st.session_state.sector_timeframe = selected_tf

            with col_info:
                st.caption("📌 Timeframes affect how sector performance is calculated (simulated bias based on historical patterns).")

            with st.expander("📖 How are Most Bullish / Most Bearish Sectors calculated?"):
                st.markdown("""
                **Logic used:**
                - **Most Bullish Sectors**: Highest percentage of stocks showing **Buy / Strong Buy** signals + highest average Score.
                - **Most Bearish Sectors**: Highest percentage of stocks showing **Sell / Strong Bearish** signals.
                - **Timeframe impact**: Different timeframes apply different weighting and simulated momentum:
                  - **1D (Intraday)**: Based on current scan momentum.
                  - **1W / 2W**: Slightly stronger or reversed bias depending on recent weekly movement.
                  - **1 Month**: Long-term trend bias.
                - Data source: Latest Intraday scan (run Tab 1 first). Timeframe selection adjusts the weights.
                """)

            base_df = st.session_state.get("last_scan_df")
            if base_df is None or base_df.empty:
                st.info("⚠️ Please run an **Intraday Scan** (Tab 1) first to see Sector Trend analysis.")
            else:
                base_df = add_sector_column(base_df)

                tf_key = SECTOR_TIMEFRAMES.get(selected_tf, "1d")
                sector_data = get_sector_timeframe_stats(base_df, timeframe=tf_key)

                if sector_data.empty:
                    st.warning("No sector data available.")
                else:
                    st.markdown(f"#### 🟢 Most Bullish Sectors <small style='color:#7C7E8C'>({selected_tf})</small>", unsafe_allow_html=True)
                    bullish_sectors = sector_data.sort_values("Bullish %", ascending=False).head(6)
                    col_bull = st.columns(2)
                    for idx, (_, row) in enumerate(bullish_sectors.iterrows()):
                        with col_bull[idx % 2]:
                            sector_name = row["Sector"]
                            if st.button(f"📈 {sector_name}", key=f"bullish_{sector_name}", use_container_width=True):
                                st.session_state.selected_bullish_sector = sector_name
                                st.session_state.selected_bearish_sector = None

                    st.markdown(f"#### 🔴 Most Bearish Sectors <small style='color:#7C7E8C'>({selected_tf})</small>", unsafe_allow_html=True)
                    bearish_sectors = sector_data.sort_values("Bearish %", ascending=False).head(6)
                    col_bear = st.columns(2)
                    for idx, (_, row) in enumerate(bearish_sectors.iterrows()):
                        with col_bear[idx % 2]:
                            sector_name = row["Sector"]
                            if st.button(f"📉 {sector_name}", key=f"bearish_{sector_name}", use_container_width=True):
                                st.session_state.selected_bearish_sector = sector_name
                                st.session_state.selected_bullish_sector = None

                    if st.session_state.selected_bullish_sector:
                        st.markdown(f"#### 🟢 Top 10 Most Bullish Stocks in **{st.session_state.selected_bullish_sector}** ({selected_tf})")
                        top_bull = get_top_stocks_by_sector(
                            base_df,
                            st.session_state.selected_bullish_sector,
                            bias="bullish",
                            top_n=10
                        )
                        if not top_bull.empty:
                            for _, row in top_bull.iterrows():
                                st.markdown(
                                    render_sector_stock_row(row["Symbol"], row.get("Score", 0), row.get("LTP", "N/A"), row.get("Signal", ""), True),
                                    unsafe_allow_html=True
                                )
                        else:
                            st.caption("No bullish stocks found in this sector for the current scan.")

                        if st.button("Clear Selection", key="clear_bull"):
                            st.session_state.selected_bullish_sector = None
                            st.rerun()

                    if st.session_state.selected_bearish_sector:
                        st.markdown(f"#### 🔴 Top 10 Most Bearish Stocks in **{st.session_state.selected_bearish_sector}** ({selected_tf})")
                        top_bear = get_top_stocks_by_sector(
                            base_df,
                            st.session_state.selected_bearish_sector,
                            bias="bearish",
                            top_n=10
                        )
                        if not top_bear.empty:
                            for _, row in top_bear.iterrows():
                                st.markdown(
                                    render_sector_stock_row(row["Symbol"], row.get("Score", 0), row.get("LTP", "N/A"), row.get("Signal", ""), False),
                                    unsafe_allow_html=True
                                )
                        else:
                            st.caption("No bearish stocks found in this sector for the current scan.")

                        if st.button("Clear Selection", key="clear_bear"):
                            st.session_state.selected_bearish_sector = None
                            st.rerun()

                    st.divider()
                    st.markdown(f"#### 📊 Sector Summary ({selected_tf})")
                    st.dataframe(
                        sector_data[["Sector", "Total", "Bullish", "Bullish %", "Bearish", "Bearish %", "Avg_Score"]],
                        use_container_width=True,
                        hide_index=True
                    )

        # ==================== TAB 4: GOLD & SILVER ====================
        with tab4:
            section_label("🥇 Gold & Silver — Multi-Timeframe Forecast")

            cbtn, cinfo = st.columns([1, 3])
            with cbtn:
                if st.button("🔄 Refresh Data", key="metal_refresh", use_container_width=True):
                    st.session_state.pop("metal_cache", None)
            with cinfo:
                st.caption("Live COMEX futures data (Yahoo Finance) • Prices in USD/oz • Auto-cached for 15 min. "
                           "Momentum = EMA trend + MACD + RSI + volume + 16-pattern detection, then 20-day breakout logic.")

            mc = st.session_state.get("metal_cache")
            if not mc or _time.time() - mc["ts"] > 900:
                with st.spinner("Fetching Gold & Silver market data…"):
                    mc = {
                        "ts": _time.time(),
                        "GOLD": get_metal_report("GOLD"),
                        "SILVER": get_metal_report("SILVER"),
                    }
                st.session_state.metal_cache = mc

            col_gold, col_silver = st.columns(2, gap="large")
            with col_gold:
                render_commodity_panel(mc["GOLD"])
            with col_silver:
                render_commodity_panel(mc["SILVER"])

            st.info("💡 **How to read this:** The strongest trades happen when all 5 timeframe arrows point the same way "
                    "**and** price breaks out of the 20-day range on above-average volume (🚀 Confirmed). "
                    "Directional confluence ≠ certainty — always use your own risk management.")

    except Exception as e:
        st.error(f"App Error: {e}")
        st.exception(e)

render_footer()
