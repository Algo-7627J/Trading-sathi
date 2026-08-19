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
import datetime as _dt
try:
    import extra_streamlit_components as stx
    _STX_AVAILABLE = True
except Exception:
    stx = None
    _STX_AVAILABLE = False
from services import build_universe
from analysis import scan_universe
from next_day import scan_next_day
from accuracy import save_predictions, load_predictions, score_predictions, accuracy_summary
from fii_dii import fetch_fii_dii, log_fii_dii, load_fii_dii_history
from delivery import (
    fetch_delivery_frame, delivery_date, combine_with_delivery,
    live_session_move, live_accuracy,
)
from commodities import get_metal_report
from momentum import (
    scan_strong_direction, scan_consecutive,
    render_momentum_card, render_streak_card,
)
from pead import scan_pead, render_pead_card, pead_table
from storage import ensure_data_files, save_latest_scan, append_signal_history, load_watchlist
from ui_helpers import (
    inject_custom_css, render_title, section_label, render_stat_row,
    render_watchlist_manager, render_next_day_results,
    sort_by_priority, render_compact_table_view, render_compact_cards_view,
    render_sector_card, render_bull_bear_sections, render_count_tile,
    render_sector_stock_row, render_footer, render_commodity_panel,
    render_fii_dii_banner, render_delivery_card,
)
from sectors import add_sector_column, get_sector_timeframe_stats, get_top_stocks_by_sector

st.set_page_config(page_title="RAO SAHAB", layout="wide", page_icon="📈")
inject_custom_css()
ensure_data_files()

# ====================== PERSISTENT FYERS LOGIN (Cookie - 12 hours) ======================
# This restores FYERS session from browser cookie so you don't generate auth_code again and again.
# Token is saved for 12 hours (FYERS tokens expire daily). Refreshing the page keeps you logged in.

_fyers_cookie_manager = None
try:
    if _STX_AVAILABLE and stx is not None:
        _fyers_cookie_manager = stx.CookieManager(key="fyers_persist_cookie_main")
        # small delay to let cookie load (required by extra_streamlit_components)
        _time.sleep(0.15)
        _saved_token = _fyers_cookie_manager.get(cookie="fyers_access_token")
        _saved_expiry = _fyers_cookie_manager.get(cookie="fyers_token_expiry")
        if st.session_state.get("fyers") is None and _saved_token and str(_saved_token) not in ("None", "", "null"):
            _is_expired = False
            if _saved_expiry:
                try:
                    _exp_ts = float(str(_saved_expiry))
                    if _time.time() > _exp_ts:
                        _is_expired = True
                except Exception:
                    pass
            if not _is_expired:
                try:
                    if fyersModel is not None:
                        _test_fyers = fyersModel.FyersModel(client_id=APP_ID, token=str(_saved_token), log_path="")
                        # Light validation - optional API call (profile). Skip if fails, still consider valid.
                        try:
                            # Don't fail if profile call fails - token might still be valid for data
                            _test_fyers.get_profile = getattr(_test_fyers, "get_profile", None)
                        except Exception:
                            pass
                        st.session_state.fyers = _test_fyers
                        st.session_state.access_token = str(_saved_token)
                except Exception:
                    pass
            else:
                try:
                    _fyers_cookie_manager.delete("fyers_access_token", key="persist_del_token_expired")
                    _fyers_cookie_manager.delete("fyers_token_expiry", key="persist_del_expiry_expired")
                except Exception:
                    pass
except Exception:
    pass

