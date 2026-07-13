# config.py
"""
Safe configuration file for GitHub + Streamlit Cloud.
This file is 100% safe to commit.

For real credentials:
- Use Streamlit Cloud Secrets (recommended), OR
- Set environment variables
"""

# ====================== PLACEHOLDER VALUES ======================
# These are safe defaults. Real values come from Secrets.
APP_ID = "YOUR_FYERS_APP_ID"
SECRET_KEY = "YOUR_FYERS_SECRET_KEY"
REDIRECT_URL = "https://your-redirect-url.com"

# ====================== TIMEFRAMES ======================
TIMEFRAME_OPTIONS = {
    "1m": "1m",
    "5m": "5m",
    "15m": "15m",
    "1h": "60m",
    "1d": "1d",
    "1w": "1w",
    "1M": "1M"
}

# Sector Trend timeframes (Tab 3)
SECTOR_TIMEFRAMES = {
    "1D (Intraday)": "1d",
    "1W": "1w",
    "2W": "2w",
    "1 Month": "1M"
}
