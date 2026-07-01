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
from next_day import scan_next_day
from storage import ensure_data_files, save_latest_scan, append_signal_history, load_watchlist
from ui_helpers import (
    inject_custom_css,
    render_title,
    section_label,
    render_stat_row,
    render_summary_cards,
    render_sector_tabs,
    render_watchlist_manager,
    render_next_day_results,
    render_common_direction_results,
    sort_by_priority,
)
from sectors import add_sector_column

st.set_page_config(page_title="Trading Sathi", layout="wide", page_icon="📊")
inject_custom_css()
ensure_data_files()

for k, v in [
    ("fyers", None),
    ("access_token", None),
    ("run_scan", False),
    ("last_scan_df", None),
    ("run_next_day_scan", False),
    ("next_day_df", None),
]:
    if k not in st.session_state:
        st.session_state[k] = v

render_title(
    "Trading Sathi",
    "Intraday scanner + backtested next-day outlook for NSE F&O, index & commodity trading",
    connected=st.session_state.fyers is not None,
)

if st.session_state.fyers is None:
    login_box = st.container(border=True)
    with login_box:
        st.markdown("**Connect to FYERS**")
        st.caption("Step 1 — Login to FYERS and get your auth code")

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
                st.link_button("Login to FYERS", login_url, type="primary")
            except Exception as e:
                st.error(f"Unable to generate FYERS login URL: {e}")

        st.caption("Step 2 — Paste the auth_code here")
        auth_code = st.text_input("auth_code", label_visibility="collapsed", placeholder="Paste your auth_code...")
        if st.button("Generate Access Token", type="primary"):
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
                        st.success("Login successful.")
                        st.rerun()
                    else:
                        st.error(f"Token generation failed: {response}")
                except Exception as e:
                    st.error(f"Login failed: {e}")

