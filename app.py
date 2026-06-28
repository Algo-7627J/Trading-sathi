import streamlit as st
import pandas as pd

try:
    from fyers_apiv3 import fyersModel
except Exception:
    fyersModel = None

from config import APP_ID, SECRET_KEY, REDIRECT_URL
from services import build_universe
from analysis import scan_universe
from storage import ensure_data_files, save_latest_scan, append_signal_history
from ui_helpers import inject_custom_css, render_summary_cards, display_signal_table

st.set_page_config(page_title="Trading Sathi", layout="wide")
inject_custom_css()
ensure_data_files()

st.title("🤖 Trading Sathi - Intraday + 2 Day Smart Scanner")
st.caption("Technical + Momentum + Volume + Multi-candle Patterns + OI + News")

for k, v in [("fyers", None), ("access_token", None), ("run_scan", False)]:
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

    with st.spinner("Loading symbol universe from NSE & FYERS..."):
        uni = build_universe()

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("F&O Stocks", len(uni["stocks"]))
    m2.metric("Index Futures", len(uni["indices"]))
    m3.metric("Commodities", len(uni["commodities"]))
    m4.metric("Total", len(uni["all"]))

    st.subheader("Scan Settings")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        scope = st.selectbox(
            "Universe to scan",
            ["Everything (Stocks + Index + Commodity)", "Only F&O Stocks", "Only Index Futures", "Only Commodities"],
        )
    with c2:
        include_news = st.checkbox("Include News", value=True)
    with c3:
        include_fund = st.checkbox("Include Fundamental/Results (optional)", value=False)
    with c4:
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
    txt = st.text_area("One symbol per line", value="\n".join(chosen), height=260)
    symbols = [s.strip() for s in txt.split("\n") if s.strip()]
    if limit and limit > 0:
        symbols = symbols[:limit]

    st.write(f"Symbols queued for scan: **{len(symbols)}**")

    a, b = st.columns(2)
    with a:
        if st.button("🔍 Run Smart Scan", type="primary"):
            st.session_state.run_scan = True
    with b:
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
            df = scan_universe(
                st.session_state.fyers,
                symbols,
                include_news=include_news,
                include_fundamental=include_fund,
                progress=prog,
            )
            prog.empty()
            save_latest_scan(df)
            append_signal_history(df)

            st.subheader("Scan Results")
            if not df.empty:
                df_sorted = df.sort_values("Score", ascending=False, na_position="last")
                render_summary_cards(df_sorted)
                display_signal_table(df_sorted)

                buy = df_sorted[df_sorted["Signal"].isin(["STRONG BUY", "BUY"])]
                sell = df_sorted[df_sorted["Signal"].isin(["STRONG SELL", "SELL"])]
                x, y = st.columns(2)
                with x:
                    st.subheader(f"🟢 BUY ({len(buy)})")
                    display_signal_table(buy)
                with y:
                    st.subheader(f"🔴 SELL ({len(sell)})")
                    display_signal_table(sell)

                st.download_button(
                    "Download results CSV",
                    df_sorted.to_csv(index=False).encode(),
                    "scan_results.csv",
                    "text/csv",
                )
            else:
                st.warning("No results returned.")

    with st.expander("ℹ️ How this scanner works"):
        st.markdown(
            """
            This scanner is built for **intraday and max 2-day holding ideas**.

            Core factors used:
            - Technical Trend
            - Momentum
            - Volume
            - Multi-candle chart patterns
            - OI analysis
            - News sentiment

            Multi-candle patterns included:
            - Cup and Handle
            - Double Bottom / Double Top
            - Triangle Breakout / Breakdown
            - Range Breakout / Breakdown
            - Flag
            - Pennant
            - Head and Shoulders
            """
        )
