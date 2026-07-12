import streamlit as st
import pandas as pd

try:
    from fyers_apiv3 import fyersModel
except:
    fyersModel = None

from config import APP_ID, SECRET_KEY, REDIRECT_URL, TIMEFRAME_OPTIONS
from services import build_universe
from analysis import scan_universe
from next_day import scan_next_day
from storage import ensure_data_files, save_latest_scan, append_signal_history, load_watchlist
from ui_helpers import (
    inject_custom_css, render_title, section_label, render_stat_row,
    render_sector_tabs, render_watchlist_manager, render_next_day_results,
    sort_by_priority, render_compact_table_view, render_compact_cards_view
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

df = st.session_state.get("last_scan_df")

render_title("Trading Sathi", "Intraday + Next-Day Scanner", connected=st.session_state.fyers is not None)

if st.session_state.fyers is None:
    with st.container(border=True):
        st.markdown("### Connect to FYERS")
        if fyersModel is None:
            st.error("fyers_apiv3 not installed.")
        else:
            try:
                session = fyersModel.SessionModel(
                    client_id=APP_ID, secret_key=SECRET_KEY,
                    redirect_uri=REDIRECT_URL, response_type="code",
                    grant_type="authorization_code"
                )
                st.link_button("Login to FYERS", session.generate_authcode(), type="primary")
            except Exception as e:
                st.error(str(e))

        auth_code = st.text_input("Paste auth_code", label_visibility="collapsed")
        if st.button("Generate Access Token", type="primary"):
            if auth_code:
                try:
                    session = fyersModel.SessionModel(
                        client_id=APP_ID, secret_key=SECRET_KEY,
                        redirect_uri=REDIRECT_URL, response_type="code",
                        grant_type="authorization_code"
                    )
                    session.set_token(auth_code)
                    response = session.generate_token()
                    if "access_token" in response:
                        token = response["access_token"]
                        st.session_state.fyers = fyersModel.FyersModel(client_id=APP_ID, token=token, log_path="")
                        st.success("Login successful!")
                        st.rerun()
                except Exception as e:
                    st.error(f"Login failed: {e}")
else:
    with st.sidebar:
        st.markdown("**Trading Sathi**")
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
    tab1, tab2, tab3 = st.tabs(["Intraday Scanner", "Next-Day Outlook", "Common Direction"])

    # ==================== TAB 1: INTRADAY ====================
    with tab1:
        section_label("Scan Settings")
        c1, c2, c3, c4, c5 = st.columns(5)
        with c1: scope = st.selectbox("Universe", ["Everything", "Only F&O Stocks", "Only Index", "Only Commodities", "Only Watchlist"])
        with c2: timeframe_mode = st.selectbox("Timeframe", list(TIMEFRAME_OPTIONS.keys()), index=2)
        with c3: include_news = st.checkbox("News", value=True)
        with c4: include_fund = st.checkbox("Fundamentals", value=False)
        with c5: limit = st.number_input("Max symbols", 0, 100, 25)

        if scope == "Only F&O Stocks": chosen = uni["stocks"]
        elif scope == "Only Index": chosen = uni["indices"]
        elif scope == "Only Commodities": chosen = uni["commodities"]
        elif scope == "Only Watchlist": chosen = watchlist
        else: chosen = uni["all"]

        with st.expander("Edit Symbols"):
            txt = st.text_area("Symbols", value="\n".join(chosen), height=160, label_visibility="collapsed")
        symbols = [s.strip() for s in txt.split("\n") if s.strip()]
        if limit > 0: symbols = symbols[:limit]

        if st.button("Run Scan", type="primary", use_container_width=True, key="intraday_run"):
            st.session_state.run_scan = True

        if st.session_state.run_scan:
            st.session_state.run_scan = False
            if symbols:
                prog = st.progress(0.0, text="Scanning...")
                result = scan_universe(st.session_state.fyers, symbols, timeframe_mode=timeframe_mode,
                                       include_news=include_news, include_fundamental=include_fund, progress=prog)
                prog.empty()
                save_latest_scan(result)
                append_signal_history(result)
                st.session_state.last_scan_df = result
                df = result

        # Strong Buy / Sell Cards (same as before)
        if df is not None and not df.empty:
            df_sorted = add_sector_column(df)
            section_label("Results")

            strong_buy = df_sorted[df_sorted["Signal"].str.contains("Strong Buy|Buy", case=False, na=False)]
            strong_sell = df_sorted[df_sorted["Signal"].str.contains("Strong Sell|Sell", case=False, na=False)]

            c1, c2 = st.columns(2)
            with c1:
                st.markdown(f"""<div style="background:#052e16; border:1px solid #16a34a; padding:20px; border-radius:14px; text-align:center; color:white;">
                    <div style="font-size:15px;">🟢 STRONG BUY</div>
                    <div style="font-size:42px; font-weight:800;">{len(strong_buy)}</div></div>""", unsafe_allow_html=True)
                if st.button("View Strong Buy", key="view_buy", use_container_width=True):
                    st.session_state.show_strong_buy = True
                    st.session_state.show_strong_sell = False

            with c2:
                st.markdown(f"""<div style="background:#450a0a; border:1px solid #b91c1c; padding:20px; border-radius:14px; text-align:center; color:white;">
                    <div style="font-size:15px;">🔴 STRONG SELL</div>
                    <div style="font-size:42px; font-weight:800;">{len(strong_sell)}</div></div>""", unsafe_allow_html=True)
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
                                <div><span style="font-size:18px; font-weight:800; color:{txt_color};">{row.get('Symbol')}</span>
                                <span style="margin-left:10px; color:#9ca3af;">Score: <b>{score:.1f}</b></span></div>
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
                view = st.radio("View Mode", ["Table", "Cards"], horizontal=True)
                if view == "Table":
                    render_compact_table_view(df_sorted)
                else:
                    render_compact_cards_view(df_sorted)
                st.download_button("Download CSV", df_sorted.to_csv(index=False).encode(), "results.csv", "text/csv")

    # ==================== TAB 2: NEXT-DAY OUTLOOK (FIXED) ====================
    with tab2:
        section_label("Next-Day Outlook Settings")

        nd_scope = st.selectbox("Universe", ["Everything", "Only F&O Stocks", "Only Index", "Only Commodities", "Only Watchlist"], key="nd_scope")
        nd_limit = st.number_input("Max symbols", 0, 100, 20, key="nd_limit")

        if nd_scope == "Only F&O Stocks": nd_chosen = uni["stocks"]
        elif nd_scope == "Only Index": nd_chosen = uni["indices"]
        elif nd_scope == "Only Commodities": nd_chosen = uni["commodities"]
        elif nd_scope == "Only Watchlist": nd_chosen = watchlist
        else: nd_chosen = uni["all"]

        with st.expander("Edit Symbols"):
            nd_txt = st.text_area("Symbols", value="\n".join(nd_chosen), height=160, label_visibility="collapsed", key="nd_symbols")
        nd_symbols = [s.strip() for s in nd_txt.split("\n") if s.strip()]
        if nd_limit > 0: nd_symbols = nd_symbols[:nd_limit]

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
            st.download_button("Download Next-Day CSV", nd_df.to_csv(index=False).encode(), "next_day_results.csv", "text/csv")
        elif nd_df is not None:
            st.info("No results found.")

    # ==================== TAB 3: COMMON DIRECTION ====================
    with tab3:
        section_label("Common Direction")
        render_common_direction_results(
            st.session_state.get("last_scan_df"),
            st.session_state.get("next_day_df")
        )
