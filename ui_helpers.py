# ui_helpers.py — Groww-style UI components for RAO SAHAB
import streamlit as st
import pandas as pd

# ====================== GROWW-STYLE DESIGN TOKENS ======================
GREEN = "#00B386"        # Groww positive green
GREEN_DARK = "#00875F"
RED = "#EB5B3C"          # Groww negative red
RED_DARK = "#C93A20"
INK = "#44475B"          # primary text
HEADING = "#2B2D3F"      # heading text
MUTED = "#7C7E8C"        # secondary text
BORDER = "#E9EBEE"
GREEN_TINT = "#E5F7F0"
RED_TINT = "#FDECE8"
GRAY_TINT = "#F1F2F4"
NEUT_BAR = "#EEF0F2"


def inject_custom_css():
    st.markdown("""
    <style>
    /* ---------- Base ---------- */
    .stApp { background-color: #FFFFFF; color: #44475B; }
    .block-container { padding-top: 1.6rem; max-width: 1180px; }
    h1, h2, h3, h4 { color: #2B2D3F; }

    /* ---------- Sidebar ---------- */
    section[data-testid="stSidebar"] {
        background: #F8F9FA;
        border-right: 1px solid #E9EBEE;
    }

    /* ---------- Buttons ---------- */
    .stButton > button {
        border-radius: 8px;
        border: 1px solid #DCE0E4;
        background: #FFFFFF;
        color: #44475B;
        font-weight: 600;
        transition: all .15s ease;
    }
    .stButton > button:hover {
        border-color: #00B386;
        color: #00875F;
        box-shadow: 0 1px 4px rgba(0,179,134,.18);
    }
    .stButton > button[kind="primary"] {
        background: #00B386;
        border-color: #00B386;
        color: #FFFFFF;
    }
    .stButton > button[kind="primary"]:hover {
        background: #009E76;
        border-color: #009E76;
        color: #FFFFFF;
    }

    /* ---------- Tabs ---------- */
    .stTabs [data-baseweb="tab-list"] {
        gap: 6px;
        border-bottom: 1px solid #EEF0F2;
    }
    .stTabs [data-baseweb="tab"] {
        font-weight: 600;
    }

    /* ---------- Inputs / widgets polish ---------- */
    [data-testid="stDataFrame"] {
        border: 1px solid #E9EBEE;
        border-radius: 12px;
    }
    [data-testid="stExpander"] {
        border: 1px solid #E9EBEE;
        border-radius: 10px;
    }
    div[data-testid="stTextInput"] input,
    div[data-testid="stNumberInput"] input,
    div[data-baseweb="select"] > div {
        border-radius: 8px !important;
    }
    hr { border-color: #EEF0F2; }

    /* ---------- Groww-style cards ---------- */
    .opl-card {
        background: #FFFFFF;
        border: 1px solid #E9EBEE;
        border-radius: 12px;
        padding: 12px 14px;
        margin-bottom: 10px;
        box-shadow: 0 1px 2px rgba(23,24,29,.04);
    }
    .opl-card.bull { border-left: 4px solid #00B386; }
    .opl-card.bear { border-left: 4px solid #EB5B3C; }
    .opl-sym { font-size: 16px; font-weight: 700; color: #2F3244; }
    .opl-sector { font-size: 12px; color: #7C7E8C; margin-left: 7px; font-weight: 500; }
    .opl-price { font-weight: 700; color: #44475B; font-size: 15px; }
    .opl-sub { font-size: 12.5px; color: #7C7E8C; margin-top: 6px; }

    .chip {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 999px;
        font-size: 12px;
        font-weight: 600;
    }
    .chip-green { background: #E5F7F0; color: #00875F; }
    .chip-red { background: #FDECE8; color: #C93A20; }
    .chip-gray { background: #F1F2F4; color: #7C7E8C; }

    .opl-tile {
        background: #FFFFFF;
        border: 1px solid #E9EBEE;
        border-radius: 12px;
        padding: 14px 16px;
        text-align: center;
        box-shadow: 0 1px 2px rgba(23,24,29,.04);
    }
    .opl-tile .lbl { font-size: 13px; color: #7C7E8C; font-weight: 600; }
    .opl-tile .val { font-size: 30px; font-weight: 800; margin-top: 2px; }

    .opl-sechead {
        display: flex; align-items: center; gap: 8px;
        margin: 16px 0 8px 0;
    }
    .opl-sechead .t { font-size: 16.5px; font-weight: 700; color: #2B2D3F; }
    </style>
    """, unsafe_allow_html=True)