# Auto-capture FYERS redirect (if REDIRECT_URL = your streamlit app URL, no copy-paste needed)
if st.session_state.get("fyers") is None and fyersModel is not None:
    try:
        _qp = st.query_params
        _qp_auth = _qp.get("auth_code") or _qp.get("code") or _qp.get("authCode")
        if isinstance(_qp_auth, list):
            _qp_auth = _qp_auth[0] if _qp_auth else None
        if _qp_auth and len(str(_qp_auth).strip()) > 15:
            _qp_auth = str(_qp_auth).strip()
            try:
                _auto_session = fyersModel.SessionModel(
                    client_id=APP_ID,
                    secret_key=SECRET_KEY,
                    redirect_uri=REDIRECT_URL,
                    response_type="code",
                    grant_type="authorization_code"
                )
                _auto_session.set_token(_qp_auth)
                _auto_resp = _auto_session.generate_token()
                if _auto_resp and isinstance(_auto_resp, dict) and "access_token" in _auto_resp:
                    _auto_token = _auto_resp["access_token"]
                    st.session_state.fyers = fyersModel.FyersModel(client_id=APP_ID, token=_auto_token, log_path="")
                    st.session_state.access_token = _auto_token
                    if _STX_AVAILABLE and _fyers_cookie_manager is not None:
                        try:
                            _exp_dt = _dt.datetime.now() + _dt.timedelta(hours=12)
                            _exp_ts2 = _time.time() + 12*3600
                            _fyers_cookie_manager.set("fyers_access_token", _auto_token, expires_at=_exp_dt, key="auto_persist_set_token")
                            _fyers_cookie_manager.set("fyers_token_expiry", str(_exp_ts2), expires_at=_exp_dt, key="auto_persist_set_expiry")
                        except Exception:
                            pass
                    try:
                        st.query_params.clear()
                    except Exception:
                        pass
                    st.toast("✅ Auto-login successful! Staying logged in for 12 hours.", icon="🔐")
                    _time.sleep(0.8)
                    st.rerun()
            except Exception as _ae:
                # Don't block UI if auto-login fails, just show hint
                pass
    except Exception:
        pass
# ====================== END PERSISTENT LOGIN ======================



