import streamlit as st
import pandas as pd

try:
    from fyers_apiv3 import fyersModel
except Exception:
    fyersModel = None

try:
    from streamlit_autorefresh import st_autorefresh
except Exception:
    st_autorefresh = None

from config import APP_ID, SECRET_KEY, REDIRECT_URL, TIMEFRAME_OPTIONS
from services import build_universe
from analysis import scan_universe
from storage import ensure_data_files, save_latest_scan, append_signal_history, load_watchlist
from ui_helpers import (
    inject_custom_css,
    render_summary_cards,
    display_signal_table,
    render_sector_tabs,
    render_watchlist_manager,
    render_watchlist_results,
    render_signal_bar_chart,
    sort_by_priority,
)
from sectors import add_sector_column

st.set_page_config(page_title="Trading Sathi", layout="wide", page_icon="🤖")
inject_custom_css()
ensure_data_files()

st.title("🤖 Trading Sathi - Intraday + 2 Day Smart Scanner")
st.caption("Technical + Momentum + Volume + Multi-candle Patterns + OI + News + Fundamentals + Sector View + Multi-Timeframe Confirmation")

for k, v in [("fyers", None), ("access_token", None), ("run_scan", False), ("last_scan_df", None)]:
    if k not in st.session_state:
        st.session_state[k] = v

if st.session_state.fyers is None:
    st.info("Step 1: Login to FYERS and get auth code")

    if fyersModel is None:
        st.error("fyers_apiv3 library not installed. Add it in requirements.txt")
    elif not APP_ID or not SECRET_KEY or not REDIRECT_URL:
        st.error("Set FYERS_APP_ID, FYERS_SECRET_KEY and FYERS_REDIRECT_URL in Streamlit secrets.")
    else:
        try:
            session = fyersModel.SessionModel(
                client_id=APP_ID,
                secret_key=SECRET_KEY,
                redirect_uri=REDIRECT_URL,
                response_type="code",
                grant_type="authorization_code",
            )
            login_url = session.generate_authcode()
            st.markdown(f"**[👉 Click here to Login to FYERS]({login_url})**")
        except Exception as e:
            st.error(f"Unable to generate FYERS login URL: {e}")

    auth_code = st.text_input("Step 2: Paste the auth_code here:")
    if st.button("Generate Access Token"):
        if not auth_code:
            st.error("Please paste the auth_code first.")
        else:
            try:
                session = fyersModel.SessionModel(
                    client_id=APP_ID,
                    secret_key=SECRET_KEY,
                    redirect_uri=REDIRECT_URL,
                    response_type="code",
                    grant_type="authorization_code",
                )
                session.set_token(auth_code)
                response = session.generate_token()
                if "access_token" in response:
                    token = response["access_token"]
                    st.session_state.access_token = token
                    st.session_state.fyers = fyersModel.FyersModel(client_id=APP_ID, token=token, log_path="")
                    st.success("Login Successful!")
                    st.rerun()
                else:
                    st.error(f"Token generation failed: {response}")
            except Exception as e:
                st.error(f"Login failed: {e}")

