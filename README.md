# Trading Sathi

Trading Sathi ek Streamlit-based smart scanner hai jo intraday aur max 2-day holding ideas ke liye design kiya gaya hai.

## Features

- NSE F&O stocks scan
- Index futures scan
- Commodity futures scan
- Technical trend analysis
- Momentum analysis
- Volume analysis
- Multi-candle chart pattern detection
- OI analysis
- News sentiment analysis
- Telegram alerts
- Downloadable scan results CSV
- Signal history tracking

## Multi-Candle Patterns Included

- Cup and Handle
- Double Bottom
- Double Top
- Triangle Breakout / Breakdown
- Range Breakout / Breakdown
- Flag
- Pennant
- Head and Shoulders

## Required Streamlit Secrets

Aapko Streamlit secrets me ye values add karni hongi:

- `FYERS_APP_ID`
- `FYERS_SECRET_KEY`
- `FYERS_REDIRECT_URL`
- `TELEGRAM_TOKEN`
- `TELEGRAM_CHAT_ID`
- `NEWS_API_KEY`

## How to Run

```bash
streamlit run app.py