# ====================== SMALL FORMATTERS ======================
def _fmt_money(v):
    try:
        return f"₹{float(v):,.2f}"
    except (TypeError, ValueError):
        return f"₹{v}"


def _chip(text, tone="gray"):
    return f'<span class="chip chip-{tone}">{text}</span>'


def _tone_for_signal(signal):
    s = str(signal).lower()
    if "buy" in s or "bullish" in s:
        return "green"
    if "sell" in s or "bearish" in s:
        return "red"
    return "gray"


# ====================== LAYOUT PIECES ======================
def render_title(title, subtitle, connected=False):
    """Groww-style top navbar."""
    dot, dtxt, dcol = ("●", "FYERS Connected", GREEN_DARK) if connected else ("○", "Not Connected", MUTED)
    st.markdown(f"""
    <div style="display:flex; align-items:center; gap:14px; padding:6px 0 14px 0;
                border-bottom:1px solid {NEUT_BAR}; margin-bottom:16px;">
        <div style="width:44px; height:44px; border-radius:12px;
                    background:linear-gradient(135deg,#00B386,#00D09C);
                    display:flex; align-items:center; justify-content:center;
                    color:#fff; font-weight:700; font-size:18px; box-shadow:0 2px 6px rgba(0,179,134,.35);">RS</div>
        <div>
            <div style="font-size:22px; font-weight:700; color:{HEADING}; line-height:1.15;">{title}</div>
            <div style="font-size:13px; color:{MUTED};">{subtitle}</div>
        </div>
        <div style="margin-left:auto; font-size:13px; font-weight:600; color:{dcol};">{dot} {dtxt}</div>
    </div>
    """, unsafe_allow_html=True)


def section_label(text):
    st.markdown(
        f"<div class='opl-sechead'><span class='t'>{text}</span></div>",
        unsafe_allow_html=True,
    )


def render_stat_row(stats):
    cols = st.columns(len(stats))
    for i, stat in enumerate(stats):
        with cols[i]:
            st.markdown(f"""
            <div class="opl-tile">
                <div class="lbl">{stat['label']}</div>
                <div class="val" style="color:{ink_or(stat)}">{stat['value']}</div>
            </div>
            """, unsafe_allow_html=True)


def ink_or(stat):
    return stat.get("color", INK)


# ====================== COUNT TILES (Strong Buy / Strong Sell etc.) ======================
def render_count_tile(label, count, tone="green", icon=""):
    tones = {
        "green": (GREEN_DARK, GREEN_TINT, "#BFE9D8"),
        "red": (RED_DARK, RED_TINT, "#F3CDC2"),
        "gray": (MUTED, GRAY_TINT, BORDER),
    }
    c, bg, brd = tones.get(tone, tones["gray"])
    st.markdown(f"""
    <div style="background:{bg}; border:1px solid {brd}; border-radius:14px;
                padding:20px; text-align:center;">
        <div style="font-size:14px; font-weight:600; color:{c};">{icon} {label}</div>
        <div style="font-size:40px; font-weight:700; color:{c}; margin-top:2px;">{count}</div>
    </div>
    """, unsafe_allow_html=True)


