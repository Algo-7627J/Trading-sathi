# ui_helpers.py
import streamlit as st
import pandas as pd

def inject_custom_css():
    st.markdown("""
    <style>
    .stApp { background-color: #0f172a; color: #e2e8f0; }
    .stButton > button { background-color: #1e2937; border: 1px solid #334155; color: white; }
    .stButton > button:hover { background-color: #334155; border-color: #64748b; }
    .metric-card { background: #1e2937; border-radius: 12px; padding: 16px; border: 1px solid #334155; }
    .bullish { background: #052e16; border: 1px solid #16a34a; }
    .bearish { background: #450a0a; border: 1px solid #b91c1c; }
    .sector-card { 
        background: #1e2937; 
        border-radius: 12px; 
        padding: 14px; 
        margin-bottom: 8px; 
        border: 1px solid #475569;
        cursor: pointer;
    }
    .sector-card:hover { border-color: #64748b; background: #334155; }
    .stock-card {
        background: #1e2937;
        border-radius: 10px;
        padding: 12px;
        margin-bottom: 8px;
        border: 1px solid #334155;
    }
    </style>
    """, unsafe_allow_html=True)

def render_title(title, subtitle, connected=False):
    st.markdown(f"""
    <div style="display:flex; align-items:center; gap:12px; margin-bottom:8px;">
        <div style="font-size:32px; font-weight:800;">{title}</div>
        <div style="font-size:18px; color:#64748b;">{subtitle}</div>
    </div>
    """, unsafe_allow_html=True)
    if connected:
        st.caption("🟢 Connected to FYERS")

def section_label(text):
    st.markdown(f"<h3 style='margin:12px 0 8px 0; color:#cbd5e1; font-size:18px;'>{text}</h3>", unsafe_allow_html=True)

def render_stat_row(stats):
    cols = st.columns(len(stats))
    for i, stat in enumerate(stats):
        with cols[i]:
            st.markdown(f"""
            <div class="metric-card">
                <div style="font-size:12px; color:#94a3b8;">{stat['label']}</div>
                <div style="font-size:24px; font-weight:700; margin-top:4px;">{stat['value']}</div>
            </div>
            """, unsafe_allow_html=True)

def render_watchlist_manager(all_symbols):
    st.markdown("**Watchlist**")
    watchlist = st.session_state.get("watchlist", [])
    
    if "watchlist" not in st.session_state:
        st.session_state.watchlist = []
    
    col1, col2 = st.columns([3,1])
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
            c1, c2 = st.columns([4,1])
            c1.write(sym)
            if c2.button("✕", key=f"rm_{i}", use_container_width=True):
                st.session_state.watchlist.remove(sym)
                st.rerun()
    else:
        st.caption("No symbols in watchlist")

def render_compact_table_view(df):
    if df is None or df.empty:
        return
    display_cols = [c for c in ["Symbol", "Sector", "LTP", "Signal", "Score", "Pattern", "MTF Status", "Volume"] if c in df.columns]
    st.dataframe(df[display_cols], use_container_width=True, hide_index=True, height=400)

def render_compact_cards_view(df):
    if df is None or df.empty:
        return
    for _, row in df.iterrows():
        symbol = row.get("Symbol", "N/A")
        score = float(row.get("Score", 0))
        ltp = row.get("LTP", "N/A")
        signal = str(row.get("Signal", ""))
        pattern = row.get("Pattern", "N/A")
        mtf = row.get("MTF Status", "N/A")
        vol = row.get("Volume", "N/A")
        sector = row.get("Sector", "N/A")
        
        is_bull = "Buy" in signal or "Bullish" in signal or score > 0
        bg = "#052e16" if is_bull else "#450a0a"
        border = "#16a34a" if is_bull else "#b91c1c"
        txt = "#22c55e" if is_bull else "#ef4444"
        
        st.markdown(f"""
        <div style="background:{bg}; border:1px solid {border}; border-radius:12px; padding:14px; margin-bottom:8px;">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <div>
                    <span style="font-size:17px; font-weight:700; color:{txt};">{symbol}</span>
                    <span style="margin-left:8px; font-size:12px; color:#94a3b8;">{sector}</span>
                </div>
                <div style="font-weight:600; color:#e2e8f0;">₹{ltp}</div>
            </div>
            <div style="margin:6px 0; font-size:13px; color:#cbd5e1;">
                <b>{signal}</b> • Score: {score:.1f}
            </div>
            <div style="font-size:12px; color:#94a3b8;">
                {pattern} • MTF: {mtf} • Vol: {vol}
            </div>
        </div>
        """, unsafe_allow_html=True)