# ====================== SESSION STATE ======================
defaults = {
    "fyers": None,
    "access_token": None,
    "run_scan": False,
    "last_scan_df": None,
    "run_next_day_scan": False,
    "next_day_df": None,
    "accuracy_results": None,
    "show_strong_buy": False,
    "show_strong_sell": False,
    "selected_bullish_sector": None,
    "selected_bearish_sector": None,
    "sector_timeframe": "1D (Intraday)",
    "watchlist": [],
    "strong_direction_df": None,
    "streak_df": None,
    "pead_df": None,
    "run_sd_scan": False,
    "run_sk_scan": False,
    "run_pead_scan": False,
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
                    st.caption("💡 After login, you will be redirected back. If your FYERS Redirect URL is set to this Streamlit app URL, login will be automatic. Otherwise, copy the `auth_code` from the redirect URL and paste below.")
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
                            st.session_state.access_token = token
                            # --- Persist token to cookie for 12 hours (no more auth_code on refresh) ---
                            if _STX_AVAILABLE and _fyers_cookie_manager is not None:
                                try:
                                    _exp_dt2 = _dt.datetime.now() + _dt.timedelta(hours=12)
                                    _exp_ts3 = _time.time() + 12*3600
                                    _fyers_cookie_manager.set("fyers_access_token", token, expires_at=_exp_dt2, key="manual_persist_set_token")
                                    _fyers_cookie_manager.set("fyers_token_expiry", str(_exp_ts3), expires_at=_exp_dt2, key="manual_persist_set_expiry")
                                except Exception as _ce2:
                                    pass
                            try:
                                st.query_params.clear()
                            except Exception:
                                pass
                            st.success("✅ Login successful! You will stay logged in for 12 hours — no need to generate auth_code again on refresh.")
                            _time.sleep(0.8)
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
                st.session_state.access_token = None
                if _STX_AVAILABLE and _fyers_cookie_manager is not None:
                    try:
                        _fyers_cookie_manager.delete("fyers_access_token", key="logout_del_token")
                        _fyers_cookie_manager.delete("fyers_token_expiry", key="logout_del_expiry")
                    except Exception:
                        pass
                try:
                    _fyers_cookie_manager.delete("fyers_access_token", key="logout_del_token2") if _fyers_cookie_manager else None
                except Exception:
                    pass
                try:
                    st.query_params.clear()
                except Exception:
                    pass
                st.rerun()

        render_stat_row([
            {"label": "F&O Stocks", "value": len(uni["stocks"])},
            {"label": "Index", "value": len(uni["indices"])},
            {"label": "Commodities", "value": len(uni["commodities"])},
            {"label": "Total Universe", "value": len(uni["all"])},
        ])

        watchlist = load_watchlist()
        tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9 = st.tabs([
            "⚡ Intraday Scanner", "📅 Next-Day Outlook", "🏭 Sector Trend",
            "🥇 Gold & Silver", "🎯 Accuracy Report", "📦 Delivery Combo",
            "🧭 Strong Direction", "🔥 Streak Movers", "📢 PEAD Tool",
        ])

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

            nd_flow = st.checkbox(
                "🕒 Analyze last-30min flow (buying vs heavy selling)",
                value=True, key="nd_flow",
                help="Fetches 5-min candles to detect accumulation/distribution in the last 30 minutes of the session — a key next-day cue.",
            )

            if st.button("📅 Run Next-Day Analysis", type="primary", use_container_width=True, key="run_next_day"):
                st.session_state.run_next_day_scan = True

            if st.session_state.run_next_day_scan:
                st.session_state.run_next_day_scan = False
                if nd_symbols:
                    prog = st.progress(0.0, text="Analyzing next-day outlook…")
                    nd_result = scan_next_day(st.session_state.fyers, nd_symbols,
                                              progress=prog, include_flow=nd_flow)
                    prog.empty()
                    st.session_state.next_day_df = nd_result
                    try:
                        save_predictions(nd_result)
                        st.caption("📝 Today's outlook saved to the Accuracy Tracker (Tab 5).")
                    except Exception:
                        pass

            # ---- FII / DII market-wide sentiment (cached for the session) ----
            if "fii_dii" not in st.session_state:
                with st.spinner("Fetching FII/DII data…"):
                    fd = fetch_fii_dii()
                if fd:
                    log_fii_dii(fd)
                st.session_state.fii_dii = fd
            if st.session_state.get("fii_dii"):
                render_fii_dii_banner(st.session_state.fii_dii)
            with st.expander("📜 FII/DII History"):
                hist = load_fii_dii_history()
                if hist.empty:
                    st.caption("No history yet — a new row is saved each time you open this tab.")
                else:
                    st.dataframe(hist, use_container_width=True, hide_index=True)

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

        # ==================== TAB 5: ACCURACY REPORT ====================
        with tab5:
            section_label("🎯 Prediction Accuracy Tracker")
            st.caption("Each Next-Day Outlook (Tab 2) is logged automatically. Here we compare every "
                       "prediction against the market's actual next-day move, so you can see how accurate "
                       "the app really is over time.")

            preds = load_predictions()

            if preds is None or preds.empty:
                st.info("📭 No predictions logged yet.\n\n"
                        "Run the **📅 Next-Day Analysis** on Tab 2 — the outlooks are saved here automatically. "
                        "Come back after the next trading day to see how they performed.")
            else:
                n_dates = preds["Prediction_Date"].astype(str).nunique()
                c1, c2 = st.columns([2, 1])
                with c1:
                    st.markdown(f"**{len(preds)}** predictions logged across **{n_dates}** trading day(s).")
                with c2:
                    refresh = st.button("🔄 Refresh Accuracy", type="primary",
                                        use_container_width=True, key="accuracy_refresh")

                if refresh:
                    st.session_state.accuracy_results = None

                if st.session_state.get("accuracy_results") is None:
                    if st.session_state.fyers is None:
                        st.warning("🔒 Not connected to market data. Log in to refresh accuracy.")
                    else:
                        with st.spinner("Fetching actual market moves & scoring predictions…"):
                            prog = st.progress(0.0, text="Checking predictions…")
                            results = score_predictions(st.session_state.fyers, progress=prog)
                            prog.empty()
                        st.session_state.accuracy_results = results

                results = st.session_state.get("accuracy_results")
                if results is not None and not results.empty:
                    s = accuracy_summary(results)

                    n1, n2, n3, n4 = st.columns(4)
                    acc_txt = f"{s['accuracy']:.1f}%" if s["accuracy"] is not None else "—"
                    with n1:
                        render_count_tile("ACCURACY", acc_txt, "green", "🎯")
                    with n2:
                        render_count_tile("CORRECT", s["correct"], "green", "✅")
                    with n3:
                        render_count_tile("WRONG", s["wrong"], "red", "❌")
                    with n4:
                        render_count_tile("PENDING", s["pending"], "gray", "⏳")

                    st.caption(f"➖ Sideways (within ±{0.30}%): **{s['sideways']}** · "
                               f"Total predictions: **{s['total']}**")

                    st.divider()
                    section_label("Detailed Results")

                    view = st.radio("View", ["Table", "By Day"], horizontal=True, key="acc_view_mode")
                    disp = results.copy()
                    vmap = {
                        "Correct": "✅ Correct", "Wrong": "❌ Wrong",
                        "Sideways": "➖ Sideways", "Pending": "⏳ Pending",
                    }
                    disp["Verdict"] = disp["Verdict"].map(vmap).fillna(disp["Verdict"])
                    disp["Actual_Move_Pct"] = disp["Actual_Move_Pct"].apply(
                        lambda x: f"{x:+.2f}%" if pd.notna(x) else "—")
                    disp = disp.sort_values(
                        ["Prediction_Date", "Verdict", "Symbol"], ascending=[False, True, True])

                    show_cols = [c for c in ["Prediction_Date", "Symbol", "Bias", "Outlook",
                                             "Last30Min", "Actual_Move_Pct", "Verdict", "Next_Date"]
                                 if c in disp.columns]

                    if view == "By Day":
                        for d, g in disp.groupby("Prediction_Date", sort=False):
                            st.markdown(f"**📅 {d}** — "
                                        f"{g[g['Verdict'].str.contains('Correct', na=False)].shape[0]} correct · "
                                        f"{g[g['Verdict'].str.contains('Wrong', na=False)].shape[0]} wrong · "
                                        f"{g[g['Verdict'].str.contains('Pending', na=False)].shape[0]} pending")
                            st.dataframe(g[show_cols], use_container_width=True, hide_index=True)
                    else:
                        st.dataframe(disp[show_cols], use_container_width=True, hide_index=True)

                    st.download_button(
                        "⬇️ Download Accuracy Report (CSV)",
                        results.to_csv(index=False).encode(),
                        "accuracy_report.csv",
                        "text/csv",
                    )
                elif results is not None:
                    st.info("No results to show yet.")

        # ==================== TAB 6: DELIVERY COMBO ====================
        with tab6:
            section_label("📦 High Delivery + Scan Combo")
            st.caption("Delivery % = shares actually delivered to buyers vs total traded. "
                       "A **bullish scan signal + high delivery %** means investors are taking delivery, "
                       "not just intraday speculation — a stronger, conviction-based next-day cue.")

            c1, c2, c3 = st.columns([2, 1, 1])
            with c1:
                src = st.selectbox(
                    "Combine with", ["Intraday Scanner", "Next-Day Outlook"], key="delivery_src")
            with c2:
                min_delivery = st.slider("Min delivery %", 0, 100, 0, 5, key="delivery_min_pct")
            with c3:
                top_n = st.number_input("Top N (0 = All)", min_value=0, value=25, step=5, key="delivery_top_n")

            # ---- fetch delivery data (bulk MTO, cached) ----
            if st.button("🔄 Fetch Delivery Data", key="delivery_refresh", use_container_width=True):
                st.session_state.delivery_force = True

            with st.spinner("Loading security-wise delivery data…"):
                ddf = fetch_delivery_frame(force_refresh=st.session_state.get("delivery_force", False))
            st.session_state.delivery_force = False

            if ddf.empty:
                st.warning("⚠️ Could not load delivery data from NSE. Try again later.")
            else:
                ddate = delivery_date(ddf)
                st.caption(f"📆 Delivery data as of **{ddate}** (NSE security-wise delivery, published after market close).")

                # ---- pick the scan source ----
                if src == "Intraday Scanner":
                    scan_df = st.session_state.get("last_scan_df")
                else:
                    scan_df = st.session_state.get("next_day_df")

                if scan_df is None or scan_df.empty:
                    st.info(f"⚠️ No **{src}** results yet. Run the scan on its tab first, "
                            "then come back here to see the delivery combo.")
                else:
                    merged = combine_with_delivery(scan_df, ddf)
                    if merged.empty:
                        st.info("No overlapping symbols between the scan and delivery data.")
                    else:
                        merged = merged[merged["DeliveryPct"] >= min_delivery]

                        bull = merged[merged["Direction"] == "Bullish"]
                        bear = merged[merged["Direction"] == "Bearish"]
                        neu = merged[merged["Direction"] == "Neutral"]

                        t1, t2, t3 = st.columns(3)
                        with t1:
                            render_count_tile("BULLISH + DELIVERY", len(bull), "green", "📦")
                        with t2:
                            render_count_tile("BEARISH + DELIVERY", len(bear), "red", "📦")
                        with t3:
                            render_count_tile("NEUTRAL", len(neu), "gray", "⚪")

                        def _top(tbl):
                            return tbl.head(top_n) if top_n > 0 else tbl

                        bull_top = _top(bull)
                        bear_top = _top(bear)

                        view = st.radio("View Mode", ["Cards", "Table"], horizontal=True, key="delivery_view")

                        def _show(tbl, head):
                            if tbl.empty:
                                st.caption("No stocks matching this filter.")
                                return
                            st.markdown(head, unsafe_allow_html=True)
                            if view == "Cards":
                                for _, r in tbl.iterrows():
                                    st.markdown(render_delivery_card(r), unsafe_allow_html=True)
                            else:
                                show = [c for c in ["Symbol", "DeliveryPct", "QtyTraded",
                                                    "DeliverableQty", "Signal", "Bias", "Outlook",
                                                    "LTP", "Score", "Confidence", "Last30Min"]
                                        if c in tbl.columns]
                                t = tbl.copy()
                                if "DeliveryPct" in t.columns:
                                    t["DeliveryPct"] = t["DeliveryPct"].apply(lambda x: f"{x:.2f}%")
                                if "QtyTraded" in t.columns:
                                    t["QtyTraded"] = t["QtyTraded"].apply(lambda x: f"{x:,}")
                                if "DeliverableQty" in t.columns:
                                    t["DeliverableQty"] = t["DeliverableQty"].apply(lambda x: f"{x:,}")
                                st.dataframe(t[show], use_container_width=True, hide_index=True)

                        st.divider()
                        section_label("🟢 Highest Delivery + Bullish")
                        _show(bull_top, "#### 🟢 Highest Delivery + Bullish (conviction buying)")

                        st.divider()
                        section_label("🔴 Highest Delivery + Bearish")
                        _show(bear_top, "#### 🔴 Highest Delivery + Bearish (delivery-based selling)")

                        st.download_button(
                            "⬇️ Download Delivery Combo (CSV)",
                            merged.to_csv(index=False).encode(),
                            "delivery_combo.csv",
                            "text/csv",
                        )

                        # ==================== LIVE SESSION CHECK ====================
                        st.divider()
                        section_label("🎯 Live Session Check — are the combos behaving?")
                        st.caption("Checks **today's live move** (vs previous close) for each combo stock. "
                                   "A 🟢 bullish+delivery stock should be **rising** today; a 🔴 bearish+delivery "
                                   "stock should be **falling** — the ✓/✗ shows who's on track right now.")

                        if st.button("🔴 Run Live Check", type="primary", use_container_width=True, key="delivery_live_run"):
                            st.session_state.delivery_live = None
                            st.session_state.delivery_live_requested = True

                        check_df = pd.concat([bull_top, bear_top], ignore_index=True)
                        if check_df.empty:
                            st.info("No combo stocks to check (empty bullish/bearish lists).")
                        elif st.session_state.get("delivery_live_requested"):
                            if st.session_state.get("delivery_live") is None:
                                with st.spinner("Fetching today's live moves…"):
                                    prog = st.progress(0.0, text="Checking live moves…")
                                    live_df = live_session_move(st.session_state.fyers, check_df, progress=prog)
                                    prog.empty()
                                st.session_state.delivery_live = live_df

                        live_df = st.session_state.get("delivery_live")
                        if not st.session_state.get("delivery_live_requested"):
                            st.caption("👆 Click **🔴 Run Live Check** to compare each combo call against today's live movement.")
                        elif live_df is not None and not live_df.empty:
                            bull_live = live_df[live_df["Direction"] == "Bullish"]
                            bear_live = live_df[live_df["Direction"] == "Bearish"]
                            sb = live_accuracy(bull_live)
                            sr = live_accuracy(bear_live)
                            sa = live_accuracy(live_df)

                            def _ontrack(s):
                                return f"{s['correct']}/{s['correct'] + s['wrong']}" if (s["correct"] + s["wrong"]) else "—"

                            a1, a2, a3 = st.columns(3)
                            with a1:
                                render_count_tile("BULLISH ON TRACK", _ontrack(sb), "green", "🟢📦")
                            with a2:
                                render_count_tile("BEARISH ON TRACK", _ontrack(sr), "red", "🔴📦")
                            with a3:
                                acc_txt = f"{sa['accuracy']:.0f}%" if sa["accuracy"] is not None else "—"
                                render_count_tile("OVERALL ACCURACY", acc_txt, "gray", "🎯")

                            live_map = live_df.set_index("Symbol").to_dict("index")

                            def _show_live(tbl, head):
                                if tbl.empty:
                                    st.caption("No stocks.")
                                    return
                                st.markdown(head, unsafe_allow_html=True)
                                if view == "Cards":
                                    for _, r in tbl.iterrows():
                                        lv = live_map.get(r["Symbol"])
                                        st.markdown(render_delivery_card(r, live=lv), unsafe_allow_html=True)
                                else:
                                    disp = live_df[live_df["Symbol"].isin(tbl["Symbol"].tolist())].copy()
                                    disp = disp[["Symbol", "Direction", "DeliveryPct", "PrevClose", "LTP", "MovePct", "Status"]]
                                    if "DeliveryPct" in disp.columns:
                                        disp["DeliveryPct"] = disp["DeliveryPct"].apply(lambda x: f"{x:.2f}%")
                                    if "MovePct" in disp.columns:
                                        disp["MovePct"] = disp["MovePct"].apply(lambda x: f"{x:+.2f}%" if pd.notna(x) else "—")
                                    st.dataframe(disp, use_container_width=True, hide_index=True)

                            st.divider()
                            _show_live(bull_top, "#### 🟢 Bullish Combo — live behaviour")
                            st.divider()
                            _show_live(bear_top, "#### 🔴 Bearish Combo — live behaviour")

                            st.download_button(
                                "⬇️ Download Live Check (CSV)",
                                live_df.to_csv(index=False).encode(),
                                "delivery_live_check.csv",
                                "text/csv",
                            )

        # ==================== TAB 7: STRONG DIRECTION (1D + 1W + 1M) ====================
        with tab7:
            section_label("🧭 Strong Direction — 1D · 1W · 1M Aligned")
            st.caption("Stocks whose momentum points the **same way** across the 1-day, 1-week and 1-month "
                       "timeframes. All three green = Strong Up, all three red = Strong Down — a clean, "
                       "high-conviction directional bias. Built from ~1 year of daily candles.")

            sd1, sd2, sd3 = st.columns([2, 1, 1])
            with sd1:
                sd_scope = st.selectbox(
                    "Universe",
                    ["Only F&O Stocks", "Everything", "Only Watchlist"],
                    key="sd_scope",
                )
            with sd2:
                sd_min = st.number_input("Min move per timeframe (%)", min_value=0.0, value=0.5, step=0.1, key="sd_min")
            with sd3:
                sd_limit = st.number_input("Max symbols (0 = All)", min_value=0, value=0, step=10, key="sd_limit")

            if sd_scope == "Everything":
                sd_chosen = uni["all"]
            elif sd_scope == "Only Watchlist":
                sd_chosen = watchlist if watchlist else uni["stocks"]
            else:
                sd_chosen = uni["stocks"]
            if sd_limit > 0:
                sd_chosen = sd_chosen[:sd_limit]

            if st.button("🧭 Run Strong Direction Scan", type="primary", use_container_width=True, key="run_sd"):
                st.session_state.run_sd_scan = True

            if st.session_state.get("run_sd_scan"):
                st.session_state.run_sd_scan = False
                prog = st.progress(0.0, text="Scanning multi-timeframe momentum…")
                sd_df = scan_strong_direction(st.session_state.fyers, sd_chosen, min_move=sd_min, progress=prog)
                prog.empty()
                st.session_state.strong_direction_df = sd_df

            sd_df = st.session_state.get("strong_direction_df")
            if sd_df is not None and not sd_df.empty:
                up = sd_df[sd_df["Direction"] == "Strong Up"].sort_values("Avg %", ascending=False)
                down = sd_df[sd_df["Direction"] == "Strong Down"].sort_values("Avg %", ascending=True)

                s1, s2 = st.columns(2)
                with s1:
                    render_count_tile("STRONG UP (1D+1W+1M)", len(up), "green", "🟢")
                with s2:
                    render_count_tile("STRONG DOWN (1D+1W+1M)", len(down), "red", "🔴")

                view = st.radio("View Mode", ["Cards", "Table"], horizontal=True, key="sd_view", label_visibility="collapsed")

                st.divider()
                section_label("🟢 Strong Up — all timeframes bullish")
                if up.empty:
                    st.caption("No strong-up stocks found at the current minimum move.")
                elif view == "Cards":
                    for _, r in up.iterrows():
                        st.markdown(render_momentum_card(r), unsafe_allow_html=True)
                else:
                    st.dataframe(up, use_container_width=True, hide_index=True)

                st.divider()
                section_label("🔴 Strong Down — all timeframes bearish")
                if down.empty:
                    st.caption("No strong-down stocks found at the current minimum move.")
                elif view == "Cards":
                    for _, r in down.iterrows():
                        st.markdown(render_momentum_card(r), unsafe_allow_html=True)
                else:
                    st.dataframe(down, use_container_width=True, hide_index=True)

                st.download_button("⬇️ Download CSV", sd_df.to_csv(index=False).encode(), "strong_direction.csv", "text/csv")
            elif sd_df is not None:
                st.info("No stocks with all three timeframes aligned at the current minimum move.")
            else:
                st.info("👆 Click **Run Strong Direction Scan** to find stocks aligned across 1D, 1W and 1M.")

        # ==================== TAB 8: CONSECUTIVE STREAK ====================
        with tab8:
            section_label("🔥 Consecutive Streak Movers")
            st.caption("Stocks that have closed **UP** (or **DOWN**) for N days in a row. Persistent one-way "
                       "closes usually flag strong momentum — and moves that may be getting over-extended.")

            sk1, sk2, sk3 = st.columns([2, 1, 1])
            with sk1:
                sk_scope = st.selectbox("Universe", ["Only F&O Stocks", "Everything", "Only Watchlist"], key="sk_scope")
            with sk2:
                sk_min = st.number_input("Min consecutive days", min_value=3, max_value=15, value=5, step=1, key="sk_min")
            with sk3:
                sk_limit = st.number_input("Max symbols (0 = All)", min_value=0, value=0, step=10, key="sk_limit")

            if sk_scope == "Everything":
                sk_chosen = uni["all"]
            elif sk_scope == "Only Watchlist":
                sk_chosen = watchlist if watchlist else uni["stocks"]
            else:
                sk_chosen = uni["stocks"]
            if sk_limit > 0:
                sk_chosen = sk_chosen[:sk_limit]

            if st.button("🔥 Run Streak Scan", type="primary", use_container_width=True, key="run_sk"):
                st.session_state.run_sk_scan = True

            if st.session_state.get("run_sk_scan"):
                st.session_state.run_sk_scan = False
                prog = st.progress(0.0, text="Counting consecutive closes…")
                sk_df = scan_consecutive(st.session_state.fyers, sk_chosen, min_streak=sk_min, progress=prog)
                prog.empty()
                st.session_state.streak_df = sk_df

            sk_df = st.session_state.get("streak_df")
            if sk_df is not None and not sk_df.empty:
                up = sk_df[sk_df["Direction"] == "Up"].sort_values("Streak", ascending=False)
                down = sk_df[sk_df["Direction"] == "Down"].sort_values("Streak", ascending=False)

                k1, k2 = st.columns(2)
                with k1:
                    render_count_tile("CONSECUTIVE UP DAYS", len(up), "green", "🟢")
                with k2:
                    render_count_tile("CONSECUTIVE DOWN DAYS", len(down), "red", "🔴")

                view = st.radio("View Mode", ["Cards", "Table"], horizontal=True, key="sk_view", label_visibility="collapsed")

                st.divider()
                section_label(f"🟢 Up {sk_min}+ days in a row")
                if up.empty:
                    st.caption("No stocks with a consecutive up-streak at this length.")
                elif view == "Cards":
                    for _, r in up.iterrows():
                        st.markdown(render_streak_card(r), unsafe_allow_html=True)
                else:
                    st.dataframe(up, use_container_width=True, hide_index=True)

                st.divider()
                section_label(f"🔴 Down {sk_min}+ days in a row")
                if down.empty:
                    st.caption("No stocks with a consecutive down-streak at this length.")
                elif view == "Cards":
                    for _, r in down.iterrows():
                        st.markdown(render_streak_card(r), unsafe_allow_html=True)
                else:
                    st.dataframe(down, use_container_width=True, hide_index=True)

                st.download_button("⬇️ Download CSV", sk_df.to_csv(index=False).encode(), "consecutive_streaks.csv", "text/csv")
            elif sk_df is not None:
                st.info(f"No stocks with {sk_min}+ consecutive same-direction closes right now.")
            else:
                st.info(f"👆 Click **Run Streak Scan** to find stocks closing up or down {sk_min}+ days in a row.")

        # ==================== TAB 9: PEAD TOOL ====================
        with tab9:
            section_label("📢 PEAD — Post-Earnings Announcement Drift")
            st.caption("Stocks that have **already declared results**. For each stock: **Result Quality** "
                       "(Good / Mixed / Bad — scored from the EPS surprise vs estimates plus Revenue & Profit "
                       "YoY growth) and the **post-result drift** — is the stock still *running* after the "
                       "announcement?")

            pe1, pe2 = st.columns([2, 1])
            with pe1:
                pe_scope = st.selectbox("Universe", ["Only F&O Stocks", "Only Watchlist"], key="pe_scope")
            with pe2:
                pe_limit = st.number_input(
                    "Max symbols (0 = All)", min_value=0, value=60, step=10, key="pe_limit",
                    help="Earnings data is fetched one symbol at a time from Yahoo Finance — scanning the full list takes a few minutes.",
                )

            if pe_scope == "Only Watchlist":
                pe_chosen = watchlist if watchlist else uni["stocks"]
            else:
                pe_chosen = uni["stocks"]
            if pe_limit > 0:
                pe_chosen = pe_chosen[:pe_limit]

            st.caption("ℹ️ Data source: Yahoo Finance earnings calendar + financials, plus FYERS/Yahoo daily candles "
                       "for the drift. A few NSE symbols have no earnings dates in Yahoo — they are simply skipped.")

            if st.button("📢 Run PEAD Scan", type="primary", use_container_width=True, key="run_pead"):
                st.session_state.run_pead_scan = True

            if st.session_state.get("run_pead_scan"):
                st.session_state.run_pead_scan = False
                prog = st.progress(0.0, text="Fetching earnings & computing drift…")
                pe_df = scan_pead(st.session_state.fyers, pe_chosen, progress=prog)
                prog.empty()
                st.session_state.pead_df = pe_df

            pe_df = st.session_state.get("pead_df")
            if pe_df is not None and not pe_df.empty:
                running = pe_df[pe_df["PEAD"].str.contains("Running Up|Drifting Down", case=False, na=False)]
                good = pe_df[pe_df["Quality"] == "Good"]
                bad = pe_df[pe_df["Quality"] == "Bad"]
                p1, p2, p3 = st.columns(3)
                with p1:
                    render_count_tile("RUNNING AFTER RESULTS", len(running), "green", "📢")
                with p2:
                    render_count_tile("GOOD RESULT", len(good), "green", "✅")
                with p3:
                    render_count_tile("BAD RESULT", len(bad), "red", "❌")

                view = st.radio("View Mode", ["Cards", "Table"], horizontal=True, key="pe_view", label_visibility="collapsed")

                def _show_pead(tbl, head):
                    if tbl.empty:
                        st.caption("Nothing in this bucket.")
                        return
                    st.markdown(head, unsafe_allow_html=True)
                    if view == "Cards":
                        for _, r in tbl.iterrows():
                            st.markdown(render_pead_card(r), unsafe_allow_html=True)
                    else:
                        st.dataframe(pead_table(tbl), use_container_width=True, hide_index=True)

                st.divider()
                _show_pead(pe_df[pe_df["PEAD"].str.contains("Running Up", case=False, na=False)],
                           "#### 🚀 Running Up after results")
                st.divider()
                _show_pead(pe_df[pe_df["PEAD"].str.contains("Drifting Down", case=False, na=False)],
                           "#### 🔻 Drifting Down after results")
                st.divider()
                _show_pead(pe_df[pe_df["PEAD"].str.contains("good result|bad result", case=False, na=False)],
                           "#### ⚠️ Divergence — price drift vs result quality")
                st.divider()
                _show_pead(pe_df[pe_df["PEAD"].str.contains("No Clear Drift", case=False, na=False)],
                           "#### ➖ No clear drift")

                st.download_button("⬇️ Download PEAD CSV", pe_df.to_csv(index=False).encode(), "pead_tool.csv", "text/csv")
            elif pe_df is not None:
                st.info("No recent reported earnings found for the scanned symbols.")
            else:
                st.info("👆 Click **Run PEAD Scan** to find stocks with recent results and check whether they're still drifting.")

    except Exception as e:
        st.error(f"App Error: {e}")
        st.exception(e)

render_footer()
