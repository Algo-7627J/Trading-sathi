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

# ====================== SESSION STATE ======================
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
        if fyersModel is None:
            st.error("fyers_apiv3 library not installed.")
        else:
            try:
                session = fyersModel.SessionModel(
                    client_id=APP_ID, secret_key=SECRET_KEY,
                    redirect_uri=REDIRECT_URL, response_type="code",
                    grant_type="authorization_code",
                )
                login_url = session.generate_authcode()
                st.link_button("Login to FYERS", login_url, type="primary")
            except Exception as e:
                st.error(f"Error: {e}")

        auth_code = st.text_input("Paste auth_code here", label_visibility="collapsed")
        if st.button("Generate Access Token", type="primary"):
            if auth_code:
                try:
                    session = fyersModel.SessionModel(
                        client_id=APP_ID, secret_key=SECRET_KEY,
                        redirect_uri=REDIRECT_URL, response_type="code",
                        grant_type="authorization_code",
                    )
                    session.set_token(auth_code)
                    response = session.generate_token()
                    if "access_token" in response:
                        token = response["access_token"]
                        st.session_state.access_token = token
                        st.session_state.fyers = fyersModel.FyersModel(client_id=APP_ID, token=token, log_path="")
                        st.success("Login successful!")
                        st.rerun()
                except Exception as e:
                    st.error(f"Login failed: {e}")
