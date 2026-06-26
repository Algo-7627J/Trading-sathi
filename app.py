import streamlit as st
import pandas as pd
from fyers_apiv3 import fyersModel
from fyers_apiv3.FyersModel import SessionModel
import time
import requests
from datetime import datetime, timedelta

# --- CONFIG ---
APP_ID = st.secrets.get("FYERS_APP_ID", "")
SECRET_KEY = st.secrets.get("FYERS_SECRET_KEY", "")
TELEGRAM_TOKEN = st.secrets.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = st.secrets.get("TELEGRAM_CHAT_ID", "")
REDIRECT_URL = "https://www.google.com"

def send_telegram_msg(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage?chat_id={TELEGRAM_CHAT_ID}&text={message}"
        requests.get(url, timeout=5)
    except:
        pass

st.set_page_config(page_title="Trading Sathi", layout="wide")

if 'fyers' not in st.session_state:
    st.session_state.fyers = None

st.title("🤖 My Intelligent Trading Sathi")

if not st.session_state.fyers:
    st.info("Step 1: Get Auth Code from Fyers")

    login_url = f"https://api.fyers.in/api/v2/generate-authcode?client_id={APP_ID}&redirect_uri={REDIRECT_URL}&response_type=code&state=sample_state"
    st.markdown(f"**[👉 Click here to Login to Fyers]({login_url})**")

    auth_code = st.text_input("Step 2: Paste the 'auth_code' here:")

    if st.button("Generate Access Token"):
        try:
            session = SessionModel(
                client_id=APP_ID,
                secret_key=SECRET_KEY,
                redirect_uri=REDIRECT_URL,
                response_type="code",
                grant_type="authorization_code"
            )
            session.set_token(auth_code)
            response = session.generate_token()
            access_token = response["access_token"]

            st.session_state.fyers = fyersModel.FyersModel(
                client_id=APP_ID,
                token=access_token,
                log_path=""
            )
            st.success("Login Successful!")
            st.rerun()
        except Exception as e:
            st.error(f"Login failed: {e}")

else:
    st.success("✅ Sathi is Monitoring...")

    if st.button("Logout"):
        st.session_state.fyers = None
        st.rerun()

    placeholder = st.empty()

    symbols = [
        "NSE:RELIANCE-EQ",
        "NSE:SBIN-EQ",
        "NSE:TATASTEEL-EQ",
        "NSE:INFY-EQ",
        "NSE:HDFCBANK-EQ"
    ]

    now = datetime.now()
    with placeholder.container():
        st.write(f"⏳ Last Scan: {now.strftime('%H:%M:%S')}")

        for sym in symbols:
            try:
                from_d = (now - timedelta(days=3)).strftime('%Y-%m-%d')
                to_d = now.strftime('%Y-%m-%d')

                data = {
                    "symbol": sym,
                    "resolution": "15",
                    "date_format": "1",
                    "range_from": from_d,
                    "range_to": to_d,
                    "cont_flag": "1"
                }

                res = st.session_state.fyers.history(data)

                if res and res.get('s') == 'ok':
                    df = pd.DataFrame(res['candles'], columns=['ts', 'o', 'h', 'l', 'c', 'v'])
                    df['EMA20'] = df['c'].ewm(span=20, adjust=False).mean()

                    lc = df['c'].iloc[-1]
                    ev = df['EMA20'].iloc[-1]

                    if lc > ev * 1.005:
                        st.write(f"🚀 BUY: {sym} at {lc}")
                        send_telegram_msg(f"🚀 BUY: {sym} at {lc}")
                    elif lc < ev * 0.995:
                        st.write(f"📉 SELL: {sym} at {lc}")
                        send_telegram_msg(f"📉 SELL: {sym} at {lc}")

            except Exception as e:
                st.warning(f"Error for {sym}: {e}")

    st.info("Refresh the app manually or add auto-refresh logic carefully.")
