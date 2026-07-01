# Trading Sathi

Trading Sathi ek Streamlit-based smart scanner hai jo intraday aur max 2-day holding ideas ke liye design kiya gaya hai.

## Features

- NSE F&O stocks scan
- Index futures scan
- Commodity futures scan
- Technical trend analysis
- Momentum analysis
- Volume analysis
- Multi-candle chart pattern detection (16 patterns)
- OI analysis
- News sentiment analysis
- Real fundamentals & quarterly results (via Screener.in, best-effort)
- Sector-wise results view with tabs, Strong Buy/Strong Sell always shown first
- Persistent watchlist (add/remove symbols, dedicated results section)
- Live auto-refresh scanning
- Telegram alerts
- Downloadable scan results CSV
- Signal history tracking

## Multi-Candle Patterns Included

- Cup and Handle
- Double Bottom
- Double Top
- Triangle Breakout / Breakdown
- Rising Wedge
- Falling Wedge
- Rounding Bottom
- Range Breakout / Breakdown
- Flag (Bull/Bear)
- Pennant (Bull/Bear)
- Head and Shoulders
- Inverse Head and Shoulders
- Bullish Engulfing
- Bearish Engulfing
- Morning Star
- Evening Star

## Sector-wise View

Scan results are grouped into sector tabs (Banking, IT, Auto, Pharma, FMCG,
Metals, Energy, Power, Infra, Cement, Chemicals, Telecom, Realty, Consumer
Durables, Media, Capital Goods, Defense, Textiles, Aviation, Retail, New Age
& Internet, Index, Commodity, Others). Within every tab (and overall),
**STRONG BUY** and **STRONG SELL** signals are always ranked to the top,
followed by BUY/SELL, then HOLD - sorted by score strength.

Sector mapping lives in `data/sector_map.csv` and can be hand-edited/extended.

## Fundamentals & Results

When "Include Fundamentals/Results" is enabled, the scanner fetches P/E, ROE,
ROCE and the latest quarter's Sales/Net Profit QoQ growth from Screener.in
(no API key required, unofficial best-effort scrape - may be slower or
occasionally unavailable if Screener changes its layout or rate-limits).

## Watchlist

Add/remove symbols from a persistent watchlist in the sidebar. You can scan
"Only Watchlist" symbols, and watchlist results are always shown in a
dedicated section after every scan regardless of scan scope.

## Live Auto-Refresh

Enable auto-refresh in the sidebar to automatically re-run the last scan
configuration at a chosen interval (30s - 30min) without manual clicks.

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
pip install -r requirements.txt
streamlit run app.py
```