else:
    with st.sidebar:
        st.markdown("**Trading Sathi**")
        with st.spinner("Loading symbols..."):
            uni = build_universe()
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
    tab_intraday, tab_next_day, tab_common = st.tabs(["Intraday Scanner", "Next-Day Outlook", "Common Direction"])

    # ==================== TAB 1: INTRADAY ====================
    with tab_intraday:
        section_label("Scan Settings")
        c1, c2, c3, c4, c5 = st.columns(5)
        with c1:
            scope = st.selectbox("Universe", ["Everything", "Only F&O Stocks", "Only Index", "Only Commodities", "Only Watchlist"], key="scope")
        with c2:
            timeframe_mode = st.selectbox("Timeframe", list(TIMEFRAME_OPTIONS.keys()), index=2)
        with c3:
            include_news = st.checkbox("News", value=True)
        with c4:
            include_fund = st.checkbox("Fundamentals", value=False)
        with c5:
            limit = st.number_input("Max symbols", 0, 100, 25)

        if scope == "Only F&O Stocks":
            chosen = uni["stocks"]
        elif scope == "Only Index":
            chosen = uni["indices"]
        elif scope == "Only Commodities":
            chosen = uni["commodities"]
        elif scope == "Only Watchlist":
            chosen = watchlist
        else:
            chosen = uni["all"]

        with st.expander("Edit Symbols"):
            txt = st.text_area("Symbols", value="\n".join(chosen), height=180, label_visibility="collapsed")
        symbols = [s.strip() for s in txt.split("\n") if s.strip()]
        if limit > 0:
            symbols = symbols[:limit]

        if st.button("Run Scan", type="primary", use_container_width=True):
            st.session_state.run_scan = True

        if st.session_state.run_scan:
            st.session_state.run_scan = False
            if symbols:
                prog = st.progress(0.0, text="Scanning...")
                result_df = scan_universe(st.session_state.fyers, symbols, timeframe_mode=timeframe_mode,
                                          include_news=include_news, include_fundamental=include_fund, progress=prog)
                prog.empty()
                save_latest_scan(result_df)
                append_signal_history(result_df)
                st.session_state.last_scan_df = result_df
                df = result_df

        # ====================== IMPROVED CARD VIEW ======================
        if df is not None and not df.empty:
            df_sorted = add_sector_column(df)
            section_label("Results")

            strong_buy = df_sorted[df_sorted["Signal"].str.contains("Strong Buy|Buy", case=False, na=False)]
            strong_sell = df_sorted[df_sorted["Signal"].str.contains("Strong Sell|Sell", case=False, na=False)]

            col1, col2 = st.columns(2)

            with col1:
                st.markdown(f"""
                    <div style="background: linear-gradient(135deg, #0f766e, #134e4b); padding: 22px; border-radius: 16px; text-align: center; color: white; border: 1px solid #14b8a6;">
                        <div style="font-size:15px; opacity:0.9;">🟢 STRONG BUY</div>
                        <div style="font-size:42px; font-weight:800; margin:6px 0;">{len(strong_buy)}</div>
                        <div style="font-size:13px; opacity:0.85;">Click to view all</div>
                    </div>
                """, unsafe_allow_html=True)
                if st.button("View Strong Buy", key="btn_buy", use_container_width=True):
                    st.session_state.show_strong_buy = True
                    st.session_state.show_strong_sell = False

            with col2:
                st.markdown(f"""
                    <div style="background: linear-gradient(135deg, #9f1239, #7f1d1d); padding: 22px; border-radius: 16px; text-align: center; color: white; border: 1px solid #f87171;">
                        <div style="font-size:15px; opacity:0.9;">🔴 STRONG SELL</div>
                        <div style="font-size:42px; font-weight:800; margin:6px 0;">{len(strong_sell)}</div>
                        <div style="font-size:13px; opacity:0.85;">Click to view all</div>
                    </div>
                """, unsafe_allow_html=True)
                if st.button("View Strong Sell", key="btn_sell", use_container_width=True):
                    st.session_state.show_strong_sell = True
                    st.session_state.show_strong_buy = False

            # Show detailed cards when clicked
            if st.session_state.show_strong_buy or st.session_state.show_strong_sell:
                selected = strong_buy if st.session_state.show_strong_buy else strong_sell
                title = "🟢 Strong Buy Stocks" if st.session_state.show_strong_buy else "🔴 Strong Sell Stocks"

                st.markdown(f"### {title}")

                for _, row in selected.iterrows():
                    score = float(row.get("Score", 0))
                    is_buy = score > 0
                    bg = "#052e16" if is_buy else "#450a0a"
                    border = "#16a34a" if is_buy else "#b91c1c"
                    text_color = "#22c55e" if is_buy else "#ef4444"

                    st.markdown(f"""
                        <div style="background-color:{bg}; border:1px solid {border}; border-radius:12px; padding:16px 20px; margin-bottom:12px;">
                            <div style="display:flex; justify-content:space-between; align-items:center;">
                                <div>
                                    <span style="font-size:18px; font-weight:800; color:{text_color};">{row.get('Symbol')}</span>
                                    <span style="margin-left:12px; font-size:13px; color:#9ca3af;">Score: <b>{score:.1f}</b></span>
                                </div>
                                <div style="font-size:16px; font-weight:600; color:#d1d4dc;">₹{row.get('LTP', 'N/A')}</div>
                            </div>
                            <div style="margin-top:8px; font-size:13.5px; color:#9ca3af;">
                                <b>Pattern:</b> {row.get('Pattern', 'N/A')} &nbsp;•&nbsp;
                                <b>MTF:</b> {row.get('MTF Status', 'N/A')} &nbsp;•&nbsp;
                                <b>Vol:</b> {row.get('Volume', 'N/A')}
                            </div>
                        </div>
                    """, unsafe_allow_html=True)

                if st.button("← Back to Overview", use_container_width=True):
                    st.session_state.show_strong_buy = False
                    st.session_state.show_strong_sell = False
                    st.rerun()

            else:
                # Default view
                with st.container(border=True):
                    display_mode = st.radio("View", ["Compact Table", "Compact Cards"], horizontal=True, index=0)

                if display_mode == "Compact Table":
                    render_compact_table_view(df_sorted)
                else:
                    render_compact_cards_view(df_sorted)

                st.download_button("Download CSV", df_sorted.to_csv(index=False).encode(), "results.csv", "text/csv")

        elif df is not None:
            st.info("No results returned.")
