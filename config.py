import streamlit as st

APP_ID = st.secrets.get("FYERS_APP_ID", "")
SECRET_KEY = st.secrets.get("FYERS_SECRET_KEY", "")
REDIRECT_URL = st.secrets.get("FYERS_REDIRECT_URL", "")
TELEGRAM_TOKEN = st.secrets.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = st.secrets.get("TELEGRAM_CHAT_ID", "")
NEWS_API_KEY = st.secrets.get("NEWS_API_KEY", "")

NSE_FO_LIST_URL = "https://www.nseindia.com/api/master-quote"
FYERS_NSE_FO_MASTER = "https://public.fyers.in/sym_details/NSE_FO.csv"
FYERS_MCX_MASTER = "https://public.fyers.in/sym_details/MCX_COM.csv"
NEWS_API_URL = "https://newsapi.org/v2/everything"

COMMODITY_BASES = ["GOLD", "GOLDM", "SILVER", "SILVERM", "CRUDEOIL", "CRUDEOILM"]
INDEX_BASES = ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

LOOKBACK_DAYS = 30
NEWS_LOOKBACK_DAYS = 2

TIMEFRAME_OPTIONS = {
    "5 min only": {
        "primary": "5",
        "confirm": None,
        "label": "5m"
    },
    "5 min + 15 min": {
        "primary": "5",
        "confirm": "15",
        "label": "5m + 15m"
    },
    "15 min + 1 hr": {
        "primary": "15",
        "confirm": "60",
        "label": "15m + 1h"
    },
    "1 hr + 4 hr": {
        "primary": "60",
        "confirm": "240",
        "label": "1h + 4h"
    },
}

WEIGHTS = {
    "technical": 25,
    "momentum": 15,
    "volume": 10,
    "pattern": 20,
    "oi": 15,
    "news": 10,
    "fundamental": 3,
    "results": 2,
}

CONFIRMATION_BONUS = 12
CONFIRMATION_PENALTY = 10

STRONG_BUY_THRESHOLD = 55
BUY_THRESHOLD = 20
SELL_THRESHOLD = -20
STRONG_SELL_THRESHOLD = -55

NEWS_POSITIVE_KEYWORDS = [
    "order win", "beats estimates", "beat estimates", "strong demand", "margin expansion",
    "upgrade", "target raised", "growth", "record high", "partnership", "approval",
    "expansion", "profit jumps", "recovery", "bullish", "outperform"
]

NEWS_NEGATIVE_KEYWORDS = [
    "downgrade", "misses estimates", "miss estimate", "weak demand", "margin pressure",
    "penalty", "probe", "lawsuit", "decline", "loss", "default", "fraud",
    "guidance cut", "bearish", "underperform", "fall", "drops"
]
