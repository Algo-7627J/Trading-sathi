import streamlit as st
import pandas as pd

try:
    from fyers_apiv3 import fyersModel
except:
    fyersModel = None

# ====================== BULLETPROOF CONFIG (NO MORE IMPORT ERROR) ======================
# This block guarantees the variables ALWAYS exist.
# Even if config.py is deleted or broken, the app will run.

import os

# === SAFE DEFAULTS (always defined) ===
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

# Try loading from config.py (optional - will not crash if missing)
try:
    from config import (
        APP_ID as _a, SECRET_KEY as _s, REDIRECT_URL as _r,
        TIMEFRAME_OPTIONS as _t, SECTOR_TIMEFRAMES as _se
    )
    if _a and "YOUR_FYERS" not in str(_a): APP_ID = _a
    if _s and "YOUR_FYERS" not in str(_s): SECRET_KEY = _s
    if _r and "your-redirect" not in str(_r).lower(): REDIRECT_URL = _r
    if _t: TIMEFRAME_OPTIONS = _t
    if _se: SECTOR_TIMEFRAMES = _se
except Exception:
    # Completely safe fallback - app continues normally
    pass

# Load from Streamlit Secrets (IMPORTANT for Cloud deployment)
try:
    import streamlit as st
    if hasattr(st, "secrets"):
        sec = st.secrets
        if "APP_ID" in sec: APP_ID = sec["APP_ID"]
        if "SECRET_KEY" in sec: SECRET_KEY = sec["SECRET_KEY"]
        if "REDIRECT_URL" in sec: REDIRECT_URL = sec["REDIRECT_URL"]

        fyers = sec.get("fyers", {})
        if isinstance(fyers, dict):
            APP_ID = fyers.get("APP_ID", APP_ID)
            SECRET_KEY = fyers.get("SECRET_KEY", SECRET_KEY)
            REDIRECT_URL = fyers.get("REDIRECT_URL", REDIRECT_URL)
except Exception:
    pass
# ====================== END BULLETPROOF CONFIG ======================
from services import build_universe
from analysis import scan_universe
from next_day import scan_next_day
from storage import ensure_data_files, save_latest_scan, append_signal_history, load_watchlist
from ui_helpers import (
    inject_custom_css, render_title, section_label, render_stat_row,
    render_watchlist_manager, render_next_day_results,
    sort_by_priority, render_compact_table_view, render_compact_cards_view,
    render_sector_card
)
from sectors import add_sector_column, get_sector_timeframe_stats, get_top_stocks_by_sector

st.set_page_config(page_title="CODE RED", layout="wide", page_icon="📊")
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

render_title("CODE RED", "Intraday + Next-Day Scanner", connected=st.session_state.fyers is not None)

# ====================== LOGIN SECTION ======================
if st.session_state.fyers is None:
    with st.container(border=True):
        st.markdown("### Connect to FYERS")
        if fyersModel is None:
            st.error("fyers_apiv3 not installed. Add it in requirements.txt")
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
                st.link_button("Login to FYERS", login_url, type="primary")
            except Exception as e:
                st.error(f"Error generating login URL: {e}")

        auth_code = st.text_input("Paste auth_code here", label_visibility="collapsed", placeholder="Paste your auth_code...")

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
                        st.error("Token generation failed. Please check your auth_code.")
                        st.write("Response received:", response)
                except Exception as e:
                    st.error(f"Login failed: {str(e)}")

