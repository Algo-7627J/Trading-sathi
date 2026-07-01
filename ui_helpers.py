import streamlit as st
import pandas as pd

from sectors import add_sector_column, ordered_sectors
from storage import load_watchlist, add_to_watchlist, remove_from_watchlist

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


def render_sector_tabs(df: pd.DataFrame):
    """
    Split scan results into sector-wise tabs. Within each tab, STRONG BUY and
    STRONG SELL signals are always shown first (highlighted), matching the
    overall priority ranking used elsewhere in the app.
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

    tab_labels = [f"{s} ({len(df[df['Sector'] == s])})" for s in sectors]
    tabs = st.tabs(["🌐 All"] + tab_labels)

    with tabs[0]:
        render_summary_cards(df)
        display_signal_table(df)

    for tab, sector in zip(tabs[1:], sectors):
        with tab:
            sector_df = df[df["Sector"] == sector]
            render_summary_cards(sector_df)
            st.markdown(f'<span class="sector-chip">{sector}</span>', unsafe_allow_html=True)
            display_signal_table(sector_df)