# ====================== WATCHLIST ======================
def render_watchlist_manager(all_symbols):
    st.markdown("**⭐ Watchlist**")
    watchlist = st.session_state.get("watchlist", [])

    if "watchlist" not in st.session_state:
        st.session_state.watchlist = []

    col1, col2 = st.columns([3, 1])
    with col1:
        new_sym = st.text_input("Add symbol", placeholder="e.g. RELIANCE", label_visibility="collapsed")
    with col2:
        if st.button("Add", use_container_width=True):
            if new_sym and new_sym.upper() not in st.session_state.watchlist:
                st.session_state.watchlist.append(new_sym.upper())
                st.rerun()

    if watchlist:
        st.caption("Current Watchlist:")
        for i, sym in enumerate(watchlist):
            c1, c2 = st.columns([4, 1])
            c1.write(sym)
            if c2.button("✕", key=f"rm_{i}", use_container_width=True):
                st.session_state.watchlist.remove(sym)
                st.rerun()
    else:
        st.caption("No symbols in watchlist")


# ====================== MOST BULLISH / MOST BEARISH ======================
def split_bull_bear(df, top_n=6):
    """
    Return (bullish_df, bearish_df) — top ranked.
    Works for intraday result frames (Signal/Score) and
    next-day frames (Outlook/Bias/Confidence — auto-detected).
    """
    empty = df.head(0) if df is not None else df
    if df is None or df.empty:
        return empty, empty

    if "Outlook" in df.columns:  # ---- NEXT-DAY MODE ----
        bias_col = "Bias" if "Bias" in df.columns else "Outlook"
        bias = df[bias_col].astype(str)
        bull = df[bias.str.contains("Bullish", case=False, na=False)]
        bear = df[bias.str.contains("Bearish", case=False, na=False)]
        sort_col = "Confidence" if "Confidence" in df.columns else None
        if sort_col:
            bull = bull.sort_values(sort_col, ascending=False)
            bear = bear.sort_values(sort_col, ascending=False)
        return bull.head(top_n), bear.head(top_n)

    # ---- INTRADAY MODE ----
    sig = df["Signal"].astype(str) if "Signal" in df.columns else pd.Series("", index=df.index)
    bull = df[sig.str.contains("Buy|Bullish", case=False, na=False)]
    bear = df[sig.str.contains("Sell|Bearish", case=False, na=False)]
    if "Score" in df.columns:
        bull = bull.sort_values("Score", ascending=False)
        bear = bear.sort_values("Score", ascending=True)
    return bull.head(top_n), bear.head(top_n)


def _intraday_stock_card(row):
    symbol = row.get("Symbol", "N/A")
    sector = row.get("Sector", "")
    ltp = _fmt_money(row.get("LTP", "N/A"))
    signal = str(row.get("Signal", "Neutral"))
    score = row.get("Score", 0)
    try:
        score = f"{float(score):.1f}"
    except (TypeError, ValueError):
        pass
    pattern = row.get("Pattern", "N/A")
    mtf = row.get("MTF Status", "N/A")
    vol = row.get("Volume", "N/A")
    tone = _tone_for_signal(signal)
    side = "bull" if tone == "green" else "bear" if tone == "red" else ""

    return f"""
    <div class="opl-card {side}">
        <div style="display:flex; justify-content:space-between; align-items:center;">
            <div><span class="opl-sym">{symbol}</span><span class="opl-sector">{sector}</span></div>
            <div class="opl-price">{ltp}</div>
        </div>
        <div style="display:flex; justify-content:space-between; align-items:center; margin-top:7px;">
            <div>{_chip(signal, tone)}<span style="font-size:12px; color:{MUTED}; margin-left:7px;">Score {score}</span></div>
            <div style="font-size:12px; color:{MUTED};">{pattern} • MTF {mtf} • Vol {vol}</div>
        </div>
    </div>"""