# ====================== MAIN APP ======================
else:
    try:
        with st.sidebar:
            st.markdown("**CODE RED**")
            
            # ====================== UNIVERSE SETTINGS ======================
            use_live = st.checkbox("🚀 Use Live NSE F&O", value=True, key="use_live_universe")
            
            if st.button("🔄 Refresh Universe", use_container_width=True):
                st.session_state.force_refresh_universe = True
            
            uni = build_universe(use_live=use_live, force_refresh=st.session_state.get("force_refresh_universe", False))
            
            # Reset force refresh
            if st.session_state.get("force_refresh_universe"):
                st.session_state.force_refresh_universe = False
            
            # Show universe source
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
            {"label": "Total", "value": len(uni["all"])},
        ])

        watchlist = load_watchlist()
        tab1, tab2, tab3 = st.tabs(["Intraday Scanner", "Next-Day Outlook", "Sector Trend"])

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

            with st.expander("Edit Symbols"):
                txt = st.text_area("Symbols", value="\n".join(chosen), height=160, label_visibility="collapsed")
            symbols = [s.strip() for s in txt.split("\n") if s.strip()]
            if limit > 0:
                symbols = symbols[:limit]

            if st.button("Run Scan", type="primary", use_container_width=True):
                st.session_state.run_scan = True

            if st.session_state.run_scan:
                st.session_state.run_scan = False
                if symbols:
                    prog = st.progress(0.0, text="Scanning...")
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
                section_label("Results")

                strong_buy = df_sorted[df_sorted["Signal"].str.contains("Strong Buy|Buy", case=False, na=False)]
                strong_sell = df_sorted[df_sorted["Signal"].str.contains("Strong Sell|Sell", case=False, na=False)]

                c1, c2 = st.columns(2)
                with c1:
                    st.markdown(f"""
                    <div style="background:#052e16; border:1px solid #16a34a; padding:20px; border-radius:14px; text-align:center; color:white;">
                        <div style="font-size:15px;">🟢 STRONG BUY</div>
                        <div style="font-size:42px; font-weight:800;">{len(strong_buy)}</div>
                    </div>""", unsafe_allow_html=True)
                    if st.button("View Strong Buy", key="view_buy", use_container_width=True):
                        st.session_state.show_strong_buy = True
                        st.session_state.show_strong_sell = False

                with c2:
                    st.markdown(f"""
                    <div style="background:#450a0a; border:1px solid #b91c1c; padding:20px; border-radius:14px; text-align:center; color:white;">
                        <div style="font-size:15px;">🔴 STRONG SELL</div>
                        <div style="font-size:42px; font-weight:800;">{len(strong_sell)}</div>
                    </div>""", unsafe_allow_html=True)
                    if st.button("View Strong Sell", key="view_sell", use_container_width=True):
                        st.session_state.show_strong_sell = True
                        st.session_state.show_strong_buy = False

                if st.session_state.show_strong_buy or st.session_state.show_strong_sell:
                    selected = strong_buy if st.session_state.show_strong_buy else strong_sell
                    st.markdown(f"### {'🟢 Strong Buy' if st.session_state.show_strong_buy else '🔴 Strong Sell'}")
                    for _, row in selected.iterrows():
                        score = float(row.get("Score", 0))
                        is_buy = score > 0
                        bg = "#052e16" if is_buy else "#450a0a"
                        border = "#16a34a" if is_buy else "#b91c1c"
                        txt_color = "#22c55e" if is_buy else "#ef4444"
                        st.markdown(f"""
                            <div style="background:{bg}; border:1px solid {border}; border-radius:12px; padding:16px; margin-bottom:10px;">
                                <div style="display:flex; justify-content:space-between;">
                                    <div>
                                        <span style="font-size:18px; font-weight:800; color:{txt_color};">{row.get('Symbol')}</span>
                                        <span style="margin-left:10px; color:#9ca3af;">Score: <b>{score:.1f}</b></span>
                                    </div>
                                    <div style="font-weight:600;">₹{row.get('LTP')}</div>
                                </div>
                                <div style="margin-top:6px; font-size:13px; color:#9ca3af;">
                                    {row.get('Pattern', 'N/A')} • MTF: {row.get('MTF Status', 'N/A')} • Vol: {row.get('Volume', 'N/A')}
                                </div>
                            </div>""", unsafe_allow_html=True)

                    if st.button("← Back", use_container_width=True):
                        st.session_state.show_strong_buy = False
                        st.session_state.show_strong_sell = False
                        st.rerun()

                else:
                    view = st.radio("View Mode", ["Table", "Cards"], horizontal=True, key="intraday_view")
                    if view == "Table":
                        render_compact_table_view(df_sorted)
                    else:
                        render_compact_cards_view(df_sorted)

                    st.download_button(
                        "Download CSV",
                        df_sorted.to_csv(index=False).encode(),
                        "intraday_results.csv",
                        "text/csv"
                    )

        # ==================== TAB 2: NEXT-DAY OUTLOOK ====================
        with tab2:
            section_label("Next-Day Outlook Settings")
            nd_scope = st.selectbox(
                "Universe",
                ["Everything", "Only F&O Stocks", "Only Index", "Only Commodities", "Only Watchlist"],
                key="nd_scope"
            )
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

            with st.expander("Edit Symbols"):
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

            if st.button("Run Next-Day Analysis", type="primary", use_container_width=True, key="run_next_day"):
                st.session_state.run_next_day_scan = True

            if st.session_state.run_next_day_scan:
                st.session_state.run_next_day_scan = False
                if nd_symbols:
                    prog = st.progress(0.0, text="Analyzing next-day outlook...")
                    nd_result = scan_next_day(st.session_state.fyers, nd_symbols, progress=prog)
                    prog.empty()
                    st.session_state.next_day_df = nd_result

            nd_df = st.session_state.get("next_day_df")
            if nd_df is not None and not nd_df.empty:
                nd_df = add_sector_column(nd_df)
                section_label("Next-Day Results")
                render_next_day_results(nd_df)
                st.download_button(
                    "Download Next-Day CSV",
                    nd_df.to_csv(index=False).encode(),
                    "next_day_results.csv",
                    "text/csv"
                )
            elif nd_df is not None:
                st.info("No results found.")

        # ==================== TAB 3: SECTOR TREND ====================
        with tab3:
            section_label("Sector Trend Analysis")

            # Timeframe selector
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

            # Explanation
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

            # Get base intraday data
            base_df = st.session_state.get("last_scan_df")
            if base_df is None or base_df.empty:
                st.info("⚠️ Please run an **Intraday Scan** (Tab 1) first to see Sector Trend analysis.")
            else:
                base_df = add_sector_column(base_df)

                # Get timeframe-adjusted sector stats
                tf_key = SECTOR_TIMEFRAMES.get(selected_tf, "1d")
                sector_data = get_sector_timeframe_stats(base_df, timeframe=tf_key)

                if sector_data.empty:
                    st.warning("No sector data available.")
                else:
                    # Most Bullish Sectors (as clickable cards)
                    st.markdown(f"### 🟢 Most Bullish Sectors <small style='color:#64748b'>({selected_tf})</small>", unsafe_allow_html=True)

                    bullish_sectors = sector_data.sort_values("Bullish %", ascending=False).head(6)

                    col_bull = st.columns(2)
                    for idx, (_, row) in enumerate(bullish_sectors.iterrows()):
                        with col_bull[idx % 2]:
                            sector_name = row["Sector"]
                            if st.button(f"📈 {sector_name}", key=f"bullish_{sector_name}", use_container_width=True):
                                st.session_state.selected_bullish_sector = sector_name
                                st.session_state.selected_bearish_sector = None

                    # Most Bearish Sectors
                    st.markdown(f"### 🔴 Most Bearish Sectors <small style='color:#64748b'>({selected_tf})</small>", unsafe_allow_html=True)

                    bearish_sectors = sector_data.sort_values("Bearish %", ascending=False).head(6)

                    col_bear = st.columns(2)
                    for idx, (_, row) in enumerate(bearish_sectors.iterrows()):
                        with col_bear[idx % 2]:
                            sector_name = row["Sector"]
                            if st.button(f"📉 {sector_name}", key=f"bearish_{sector_name}", use_container_width=True):
                                st.session_state.selected_bearish_sector = sector_name
                                st.session_state.selected_bullish_sector = None

                    # Show Top 10 stocks when a sector is clicked
                    if st.session_state.selected_bullish_sector:
                        st.markdown(f"### 🟢 Top 10 Most Bullish Stocks in **{st.session_state.selected_bullish_sector}** ({selected_tf})")
                        top_bull = get_top_stocks_by_sector(
                            base_df,
                            st.session_state.selected_bullish_sector,
                            bias="bullish",
                            top_n=10
                        )
                        if not top_bull.empty:
                            for _, row in top_bull.iterrows():
                                score = float(row.get("Score", 0))
                                st.markdown(f"""
                                <div style="background:#052e16; border:1px solid #16a34a; border-radius:10px; padding:11px 14px; margin-bottom:6px; display:flex; justify-content:space-between;">
                                    <div>
                                        <span style="font-weight:700; color:#22c55e;">{row['Symbol']}</span>
                                        <span style="margin-left:10px; font-size:13px;">Score: {score:.1f}</span>
                                    </div>
                                    <div style="font-weight:600;">₹{row.get('LTP', 'N/A')} • {row.get('Signal', '')}</div>
                                </div>
                                """, unsafe_allow_html=True)
                        else:
                            st.caption("No bullish stocks found in this sector for the current scan.")

                        if st.button("Clear Selection", key="clear_bull"):
                            st.session_state.selected_bullish_sector = None
                            st.rerun()

                    if st.session_state.selected_bearish_sector:
                        st.markdown(f"### 🔴 Top 10 Most Bearish Stocks in **{st.session_state.selected_bearish_sector}** ({selected_tf})")
                        top_bear = get_top_stocks_by_sector(
                            base_df,
                            st.session_state.selected_bearish_sector,
                            bias="bearish",
                            top_n=10
                        )
                        if not top_bear.empty:
                            for _, row in top_bear.iterrows():
                                score = float(row.get("Score", 0))
                                st.markdown(f"""
                                <div style="background:#450a0a; border:1px solid #b91c1c; border-radius:10px; padding:11px 14px; margin-bottom:6px; display:flex; justify-content:space-between;">
                                    <div>
                                        <span style="font-weight:700; color:#ef4444;">{row['Symbol']}</span>
                                        <span style="margin-left:10px; font-size:13px;">Score: {score:.1f}</span>
                                    </div>
                                    <div style="font-weight:600;">₹{row.get('LTP', 'N/A')} • {row.get('Signal', '')}</div>
                                </div>
                                """, unsafe_allow_html=True)
                        else:
                            st.caption("No bearish stocks found in this sector for the current scan.")

                        if st.button("Clear Selection", key="clear_bear"):
                            st.session_state.selected_bearish_sector = None
                            st.rerun()

                    # Summary table
                    st.divider()
                    st.markdown(f"#### 📊 Sector Summary ({selected_tf})")
                    st.dataframe(
                        sector_data[["Sector", "Total", "Bullish", "Bullish %", "Bearish", "Bearish %", "Avg_Score"]],
                        use_container_width=True,
                        hide_index=True
                    )

    except Exception as e:
        st.error(f"App Error: {e}")
        st.exception(e)
