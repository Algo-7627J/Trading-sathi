import streamlit as st
import pandas as pd
from fyers_apiv3 import fyersModel
import requests
from datetime import datetime, timedelta

# ---------------- CONFIG ----------------
APP_ID = st.secrets.get("FYERS_APP_ID", "")
SECRET_KEY = st.secrets.get("FYERS_SECRET_KEY", "")
REDIRECT_URL = st.secrets.get("FYERS_REDIRECT_URL", "")
TELEGRAM_TOKEN = st.secrets.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = st.secrets.get("TELEGRAM_CHAT_ID", "")

# Approx F&O stock universe (cash symbols used for signal scan)
DEFAULT_SYMBOLS = [
    "NSE:RELIANCE-EQ", "NSE:SBIN-EQ", "NSE:TATASTEEL-EQ", "NSE:INFY-EQ", "NSE:HDFCBANK-EQ",
    "NSE:ICICIBANK-EQ", "NSE:AXISBANK-EQ", "NSE:KOTAKBANK-EQ", "NSE:LT-EQ", "NSE:ITC-EQ",
    "NSE:MARUTI-EQ", "NSE:TCS-EQ", "NSE:BAJFINANCE-EQ", "NSE:BAJAJFINSV-EQ", "NSE:HINDUNILVR-EQ",
    "NSE:ASIANPAINT-EQ", "NSE:ULTRACEMCO-EQ", "NSE:ONGC-EQ", "NSE:NTPC-EQ", "NSE:POWERGRID-EQ",
    "NSE:BHARTIARTL-EQ", "NSE:SUNPHARMA-EQ", "NSE:TITAN-EQ", "NSE:HCLTECH-EQ", "NSE:WIPRO-EQ",
    "NSE:TECHM-EQ", "NSE:ADANIPORTS-EQ", "NSE:INDUSINDBK-EQ", "NSE:GRASIM-EQ", "NSE:JSWSTEEL-EQ",
    "NSE:HINDALCO-EQ", "NSE:COALINDIA-EQ", "NSE:BPCL-EQ", "NSE:HEROMOTOCO-EQ", "NSE:EICHERMOT-EQ",
    "NSE:DRREDDY-EQ", "NSE:CIPLA-EQ", "NSE:DIVISLAB-EQ", "NSE:APOLLOHOSP-EQ", "NSE:ADANIENT-EQ",
    "NSE:TATAMOTORS-EQ", "NSE:M&M-EQ", "NSE:UPL-EQ", "NSE:BRITANNIA-EQ", "NSE:NESTLEIND-EQ",
    "NSE:SHRIRAMFIN-EQ", "NSE:BAJAJ-AUTO-EQ", "NSE:LTIM-EQ", "NSE:TRENT-EQ", "NSE:BEL-EQ"
]


