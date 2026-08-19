# RAO SAHAB

RAO SAHAB ek Streamlit-based smart scanner hai jo intraday aur max 2-day holding ideas ke liye design kiya gaya hai.

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
- Sector-wise results view with tabs, Strong Buy/Strong Sell always shown first, as bar charts
- **Next-Day Outlook**: daily-candle based, backtested next-day direction calls
- **Strong Direction (🧭)**: stocks whose momentum is aligned in the same direction across 1-Day, 1-Week & 1-Month timeframes
- **Streak Movers (🔥)**: stocks closing up (or down) for N consecutive days
- **AI-generated analysis**: every Strong Direction / Streak card now explains the *likely reason* behind the move (real LLM if a key is set, else a rule-based narrative) + latest news headlines (Google News)
- **Premium UI**: full-width gradient header band, premium dark-green sidebar, bold solid tab buttons, gradient-tinted cards, and a **🌙 Dark Mode toggle** in the sidebar
- **Delivery % on momentum cards**: NSE security-wise delivery shows the *genuineness* of the move — high delivery = conviction-backed, low = speculative intraday churn
- **PEAD Tool (📢)**: Post-Earnings Announcement Drift — result quality (Good/Mixed/Bad) + whether the stock is still drifting after results
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

## Next-Day Outlook (Backtested)

A second tab, "🔮 Next-Day Outlook", predicts likely next-day direction using
**daily** candles (not intraday). Unlike the main scanner's abstract score,
every call here comes with a **backtested historical hit-rate**:

1. ~1 year of daily candles are fetched per symbol.
2. 8 factors are computed: Trend (EMA alignment), ADX/+DI/-DI trend
   strength, RSI/MACD momentum, Bollinger Band position, Relative Strength
   vs Nifty 50 (5-day), Support/Resistance proximity, Gap behaviour, and
   Volume confirmation.
3. The exact same rule-set is replayed on every historical day in that
   stock's own past year, comparing the predicted direction against the
   ACTUAL next-day return - producing a real "Backtest Hit Rate %" and
   sample size, separately for bullish and bearish calls, per stock.
4. A call is only shown as high-confidence **STRONG BULLISH/BEARISH** if the
   backtested sample size and hit-rate both clear a minimum bar (15+
   occurrences and 65%+ hit-rate for HIGH, 7+ and 55%+ for MEDIUM).
   Otherwise the call is downgraded and labeled "(Low Confidence)".

**Important**: no model can reliably predict tomorrow's exact move - this is
a decision-support tool, not a guarantee. Past hit-rate doesn't guarantee
future accuracy, and it can't see tomorrow's news, results, or block deals.
Always apply your own risk management.

## Strong Direction (1D + 1W + 1M)

A dedicated tab ("🧭 Strong Direction") that lists stocks whose momentum points
the **same way** across three timeframes:

- **1 Day** = latest session move
- **1 Week** = last 5 sessions
- **1 Month** = last 21 sessions

All three green → **Strong Up**; all three red → **Strong Down**. A minimum
move per timeframe (default 0.5%) filters out noise. Built from ~1 year of
daily candles (FYERS first, Yahoo Finance as an automatic fallback).

Each card also shows **Delivery %** (NSE security-wise delivery) with a
genuineness badge — *Genuine Move* (≥60%), *Moderate Conviction* (30–60%) or
*Speculative* (<30%) — plus an **AI analysis** paragraph and the latest news
headlines.

## Streak Movers (Consecutive Closes)

A tab ("🔥 Streak Movers") that finds stocks which have closed **UP** (or
**DOWN**) for N days in a row (default 5). Persistent one-way closes flag
strong momentum — and moves that may be getting over-extended. Same delivery
% + AI analysis + news enrichment as the Strong Direction cards.

## AI Analysis (reason behind the move)

The Strong Direction and Streak Movers cards generate a short analyst-style
note explaining the likely reason behind each move, combining:

1. **Real LLM** — when an API key is present in Streamlit secrets, one batched
   call per scan explains every matched stock. Supported providers:
   - `OPENAI_API_KEY` (optional `OPENAI_MODEL`, default `gpt-4o-mini`)
   - `GEMINI_API_KEY` (optional `GEMINI_MODEL`, default `gemini-1.5-flash`)
   - `ANTHROPIC_API_KEY` (optional `ANTHROPIC_MODEL`, default `claude-3-5-haiku-latest`)
2. **Built-in fallback** — a rule-based narrative from momentum, delivery %,
   RSI and volume (always available, no key needed).
3. **News headlines** — the two latest Google News headlines for the stock
   (free RSS), each shown as its **own clickable link** to the article — the
   possible *trigger* for the move.
4. **🤖 "Full AI analysis on Gemini" button** — every card has a link that
   opens **Google AI Studio** (free Gemini, no API key, just Google sign-in)
   with a pre-filled analysis prompt for that stock. No key or extension
   needed.

The same clickable-news-links + free Gemini button are also available on the
**Delivery Combo** and **PEAD Tool** cards.

## PEAD Tool (Post-Earnings Announcement Drift)

A tab ("📢 PEAD Tool") for stocks that have **already declared results**. For
each stock it shows:

- **Result Quality** — Good / Mixed / Bad, scored from the EPS surprise vs.
  analyst estimates plus Revenue & Profit YoY growth (Yahoo Finance earnings
  calendar + quarterly financials).
- **Reaction** — the immediate price move on the announcement.
- **Drift (PEAD)** — whether the stock is still *running* in the direction of
  the result after the announcement (`Running Up (PEAD)`, `Drifting Down
  (PEAD)`, or divergence setups where price moved against the result quality).

Earnings data is fetched one symbol at a time from Yahoo Finance, so scanning
the full F&O list takes a few minutes — a symbol limit is applied by default.

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

## Logic Documentation

Har section ka **working logic** samajhne ke liye:

- **In-app**: har tab ke top par **"📖 How does this work?"** expander kholein — wahi logic short form mein.
- **Full doc**: [`LOGIC.md`](LOGIC.md) — saare sections (scoring engine, Intraday, Next-Day, Sector,
  Gold & Silver, Accuracy, Delivery Combo, Strong Direction, Streak Movers, PEAD, AI analysis) ka
  step-by-step logic, scoring thresholds, aur data sources.
