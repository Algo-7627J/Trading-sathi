import streamlit as st
import pandas as pd

try:
    import altair as alt
except Exception:
    alt = None

from sectors import add_sector_column, ordered_sectors
from storage import load_watchlist, add_to_watchlist, remove_from_watchlist

SIGNAL_COLORS = {
    "STRONG BUY": "#16a34a",
    "BUY": "#4ade80",
    "HOLD": "#94a3b8",
    "SELL": "#f87171",
    "STRONG SELL": "#dc2626",
    "NO DATA": "#64748b",
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
        """
        <style>
        .main {background-color: #0f172a; color: #e2e8f0;}
        .block-container {padding-top: 1rem; padding-bottom: 2rem; max-width: 98%;}
        div[data-testid="stMetric"] {
            background: linear-gradient(135deg, #111827, #1f2937);
            border: 1px solid #334155;
            padding: 12px;
            border-radius: 14px;
        }
        .ts-card {
            background: linear-gradient(135deg, #111827, #172033);
            border: 1px solid #2b3648;
            padding: 14px 16px;
            border-radius: 14px;
            margin-bottom: 10px;
        }
        .sig-buy {color:#22c55e;font-weight:700;}
        .sig-sell {color:#ef4444;font-weight:700;}
        .sig-hold {color:#f59e0b;font-weight:700;}
        .sig-neutral {color:#94a3b8;font-weight:700;}

        .sector-chip {
            display:inline-block;
            background: linear-gradient(135deg, #1e293b, #0f172a);
            border: 1px solid #334155;
            color: #93c5fd;
            padding: 3px 10px;
            border-radius: 999px;
            font-size: 12px;
            font-weight: 600;
            margin-bottom: 6px;
        }

        div[data-testid="stTabs"] button[data-baseweb="tab"] {
            font-weight: 600;
        }

        .watch-star {
            color: #facc15;
            font-weight: 700;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_summary_cards(df: pd.DataFrame):
    total = len(df) if df is not None else 0
    buy = len(df[df["Signal"].isin(["BUY", "STRONG BUY"])]) if total else 0
    sell = len(df[df["Signal"].isin(["SELL", "STRONG SELL"])]) if total else 0
    strong_buy = len(df[df["Signal"] == "STRONG BUY"]) if total else 0
    strong_sell = len(df[df["Signal"] == "STRONG SELL"]) if total else 0
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Scanned", total)
    c2.metric("Buy", buy)
    c3.metric("Sell", sell)
    c4.metric("Strong Buy", strong_buy)
    c5.metric("Strong Sell", strong_sell)


def signal_badge(signal: str):
    if signal in ["BUY", "STRONG BUY"]:
        cls = "sig-buy"
    elif signal in ["SELL", "STRONG SELL"]:
        cls = "sig-sell"
    elif signal == "HOLD":
        cls = "sig-hold"
    else:
        cls = "sig-neutral"
    return f'<span class="{cls}">{signal}</span>'


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
        df["_abs_score"] = df["Score"].abs().fillna(-1)
    else:
        df["_abs_score"] = 0
    df = df.sort_values(["_priority", "_abs_score"], ascending=[True, False])
    return df.drop(columns=["_priority", "_abs_score"])


def _style_signal_rows(df: pd.DataFrame):
    """Return a pandas Styler that tints STRONG BUY/STRONG SELL rows for visibility."""
    def highlight(row):
        sig = row.get("Signal", "")
        if sig == "STRONG BUY":
            return ["background-color: rgba(34,197,94,0.22)"] * len(row)
        if sig == "STRONG SELL":
            return ["background-color: rgba(239,68,68,0.22)"] * len(row)
        if sig == "BUY":
            return ["background-color: rgba(34,197,94,0.08)"] * len(row)
        if sig == "SELL":
            return ["background-color: rgba(239,68,68,0.08)"] * len(row)
        return [""] * len(row)

    try:
        return df.style.apply(highlight, axis=1)
    except Exception:
        return df


def display_signal_table(df: pd.DataFrame, prioritize: bool = True):
    if df is None or df.empty:
        st.warning("No data to display.")
        return
    show_df = sort_by_priority(df) if prioritize else df
    styled = _style_signal_rows(show_df)
    st.dataframe(styled, use_container_width=True, hide_index=True)


def _short_symbol(sym: str) -> str:
    """Shorten a FYERS symbol like NSE:RELIANCE-EQ -> RELIANCE for chart labels."""
    try:
        s = sym.split(":")[-1]
        s = s.replace("-EQ", "")
        return s
    except Exception:
        return sym


def render_signal_bar_chart(df: pd.DataFrame, title: str = "", height_per_row: int = 28):
    """
    Horizontal bar chart of symbols ranked by Score, colored by Signal
    (green shades for BUY/STRONG BUY, red shades for SELL/STRONG SELL).
    Falls back to a table if Altair isn't available.
    """
    if df is None or df.empty:
        st.info(f"No {title.lower()} signals in this scan." if title else "No data.")
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

    chart_df["_label"] = chart_df["Symbol"].apply(_short_symbol)
    chart_df = chart_df.sort_values("Score", key=lambda s: s.abs(), ascending=False)

    n = len(chart_df)
    chart_height = max(120, min(700, n * height_per_row))

    color_scale = alt.Scale(
        domain=list(SIGNAL_COLORS.keys()),
        range=list(SIGNAL_COLORS.values()),
    )

    tooltip_fields = ["Symbol", "Signal", "Score"]
    for extra in ("Sector", "Pattern", "Sector Info", "Reason"):
        if extra in chart_df.columns:
            tooltip_fields.append(extra)

    chart = (
        alt.Chart(chart_df)
        .mark_bar(cornerRadiusTopRight=4, cornerRadiusBottomRight=4)
        .encode(
            x=alt.X("Score:Q", title="Score"),
            y=alt.Y("_label:N", sort="-x", title=None),
            color=alt.Color("Signal:N", scale=color_scale, legend=alt.Legend(title="Signal")),
            tooltip=tooltip_fields,
        )
        .properties(height=chart_height)
    )

    if title:
        st.markdown(f"**{title}**")
    st.altair_chart(chart, use_container_width=True)


def render_watchlist_manager(all_symbols):
    """
    Sidebar-friendly widget to add/remove symbols from a persistent watchlist.
    """
    st.markdown("#### ⭐ Watchlist")
    current = load_watchlist()

    add_choice = st.selectbox(
        "Add symbol to watchlist",
        [""] + sorted(set(all_symbols) - set(current)),
        key="watchlist_add_select",
    )
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Add", key="watchlist_add_btn") and add_choice:
            add_to_watchlist(add_choice)
            st.rerun()
    with c2:
        if current:
            remove_choice = st.selectbox("Remove", [""] + current, key="watchlist_remove_select")
        else:
            remove_choice = None

    if current and st.button("Remove selected", key="watchlist_remove_btn") and remove_choice:
        remove_from_watchlist(remove_choice)
        st.rerun()

    if current:
        st.caption(f"Watching {len(current)} symbol(s): " + ", ".join(current))
    else:
        st.caption("Watchlist is empty. Add symbols above to track them across scans.")

    return current


def render_watchlist_results(df: pd.DataFrame, watchlist: list):
    if not watchlist:
        return
    st.subheader(f"⭐ Watchlist Results ({len(watchlist)})")
    wl_df = df[df["Symbol"].isin(watchlist)]
    if wl_df.empty:
        st.info("None of your watchlist symbols were included in this scan.")
    else:
        display_signal_table(wl_df)


def _sector_tab_label(sector: str, sector_df: pd.DataFrame) -> str:
    total = len(sector_df)
    sb = len(sector_df[sector_df["Signal"] == "STRONG BUY"])
    ss = len(sector_df[sector_df["Signal"] == "STRONG SELL"])
    badge = ""
    if sb:
        badge += f" 🟢{sb}"
    if ss:
        badge += f" 🔴{ss}"
    return f"{sector} ({total}){badge}"


def render_sector_tabs(df: pd.DataFrame):
    """
    Split scan results into sector-wise tabs. Each tab shows STRONG BUY /
    STRONG SELL counts right in the tab label, and renders those signals as
    horizontal bar charts (ranked by score) above the full results table -
    which itself always shows STRONG BUY/STRONG SELL rows first.
    """
    if df is None or df.empty:
        st.warning("No data to display.")
        return

    df = add_sector_column(df)
    sectors_present = df["Sector"].dropna().unique().tolist()
    sectors = ordered_sectors(sectors_present)

    if not sectors:
        display_signal_table(df)
        return

    tab_labels = [_sector_tab_label(s, df[df["Sector"] == s]) for s in sectors]
    tabs = st.tabs(["🌐 All"] + tab_labels)

    with tabs[0]:
        render_sector_panel(df)

    for tab, sector in zip(tabs[1:], sectors):
        with tab:
            sector_df = df[df["Sector"] == sector]
            st.markdown(f'<span class="sector-chip">{sector}</span>', unsafe_allow_html=True)
            render_sector_panel(sector_df)


def render_sector_panel(sector_df: pd.DataFrame):
    """Summary cards + Strong Buy/Strong Sell bar charts + full table for one sector (or 'All')."""
    render_summary_cards(sector_df)

    strong_buy = sector_df[sector_df["Signal"] == "STRONG BUY"]
    strong_sell = sector_df[sector_df["Signal"] == "STRONG SELL"]

    if not strong_buy.empty or not strong_sell.empty:
        c1, c2 = st.columns(2)
        with c1:
            render_signal_bar_chart(strong_buy, title=f"🟢🟢 STRONG BUY ({len(strong_buy)})")
        with c2:
            render_signal_bar_chart(strong_sell, title=f"🔴🔴 STRONG SELL ({len(strong_sell)})")
        st.markdown("---")

    with st.expander("📋 Full results table", expanded=False):
        display_signal_table(sector_df)


# ---------------------------------------------------------------------------
# Next-Day Outlook rendering
# ---------------------------------------------------------------------------

NEXT_DAY_COLORS = {
    "STRONG BULLISH": "#16a34a",
    "BULLISH": "#4ade80",
    "NEUTRAL": "#94a3b8",
    "BEARISH": "#f87171",
    "STRONG BEARISH": "#dc2626",
    "NO DATA": "#64748b",
}


def _next_day_color_group(outlook: str) -> str:
    """Map a possibly-suffixed label (e.g. 'BULLISH (Low Confidence)') to a base color key."""
    for key in NEXT_DAY_COLORS:
        if outlook.startswith(key):
            return key
    return "NEUTRAL"


def render_next_day_bar_chart(df: pd.DataFrame, title: str = "", height_per_row: int = 30):
    """
    Horizontal bar chart for Next-Day Outlook results, ranked by |Score|,
    colored by outlook direction/strength. Low-confidence calls are shown
    with reduced opacity so high-confidence calls stand out visually.
    """
    if df is None or df.empty:
        st.info(f"No {title.lower()} outlook in this scan." if title else "No data.")
        return

    if alt is None or "Score" not in df.columns:
        display_signal_table(df, prioritize=False)
        return

    chart_df = df.copy()
    chart_df["Score"] = pd.to_numeric(chart_df["Score"], errors="coerce")
    chart_df = chart_df.dropna(subset=["Score"])
    if chart_df.empty:
        st.info("No scoreable data.")
        return

    chart_df["_label"] = chart_df["Symbol"].apply(_short_symbol)
    chart_df["_color_group"] = chart_df["Outlook"].astype(str).apply(_next_day_color_group)
    chart_df["_opacity"] = chart_df["Confidence"].map({"HIGH": 1.0, "MEDIUM": 0.75, "LOW": 0.4}).fillna(0.5)
    chart_df = chart_df.sort_values("Score", key=lambda s: s.abs(), ascending=False)

    n = len(chart_df)
    chart_height = max(120, min(700, n * height_per_row))

    color_scale = alt.Scale(domain=list(NEXT_DAY_COLORS.keys()), range=list(NEXT_DAY_COLORS.values()))

    tooltip_fields = ["Symbol", "Outlook", "Score", "Confidence"]
    for extra in ("Backtest Sample", "Backtest Hit Rate %", "ADX", "RSI", "RS vs Nifty (5D)", "Sector"):
        if extra in chart_df.columns:
            tooltip_fields.append(extra)

    chart = (
        alt.Chart(chart_df)
        .mark_bar(cornerRadiusTopRight=4, cornerRadiusBottomRight=4)
        .encode(
            x=alt.X("Score:Q", title="Next-Day Score"),
            y=alt.Y("_label:N", sort="-x", title=None),
            color=alt.Color("_color_group:N", scale=color_scale, legend=alt.Legend(title="Outlook")),
            opacity=alt.Opacity("_opacity:Q", legend=None, scale=alt.Scale(domain=[0.4, 1.0], range=[0.4, 1.0])),
            tooltip=tooltip_fields,
        )
        .properties(height=chart_height)
    )

    if title:
        st.markdown(f"**{title}**")
    st.altair_chart(chart, use_container_width=True)
    st.caption("Faded bars = LOW confidence (backtest sample too small or hit-rate too weak to trust).")


def render_next_day_results(df: pd.DataFrame):
    """
    Full Next-Day Outlook results panel: summary metrics, Strong Bullish /
    Strong Bearish bar charts (high-visibility), then a detailed table with
    backtest hit-rate and confidence for every symbol.
    """
    if df is None or df.empty:
        st.warning("No data to display.")
        return

    total = len(df)
    strong_bull = df[df["Outlook"] == "STRONG BULLISH"]
    strong_bear = df[df["Outlook"] == "STRONG BEARISH"]
    bullish = df[df["Outlook"].astype(str).str.startswith("BULLISH")]
    bearish = df[df["Outlook"].astype(str).str.startswith("BEARISH")]
    high_conf = df[df["Confidence"] == "HIGH"]

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Analyzed", total)
    c2.metric("Strong Bullish", len(strong_bull))
    c3.metric("Strong Bearish", len(strong_bear))
    c4.metric("Bullish (any)", len(bullish))
    c5.metric("High Confidence", len(high_conf))

    st.markdown("### 🚨 Strong Calls (backtested)")
    b1, b2 = st.columns(2)
    with b1:
        render_next_day_bar_chart(strong_bull, title=f"🟢🟢 STRONG BULLISH ({len(strong_bull)})")
    with b2:
        render_next_day_bar_chart(strong_bear, title=f"🔴🔴 STRONG BEARISH ({len(strong_bear)})")

    st.markdown("---")
    st.markdown("### 📋 Full Next-Day Outlook Table")
    st.caption(
        "Backtest Hit Rate % = how often this exact rule-set's directional call was "
        "correct historically for THIS stock (over the sample size shown). "
        "Confidence is only HIGH/MEDIUM when the sample size and hit-rate both clear "
        "a minimum bar - otherwise it's marked LOW and the call is softened."
    )
    if "Confidence" in df.columns:
        show_df = df.copy()
        show_df["_conf_rank"] = show_df["Confidence"].map({"HIGH": 0, "MEDIUM": 1, "LOW": 2}).fillna(3)
        show_df["_abs_score"] = pd.to_numeric(show_df.get("Score"), errors="coerce").abs().fillna(-1)
        show_df = show_df.sort_values(
            ["_conf_rank", "_abs_score"], ascending=[True, False]
        ).drop(columns=["_conf_rank", "_abs_score"])
    else:
        show_df = df
    st.dataframe(show_df, use_container_width=True, hide_index=True)