def render_next_day_results(df):
    """Render next day results in card view (similar to intraday)"""
    if df is None or df.empty:
        st.info("No next-day outlook data available.")
        return
    
    st.markdown("### 📅 Next-Day Outlook Cards")
    
    # Add a view mode option
    view_mode = st.radio("View", ["Cards", "Table"], horizontal=True, key="nd_view_mode")
    
    if view_mode == "Table":
        display_cols = [c for c in ["Symbol", "Sector", "Outlook", "Expected_Move", "Confidence", "Bias", "Key_Levels"] if c in df.columns]
        st.dataframe(df[display_cols], use_container_width=True, hide_index=True)
        return
    
    # Card view
    for _, row in df.iterrows():
        symbol = row.get("Symbol", "N/A")
        outlook = str(row.get("Outlook", "Neutral"))
        exp_move = row.get("Expected_Move", "N/A")
        conf = row.get("Confidence", 0)
        bias = str(row.get("Bias", "Neutral"))
        sector = row.get("Sector", "N/A")
        key_levels = row.get("Key_Levels", "N/A")
        
        is_bull = "Bullish" in outlook or "Buy" in outlook or bias == "Bullish"
        bg = "#052e16" if is_bull else "#450a0a" if "Bearish" in outlook or bias == "Bearish" else "#1e2937"
        border = "#16a34a" if is_bull else "#b91c1c" if "Bearish" in outlook or bias == "Bearish" else "#475569"
        color = "#22c55e" if is_bull else "#ef4444" if "Bearish" in outlook else "#94a3b8"
        
        st.markdown(f"""
        <div style="background:{bg}; border:1px solid {border}; border-radius:12px; padding:14px; margin-bottom:10px;">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <div>
                    <span style="font-size:17px; font-weight:700; color:{color};">{symbol}</span>
                    <span style="margin-left:8px; font-size:12px; color:#64748b;">{sector}</span>
                </div>
                <div style="text-align:right;">
                    <div style="font-size:13px; color:#cbd5e1;">{outlook}</div>
                    <div style="font-weight:600; color:#e2e8f0;">{exp_move}</div>
                </div>
            </div>
            <div style="margin-top:8px; display:flex; gap:16px; font-size:13px;">
                <div><span style="color:#94a3b8;">Confidence:</span> <b>{conf}%</b></div>
                <div><span style="color:#94a3b8;">Bias:</span> <span style="color:{color};">{bias}</span></div>
            </div>
            <div style="margin-top:4px; font-size:12px; color:#64748b;">
                {key_levels}
            </div>
        </div>
        """, unsafe_allow_html=True)

def sort_by_priority(df):
    if df is None or df.empty or "Score" not in df.columns:
        return df
    return df.sort_values("Score", ascending=False)

def render_sector_card(sector, total, bullish, bearish, avg_score, is_bullish=True, key_prefix=""):
    """Clickable sector card"""
    pct = (bullish / total * 100) if total > 0 else 0
    color = "#16a34a" if is_bullish else "#ef4444"
    bg = "#052e16" if is_bullish else "#450a0a"
    
    col1, col2 = st.columns([4, 1])
    with col1:
        st.markdown(f"""
        <div style="background:{bg}; border:1px solid {color}; border-radius:10px; padding:12px 14px; margin-bottom:6px;">
            <div style="display:flex; justify-content:space-between;">
                <div>
                    <span style="font-weight:700; font-size:15px; color:white;">{sector}</span>
                    <span style="margin-left:8px; font-size:12px; color:#94a3b8;">{total} stocks</span>
                </div>
                <div style="text-align:right; font-size:13px;">
                    <span style="color:{color};">{bullish if is_bullish else bearish}</span>
                    <span style="color:#64748b;"> / {total}</span>
                </div>
            </div>
            <div style="font-size:12px; margin-top:4px;">
                Bullish: {bullish} ({pct:.0f}%) • Avg Score: {avg_score:.1f}
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        if st.button("View Stocks", key=f"{key_prefix}_{sector}", use_container_width=True):
            return sector
    return None

def load_watchlist():
    if "watchlist" not in st.session_state:
        st.session_state.watchlist = []
    return st.session_state.watchlist

# Add any other helpers as needed
