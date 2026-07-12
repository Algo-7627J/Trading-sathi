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
    render_compact_table_view,
    render_compact_cards_view,
)
from sectors import add_sector_column

st.set_page_config(page_title="Trading Sathi", layout="wide", page_icon="📊")

inject_custom_css()
ensure_data_files()

# ====================== SESSION STATE INITIALIZATION ======================
for k, v in [
    ("fyers", None),
    ("access_token", None),
    ("run_scan", False),
    ("last_scan_df", None),
    ("run_next_day_scan", False),
    ("next_day_df", None),
    ("show_strong_buy", False),
    ("show_strong_sell", False),
]:
    if k not in st.session_state:
        st.session_state[k] = v

# ====================== SAFE df DEFINITION ======================
df = st.session_state.get("last_scan_df", None)

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
            scope = st.selectbox("Universe", [
                "Everything (Stocks + Index + Commodity)",
                "Only F&O Stocks",
                "Only Index Futures",
                "Only Commodities",
                "Only Watchlist",
            ], key="intraday_scope")
        with c2:
            timeframe_mode = st.selectbox("Timeframe", list(TIMEFRAME_OPTIONS.keys()), index=2, key="intraday_timeframe")
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
            st.caption("Fundamentals/Results are scraped best-effort from Screener.in")

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
                df = st.session_state.get("last_scan_df", None)

        # ====================== STRONG BUY & STRONG SELL CARDS ======================
        if df is not None and not df.empty:
            df_sorted = add_sector_column(df)
            section_label("Results")

            strong_buy = df_sorted[df_sorted["Signal"].str.contains("Strong Buy|Buy", case=False, na=False)]
            strong_sell = df_sorted[df_sorted["Signal"].str.contains("Strong Sell|Sell", case=False, na=False)]

            col1, col2 = st.columns(2)

            with col1:
                st.markdown(f"""
                    <div style="background: linear-gradient(135deg, #166534, #14532d); padding: 25px; border-radius: 16px; text-align: center; color: white; box-shadow: 0 4px 15px rgba(0,0,0,0.3);">
                        <h2 style="margin:0; font-size:22px;">🟢 STRONG BUY</h2>
                        <h1 style="margin:8px 0; font-size:48px; font-weight:700;">{len(strong_buy)}</h1>
                        <p style="margin:0; opacity:0.9;">Click below to view all</p>
                    </div>
                """, unsafe_allow_html=True)
                if st.button("📋 View Strong Buy Stocks", key="btn_strong_buy", use_container_width=True):
                    st.session_state.show_strong_buy = True
                    st.session_state.show_strong_sell = False

            with col2:
                st.markdown(f"""
                    <div style="background: linear-gradient(135deg, #991b1b, #7f1d1d); padding: 25px; border-radius: 16px; text-align: center; color: white; box-shadow: 0 4px 15px rgba(0,0,0,0.3);">
                        <h2 style="margin:0; font-size:22px;">🔴 STRONG SELL</h2>
                        <h1 style="margin:8px 0; font-size:48px; font-weight:700;">{len(strong_sell)}</h1>
                        <p style="margin:0; opacity:0.9;">Click below to view all</p>
                    </div>
                """, unsafe_allow_html=True)
                if st.button("📋 View Strong Sell Stocks", key="btn_strong_sell", use_container_width=True):
                    st.session_state.show_strong_sell = True
                    st.session_state.show_strong_buy = False

            # Show results when clicked
            if st.session_state.show_strong_buy:
                st.markdown("### 🟢 Strong Buy Stocks")
                render_compact_cards_view(strong_buy) if not strong_buy.empty else st.info("No Strong Buy signals found.")

            elif st.session_state.show_strong_sell:
                st.markdown("### 🔴 Strong Sell Stocks")
                render_compact_cards_view(strong_sell) if not strong_sell.empty else st.info("No Strong Sell signals found.")

            else:
                # Default view
                with st.container(border=True):
                    c1, c2, c3, c4 = st.columns([1.4, 1.3, 1.2, 1.3])
                    with c1:
                        display_mode = st.radio("Display Mode", ["Top Signals + Clean Table", "Compact Cards", "Full (with Charts)"], horizontal=True, index=0, key="intraday_display_mode")
                    with c2:
                        top_n = st.slider("Show top N signals", 5, 35, 12, 1, key="intraday_top_n") if display_mode != "Full (with Charts)" else 0
                    with c3:
                        hide_charts = st.checkbox("Hide bar charts", value=True, key="intraday_hide_charts")
                    with c4:
                        only_high_conv = st.checkbox("Only HIGH Conviction", value=False, key="intraday_only_high_conv")

                df_to_display = sort_by_priority(df_sorted)
                if only_high_conv:
                    df_to_display = df_to_display[
                        df_to_display.apply(lambda r: str(r.get("MTF Status", "")).lower() == "confirmed" and abs(float(r.get("Score") or 0)) >= 35, axis=1)
                    ]
                if display_mode != "Full (with Charts)" and top_n > 0:
                    df_to_display = df_to_display.head(top_n)

                if display_mode == "Top Signals + Clean Table":
                    render_compact_table_view(df_to_display, hide_charts=hide_charts)
                elif display_mode == "Compact Cards":
                    render_compact_cards_view(df_to_display)
                else:
                    render_sector_tabs(df_sorted)

                if watchlist:
                    wl_df = df_sorted[df_sorted["Symbol"].isin(watchlist)]
                    if not wl_df.empty:
                        section_label(f"Watchlist ({len(wl_df)})")
                        st.dataframe(sort_by_priority(wl_df), use_container_width=True, hide_index=True)

                st.download_button("Download results CSV", sort_by_priority(df_sorted).to_csv(index=False).encode(), "scan_results.csv", "text/csv")

        elif df is not None:
            st.info("No results returned.")
