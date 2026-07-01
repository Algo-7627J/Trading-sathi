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
    render_hero_header,
    section_header,
    render_stat_cards,
    render_summary_cards,
    display_signal_table,
    render_sector_tabs,
    render_watchlist_manager,
    render_watchlist_results,
    render_signal_bar_chart,
    render_next_day_results,
    sort_by_priority,
)
from sectors import add_sector_column

st.set_page_config(page_title="Trading Sathi", layout="wide", page_icon="🤖")
inject_custom_css()
ensure_data_files()

render_hero_header(
    "🤖 Trading Sathi",
    "Intraday Scanner + Backtested Next-Day Outlook for NSE F&O, Index & Commodity trading",
    tags=[
        "📊 Technical", "⚡ Momentum", "📦 Volume", "🕯️ Patterns",
        "📈 OI", "📰 News", "💰 Fundamentals", "🏷️ Sectors", "🔮 Next-Day Outlook",
    ],
)

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

if st.session_state.fyers is None:
    login_box = st.container(border=True)
    login_box.markdown(
        '<div class="ts-section-header" style="margin-top:0;">'
        '<div class="ts-section-icon">🔐</div>'
        '<h3>Connect to FYERS</h3>'
        '<span class="ts-section-sub">One-time login to start scanning</span>'
        "</div>",
        unsafe_allow_html=True,
    )
    login_box.info("**Step 1** — Login to FYERS and get your auth code")

    with login_box:
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
                st.link_button("👉 Login to FYERS", login_url, type="primary")
            except Exception as e:
                st.error(f"Unable to generate FYERS login URL: {e}")

        st.markdown("**Step 2** — Paste the auth_code here")
        auth_code = st.text_input("auth_code", label_visibility="collapsed", placeholder="Paste your auth_code...")
        if st.button("🔑 Generate Access Token", type="primary"):
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
    st.markdown(
        '<div style="display:flex;align-items:center;gap:8px;margin-bottom:18px;">'
        '<span style="background:rgba(34,197,94,0.15);color:#4ade80;border:1px solid rgba(74,222,128,0.35);'
        'padding:5px 14px;border-radius:999px;font-size:13px;font-weight:700;">🟢 Connected to FYERS</span>'
        "</div>",
        unsafe_allow_html=True,
    )

    with st.sidebar:
        st.markdown(
            '<div style="text-align:center;padding:8px 0 16px 0;">'
            '<div style="font-size:1.8rem;">🤖</div>'
            '<div style="font-weight:800;font-size:1.1rem;color:#f1f5f9;">Trading Sathi</div>'
            '<div style="font-size:11.5px;color:#64748b;">Control Panel</div>'
            "</div>",
            unsafe_allow_html=True,
        )

        with st.spinner("Loading symbol universe from NSE & FYERS..."):
            uni = build_universe()

        render_watchlist_manager(uni["all"])

        st.markdown('<hr class="ts-divider">', unsafe_allow_html=True)
        st.markdown(
            '<div style="font-weight:700;color:#f1f5f9;margin-bottom:6px;">🔄 Live Auto-Refresh</div>',
            unsafe_allow_html=True,
        )
        auto_refresh_on = st.checkbox("Enable auto-refresh scan", value=False)
        refresh_interval = st.number_input(
            "Refresh every (seconds)", min_value=30, max_value=1800, value=180, step=30,
            disabled=not auto_refresh_on,
        )
        if auto_refresh_on:
            if st_autorefresh is not None:
                st_autorefresh(interval=int(refresh_interval * 1000), key="ts_autorefresh")
                st.caption(f"⏱️ Auto-refreshing every {refresh_interval}s")
            else:
                st.warning("Install `streamlit-autorefresh` to enable this (see requirements.txt).")

        st.markdown('<hr class="ts-divider">', unsafe_allow_html=True)
        if st.button("🚪 Logout", use_container_width=True):
            for k in ("fyers", "access_token", "run_scan"):
                st.session_state[k] = None if k != "run_scan" else False
            st.rerun()

    section_header("Universe Overview", icon="🌐", sub="Live symbol counts from NSE & FYERS")
    render_stat_cards([
        {"label": "F&O Stocks", "value": len(uni["stocks"]), "icon": "🏢", "color": "#818cf8"},
        {"label": "Index Futures", "value": len(uni["indices"]), "icon": "📊", "color": "#38bdf8"},
        {"label": "Commodities", "value": len(uni["commodities"]), "icon": "🪙", "color": "#facc15"},
        {"label": "Total Universe", "value": len(uni["all"]), "icon": "🌐", "color": "#4ade80"},
    ])

    watchlist = load_watchlist()

    tab_intraday, tab_next_day = st.tabs(["⚡ Intraday / 2-Day Scanner", "🔮 Next-Day Outlook (Backtested)"])

    # =====================================================================
    # TAB 1: Existing intraday / 2-day scanner
    # =====================================================================
    with tab_intraday:
        section_header("Scan Settings", icon="⚙️")
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
                key="intraday_scope",
            )

        with c2:
            timeframe_mode = st.selectbox(
                "Timeframe Mode",
                list(TIMEFRAME_OPTIONS.keys()),
                index=2,
                key="intraday_timeframe",
            )

        with c3:
            include_news = st.checkbox("Include News", value=True, key="intraday_news")

        with c4:
            include_fund = st.checkbox("Include Fundamentals/Results", value=False, key="intraday_fund")

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

        with st.expander("📝 Editable Symbol List", expanded=False):
            txt = st.text_area("One symbol per line", value="\n".join(chosen), height=220, key="intraday_symbols")
        symbols = [s.strip() for s in txt.split("\n") if s.strip()]
        if limit and limit > 0:
            symbols = symbols[:limit]

        info_cols = st.columns(2)
        with info_cols[0]:
            st.markdown(
                f'<div class="ts-card" style="padding:10px 16px;">📋 Symbols queued: '
                f'<b style="color:#a5b4fc;">{len(symbols)}</b></div>',
                unsafe_allow_html=True,
            )
        with info_cols[1]:
            st.markdown(
                f'<div class="ts-card" style="padding:10px 16px;">⏱️ Timeframe: '
                f'<b style="color:#a5b4fc;">{timeframe_mode}</b></div>',
                unsafe_allow_html=True,
            )

        if include_fund:
            st.caption("ℹ️ Fundamentals/Results are scraped best-effort from Screener.in and may be slower or occasionally unavailable.")

        a, b = st.columns([1, 2])
        with a:
            if st.button("🔍 Run Smart Scan", type="primary", key="run_intraday_scan", use_container_width=True):
                st.session_state.run_scan = True
        with b:
            st.caption("💡 Tip: enable auto-refresh in the sidebar for continuous live scanning.")

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

            st.markdown('<hr class="ts-divider">', unsafe_allow_html=True)
            section_header("Scan Results", icon="📈")
            render_summary_cards(df_sorted)

            strong_buy = df_sorted[df_sorted["Signal"] == "STRONG BUY"]
            strong_sell = df_sorted[df_sorted["Signal"] == "STRONG SELL"]
            buy = df_sorted[df_sorted["Signal"] == "BUY"]
            sell = df_sorted[df_sorted["Signal"] == "SELL"]

            section_header("Overall Strong Signals", icon="🚨", sub="Across all sectors")
            sb, ss = st.columns(2)
            with sb:
                render_signal_bar_chart(strong_buy, title=f"🟢🟢 STRONG BUY ({len(strong_buy)})")
            with ss:
                render_signal_bar_chart(strong_sell, title=f"🔴🔴 STRONG SELL ({len(strong_sell)})")

            section_header("Sector-wise Results", icon="🗂️", sub="Strong Buy/Sell shown first, as bar charts")
            render_sector_tabs(df_sorted)

            render_watchlist_results(df_sorted, watchlist)

            section_header("All Buy / Sell Signals", icon="📋")
            x, y = st.columns(2)
            with x:
                st.markdown(f'<div class="ts-card ts-card-bullish">🟢 <b>BUY</b> &nbsp;·&nbsp; {len(buy)} stocks</div>', unsafe_allow_html=True)
                display_signal_table(buy)
            with y:
                st.markdown(f'<div class="ts-card ts-card-bearish">🔴 <b>SELL</b> &nbsp;·&nbsp; {len(sell)} stocks</div>', unsafe_allow_html=True)
                display_signal_table(sell)

            st.download_button(
                "⬇️ Download results CSV",
                sort_by_priority(df_sorted).to_csv(index=False).encode(),
                "scan_results.csv",
                "text/csv",
                use_container_width=True,
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

    # =====================================================================
    # TAB 2: Next-Day Outlook (daily-candle based + historical backtest)
    # =====================================================================
    with tab_next_day:
        st.markdown(
            '<div class="ts-card" style="border-left:4px solid #f59e0b;">'
            '⚠️ <b>Please read before using</b>: No model can reliably predict '
            "tomorrow's exact move &mdash; markets are affected by news, global "
            "cues and randomness no technical signal can see. This tool "
            "combines several daily-timeframe signals <b>and</b> backtests that "
            "exact rule-set on each stock's own past ~1 year of data, so "
            "every call shows an honest historical hit-rate instead of a "
            "blind score. Treat <b>STRONG BULLISH/BEARISH</b> with HIGH "
            "confidence as your best-supported ideas, and treat LOW "
            "confidence calls skeptically or ignore them."
            "</div>",
            unsafe_allow_html=True,
        )

        section_header("Analysis Settings", icon="⚙️")
        nd1, nd2 = st.columns(2)
        with nd1:
            nd_scope = st.selectbox(
                "Universe to analyze",
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

        with st.expander("📝 Editable Symbol List", expanded=False):
            nd_txt = st.text_area("One symbol per line", value="\n".join(nd_chosen), height=200, key="next_day_symbols")
        nd_symbols = [s.strip() for s in nd_txt.split("\n") if s.strip()]
        if nd_limit and nd_limit > 0:
            nd_symbols = nd_symbols[:nd_limit]

        st.markdown(
            f'<div class="ts-card" style="padding:10px 16px;">📋 Symbols queued for analysis: '
            f'<b style="color:#a5b4fc;">{len(nd_symbols)}</b></div>',
            unsafe_allow_html=True,
        )
        st.caption(
            "Uses ~1 year of daily candles per symbol. Backtests Trend, ADX/DI "
            "trend-strength, RSI/MACD momentum, Bollinger Band position, "
            "Relative Strength vs Nifty 50, Support/Resistance proximity, "
            "Gap behaviour and Volume confirmation against that stock's own "
            "historical next-day outcomes."
        )

        if st.button("🔮 Run Next-Day Outlook Scan", type="primary", key="run_next_day_scan_btn"):
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
            st.markdown('<hr class="ts-divider">', unsafe_allow_html=True)
            section_header("Next-Day Outlook Results", icon="🔮")
            render_next_day_results(nd_df)

            st.download_button(
                "⬇️ Download Next-Day Outlook CSV",
                nd_df.to_csv(index=False).encode(),
                "next_day_outlook.csv",
                "text/csv",
                key="download_next_day_csv",
                use_container_width=True,
            )
        elif nd_df is not None:
            st.warning("No results returned.")

        with st.expander("ℹ️ How Next-Day Outlook works & its limits"):
            st.markdown(
                """
                ### What it does
                For each symbol, ~1 year of **daily** candles are fetched and
                combined into 8 factors:

                - **Trend** - price vs EMA10/20/50 alignment
                - **ADX / +DI / -DI** - is there an actual trend, and which
                  direction is it in (ADX below ~20 means no real trend, so
                  this factor contributes nothing)
                - **Momentum** - RSI + MACD histogram
                - **Bollinger Bands** - overbought/oversold position within
                  the band
                - **Relative Strength vs Nifty 50** - is the stock
                  outperforming or underperforming the index over 5 days
                - **Support/Resistance** - proximity to/breakout of the
                  20-day high/low range
                - **Gap behaviour** - unusually large opening gaps
                - **Volume confirmation** - is the move backed by above/below
                  average volume

                ### The backtest (why this is different from a normal scanner)
                The exact same rule-set above is replayed on every historical
                day in that stock's past year, and the actual next-day
                outcome is checked. This produces a real **Backtest Hit
                Rate %** and sample size for BULLISH calls and BEARISH calls
                *separately, per stock* - because a rule-set that works well
                on one stock may not work at all on another.

                **Confidence** is only marked:
                - **HIGH** if the backtest sample has 15+ occurrences and 65%+
                  historical hit-rate for that direction
                - **MEDIUM** if it has 7+ occurrences and 55%+ hit-rate
                - **LOW** otherwise - and the call is softened (e.g. "STRONG
                  BULLISH" becomes "BULLISH (Low Confidence)")

                ### Honest limitations
                - Past hit-rate does **not** guarantee future accuracy -
                  markets change regimes.
                - This does not account for company-specific news, results,
                  block deals, or broader market shocks happening tomorrow.
                - A ~1 year sample is limited; treat this as a **decision
                  support tool**, not a guarantee. Always apply your own risk
                  management (stop-loss, position sizing).
                """
            )