def _nextday_stock_card(row):
    symbol = row.get("Symbol", "N/A")
    sector = row.get("Sector", "")
    outlook = str(row.get("Outlook", "Neutral"))
    exp_move = row.get("Expected_Move", "N/A")
    try:
        conf = int(float(row.get("Confidence", 0)))
    except (TypeError, ValueError):
        conf = 0
    key_levels = row.get("Key_Levels", "")
    ltp = row.get("LTP", None)
    tone = _tone_for_signal(outlook)
    side = "bull" if tone == "green" else "bear" if tone == "red" else ""
    bar_col = GREEN if tone == "green" else RED if tone == "red" else "#C9CDD4"
    ltp_html = f'<span class="opl-price" style="margin-right:10px;">{_fmt_money(ltp)}</span>' if ltp is not None else ""

    return f"""
    <div class="opl-card {side}">
        <div style="display:flex; justify-content:space-between; align-items:center;">
            <div><span class="opl-sym">{symbol}</span><span class="opl-sector">{sector}</span></div>
            <div>{ltp_html}{_chip(outlook, tone)}</div>
        </div>
        <div style="display:flex; justify-content:space-between; align-items:center; margin-top:7px;">
            <span style="font-size:13px; color:{INK}; font-weight:600;">Exp. Move: {exp_move}</span>
            <span style="font-size:12px; color:{MUTED};">{key_levels}</span>
        </div>
        <div style="display:flex; align-items:center; gap:8px; margin-top:9px;">
            <div style="flex:1; background:{NEUT_BAR}; border-radius:999px; height:6px;">
                <div style="width:{conf}%; background:{bar_col}; height:6px; border-radius:999px;"></div>
            </div>
            <span style="font-size:12px; color:{MUTED}; white-space:nowrap;">{conf}% conf.</span>
        </div>
    </div>"""


def _section_head(emoji, label, count, tone):
    color = GREEN_DARK if tone == "green" else RED_DARK if tone == "red" else MUTED
    return f"""
    <div style="display:flex; align-items:center; gap:8px; margin:10px 0 10px 0;">
        <span style="font-size:18px;">{emoji}</span>
        <span style="font-size:17px; font-weight:700; color:{HEADING};">{label}</span>
        <span class="chip chip-{'green' if tone=='green' else 'red' if tone=='red' else 'gray'}"
              style="margin-left:2px;">{count} stocks</span>
    </div>"""


def render_bull_bear_sections(df, top_n=6, key_prefix="bb"):
    """
    🟢 Most Bullish / 🔴 Most Bearish — side-by-side ranked card columns.
    Auto-detects intraday vs next-day frames.
    """
    if df is None or df.empty:
        return

    bull, bear = split_bull_bear(df, top_n=top_n)
    is_nextday = "Outlook" in df.columns
    card_fn = _nextday_stock_card if is_nextday else _intraday_stock_card

    cb, cs = st.columns(2, gap="large")

    with cb:
        st.markdown(_section_head("🟢", "Most Bullish", len(bull), "green"), unsafe_allow_html=True)
        if bull.empty:
            st.markdown(f'<div class="opl-card"><div class="opl-sub" style="margin:0;">No bullish setups right now.</div></div>', unsafe_allow_html=True)
        for _, row in bull.iterrows():
            st.markdown(card_fn(row), unsafe_allow_html=True)

    with cs:
        st.markdown(_section_head("🔴", "Most Bearish", len(bear), "red"), unsafe_allow_html=True)
        if bear.empty:
            st.markdown(f'<div class="opl-card"><div class="opl-sub" style="margin:0;">No bearish setups right now.</div></div>', unsafe_allow_html=True)
        for _, row in bear.iterrows():
            st.markdown(card_fn(row), unsafe_allow_html=True)


# ====================== FULL RESULT VIEWS ======================
def render_compact_table_view(df):
    if df is None or df.empty:
        return
    display_cols = [c for c in ["Symbol", "Sector", "LTP", "Signal", "Score", "Pattern", "MTF Status", "Volume"] if c in df.columns]
    st.dataframe(df[display_cols], use_container_width=True, hide_index=True, height=400)