else:
    with st.sidebar:
        st.markdown("**Trading Sathi**")
        st.caption("Control panel")

        with st.spinner("Loading symbol universe..."):
            uni = build_universe()

        st.divider()
        render_watchlist_manager(uni["all"])

        st.divider()
        st.markdown("**Auto-Refresh**")
        auto_refresh_on = st.checkbox("Enable auto-refresh scan", value=False)
        refresh_interval = st.number_input(
            "Refresh every (seconds)", min_value=30, max_value=1800, value=180, step=30,
            disabled=not auto_refresh_on,
        )
        if auto_refresh_on:
            if st_autorefresh is not None:
                st_autorefresh(interval=int(refresh_interval * 1000), key="ts_autorefresh")
                st.caption(f"Refreshing every {refresh_interval}s")
            else:
                st.warning("Install `streamlit-autorefresh` to enable this.")

        st.divider()
        if st.button("Logout", use_container_width=True):
            for k in ("fyers", "access_token", "run_scan"):
                st.session_state[k] = None if k != "run_scan" else False
            st.rerun()

    render_stat_row([
        {"label": "F&O Stocks", "value": len(uni["stocks"])},
        {"label": "Index Futures", "value": len(uni["indices"])},
        {"label": "Commodities", "value": len(uni["commodities"])},
        {"label": "Total Universe", "value": len(uni["all"])},
    ])

    watchlist = load_watchlist()

    tab_intraday, tab_next_day, tab_common = st.tabs(
        ["Intraday / 2-Day Scanner", "Next-Day Outlook", "Common Direction"]
    )

    # =====================================================================
    # TAB 1: Intraday / 2-day scanner
    # =====================================================================
    with tab_intraday:
        section_label("Scan Settings")
        c1, c2, c3, c4, c5 = st.columns(5)

        with c1:
            scope = st.selectbox(
                "Universe",
                [
                    "Everything (Stocks + Index + Commodity)",
                    "Only F&O Stocks",
                    "Only Index Futures",
                    "Only Commodities",
                    "Only Watchlist",
                ],
                key="intraday_scope",
            )

        with c2:
            timeframe_mode = st.selectbox(
                "Timeframe",
                list(TIMEFRAME_OPTIONS.keys()),
                index=2,
                key="intraday_timeframe",
            )

        with c3:
            include_news = st.checkbox("News", value=True, key="intraday_news")

        with c4:
            include_fund = st.checkbox("Fundamentals", value=False, key="intraday_fund")

        with c5:
            limit = st.number_input("Max symbols (0 = all)", min_value=0, value=25, step=5, key="intraday_limit")

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

        with st.expander("Edit symbol list"):
            txt = st.text_area("One symbol per line", value="\n".join(chosen), height=200, key="intraday_symbols", label_visibility="collapsed")
        symbols = [s.strip() for s in txt.split("\n") if s.strip()]
        if limit and limit > 0:
            symbols = symbols[:limit]

        if include_fund:
            st.caption("Fundamentals/Results are scraped best-effort from Screener.in and may be slower or occasionally unavailable.")

        a, b = st.columns([1, 3])
        with a:
            if st.button("Run Scan", type="primary", key="run_intraday_scan", use_container_width=True):
                st.session_state.run_scan = True
        with b:
            st.caption(f"{len(symbols)} symbols queued · {timeframe_mode}")

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

            section_label("Results")
            render_sector_tabs(df_sorted)

            if watchlist:
                wl_df = df_sorted[df_sorted["Symbol"].isin(watchlist)]
                if not wl_df.empty:
                    section_label(f"Watchlist ({len(wl_df)})")
                    st.dataframe(sort_by_priority(wl_df), use_container_width=True, hide_index=True)

            st.download_button(
                "Download results CSV",
                sort_by_priority(df_sorted).to_csv(index=False).encode(),
                "scan_results.csv",
                "text/csv",
            )
        elif df is not None:
            st.info("No results returned.")

        with st.expander("How this scanner works"):
            st.markdown(
                """
Built for **intraday and max 2-day holding ideas**.

**Timeframe modes** — 5 min only · 5 min + 15 min · 15 min + 1 hr · 1 hr + 4 hr

**Core factors** — Technical trend, momentum, volume, multi-candle chart patterns,
OI analysis, news sentiment, fundamentals & quarterly results (optional), multi-timeframe confirmation.

**Patterns detected** — Cup and Handle, Double Bottom/Top, Triangle Breakout/Breakdown,
Rising/Falling Wedge, Rounding Bottom, Range Breakout/Breakdown, Flag, Pennant,
Head and Shoulders (+ Inverse), Bullish/Bearish Engulfing, Morning/Evening Star.

**Sectors** — Results are grouped into sector tabs. Strong Buy/Sell signals are
always ranked first within every tab.

**Watchlist** — Add symbols from the sidebar to track them separately after every scan.

**Auto-refresh** — Enable in the sidebar to re-run the scan automatically at a set interval.
                """
            )

    # =====================================================================
    # TAB 2: Next-Day Outlook (daily-candle based + historical backtest)
    # =====================================================================
    with tab_next_day:
        st.markdown(
            '<div class="ts-card ts-card-notice">'
            "No model can reliably predict tomorrow's exact move — markets are affected by "
            "news, global cues and randomness no technical signal can see. This tool combines "
            "several daily-timeframe signals <b>and</b> backtests that exact rule-set on each "
            "stock's own past ~1 year of data, so every call shows an honest historical hit-rate "
            "instead of a blind score. Treat HIGH-confidence calls as your best-supported ideas, "
            "and treat LOW-confidence calls skeptically."
            "</div>",
            unsafe_allow_html=True,
        )

        section_label("Analysis Settings")
        nd1, nd2 = st.columns(2)
        with nd1:
            nd_scope = st.selectbox(
                "Universe",
                [
                    "Everything (Stocks + Index + Commodity)",
                    "Only F&O Stocks",
                    "Only Index Futures",
                    "Only Commodities",
                    "Only Watchlist",
                ],
                key="next_day_scope",
            )
        with nd2:
            nd_limit = st.number_input("Max symbols (0 = all)", min_value=0, value=20, step=5, key="next_day_limit")

        if nd_scope == "Only F&O Stocks":
            nd_chosen = uni["stocks"]
        elif nd_scope == "Only Index Futures":
            nd_chosen = uni["indices"]
        elif nd_scope == "Only Commodities":
            nd_chosen = uni["commodities"]
        elif nd_scope == "Only Watchlist":
            nd_chosen = watchlist
        else:
            nd_chosen = uni["all"]

        with st.expander("Edit symbol list"):
            nd_txt = st.text_area("One symbol per line", value="\n".join(nd_chosen), height=200, key="next_day_symbols", label_visibility="collapsed")
        nd_symbols = [s.strip() for s in nd_txt.split("\n") if s.strip()]
        if nd_limit and nd_limit > 0:
            nd_symbols = nd_symbols[:nd_limit]

        st.caption(
            f"{len(nd_symbols)} symbols queued · uses ~1 year of daily candles per symbol, "
            "backtesting Trend, ADX/DI, RSI/MACD, Bollinger Bands, Relative Strength vs Nifty, "
            "Support/Resistance, Gap and Volume against each stock's own history."
        )

        if st.button("Run Next-Day Analysis", type="primary", key="run_next_day_scan_btn"):
            st.session_state.run_next_day_scan = True

        if st.session_state.get("run_next_day_scan"):
            st.session_state.run_next_day_scan = False
            if not nd_symbols:
                st.error("No symbols to analyze.")
            else:
                prog = st.progress(0.0, text="Starting next-day analysis...")
                nd_df = scan_next_day(st.session_state.fyers, nd_symbols, progress=prog)
                prog.empty()
                st.session_state.next_day_df = nd_df

        nd_df = st.session_state.get("next_day_df")

        if nd_df is not None and not nd_df.empty:
            nd_df = add_sector_column(nd_df)
            section_label("Results")
            render_next_day_results(nd_df)

            st.download_button(
                "Download Next-Day Outlook CSV",
                nd_df.to_csv(index=False).encode(),
                "next_day_outlook.csv",
                "text/csv",
                key="download_next_day_csv",
            )
        elif nd_df is not None:
            st.info("No results returned.")

        with st.expander("How Next-Day Outlook works & its limits"):
            st.markdown(
                """
**What it does** — For each symbol, ~1 year of daily candles are combined into 8 factors:
Trend (EMA10/20/50), ADX/+DI/-DI trend strength, RSI/MACD momentum, Bollinger Band position,
Relative Strength vs Nifty 50 (5-day), Support/Resistance proximity, Gap behaviour, and Volume confirmation.

**The backtest** — The exact same rule-set is replayed on every day in that stock's own past
year, comparing the predicted direction against the actual next-day return. This produces a
real backtest hit-rate and sample size per stock, calculated separately for bullish and bearish calls.

**Confidence** — HIGH requires 15+ backtested occurrences and 65%+ historical hit-rate.
MEDIUM requires 7+ occurrences and 55%+. Otherwise it's LOW and the call is softened.

**Limitations** — Past hit-rate does not guarantee future accuracy. This cannot account for
tomorrow's news, results or block deals. Treat this as decision support, not a guarantee —
always apply your own risk management.
                """
            )

    # =====================================================================
    # TAB 3: Common Direction - cross-reference intraday scan vs next-day outlook
    # =====================================================================
    with tab_common:
        st.markdown(
            '<div class="ts-card ts-card-notice">'
            "Shows stocks where the Intraday/2-Day Scanner and the Next-Day Outlook "
            "independently agree on direction — run both scans (in the other two tabs) "
            "with overlapping symbol lists first, then check back here."
            "</div>",
            unsafe_allow_html=True,
        )

        section_label("Agreement")
        render_common_direction_results(
            st.session_state.get("last_scan_df"),
            st.session_state.get("next_day_df"),
        )
