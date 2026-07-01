import streamlit as st
import pandas as pd

try:
    import altair as alt
except Exception:
    alt = None

from sectors import add_sector_column, ordered_sectors
from storage import load_watchlist, add_to_watchlist, remove_from_watchlist

# ---------------------------------------------------------------------------
# Palette - flat, restrained, professional (TradingView / Groww style).
# Color is used ONLY to communicate gain/loss/direction, never decoration.
# ---------------------------------------------------------------------------
BG = "#0e1117"
SURFACE = "#161a25"
BORDER = "rgba(255,255,255,0.08)"
TEXT = "#d1d4dc"
TEXT_MUTED = "#787b86"
GREEN = "#26a69a"
RED = "#ef5350"
BLUE = "#2962ff"
AMBER = "#f0b90b"

SIGNAL_COLORS = {
    "STRONG BUY": GREEN,
    "BUY": GREEN,
    "HOLD": TEXT_MUTED,
    "SELL": RED,
    "STRONG SELL": RED,
    "NO DATA": TEXT_MUTED,
}

NEXT_DAY_COLORS = {
    "STRONG BULLISH": GREEN,
    "BULLISH": GREEN,
    "NEUTRAL": TEXT_MUTED,
    "BEARISH": RED,
    "STRONG BEARISH": RED,
    "NO DATA": TEXT_MUTED,
}

# Lower number = higher priority = shown first.
SIGNAL_PRIORITY = {
    "STRONG BUY": 0,
    "STRONG SELL": 0,
    "BUY": 1,
    "SELL": 1,
    "HOLD": 2,
    "NO DATA": 3,
}