else:
    st.success("✅ Connected to FYERS")

    with st.sidebar:
        st.header("⚙️ Settings")

        with st.spinner("Loading symbol universe from NSE & FYERS..."):
            uni = build_universe()

        render_watchlist_manager(uni["all"])

        st.markdown("---")
        st.markdown("#### 🔄 Live Auto-Refresh")
        auto_refresh_on = st.checkbox("Enable auto-refresh scan", value=False)
        refresh_interval = st.number_input(
            "Refresh every (seconds)", min_value=30, max_value=1800, value=180, step=30,
            disabled=not auto_refresh_on,
        )
        if auto_refresh_on:
            if st_autorefresh is not None:
                st_autorefresh(interval=int(refresh_interval * 1000), key="ts_autorefresh")
                st.caption(f"Auto-refreshing every {refresh_interval}s")
            else:
                st.warning("Install `streamlit-autorefresh` to enable this (see requirements.txt).")

        if st.button("Logout"):
            for k in ("fyers", "access_token", "run_scan"):
                st.session_state[k] = None if k != "run_scan" else False
            st.rerun()

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("F&O Stocks", len(uni["stocks"]))
    m2.metric("Index Futures", len(uni["indices"]))
    m3.metric("Commodities", len(uni["commodities"]))
    m4.metric("Total", len(uni["all"]))

    st.subheader("Scan Settings")
    c1, c2, c3, c4, c5 = st.columns(5)

    with c1:
        scope = st.selectbox(
            "Universe to scan",
            [
                "Everything (Stocks + Index + Commodity)",
                "Only F&O Stocks",
                "Only Index Futures",
                "Only Commodities",
                "Only Watchlist",
            ],
        )

    with c2:
        timeframe_mode = st.selectbox(
            "Timeframe Mode",
            list(TIMEFRAME_OPTIONS.keys()),
            index=2
        )

    with c3:
        include_news = st.checkbox("Include News", value=True)

    with c4:
        include_fund = st.checkbox("Include Fundamentals/Results", value=False)

    with c5:
        limit = st.number_input("Max symbols (0 = all)", min_value=0, value=25, step=5)

    watchlist = load_watchlist()

    if scope == "Only F&O Stocks":
        chosen = uni["stocks"]
    elif scope == "Only Index Futures":
        chosen = uni["indices"]
    elif scope == "Only Commodities":
        chosen = uni["commodities"]
    elif scope == "Only Watchlist":
        chosen = watchlist
    else:
        chosen = uni["all"]

    st.subheader("Editable Symbol List")
    txt = st.text_area("One symbol per line", value="\n".join(chosen), height=220)
    symbols = [s.strip() for s in txt.split("\n") if s.strip()]
    if limit and limit > 0:
        symbols = symbols[:limit]

    st.write(f"Symbols queued for scan: **{len(symbols)}**")
    st.info(f"Selected Timeframe Mode: **{timeframe_mode}**")

    if include_fund:
        st.caption("ℹ️ Fundamentals/Results are scraped best-effort from Screener.in and may be slower or occasionally unavailable.")

    a, b = st.columns(2)
    with a:
        if st.button("🔍 Run Smart Scan", type="primary"):
            st.session_state.run_scan = True
    with b:
        st.caption("Tip: enable auto-refresh in the sidebar for continuous live scanning.")

    if auto_refresh_on:
        st.session_state.run_scan = True

    if st.session_state.run_scan:
        st.session_state.run_scan = False
        if not symbols:
            st.error("No symbols to scan.")
        else:
            prog = st.progress(0.0, text="Starting scan...")
            df = scan_universe(
                st.session_state.fyers,
                symbols,
                timeframe_mode=timeframe_mode,
                include_news=include_news,
                include_fundamental=include_fund,
                progress=prog,
            )
            prog.empty()

            save_latest_scan(df)
            append_signal_history(df)
            st.session_state.last_scan_df = df

    df = st.session_state.last_scan_df

    if df is not None and not df.empty:
        df_sorted = add_sector_column(df)

        st.subheader("Scan Results")
        render_summary_cards(df_sorted)

        strong_buy = df_sorted[df_sorted["Signal"] == "STRONG BUY"]
        strong_sell = df_sorted[df_sorted["Signal"] == "STRONG SELL"]
        buy = df_sorted[df_sorted["Signal"] == "BUY"]
        sell = df_sorted[df_sorted["Signal"] == "SELL"]

        st.markdown("### 🚨 Overall Strong Signals (all sectors)")
        sb, ss = st.columns(2)
        with sb:
            render_signal_bar_chart(strong_buy, title=f"🟢🟢 STRONG BUY ({len(strong_buy)})")
        with ss:
            render_signal_bar_chart(strong_sell, title=f"🔴🔴 STRONG SELL ({len(strong_sell)})")

        st.markdown("### 🗂️ Sector-wise Results (Strong Buy / Strong Sell shown first, as bar charts)")
        render_sector_tabs(df_sorted)

        st.markdown("---")
        render_watchlist_results(df_sorted, watchlist)

        st.markdown("---")
        x, y = st.columns(2)
        with x:
            st.subheader(f"🟢 BUY ({len(buy)})")
            display_signal_table(buy)
        with y:
            st.subheader(f"🔴 SELL ({len(sell)})")
            display_signal_table(sell)

        st.download_button(
            "Download results CSV",
            sort_by_priority(df_sorted).to_csv(index=False).encode(),
            "scan_results.csv",
            "text/csv",
        )
    elif df is not None:
        st.warning("No results returned.")

    with st.expander("ℹ️ How this scanner works"):
        st.markdown(
            """
            This scanner is built for **intraday and max 2-day holding ideas**.

            ### Timeframe modes available
            - **5 min only**
            - **5 min + 15 min**
            - **15 min + 1 hr**
            - **1 hr + 4 hr**

            ### Core factors used
            - Technical Trend
            - Momentum
            - Volume
            - Multi-candle chart patterns
            - OI analysis
            - News sentiment
            - Fundamentals & Quarterly Results (optional, via Screener.in)
            - Multi-timeframe confirmation

            ### Multi-candle patterns included
            - Cup and Handle
            - Double Bottom / Double Top
            - Triangle Breakout / Breakdown
            - Rising Wedge / Falling Wedge
            - Rounding Bottom
            - Range Breakout / Breakdown
            - Flag / Pennant
            - Head and Shoulders / Inverse Head and Shoulders
            - Bullish/Bearish Engulfing
            - Morning Star / Evening Star

            ### Sector View
            Results are grouped into sector-wise tabs. Within every sector (and
            overall), **STRONG BUY** and **STRONG SELL** signals are always
            ranked to the top, followed by BUY/SELL, then HOLD.

            ### Watchlist
            Add symbols to a persistent watchlist from the sidebar. Watchlist
            symbols can be scanned exclusively, and their latest results are
            always shown in a dedicated section after each scan.

            ### Live Auto-Refresh
            Enable auto-refresh in the sidebar to automatically re-run the
            scan at a chosen interval without manual clicks.
            """
        )
