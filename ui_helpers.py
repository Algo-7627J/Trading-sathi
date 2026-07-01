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

# A vivid, high-contrast palette used to color-code sector chips
# consistently (hash of sector name -> color), so each sector is visually
# distinct across the whole app.
SECTOR_PALETTE = [
    "#f97316", "#22c55e", "#38bdf8", "#a78bfa", "#f43f5e",
    "#eab308", "#2dd4bf", "#fb7185", "#818cf8", "#4ade80",
    "#fbbf24", "#60a5fa", "#e879f9", "#34d399", "#fca5a5",
    "#93c5fd", "#c084fc", "#facc15", "#5eead4", "#fda4af",
    "#a3e635", "#7dd3fc", "#f472b6", "#bef264",
]


def _sector_color(sector: str) -> str:
    if not sector:
        return "#64748b"
    idx = sum(ord(c) for c in str(sector)) % len(SECTOR_PALETTE)
    return SECTOR_PALETTE[idx]


def inject_custom_css():
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Manrope:wght@600;700;800&display=swap');

        html, body, [class*="css"] { font-family: 'Inter', -apple-system, sans-serif; }

        /* ---------- App background ---------- */
        .stApp {
            background:
                radial-gradient(circle at 10% 0%, rgba(99,102,241,0.10) 0%, transparent 40%),
                radial-gradient(circle at 90% 10%, rgba(20,184,166,0.10) 0%, transparent 40%),
                #0a0e1a;
            color: #e2e8f0;
        }
        .block-container {
            padding-top: 1.2rem;
            padding-bottom: 3rem;
            max-width: 98%;
        }

        /* ---------- Headings ---------- */
        h1, h2, h3 { font-family: 'Manrope', 'Inter', sans-serif; letter-spacing: -0.01em; }
        h2, h3 { color: #f1f5f9 !important; }

        /* ---------- Hero header ---------- */
        .ts-hero {
            background: linear-gradient(120deg, #4338ca 0%, #6d28d9 45%, #0891b2 100%);
            border-radius: 22px;
            padding: 28px 32px;
            margin-bottom: 22px;
            box-shadow: 0 12px 40px rgba(79, 70, 229, 0.35);
            position: relative;
            overflow: hidden;
        }
        .ts-hero::after {
            content: "";
            position: absolute; inset: 0;
            background: radial-gradient(circle at 85% -10%, rgba(255,255,255,0.20), transparent 55%);
        }
        .ts-hero h1 {
            color: #ffffff !important;
            font-size: 1.9rem;
            margin: 0 0 6px 0;
            font-weight: 800;
            position: relative;
        }
        .ts-hero p {
            color: rgba(255,255,255,0.88);
            margin: 0;
            font-size: 0.95rem;
            position: relative;
        }
        .ts-hero .ts-hero-tags { margin-top: 14px; position: relative; }
        .ts-hero .ts-tag {
            display: inline-block;
            background: rgba(255,255,255,0.16);
            border: 1px solid rgba(255,255,255,0.28);
            color: #fff;
            padding: 4px 12px;
            border-radius: 999px;
            font-size: 12px;
            font-weight: 600;
            margin: 3px 6px 3px 0;
            backdrop-filter: blur(6px);
        }

        /* ---------- Stat cards (custom, replaces plain st.metric look) ---------- */
        .ts-stat-row { display: flex; gap: 14px; flex-wrap: wrap; margin-bottom: 18px; }
        .ts-stat-card {
            flex: 1 1 150px;
            background: linear-gradient(160deg, #131a2c 0%, #0f1526 100%);
            border: 1px solid rgba(148,163,184,0.14);
            border-radius: 16px;
            padding: 16px 18px;
            position: relative;
            overflow: hidden;
            transition: transform 0.15s ease, border-color 0.15s ease;
        }
        .ts-stat-card:hover {
            transform: translateY(-2px);
            border-color: rgba(148,163,184,0.32);
        }
        .ts-stat-card .ts-stat-bar {
            position: absolute; left: 0; top: 0; bottom: 0; width: 4px;
        }
        .ts-stat-card .ts-stat-label {
            color: #94a3b8; font-size: 12.5px; font-weight: 600;
            text-transform: uppercase; letter-spacing: 0.04em; margin-bottom: 6px;
        }
        .ts-stat-card .ts-stat-value {
            font-size: 1.7rem; font-weight: 800; color: #f8fafc; font-family: 'Manrope', sans-serif;
        }
        .ts-stat-card .ts-stat-icon { font-size: 1.3rem; margin-bottom: 4px; display: block; }

        /* Native st.metric fallback styling (kept for places still using it) */
        div[data-testid="stMetric"] {
            background: linear-gradient(160deg, #131a2c 0%, #0f1526 100%);
            border: 1px solid rgba(148,163,184,0.14);
            padding: 14px 16px;
            border-radius: 16px;
        }
        div[data-testid="stMetricLabel"] { color: #94a3b8 !important; }

        /* ---------- Section header ---------- */
        .ts-section-header {
            display: flex; align-items: center; gap: 10px;
            margin: 26px 0 14px 0;
            padding-bottom: 8px;
            border-bottom: 2px solid rgba(148,163,184,0.14);
        }
        .ts-section-header .ts-section-icon {
            font-size: 1.3rem;
            width: 38px; height: 38px;
            display: flex; align-items: center; justify-content: center;
            border-radius: 10px;
            background: linear-gradient(135deg, rgba(99,102,241,0.25), rgba(20,184,166,0.25));
        }
        .ts-section-header h3 { margin: 0 !important; font-size: 1.15rem !important; }
        .ts-section-header .ts-section-sub { color: #94a3b8; font-size: 12.5px; margin-left: auto; }

        /* ---------- Cards / containers ---------- */
        .ts-card {
            background: linear-gradient(160deg, #131a2c 0%, #0f1526 100%);
            border: 1px solid rgba(148,163,184,0.14);
            padding: 18px 20px;
            border-radius: 16px;
            margin-bottom: 14px;
        }
        .ts-card-bullish { border-left: 4px solid #22c55e; }
        .ts-card-bearish { border-left: 4px solid #f43f5e; }

        /* ---------- Badges / pills ---------- */
        .ts-badge {
            display: inline-flex; align-items: center; gap: 5px;
            padding: 4px 12px; border-radius: 999px;
            font-size: 12.5px; font-weight: 700; letter-spacing: 0.01em;
        }
        .ts-badge-strongbuy { background: rgba(34,197,94,0.20); color: #4ade80; border: 1px solid rgba(74,222,128,0.35); }
        .ts-badge-buy { background: rgba(34,197,94,0.12); color: #86efac; border: 1px solid rgba(134,239,172,0.25); }
        .ts-badge-hold { background: rgba(245,158,11,0.15); color: #fbbf24; border: 1px solid rgba(251,191,36,0.3); }
        .ts-badge-sell { background: rgba(244,63,94,0.12); color: #fca5a5; border: 1px solid rgba(252,165,165,0.25); }
        .ts-badge-strongsell { background: rgba(244,63,94,0.20); color: #f87171; border: 1px solid rgba(248,113,113,0.35); }
        .ts-badge-neutral { background: rgba(148,163,184,0.14); color: #cbd5e1; border: 1px solid rgba(203,213,225,0.25); }

        /* ---------- Sector chip ---------- */
        .sector-chip {
            display: inline-block;
            padding: 5px 14px;
            border-radius: 999px;
            font-size: 12.5px;
            font-weight: 700;
            margin-bottom: 10px;
            letter-spacing: 0.01em;
        }

        /* ---------- Tabs ---------- */
        div[data-testid="stTabs"] button[data-baseweb="tab"] {
            font-weight: 700;
            border-radius: 10px 10px 0 0;
            padding: 10px 16px;
            color: #94a3b8;
        }
        div[data-testid="stTabs"] button[aria-selected="true"] {
            color: #a5b4fc !important;
            background: linear-gradient(180deg, rgba(99,102,241,0.14), transparent);
            border-bottom: 3px solid #818cf8 !important;
        }
        div[data-testid="stTabs"] { border-bottom: 1px solid rgba(148,163,184,0.14); }

        /* ---------- Buttons ---------- */
        div[data-testid="stButton"] button[kind="primary"] {
            background: linear-gradient(120deg, #6366f1, #0891b2);
            border: none;
            font-weight: 700;
            box-shadow: 0 6px 18px rgba(99,102,241,0.35);
            transition: transform 0.12s ease;
        }
        div[data-testid="stButton"] button[kind="primary"]:hover {
            transform: translateY(-1px);
            box-shadow: 0 8px 22px rgba(99,102,241,0.45);
        }
        div[data-testid="stButton"] button[kind="secondary"] {
            border: 1px solid rgba(148,163,184,0.3);
            background: rgba(148,163,184,0.06);
        }

        /* ---------- Sidebar ---------- */
        section[data-testid="stSidebar"] {
            background: linear-gradient(180deg, #0d1220 0%, #0a0e1a 100%);
            border-right: 1px solid rgba(148,163,184,0.12);
        }
        section[data-testid="stSidebar"] h1,
        section[data-testid="stSidebar"] h2,
        section[data-testid="stSidebar"] h3,
        section[data-testid="stSidebar"] h4 { color: #e2e8f0 !important; }

        /* ---------- Alerts ---------- */
        div[data-testid="stAlert"] { border-radius: 14px; }

        /* ---------- Expander ---------- */
        details {
            background: rgba(148,163,184,0.04);
            border: 1px solid rgba(148,163,184,0.12);
            border-radius: 14px !important;
        }

        /* ---------- Divider replacement ---------- */
        .ts-divider {
            height: 1px;
            background: linear-gradient(90deg, transparent, rgba(148,163,184,0.28), transparent);
            margin: 22px 0;
            border: none;
        }

        /* ---------- Misc ---------- */
        .sig-buy {color:#22c55e;font-weight:700;}
        .sig-sell {color:#ef4444;font-weight:700;}
        .sig-hold {color:#f59e0b;font-weight:700;}
        .sig-neutral {color:#94a3b8;font-weight:700;}
        .watch-star { color: #facc15; font-weight: 700; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_hero_header(title: str, subtitle: str, tags=None):
    """Colorful gradient hero banner used at the top of the app."""
    tags_html = ""
    if tags:
        tags_html = '<div class="ts-hero-tags">' + "".join(
            f'<span class="ts-tag">{t}</span>' for t in tags
        ) + "</div>"
    st.markdown(
        f"""
        <div class="ts-hero">
            <h1>{title}</h1>
            <p>{subtitle}</p>
            {tags_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_header(title: str, icon: str = "📊", sub: str = ""):
    """Consistent, colorful section title used to visually separate parts of the page."""
    sub_html = f'<span class="ts-section-sub">{sub}</span>' if sub else ""
    st.markdown(
        f"""
        <div class="ts-section-header">
            <div class="ts-section-icon">{icon}</div>
            <h3>{title}</h3>
            {sub_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_stat_cards(items):
    """
    Render a row of custom-styled stat cards.
    items: list of dicts {label, value, icon, color}
    """
    cards_html = ""
    for it in items:
        color = it.get("color", "#6366f1")
        icon = it.get("icon", "📌")
        cards_html += f"""
        <div class="ts-stat-card">
            <div class="ts-stat-bar" style="background:{color};"></div>
            <span class="ts-stat-icon">{icon}</span>
            <div class="ts-stat-label">{it.get('label','')}</div>
            <div class="ts-stat-value">{it.get('value','')}</div>
        </div>
        """
    st.markdown(f'<div class="ts-stat-row">{cards_html}</div>', unsafe_allow_html=True)


def render_summary_cards(df: pd.DataFrame):
    total = len(df) if df is not None else 0
    buy = len(df[df["Signal"].isin(["BUY", "STRONG BUY"])]) if total else 0
    sell = len(df[df["Signal"].isin(["SELL", "STRONG SELL"])]) if total else 0
    strong_buy = len(df[df["Signal"] == "STRONG BUY"]) if total else 0
    strong_sell = len(df[df["Signal"] == "STRONG SELL"]) if total else 0
    render_stat_cards([
        {"label": "Scanned", "value": total, "icon": "🔎", "color": "#818cf8"},
        {"label": "Buy", "value": buy, "icon": "🟢", "color": "#4ade80"},
        {"label": "Sell", "value": sell, "icon": "🔴", "color": "#f87171"},
        {"label": "Strong Buy", "value": strong_buy, "icon": "🚀", "color": "#16a34a"},
        {"label": "Strong Sell", "value": strong_sell, "icon": "📉", "color": "#dc2626"},
    ])


def signal_badge(signal: str) -> str:
    """Return an HTML pill badge for a Signal/Outlook string."""
    s = str(signal)
    if s.startswith("STRONG BUY") or s.startswith("STRONG BULLISH"):
        cls = "ts-badge-strongbuy"
    elif s.startswith("BUY") or s.startswith("BULLISH"):
        cls = "ts-badge-buy"
    elif s.startswith("HOLD") or s.startswith("NEUTRAL"):
        cls = "ts-badge-hold"
    elif s.startswith("STRONG SELL") or s.startswith("STRONG BEARISH"):
        cls = "ts-badge-strongsell"
    elif s.startswith("SELL") or s.startswith("BEARISH"):
        cls = "ts-badge-sell"
    else:
        cls = "ts-badge-neutral"
    return f'<span class="ts-badge {cls}">{s}</span>'


def render_sector_chip(sector: str):
    color = _sector_color(sector)
    st.markdown(
        f'<span class="sector-chip" style="background:{color}22; color:{color}; '
        f'border:1px solid {color}55;">🏷️ {sector}</span>',
        unsafe_allow_html=True,
    )


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


def _label_with_sector(row) -> str:
    """Build a chart-axis label like 'RELIANCE (Energy & Oil/Gas)' when sector is known."""
    sym = _short_symbol(row.get("Symbol", ""))
    sector = row.get("Sector")
    if sector and str(sector).strip() and str(sector).lower() != "nan":
        return f"{sym} ({sector})"
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

    chart_df["_label"] = chart_df.apply(_label_with_sector, axis=1)
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
        .mark_bar(cornerRadiusTopRight=6, cornerRadiusBottomRight=6)
        .encode(
            x=alt.X("Score:Q", title="Score"),
            y=alt.Y("_label:N", sort="-x", title=None),
            color=alt.Color("Signal:N", scale=color_scale, legend=alt.Legend(title="Signal", orient="top")),
            tooltip=tooltip_fields,
        )
        .properties(height=chart_height)
        .configure_view(strokeWidth=0)
        .configure_axis(
            labelColor="#cbd5e1", titleColor="#94a3b8", gridColor="rgba(148,163,184,0.12)",
            domainColor="rgba(148,163,184,0.25)", labelFontSize=12, titleFontSize=12,
        )
        .configure_legend(labelColor="#cbd5e1", titleColor="#e2e8f0")
    )

    if title:
        st.markdown(f'<div class="ts-card" style="padding:14px 18px 4px 18px; margin-bottom:8px;"><b>{title}</b></div>', unsafe_allow_html=True)
    st.altair_chart(chart, use_container_width=True)


def render_watchlist_manager(all_symbols):
    """
    Sidebar-friendly widget to add/remove symbols from a persistent watchlist.
    """
    st.markdown(
        '<div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;">'
        '<span style="font-size:1.1rem;">⭐</span>'
        '<span style="font-weight:700;color:#f1f5f9;">Watchlist</span>'
        "</div>",
        unsafe_allow_html=True,
    )
    current = load_watchlist()

    add_choice = st.selectbox(
        "Add symbol",
        [""] + sorted(set(all_symbols) - set(current)),
        key="watchlist_add_select",
        label_visibility="collapsed",
        placeholder="Add symbol to watchlist...",
    )
    c1, c2 = st.columns(2)
    with c1:
        if st.button("➕ Add", key="watchlist_add_btn", use_container_width=True) and add_choice:
            add_to_watchlist(add_choice)
            st.rerun()
    with c2:
        if current:
            remove_choice = st.selectbox("Remove", [""] + current, key="watchlist_remove_select", label_visibility="collapsed")
        else:
            remove_choice = None

    if current and st.button("🗑️ Remove selected", key="watchlist_remove_btn", use_container_width=True) and remove_choice:
        remove_from_watchlist(remove_choice)
        st.rerun()

    if current:
        chips = "".join(
            f'<span style="display:inline-block;background:rgba(129,140,248,0.14);color:#a5b4fc;'
            f'border:1px solid rgba(129,140,248,0.3);padding:3px 10px;border-radius:999px;'
            f'font-size:11.5px;font-weight:600;margin:3px 4px 0 0;">{_short_symbol(s)}</span>'
            for s in current
        )
        st.markdown(
            f'<div style="margin-top:8px;">{chips}</div>',
            unsafe_allow_html=True,
        )
        st.caption(f"Watching {len(current)} symbol(s)")
    else:
        st.caption("Watchlist is empty. Add symbols above to track them across scans.")

    return current


def render_watchlist_results(df: pd.DataFrame, watchlist: list):
    if not watchlist:
        return
    section_header("Watchlist Results", icon="⭐", sub=f"{len(watchlist)} symbol(s) tracked")
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
            render_sector_chip(sector)
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

    chart_df["_label"] = chart_df.apply(_label_with_sector, axis=1)
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
        .mark_bar(cornerRadiusTopRight=6, cornerRadiusBottomRight=6)
        .encode(
            x=alt.X("Score:Q", title="Next-Day Score"),
            y=alt.Y("_label:N", sort="-x", title=None),
            color=alt.Color("_color_group:N", scale=color_scale, legend=alt.Legend(title="Outlook", orient="top")),
            opacity=alt.Opacity("_opacity:Q", legend=None, scale=alt.Scale(domain=[0.4, 1.0], range=[0.4, 1.0])),
            tooltip=tooltip_fields,
        )
        .properties(height=chart_height)
        .configure_view(strokeWidth=0)
        .configure_axis(
            labelColor="#cbd5e1", titleColor="#94a3b8", gridColor="rgba(148,163,184,0.12)",
            domainColor="rgba(148,163,184,0.25)", labelFontSize=12, titleFontSize=12,
        )
        .configure_legend(labelColor="#cbd5e1", titleColor="#e2e8f0")
    )

    if title:
        st.markdown(f'<div class="ts-card" style="padding:14px 18px 4px 18px; margin-bottom:8px;"><b>{title}</b></div>', unsafe_allow_html=True)
    st.altair_chart(chart, use_container_width=True)
    st.caption("💡 Faded bars = LOW confidence (backtest sample too small or hit-rate too weak to trust).")


def _next_day_summary_cards(df: pd.DataFrame):
    total = len(df) if df is not None else 0
    strong_bull = len(df[df["Outlook"] == "STRONG BULLISH"]) if total else 0
    strong_bear = len(df[df["Outlook"] == "STRONG BEARISH"]) if total else 0
    bullish = len(df[df["Outlook"].astype(str).str.startswith("BULLISH")]) if total else 0
    high_conf = len(df[df["Confidence"] == "HIGH"]) if total else 0

    render_stat_cards([
        {"label": "Analyzed", "value": total, "icon": "🔎", "color": "#818cf8"},
        {"label": "Strong Bullish", "value": strong_bull, "icon": "🚀", "color": "#16a34a"},
        {"label": "Strong Bearish", "value": strong_bear, "icon": "📉", "color": "#dc2626"},
        {"label": "Bullish (any)", "value": bullish, "icon": "🟢", "color": "#4ade80"},
        {"label": "High Confidence", "value": high_conf, "icon": "⭐", "color": "#facc15"},
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
    """Summary cards + Strong Bullish/Strong Bearish bar charts + full table for one sector (or 'All')."""
    _next_day_summary_cards(df)

    strong_bull = df[df["Outlook"] == "STRONG BULLISH"]
    strong_bear = df[df["Outlook"] == "STRONG BEARISH"]

    if not strong_bull.empty or not strong_bear.empty:
        b1, b2 = st.columns(2)
        with b1:
            render_next_day_bar_chart(strong_bull, title=f"🟢🟢 STRONG BULLISH ({len(strong_bull)})")
        with b2:
            render_next_day_bar_chart(strong_bear, title=f"🔴🔴 STRONG BEARISH ({len(strong_bear)})")
        st.markdown("---")

    with st.expander("📋 Full results table", expanded=False):
        st.dataframe(_next_day_sorted_table(df), use_container_width=True, hide_index=True)


def _next_day_sector_tab_label(sector: str, sector_df: pd.DataFrame) -> str:
    total = len(sector_df)
    sb = len(sector_df[sector_df["Outlook"] == "STRONG BULLISH"])
    ss = len(sector_df[sector_df["Outlook"] == "STRONG BEARISH"])
    badge = ""
    if sb:
        badge += f" 🟢{sb}"
    if ss:
        badge += f" 🔴{ss}"
    return f"{sector} ({total}){badge}"


def render_next_day_results(df: pd.DataFrame):
    """
    Full Next-Day Outlook results panel, split into sector-wise tabs (like
    the intraday scanner). Each tab shows Strong Bullish/Strong Bearish
    counts in its label and renders those calls as horizontal bar charts
    (symbol + sector on each bar), followed by a full sortable table.
    """
    if df is None or df.empty:
        st.warning("No data to display.")
        return

    st.caption(
        "Backtest Hit Rate % = how often this exact rule-set's directional call was "
        "correct historically for THIS stock (over the sample size shown). "
        "Confidence is only HIGH/MEDIUM when the sample size and hit-rate both clear "
        "a minimum bar - otherwise it's marked LOW and the call is softened."
    )

    if "Sector" not in df.columns:
        render_next_day_panel(df)
        return

    sectors_present = df["Sector"].dropna().unique().tolist()
    sectors = ordered_sectors(sectors_present)

    if not sectors:
        render_next_day_panel(df)
        return

    tab_labels = [_next_day_sector_tab_label(s, df[df["Sector"] == s]) for s in sectors]
    tabs = st.tabs(["🌐 All"] + tab_labels)

    with tabs[0]:
        render_next_day_panel(df)

    for tab, sector in zip(tabs[1:], sectors):
        with tab:
            sector_df = df[df["Sector"] == sector]
            render_sector_chip(sector)
            render_next_day_panel(sector_df)