# ---------------- TELEGRAM FUNCTION ----------------
def send_telegram_msg(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
        requests.get(url, params=payload, timeout=5)
    except Exception:
        pass


# ---------------- SCAN FUNCTION ----------------
def scan_symbols(fyers, symbols):
    now = datetime.now()
    results = []

    for sym in symbols:
        try:
            from_d = (now - timedelta(days=5)).strftime("%Y-%m-%d")
            to_d = now.strftime("%Y-%m-%d")

            data = {
                "symbol": sym.strip(),
                "resolution": "15",
                "date_format": "1",
                "range_from": from_d,
                "range_to": to_d,
                "cont_flag": "1"
            }

            res = fyers.history(data)

            if res and res.get("s") == "ok" and "candles" in res:
                df = pd.DataFrame(res["candles"], columns=["ts", "o", "h", "l", "c", "v"])

                if len(df) >= 20:
                    df["EMA20"] = df["c"].ewm(span=20, adjust=False).mean()

                    last_close = df["c"].iloc[-1]
                    ema20 = df["EMA20"].iloc[-1]

                    signal = "HOLD"
                    if last_close > ema20 * 1.005:
                        signal = "BUY"
                        send_telegram_msg(f"🚀 BUY: {sym} at {last_close}")
                    elif last_close < ema20 * 0.995:
                        signal = "SELL"
                        send_telegram_msg(f"📉 SELL: {sym} at {last_close}")

                    results.append({
                        "Symbol": sym,
                        "Last Close": round(last_close, 2),
                        "EMA20": round(ema20, 2),
                        "Signal": signal
                    })
                else:
                    results.append({
                        "Symbol": sym,
                        "Last Close": "-",
                        "EMA20": "-",
                        "Signal": "Not enough candle data"
                    })
            else:
                results.append({
                    "Symbol": sym,
                    "Last Close": "-",
                    "EMA20": "-",
                    "Signal": f"API Error"
                })

        except Exception as e:
            results.append({
                "Symbol": sym,
                "Last Close": "-",
                "EMA20": "-",
                "Signal": f"Error: {e}"
            })

    return pd.DataFrame(results)


# ---------------- PAGE SETUP ----------------
st.set_page_config(page_title="Trading Sathi", layout="wide")
st.title("🤖 Trading Sathi - F&O Universe Scanner")

if "fyers" not in st.session_state:
    st.session_state.fyers = None

if "access_token" not in st.session_state:
    st.session_state.access_token = None

if "run_scan" not in st.session_state:
    st.session_state.run_scan = False


# ---------------- LOGIN SECTION ----------------
if st.session_state.fyers is None:
    st.info("Step 1: Login to FYERS and get auth code")

    if not APP_ID or not SECRET_KEY or not REDIRECT_URL:
        st.error("Please set FYERS_APP_ID, FYERS_SECRET_KEY and FYERS_REDIRECT_URL in Streamlit secrets.")
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
            st.markdown(f"**[👉 Click here to Login to FYERS]({login_url})**")
        except Exception as e:
            st.error(f"Unable to generate FYERS login URL: {e}")

    auth_code = st.text_input("Step 2: Paste the auth_code here:")

    if st.button("Generate Access Token"):
        if not APP_ID or not SECRET_KEY or not REDIRECT_URL:
            st.error("Missing FYERS credentials or redirect URL in Streamlit secrets.")
        elif not auth_code:
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

                if "access_token" in response:
                    access_token = response["access_token"]
                    st.session_state.access_token = access_token

                    st.session_state.fyers = fyersModel.FyersModel(
                        client_id=APP_ID,
                        token=access_token,
                        log_path=""
                    )

                    st.success("Login Successful!")
                    st.rerun()
                else:
                    st.error(f"Token generation failed: {response}")

            except Exception as e:
                st.error(f"Login failed: {e}")


# ---------------- DASHBOARD SECTION ----------------
else:
    st.success("✅ Connected to FYERS")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Scan Full F&O Stock Universe"):
            st.session_state.run_scan = True

    with col2:
        if st.button("Logout"):
            st.session_state.fyers = None
            st.session_state.access_token = None
            st.session_state.run_scan = False
            st.rerun()

    st.subheader("Editable F&O Universe Symbols")
    symbol_text = st.text_area(
        "One symbol per line",
        value="\n".join(DEFAULT_SYMBOLS),
        height=400
    )

    symbols = [s.strip() for s in symbol_text.split("\n") if s.strip()]

    st.write(f"Total symbols to scan: {len(symbols)}")

    if st.session_state.run_scan:
        st.session_state.run_scan = False

        st.info("Scanning symbols... please wait.")
        result_df = scan_symbols(st.session_state.fyers, symbols)

        st.subheader("Scan Results")
        st.dataframe(result_df, use_container_width=True)

        if not result_df.empty:
            buy_df = result_df[result_df["Signal"] == "BUY"]
            sell_df = result_df[result_df["Signal"] == "SELL"]

            st.subheader("BUY Signals")
            st.dataframe(buy_df, use_container_width=True)

            st.subheader("SELL Signals")
            st.dataframe(sell_df, use_container_width=True)
