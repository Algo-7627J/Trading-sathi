import streamlit as st
import pandas as pd


def inject_custom_css():
    st.markdown(
        """
        <style>
        .main {background-color: #0f172a; color: #e2e8f0;}
        .block-container {padding-top: 1rem; padding-bottom: 2rem; max-width: 96%;}
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


def display_signal_table(df: pd.DataFrame):
    if df is None or df.empty:
        st.warning("No data to display.")
        return
    st.dataframe(df, use_container_width=True, hide_index=True)
