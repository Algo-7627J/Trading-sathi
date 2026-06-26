import streamlit as st
import pandas as pd
from fyers_apiv3 import fyersModel
import requests
from datetime import datetime, timedelta

# ---------------- CONFIG ----------------
APP_ID = st.secrets.get("FYERS_APP_ID", "")
SECRET_KEY = st.secrets.get("FYERS_SECRET_KEY", "")
TELEGRAM_TOKEN = st.secrets.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = st.secrets.get("TELEGRAM_CHAT_ID", "")

# IMPORTANT:
# Use the same redirect URL that is registered in your FYERS app settings
REDIRECT_URL = "https://www.google.com"


# ---------------- HELPER FUNCTION ----------------
def send_telegram_msg(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return

    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message
        }
        requests.get(url, params=payload, timeout=5)
    except Exception:
        pass


# ---------------- STREAMLIT PAGE ----------------
st.set_page_config(page_title="Trading Sathi", layout="wide")
st.title("🤖 My Intelligent Trading Sathi")

if "fyers" not in st.session_state:
    st.session_state.fyers = None

if "access_token" not in st.session_state:
    st.session_state.access_token = None


# ---------------- LOGIN SECTION ----------------
if st.session_state.fyers is None:
    st.info("Step 1: Get Auth Code from FYERS")

    login_url = (
        f"https://api.fyers.in/api/v2/generate-authcode"
        f"?client_id={APP_ID}"
        f"&redirect_uri={REDIRECT_URL}"
        f"&response_type=code"
        f"&state=sample_state"
    )

    st.markdown(f"**[👉 Click here to Login to FYERS]({login_url})**")

    auth_code = st.text_input("Step 2: Paste the auth_code here:")

    if st.button("Generate Access Token"):
        if not APP_ID or not SECRET_KEY:
            st.error("FYERS_APP_ID or FYERS_SECRET_KEY is missing in Streamlit secrets.")
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


# ---------------- MAIN APP ----------------
else:
    st.success("✅ Sathi is Connected and Monitoring")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Scan Now"):
            st.session_state["run_scan"] = True

    with col2:
        if st.button("Logout"):
            st.session_state.fyers = None
            st.session_state.access_token = None
            st.rerun()

    st.write("This app checks selected stocks and sends Telegram alerts based on EMA20 logic.")

    symbols = [
        "NSE:RELIANCE-EQ",
        "NSE:SBIN-EQ",
        "NSE:TATASTEEL-EQ",
        "NSE:INFY-EQ",
        "NSE:HDFCBANK-EQ"
    ]

    st.subheader("Tracking Symbols")
    st.write(symbols)

    if st.session_state.get("run_scan", False):
        st.session_state["run_scan"] = False

        now = datetime.now()
        st.write(f"⏳ Last Scan: {now.strftime('%Y-%m-%d %H:%M:%S')}")

        results = []

        for sym in symbols:
            try:
                from_d = (now - timedelta(days=3)).strftime("%Y-%m-%d")
                to_d = now.strftime("%Y-%m-%d")

                data = {
                    "symbol": sym,
                    "resolution": "15",
                    "date_format": "1",
                    "range_from": from_d,
                    "range_to": to_d,
                    "cont_flag": "1"
                }

                res = st.session_state.fyers.history(data)

                if res and res.get("s") == "ok" and "candles" in res:
                    df = pd.DataFrame(
                        res["candles"],
                        columns=["ts", "o", "h", "l", "c", "v"]
                    )

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
                        "Signal": f"API Error: {res}"
                    })

            except Exception as e:
                results.append({
                    "Symbol": sym,
                    "Last Close": "-",
                    "EMA20": "-",
                    "Signal": f"Error: {e}"
                })

        st.subheader("Scan Results")
        st.dataframe(pd.DataFrame(results), use_container_width=True)
