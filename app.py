import streamlit as st
import pandas as pd
import pandas_ta as ta
from fyers_apiv3 import fyersModel
from fyers_apiv3.FyersModel import SessionModel
import time
import requests
from datetime import datetime

# --- CONFIG ---
APP_ID = st.secrets.get("FYERS_APP_ID", "")
SECRET_KEY = st.secrets.get("FYERS_SECRET_KEY", "")
TELEGRAM_TOKEN = st.secrets.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = st.secrets.get("TELEGRAM_CHAT_ID", "")
REDIRECT_URL = "https://www.google.com"

def send_telegram_msg(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage?chat_id={TELEGRAM_CHAT_ID}&text={message}"
        requests.get(url)
    except:
        pass

st.set_page_config(page_title="Trading Sathi", layout="wide")

if 'fyers' not in st.session_state:
    st.session_state.fyers = None

st.title("🤖 My Intelligent Trading Sathi")

if not st.session_state.fyers:
    st.info("Step 1: Get Auth Code from Fyers")
    login_url = f"https://api.fyers.in/api/v2/generate-authcode?client_id={APP_ID}&redirect_uri={REDIRECT_URL}&response_type=code&state=sample_state"
    st.markdown(f'[👉 Click here to Login to Fyers]({login_url})')
    
    auth_code = st.text_input("Step 2: Paste the 'auth_code' from the URL here:")
    
    if st.button("Generate Access Token"):
        try:
            session = SessionModel(client_id=APP_ID, secret_key=SECRET_KEY, redirect_uri=REDIRECT_URL, response_type="code", grant_type="authorization_code")
            session.set_token(auth_code)
            response = session.generate_token()
            access_token = response["access_token"]
            st.session_state.fyers = fyersModel.FyersModel(client_id=APP_ID, token=access_token, log_path="")
            st.success("Login Successful! Sathi is Active.")
            st.rerun()
        except Exception as e:
            st.error(f"Login failed: {e}")
else:
    st.success("✅ Sathi is Monitoring Market...")
    if st.button("Logout"):
        st.session_state.fyers = None
        st.rerun()

    placeholder = st.empty()
    symbols = ["NSE:RELIANCE-EQ", "NSE:SBIN-EQ", "NSE:TATASTEEL-EQ", "NSE:INFY-EQ", "NSE:HDFCBANK-EQ"]
    
    while True:
        current_time = datetime.now().strftime("%H:%M:%S")
        alerts = []
        with placeholder.container():
            st.write(f"⏳ Last Scan Time: {current_time}")
            for sym in symbols:
                try:
                    data = {"symbol": sym, "resolution": "15", "date_format": "1", 
                            "range_from": datetime.now().strftime('%Y-%m-%d'), 
                            "range_to": datetime.now().strftime('%Y-%m-%d'), "cont_flag": "1"}
                    res = st.session_state.fyers.history(data)
                    if res['s'] == 'ok' and len(res['candles']) > 10:
                        df = pd.DataFrame(res['candles'], columns=['ts', 'o', 'h', 'l', 'c', 'v'])
                        df['EMA20'] = ta.ema(df['c'], length=20)
                        last_close = df['c'].iloc[-1]
                        if last_close > df['EMA20'].iloc[-1] * 1.005:
                            msg = f"🚀 BUY ALERT: {sym} at {last_close}"
                            alerts.append(msg)
                            send_telegram_msg(msg)
                        elif last_close < df['EMA20'].iloc[-1] * 0.995:
                            msg = f"📉 SELL ALERT: {sym} at {last_close}"
                            alerts.append(msg)
                            send_telegram_msg(msg)
                except:
                    continue
            if alerts: st.write(alerts)
            else: st.write("Searching for opportunities...")
        time.sleep(300)
        st.rerun()
