
import streamlit as st
import pandas as pd
import pandas_ta as ta
from fyers_apiv3 import fyersModel
import time
import requests
from datetime import datetime
import os

# --- TELEGRAM SETTINGS ---
TELEGRAM_TOKEN = "YOUR_BOT_TOKEN"
TELEGRAM_CHAT_ID = "YOUR_CHAT_ID"

def send_telegram_msg(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage?chat_id={TELEGRAM_CHAT_ID}&text={message}"
    requests.get(url)

# --- FYERS CONFIG ---
APP_ID = st.secrets.get("FYERS_APP_ID", "YOUR_APP_ID")
SECRET_KEY = st.secrets.get("FYERS_SECRET_KEY", "YOUR_SECRET_KEY")

st.set_page_config(page_title="Cloud Trading Sathi", layout="wide")

if 'access_token' not in st.session_state:
    st.session_state.access_token = None

# --- SYMBOL FETCHING ---
@st.cache_data
def get_fo_symbols():
    try:
        url = "https://public.fyers.in/sym_details/NSE_FO.csv"
        df = pd.read_csv(url, header=None)
        return [s for s in df[0].unique() if ":NSE" in s][:100] # Limit for speed
    except:
        return ["NSE:RELIANCE-EQ", "NSE:SBIN-EQ", "NSE:INFY-EQ"]

def analyze_stock(fyers, sym):
    # Logic for Technicals + OI
    res = fyers.history({"symbol": sym, "resolution": "15", "date_format": "1", 
                         "range_from": datetime.now().strftime('%Y-%m-%d'), 
                         "range_to": datetime.now().strftime('%Y-%m-%d'), "cont_flag": "1"})
    
    if res['s'] == 'ok' and len(res['candles']) > 20:
        df = pd.DataFrame(res['candles'], columns=['ts', 'o', 'h', 'l', 'c', 'v'])
        df['EMA20'] = ta.ema(df['c'], length=20)
        curr_price = df['c'].iloc[-1]
        
        # Simple Logic: Price Above EMA20 + Volume Spike
        if curr_price > df['EMA20'].iloc[-1] and df['v'].iloc[-1] > df['v'].mean():
            return f"🚀 BULLISH Alert: {sym} at {curr_price}"
        elif curr_price < df['EMA20'].iloc[-1] and df['v'].iloc[-1] > df['v'].mean():
            return f"📉 BEARISH Alert: {sym} at {curr_price}"
    return None

# --- MAIN APP ---
st.title("☁️ Cloud Trading Sathi (24/7)")

token_input = st.text_input("Enter Fyers Access Token (valid for 24h):", type="password")
if token_input:
    st.session_state.access_token = token_input

if st.session_state.access_token:
    fyers = fyersModel.FyersModel(client_id=APP_ID, token=st.session_state.access_token, log_path="")
    
    st.success("Sathi is Active and Monitoring...")
    symbols = get_fo_symbols()
    
    # This loop runs while the script is active
    placeholder = st.empty()
    while True:
        current_time = datetime.now().strftime("%H:%M:%S")
        alerts = []
        
        with placeholder.container():
            st.write(f"Last Scan: {current_time}")
            for sym in symbols:
                alert = analyze_stock(fyers, sym)
                if alert:
                    alerts.append(alert)
                    send_telegram_msg(alert) # Sends to your mobile!
            
            if alerts:
                st.write(alerts)
            else:
                st.write("No major moves detected yet.")
        
        time.sleep(300) # Wait 5 minutes before next scan
        st.rerun()
else:
    st.info("Please provide the Access Token to start the Cloud Sathi.")