def inject_custom_css():
    st.markdown(
        f"""
        <style>
        html, body, [class*="css"] {{ font-family: -apple-system, "Segoe UI", Roboto, Inter, sans-serif; }}

        .stApp {{ background: {BG}; color: {TEXT}; }}
        .block-container {{ padding-top: 1.4rem; padding-bottom: 3rem; max-width: 1200px; }}

        h1, h2, h3, h4 {{ color: {TEXT} !important; font-weight: 600 !important; letter-spacing: -0.01em; }}
        p, span, label, div {{ color: {TEXT}; }}

        /* ---------- Simple flat title block ---------- */
        .ts-title-row {{ display: flex; align-items: baseline; gap: 10px; margin-bottom: 2px; }}
        .ts-title-row h1 {{ font-size: 1.5rem !important; margin: 0 !important; }}
        .ts-subtitle {{ color: {TEXT_MUTED}; font-size: 13px; margin-bottom: 18px; }}

        .ts-status-dot {{
            display: inline-flex; align-items: center; gap: 6px;
            font-size: 12.5px; color: {TEXT_MUTED}; font-weight: 500;
        }}
        .ts-status-dot .dot {{ width: 7px; height: 7px; border-radius: 50%; background: {GREEN}; }}

        /* ---------- Section label (minimal, no box) ---------- */
        .ts-section {{
            font-size: 13px; font-weight: 600; text-transform: uppercase;
            letter-spacing: 0.06em; color: {TEXT_MUTED};
            margin: 28px 0 10px 0; padding-bottom: 8px;
            border-bottom: 1px solid {BORDER};
        }}

        /* ---------- Stat row (flat, monochrome cards, colored numbers only) ---------- */
        .ts-stat-row {{ display: flex; gap: 1px; background: {BORDER}; border: 1px solid {BORDER}; border-radius: 8px; overflow: hidden; margin-bottom: 16px; }}
        .ts-stat {{ flex: 1; background: {SURFACE}; padding: 12px 16px; min-width: 100px; }}
        .ts-stat-label {{ font-size: 11.5px; color: {TEXT_MUTED}; margin-bottom: 4px; }}
        .ts-stat-value {{ font-size: 1.35rem; font-weight: 700; color: {TEXT}; }}

        div[data-testid="stMetric"] {{ background: {SURFACE}; border: 1px solid {BORDER}; padding: 10px 14px; border-radius: 8px; }}
        div[data-testid="stMetricLabel"] {{ color: {TEXT_MUTED} !important; }}

        /* ---------- Plain bordered card (used sparingly: login, notices) ---------- */
        .ts-card {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 8px; padding: 16px 18px; margin-bottom: 12px; }}
        .ts-card-notice {{ border-left: 3px solid {AMBER}; }}

        /* ---------- Signal text (no pills, just colored bold text like a P&L figure) ---------- */
        .ts-signal {{ font-weight: 700; font-size: 13px; }}
        .ts-signal-up {{ color: {GREEN}; }}
        .ts-signal-down {{ color: {RED}; }}
        .ts-signal-flat {{ color: {TEXT_MUTED}; }}

        /* ---------- Sector tag - single muted style, not per-sector rainbow ---------- */
        .ts-tag {{
            display: inline-block; padding: 2px 9px; border-radius: 4px;
            font-size: 11.5px; font-weight: 600; color: {TEXT_MUTED};
            background: rgba(255,255,255,0.05); border: 1px solid {BORDER};
            margin-bottom: 8px;
        }}

        /* ---------- Watchlist chip ---------- */
        .ts-chip {{
            display: inline-block; padding: 3px 10px; border-radius: 4px;
            font-size: 11.5px; font-weight: 600; color: {TEXT};
            background: rgba(255,255,255,0.06); margin: 2px 4px 2px 0;
        }}

        /* ---------- Tabs: simple underline, no gradient ---------- */
        div[data-testid="stTabs"] button[data-baseweb="tab"] {{
            font-weight: 600; font-size: 13.5px; color: {TEXT_MUTED}; padding: 8px 14px;
        }}
        div[data-testid="stTabs"] button[aria-selected="true"] {{
            color: {TEXT} !important;
            border-bottom: 2px solid {BLUE} !important;
        }}
        div[data-testid="stTabs"] {{ border-bottom: 1px solid {BORDER}; margin-bottom: 12px; }}

        /* ---------- Buttons: flat, single accent ---------- */
        div[data-testid="stButton"] button[kind="primary"] {{
            background: {BLUE}; border: none; font-weight: 600; border-radius: 6px;
        }}
        div[data-testid="stButton"] button[kind="primary"]:hover {{ background: #1e4fd6; }}
        div[data-testid="stButton"] button[kind="secondary"] {{
            border: 1px solid {BORDER}; background: transparent; border-radius: 6px;
        }}

        /* ---------- Sidebar: flat, no gradient ---------- */
        section[data-testid="stSidebar"] {{ background: {SURFACE}; border-right: 1px solid {BORDER}; }}
        section[data-testid="stSidebar"] h1, section[data-testid="stSidebar"] h2,
        section[data-testid="stSidebar"] h3, section[data-testid="stSidebar"] h4 {{ color: {TEXT} !important; }}

        /* ---------- Alerts / expander / misc ---------- */
        div[data-testid="stAlert"] {{ border-radius: 6px; }}
        details {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 8px !important; }}
        summary {{ font-weight: 600 !important; font-size: 13.5px !important; }}

        hr {{ border-color: {BORDER} !important; margin: 20px 0 !important; }}

        div[data-testid="stDataFrame"] {{ border: 1px solid {BORDER}; border-radius: 8px; }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_title(title: str, subtitle: str, connected: bool = False):
    """Flat title block - no gradient banner."""
    st.markdown(f'<div class="ts-title-row"><h1>{title}</h1></div>', unsafe_allow_html=True)
    status = ""
    if connected:
        status = '<span class="ts-status-dot"><span class="dot"></span>Connected to FYERS</span>'
    st.markdown(f'<div class="ts-subtitle">{subtitle}{"  ·  " + status if status else ""}</div>', unsafe_allow_html=True)


def section_label(title: str):
    """Minimal uppercase section divider - no icon box, no gradient."""
    st.markdown(f'<div class="ts-section">{title}</div>', unsafe_allow_html=True)


def render_stat_row(items):
    """
    Flat single-row stat strip. items: list of dicts {label, value, color}
    color is optional - only used for numbers that represent gain/loss counts.
    """
    cells = ""
    for it in items:
        color = it.get("color", TEXT)
        cells += (
            f'<div class="ts-stat">'
            f'<div class="ts-stat-label">{it.get("label","")}</div>'
            f'<div class="ts-stat-value" style="color:{color};">{it.get("value","")}</div>'
            f"</div>"
        )
    st.markdown(f'<div class="ts-stat-row">{cells}</div>', unsafe_allow_html=True)


def render_summary_cards(df: pd.DataFrame):
    total = len(df) if df is not None else 0
    buy = len(df[df["Signal"].isin(["BUY", "STRONG BUY"])]) if total else 0
    sell = len(df[df["Signal"].isin(["SELL", "STRONG SELL"])]) if total else 0
    strong_buy = len(df[df["Signal"] == "STRONG BUY"]) if total else 0
    strong_sell = len(df[df["Signal"] == "STRONG SELL"]) if total else 0
    render_stat_row([
        {"label": "Scanned", "value": total},
        {"label": "Buy", "value": buy, "color": GREEN},
        {"label": "Sell", "value": sell, "color": RED},
        {"label": "Strong Buy", "value": strong_buy, "color": GREEN},
        {"label": "Strong Sell", "value": strong_sell, "color": RED},
    ])


def signal_text(signal: str) -> str:
    """Plain colored bold text for a signal - no pill/badge, matches P&L-style display."""
    s = str(signal)
    if s.startswith("STRONG BUY") or s.startswith("BUY") or s.startswith("STRONG BULLISH") or s.startswith("BULLISH"):
        cls = "ts-signal-up"
    elif s.startswith("STRONG SELL") or s.startswith("SELL") or s.startswith("STRONG BEARISH") or s.startswith("BEARISH"):
        cls = "ts-signal-down"
    else:
        cls = "ts-signal-flat"
    return f'<span class="ts-signal {cls}">{s}</span>'


# Backward-compat alias (used to be called signal_badge)
signal_badge = signal_text


def render_sector_tag(sector: str):
    st.markdown(f'<span class="ts-tag">{sector}</span>', unsafe_allow_html=True)


def sort_by_priority(df: pd.DataFrame) -> pd.DataFrame:
    """
    Sort so STRONG BUY / STRONG SELL rows always appear first, then BUY/SELL,
    then HOLD/others - within each tier ranked by |Score| descending.
    """
    if df is None or df.empty or "Signal" not in df.columns:
        return df
    df = df.copy()
    df["_priority"] = df["Signal"].map(SIGNAL_PRIORITY).fillna(9)
    if "Score" in df.columns:
        df["_abs_score"] = pd.to_numeric(df["Score"], errors="coerce").abs().fillna(-1)
    else:
        df["_abs_score"] = 0
    df = df.sort_values(["_priority", "_abs_score"], ascending=[True, False])
    return df.drop(columns=["_priority", "_abs_score"])


def display_signal_table(df: pd.DataFrame, prioritize: bool = True):
    if df is None or df.empty:
        st.caption("No data to display.")
        return
    show_df = sort_by_priority(df) if prioritize else df
    st.dataframe(show_df, use_container_width=True, hide_index=True)


def _short_symbol(sym: str) -> str:
    """Shorten a FYERS symbol like NSE:RELIANCE-EQ -> RELIANCE for chart labels."""
    try:
        s = sym.split(":")[-1]
        s = s.replace("-EQ", "")
        return s
    except Exception:
        return sym


def _label_with_sector(row) -> str:
    """Build a chart-axis label like 'RELIANCE - Energy & Oil/Gas' when sector is known."""
    sym = _short_symbol(row.get("Symbol", ""))
    sector = row.get("Sector")
    if sector and str(sector).strip() and str(sector).lower() != "nan":
        return f"{sym} · {sector}"
    return sym


def _dark_chart(chart):
    """Apply a consistent flat dark theme to any Altair chart."""
    return (
        chart.configure_view(strokeWidth=0)
        .configure_axis(
            labelColor=TEXT_MUTED, titleColor=TEXT_MUTED, gridColor="rgba(255,255,255,0.06)",
            domainColor=BORDER, labelFontSize=11.5, titleFontSize=11.5,
        )
        .configure_legend(labelColor=TEXT_MUTED, titleColor=TEXT_MUTED, labelFontSize=11.5)
    )


def render_signal_bar_chart(df: pd.DataFrame, title: str = "", height_per_row: int = 26):
    """
    Horizontal bar chart of symbols ranked by Score, colored green/red by
    Signal direction only (flat, no gradient/rounded decoration).
    """
    if df is None or df.empty:
        st.caption(f"No {title.lower()} in this scan." if title else "No data.")
        return

    if alt is None or "Score" not in df.columns:
        display_signal_table(df)
        return

    chart_df = df.copy()
    chart_df["Score"] = pd.to_numeric(chart_df["Score"], errors="coerce")
    chart_df = chart_df.dropna(subset=["Score"])
    if chart_df.empty:
        display_signal_table(df)
        return

    chart_df["_label"] = chart_df.apply(_label_with_sector, axis=1)
    chart_df = chart_df.sort_values("Score", key=lambda s: s.abs(), ascending=False)

    n = len(chart_df)
    chart_height = max(100, min(560, n * height_per_row))

    color_scale = alt.Scale(domain=list(SIGNAL_COLORS.keys()), range=list(SIGNAL_COLORS.values()))

    tooltip_fields = ["Symbol", "Signal", "Score"]
    for extra in ("Sector", "Pattern", "Reason"):
        if extra in chart_df.columns:
            tooltip_fields.append(extra)

    chart = (
        alt.Chart(chart_df)
        .mark_bar(size=14)
        .encode(
            x=alt.X("Score:Q", title="Score"),
            y=alt.Y("_label:N", sort="-x", title=None),
            color=alt.Color("Signal:N", scale=color_scale, legend=None),
            tooltip=tooltip_fields,
        )
        .properties(height=chart_height)
    )
    chart = _dark_chart(chart)

    if title:
        st.markdown(f'<div style="font-size:13px;font-weight:600;color:{TEXT_MUTED};margin-bottom:4px;">{title}</div>', unsafe_allow_html=True)
    st.altair_chart(chart, use_container_width=True)


def render_watchlist_manager(all_symbols):
    """Sidebar widget to add/remove symbols from a persistent watchlist."""
    st.markdown('<div style="font-weight:600;font-size:13.5px;margin-bottom:8px;">Watchlist</div>', unsafe_allow_html=True)
    current = load_watchlist()

    add_choice = st.selectbox(
        "Add symbol",
        [""] + sorted(set(all_symbols) - set(current)),
        key="watchlist_add_select",
        label_visibility="collapsed",
        placeholder="Add symbol...",
    )
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Add", key="watchlist_add_btn", use_container_width=True) and add_choice:
            add_to_watchlist(add_choice)
            st.rerun()
    with c2:
        if current:
            remove_choice = st.selectbox("Remove", [""] + current, key="watchlist_remove_select", label_visibility="collapsed")
        else:
            remove_choice = None

    if current and st.button("Remove", key="watchlist_remove_btn", use_container_width=True) and remove_choice:
        remove_from_watchlist(remove_choice)
        st.rerun()

    if current:
        chips = "".join(f'<span class="ts-chip">{_short_symbol(s)}</span>' for s in current)
        st.markdown(f'<div style="margin-top:8px;">{chips}</div>', unsafe_allow_html=True)
    else:
        st.caption("No symbols added yet.")

    return current


def render_watchlist_results(df: pd.DataFrame, watchlist: list):
    if not watchlist:
        return
    section_label(f"Watchlist ({len(watchlist)})")
    wl_df = df[df["Symbol"].isin(watchlist)]
    if wl_df.empty:
        st.caption("None of your watchlist symbols were included in this scan.")
    else:
        display_signal_table(wl_df)


def _sector_tab_label(sector: str, sector_df: pd.DataFrame) -> str:
    total = len(sector_df)
    return f"{sector} ({total})"


def render_sector_panel(sector_df: pd.DataFrame):
    """Compact stats + strong signal bar charts + full table, for one sector or 'All'."""
    render_summary_cards(sector_df)

    strong_buy = sector_df[sector_df["Signal"] == "STRONG BUY"]
    strong_sell = sector_df[sector_df["Signal"] == "STRONG SELL"]

    if not strong_buy.empty or not strong_sell.empty:
        c1, c2 = st.columns(2)
        with c1:
            render_signal_bar_chart(strong_buy, title=f"Strong Buy ({len(strong_buy)})")
        with c2:
            render_signal_bar_chart(strong_sell, title=f"Strong Sell ({len(strong_sell)})")

    with st.expander(f"Full results ({len(sector_df)})", expanded=strong_buy.empty and strong_sell.empty):
        display_signal_table(sector_df)


def render_sector_tabs(df: pd.DataFrame):
    """
    Single tab bar: All / Buy / Sell / [sectors...]. Replaces multiple
    stacked sections with one coherent navigation surface.
    """
    if df is None or df.empty:
        st.caption("No data to display.")
        return

    df = add_sector_column(df)
    sectors_present = df["Sector"].dropna().unique().tolist()
    sectors = ordered_sectors(sectors_present)

    buy_df = df[df["Signal"].isin(["BUY", "STRONG BUY"])]
    sell_df = df[df["Signal"].isin(["SELL", "STRONG SELL"])]

    tab_labels = ["All", f"Buy ({len(buy_df)})", f"Sell ({len(sell_df)})"]
    tab_labels += [_sector_tab_label(s, df[df["Sector"] == s]) for s in sectors]
    tabs = st.tabs(tab_labels)

    with tabs[0]:
        render_sector_panel(df)
    with tabs[1]:
        render_sector_panel(buy_df) if not buy_df.empty else st.caption("No buy signals.")
    with tabs[2]:
        render_sector_panel(sell_df) if not sell_df.empty else st.caption("No sell signals.")

    for tab, sector in zip(tabs[3:], sectors):
        with tab:
            sector_df = df[df["Sector"] == sector]
            render_sector_panel(sector_df)


# ---------------------------------------------------------------------------
# Next-Day Outlook rendering
# ---------------------------------------------------------------------------

def _next_day_color_group(outlook: str) -> str:
    for key in NEXT_DAY_COLORS:
        if outlook.startswith(key):
            return key
    return "NEUTRAL"


def render_next_day_bar_chart(df: pd.DataFrame, title: str = "", height_per_row: int = 26):
    """Flat horizontal bar chart for Next-Day Outlook; faded bars = low confidence."""
    if df is None or df.empty:
        st.caption(f"No {title.lower()} in this scan." if title else "No data.")
        return

    if alt is None or "Score" not in df.columns:
        display_signal_table(df, prioritize=False)
        return

    chart_df = df.copy()
    chart_df["Score"] = pd.to_numeric(chart_df["Score"], errors="coerce")
    chart_df = chart_df.dropna(subset=["Score"])
    if chart_df.empty:
        st.caption("No scoreable data.")
        return

    chart_df["_label"] = chart_df.apply(_label_with_sector, axis=1)
    chart_df["_color_group"] = chart_df["Outlook"].astype(str).apply(_next_day_color_group)
    chart_df["_opacity"] = chart_df["Confidence"].map({"HIGH": 1.0, "MEDIUM": 0.7, "LOW": 0.35}).fillna(0.5)
    chart_df = chart_df.sort_values("Score", key=lambda s: s.abs(), ascending=False)

    n = len(chart_df)
    chart_height = max(100, min(560, n * height_per_row))

    color_scale = alt.Scale(domain=list(NEXT_DAY_COLORS.keys()), range=list(NEXT_DAY_COLORS.values()))

    tooltip_fields = ["Symbol", "Outlook", "Score", "Confidence"]
    for extra in ("Backtest Sample", "Backtest Hit Rate %", "ADX", "RSI", "RS vs Nifty (5D)", "Sector"):
        if extra in chart_df.columns:
            tooltip_fields.append(extra)

    chart = (
        alt.Chart(chart_df)
        .mark_bar(size=14)
        .encode(
            x=alt.X("Score:Q", title="Score"),
            y=alt.Y("_label:N", sort="-x", title=None),
            color=alt.Color("_color_group:N", scale=color_scale, legend=None),
            opacity=alt.Opacity("_opacity:Q", legend=None, scale=alt.Scale(domain=[0.35, 1.0], range=[0.35, 1.0])),
            tooltip=tooltip_fields,
        )
        .properties(height=chart_height)
    )
    chart = _dark_chart(chart)

    if title:
        st.markdown(f'<div style="font-size:13px;font-weight:600;color:{TEXT_MUTED};margin-bottom:4px;">{title}</div>', unsafe_allow_html=True)
    st.altair_chart(chart, use_container_width=True)
    st.caption("Faded bars = low confidence (small backtest sample or weak historical hit-rate).")


def _next_day_summary_row(df: pd.DataFrame):
    total = len(df) if df is not None else 0
    strong_bull = len(df[df["Outlook"] == "STRONG BULLISH"]) if total else 0
    strong_bear = len(df[df["Outlook"] == "STRONG BEARISH"]) if total else 0
    high_conf = len(df[df["Confidence"] == "HIGH"]) if total else 0

    render_stat_row([
        {"label": "Analyzed", "value": total},
        {"label": "Strong Bullish", "value": strong_bull, "color": GREEN},
        {"label": "Strong Bearish", "value": strong_bear, "color": RED},
        {"label": "High Confidence", "value": high_conf, "color": AMBER},
    ])


def _next_day_sorted_table(df: pd.DataFrame) -> pd.DataFrame:
    if "Confidence" in df.columns:
        show_df = df.copy()
        show_df["_conf_rank"] = show_df["Confidence"].map({"HIGH": 0, "MEDIUM": 1, "LOW": 2}).fillna(3)
        show_df["_abs_score"] = pd.to_numeric(show_df.get("Score"), errors="coerce").abs().fillna(-1)
        show_df = show_df.sort_values(
            ["_conf_rank", "_abs_score"], ascending=[True, False]
        ).drop(columns=["_conf_rank", "_abs_score"])
        return show_df
    return df


def render_next_day_panel(df: pd.DataFrame):
    _next_day_summary_row(df)

    strong_bull = df[df["Outlook"] == "STRONG BULLISH"]
    strong_bear = df[df["Outlook"] == "STRONG BEARISH"]

    if not strong_bull.empty or not strong_bear.empty:
        b1, b2 = st.columns(2)
        with b1:
            render_next_day_bar_chart(strong_bull, title=f"Strong Bullish ({len(strong_bull)})")
        with b2:
            render_next_day_bar_chart(strong_bear, title=f"Strong Bearish ({len(strong_bear)})")

    with st.expander(f"Full results ({len(df)})", expanded=strong_bull.empty and strong_bear.empty):
        st.dataframe(_next_day_sorted_table(df), use_container_width=True, hide_index=True)


def render_next_day_results(df: pd.DataFrame):
    """
    Single tab bar: All / Bullish / Bearish / [sectors...] for Next-Day
    Outlook results - mirrors the intraday scanner's simplified navigation.
    """
    if df is None or df.empty:
        st.caption("No data to display.")
        return

    st.caption(
        "Backtest Hit Rate % = how often this rule-set's call was historically correct "
        "for this stock. Confidence is HIGH/MEDIUM only when sample size and hit-rate "
        "both clear a minimum bar - otherwise it's LOW and the call is softened."
    )

    df = df.copy()
    bullish_df = df[df["Outlook"].astype(str).str.startswith("BULLISH") | df["Outlook"].astype(str).str.startswith("STRONG BULLISH")]
    bearish_df = df[df["Outlook"].astype(str).str.startswith("BEARISH") | df["Outlook"].astype(str).str.startswith("STRONG BEARISH")]

    sectors = []
    if "Sector" in df.columns:
        sectors_present = df["Sector"].dropna().unique().tolist()
        sectors = ordered_sectors(sectors_present)

    tab_labels = ["All", f"Bullish ({len(bullish_df)})", f"Bearish ({len(bearish_df)})"]
    tab_labels += [_sector_tab_label(s, df[df["Sector"] == s]) for s in sectors]
    tabs = st.tabs(tab_labels)

    with tabs[0]:
        render_next_day_panel(df)
    with tabs[1]:
        render_next_day_panel(bullish_df) if not bullish_df.empty else st.caption("No bullish calls.")
    with tabs[2]:
        render_next_day_panel(bearish_df) if not bearish_df.empty else st.caption("No bearish calls.")

    for tab, sector in zip(tabs[3:], sectors):
        with tab:
            sector_df = df[df["Sector"] == sector]
            render_next_day_panel(sector_df)