def render_compact_cards_view(df):
    if df is None or df.empty:
        return
    for _, row in df.iterrows():
        st.markdown(_intraday_stock_card(row), unsafe_allow_html=True)


def render_next_day_results(df):
    """Render full next-day results (Cards / Table) — Groww light theme."""
    if df is None or df.empty:
        st.info("No next-day outlook data available.")
        return

    view_mode = st.radio("View", ["Cards", "Table"], horizontal=True, key="nd_view_mode")

    if view_mode == "Table":
        display_cols = [c for c in ["Symbol", "Sector", "Outlook", "Expected_Move", "Confidence", "Bias", "Key_Levels"] if c in df.columns]
        st.dataframe(df[display_cols], use_container_width=True, hide_index=True)
        return

    for _, row in df.iterrows():
        st.markdown(_nextday_stock_card(row), unsafe_allow_html=True)


def sort_by_priority(df):
    if df is None or df.empty or "Score" not in df.columns:
        return df
    return df.sort_values("Score", ascending=False)


# ====================== SECTOR CARD (Tab 3 drill-down) ======================
def render_sector_card(sector, total, bullish, bearish, avg_score, is_bullish=True, key_prefix=""):
    pct = (bullish / total * 100) if total > 0 else 0
    if is_bullish:
        color, bg, brd = GREEN_DARK, GREEN_TINT, "#BFE9D8"
        frac = bullish
    else:
        color, bg, brd = RED_DARK, RED_TINT, "#F3CDC2"
        frac = bearish

    col1, col2 = st.columns([4, 1])
    with col1:
        st.markdown(f"""
        <div style="background:{bg}; border:1px solid {brd}; border-radius:10px;
                    padding:12px 14px; margin-bottom:6px;">
            <div style="display:flex; justify-content:space-between;">
                <div>
                    <span style="font-weight:700; font-size:15px; color:{HEADING};">{sector}</span>
                    <span style="margin-left:8px; font-size:12px; color:{MUTED};">{total} stocks</span>
                </div>
                <div style="text-align:right; font-size:13px;">
                    <span style="color:{color}; font-weight:700;">{frac}</span>
                    <span style="color:{MUTED};"> / {total}</span>
                </div>
            </div>
            <div style="font-size:12px; margin-top:4px; color:{MUTED};">
                Bullish: {bullish} ({pct:.0f}%) • Avg Score: {avg_score:.1f}
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        if st.button("View Stocks", key=f"{key_prefix}_{sector}", use_container_width=True):
            return sector
    return None


def render_sector_stock_row(symbol, score, ltp, signal, is_bull):
    if is_bull:
        bg, brd, txt = GREEN_TINT, "#BFE9D8", GREEN_DARK
    else:
        bg, brd, txt = RED_TINT, "#F3CDC2", RED_DARK
    try:
        score = f"{float(score):.1f}"
    except (TypeError, ValueError):
        pass
    return f"""
    <div style="background:{bg}; border:1px solid {brd}; border-radius:10px;
                padding:11px 14px; margin-bottom:6px; display:flex; justify-content:space-between;">
        <div>
            <span style="font-weight:700; color:{txt};">{symbol}</span>
            <span style="margin-left:10px; font-size:13px; color:{MUTED};">Score: {score}</span>
        </div>
        <div style="font-weight:600; color:{INK};">{_fmt_money(ltp)} • {signal}</div>
    </div>"""


# ====================== FOOTER ======================
def render_footer():
    st.divider()
    st.markdown(
        f"<div style='text-align:center; color:#9AA0AC; font-size:12px; padding:4px 0 22px; line-height:1.7;'>"
        "RAO SAHAB ⚡ Intraday &amp; Next-Day Scanner<br>"
        "Data is for analysis &amp; educational purposes only. Not investment advice. Trade at your own risk."
        "</div>",
        unsafe_allow_html=True,
    )


def load_watchlist():
    if "watchlist" not in st.session_state:
        st.session_state.watchlist = []
    return st.session_state.watchlist
