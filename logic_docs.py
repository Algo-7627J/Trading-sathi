# logic_docs.py — "how does this scan work?" explainers for every tab
# ------------------------------------------------------------------
# Central place for the plain-language logic behind each section.
# Rendered as an expander on each tab (render_logic_expander) and also
# mirrored in LOGIC.md for offline reading.
# ------------------------------------------------------------------
import streamlit as st


def render_logic_expander(title="📖 How does this section work?", body="", expanded=False):
    if not body:
        return
    with st.expander(title, expanded=expanded):
        st.markdown(body)


# ====================== SHARED ======================
UNIVERSE_LOGIC = """**Universe** (sidebar → live NSE F&O): the app tries to fetch the current F&O stock list from NSE
(15-min cache). If that fails, it falls back to a hardcoded list of ~180 F&O stocks, plus indices
(NIFTY50, BANKNIFTY, FINNIFTY, MIDCPNIFTY, SENSEX) and commodities (GOLD, SILVER, CRUDEOIL, NATURALGAS, COPPER).

**Data sources:** FYERS API for candles (real data when you're logged in), Yahoo Finance as an automatic
fallback for daily candles, NSE archives for delivery %, Screener.in for fundamentals, Google News RSS for
headlines. When a source is unreachable, sections either fall back to the next source or clearly mark
results as *SIMULATED* — nothing silently fakes real numbers."""

SCORER_LOGIC = """**The shared scoring engine (`score_dataframe`)** produces a confluence score from **-17 to +17** by adding
five components (same engine powers the Intraday Scanner, Next-Day Outlook, and Gold & Silver):

| Component | Max points | Logic |
|---|---|---|
| 1. EMA trend structure | ±6 | price vs EMA21, EMA9 vs EMA21, EMA21 vs EMA50, and EMA21 slope — 4 checks × ±1.5 |
| 2. MACD momentum | ±3 | histogram above/below zero (±1.5) + histogram rising/falling (±1.5) |
| 3. RSI | ±3 | graded: >70 strong (+1), >55 rising (+2), 45–55 flat (0), 30–45 weak (−2), <30 oversold bounce (+0.5) |
| 4. Volume | ±2 | last candle volume vs 21-period avg: ≥1.5× = ±2, ≥1.2× = ±1, sign by candle direction |
| 5. Chart pattern | ±3 | 16 candlestick patterns (flags, triangles, H&S, engulfing, etc.) |

**Score → Signal:**  `> +6` Strong Buy · `> +2` Buy · `−2…+2` Neutral · `< −2` Sell · `< −6` Strong Sell.
Moves smaller than ~0.08% are treated as noise (they score 0), so tiny wiggles don't flip the signal."""

# ====================== TAB 1 — INTRADAY ======================
LOGIC_INTRADAY = """**What it does:** scans every symbol in the selected universe at one timeframe (1m/5m/15m/1h/1d/1w/1M)
and ranks them by the confluence score (-17…+17).

**Step-by-step:**
1. Fetch OHLCV candles for each symbol at the chosen timeframe (FYERS).
2. Run the 5-part scoring engine (see below) → score + Signal (Strong Buy…Strong Sell).
3. Optional: add News sentiment & Fundamentals (Screener.in) to the score.
4. Sort & split into 🟢 Bullish / 🔴 Bearish / ⚪ Neutral; "Most Bullish / Most Bearish" shows the top 6 each.

**How to read the score meter on each card:** the bar grows left (red) for negative scores and right (green)
for positive scores, anchored at 0 — a full bar to either side = extreme confluence (17 points).

""" + SCORER_LOGIC

# ====================== TAB 2 — NEXT-DAY ======================
LOGIC_NEXT_DAY = """**What it does:** predicts each stock's *next-day* direction using DAILY candles (not intraday).

**Step-by-step:**
1. Fetch ~1 year of daily candles and run the same 5-part confluence scorer.
2. Map score → Outlook: `≥ +8` Strong Bullish · `≥ +3` Bullish · `≤ −8` Strong Bearish · `≤ −3` Bearish · else Neutral.
3. **Confidence** = 60–92% scaled by how large the score is (Neutral calls are capped at 45–60%).
4. **Expected move** = ATR ÷ price (a realistic ±range for tomorrow).
5. **Key levels** = recent 10-day low (support) & high (resistance).
6. **Last-30min flow:** takes the last 6 × 5-min candles → % of volume in up-candles. ≥62% = heavy buying,
   ≤38% = heavy selling; compared to the day's average 30-min volume (≥1.5× = "heavy").
7. **FII/DII banner:** official NSE institutional flow — both buying = strongly bullish, FII selling + DII buying
   = "DII absorbing" (mixed/resilient), both selling = bearish pressure.

Every run is auto-logged to the Accuracy Tracker (Tab 5) so you can see how good the calls actually are.

""" + SCORER_LOGIC

# ====================== TAB 3 — SECTOR ======================
LOGIC_SECTOR = """**What it does:** groups the latest Intraday scan (Tab 1) by sector and shows which sectors are
bullish/bearish.

**Step-by-step:**
1. Take the latest scan result and tag each stock with its sector.
2. Per sector: **Bullish %** = share of stocks with Buy/Strong Buy signals, **Bearish %** = Sell/Strong Sell,
   plus the average score.
3. **Timeframe selector applies weights** that shift the bias — note this part is *simulated* (a stable,
   seeded adjustment per timeframe: 1D ×1.0, 1W ×1.15, 2W ×0.92, 1M ×1.25), not a fresh historical re-scan.
4. Click a sector → top 10 bullish/bearish stocks inside it, ranked by score.

> ⚠️ Run the Intraday Scan first, otherwise this tab has no data to group."""

# ====================== TAB 4 — GOLD & SILVER ======================
LOGIC_METALS = """**What it does:** multi-timeframe forecast for Gold & Silver COMEX futures (GC=F, SI=F via Yahoo Finance).

**Step-by-step:**
1. Fetch 15m, daily, weekly, monthly and yearly candles.
2. Run the same 5-part confluence scorer on **each** timeframe.
3. **Weighted consensus** (longer timeframes weigh more): 15m ×0.15, daily ×0.20, weekly ×0.20,
   monthly ×0.20, yearly ×0.25 → a single score from -17 to +17.
4. **20-day breakout check:** close above the prior 20-day high = upside breakout, below the 20-day low =
   downside breakdown; volume ≥1.3× of its average = *Confirmed*, otherwise *Low-Volume*.
5. Output: per-timeframe arrows, consensus meter, breakout state, and an ATR-based expected move with
   support/resistance.

**How to read it:** strongest setups = all 5 arrows pointing the same way **and** a volume-confirmed breakout.
If Yahoo is unreachable, the panel is clearly marked *SIMULATED*.

**🤖 AI analysis (under each panel):** a rule-based analyst note (LLM if a key is set in secrets) explains
the *likely reason* behind gold/silver's move — using the consensus score, breakout state, RSI, ATR and
support/resistance — plus **fresh news headlines (≤7 days)** as the possible trigger, and a free Gemini
deep-link for a fuller read."""

# ====================== TAB 5 — ACCURACY ======================
LOGIC_ACCURACY = """**What it does:** scores every logged Next-Day prediction against what actually happened.

**Step-by-step:**
1. Every Next-Day run (Tab 2) saves each call to `data/predictions.csv`.
2. On refresh, the app fetches daily candles and finds the close on the prediction date (base) and the
   **next trading day's** close → actual move %.
3. **Verdict** (sideways band = ±0.30%):

| Bias | Correct | Wrong | Sideways |
|---|---|---|---|
| Bullish | move > +0.30% | move < −0.30% | in between |
| Bearish | move < −0.30% | move > +0.30% | in between |
| Neutral | |move| ≤ 0.30% | |move| > 0.30% | — |

4. **Accuracy** = Correct ÷ (Correct + Wrong) — sideways calls are reported separately, pending calls
   (next day hasn't closed yet) are skipped.

> 💡 This is your honest feedback loop: if accuracy stays low, the score thresholds may need tuning."""

# ====================== TAB 6 — DELIVERY COMBO ======================
LOGIC_DELIVERY = """**What it does:** combines a scan signal with **delivery %** to judge conviction.

**Delivery % = (shares actually delivered ÷ total shares traded) × 100**, from NSE's official MTO archive
(published after market close). High % = people are *taking delivery* (real conviction); low % = mostly
intraday churn.

**Step-by-step:**
1. Fetch the latest security-wise delivery file (walks back up to 10 days; cached).
2. Merge with the chosen scan (Intraday or Next-Day) by symbol.
3. Direction: from Bias (next-day) → Signal (intraday) → Score sign.
4. Filter `DeliveryPct ≥ min delivery %`, sort by delivery % (highest conviction first), take Top N.
5. Genuineness badge: **≥60% Genuine Move · 30–60% Moderate Conviction · <30% Speculative**.
6. **Live check:** today's move vs previous close — a 🟢 Bullish+delivery stock should be rising today,
   a 🔴 Bearish one falling; ✓/✗ shows who's on track.

**Interpretation:** 🟢 High delivery + Bullish = conviction accumulation · 🔴 High delivery + Bearish =
conviction distribution. High delivery alone is *not* bullish — direction comes from the scan signal."""

# ====================== TAB 7 — STRONG DIRECTION ======================
LOGIC_STRONG_DIRECTION = """**What it does:** finds stocks whose momentum is aligned in the **same direction** across three
timeframes — a clean, high-conviction directional bias.

**Step-by-step:**
1. Fetch ~1 year of daily candles per stock (FYERS → Yahoo Finance fallback).
2. Compute % moves: **1D** = last session, **1W** = last 5 sessions, **1M** = last 21 sessions.
3. A direction counts only if the move exceeds ±0.2% (noise filter).
4. **Strong Up** = all three positive **and** each ≥ your min-move setting (default 0.5%);
   **Strong Down** = all three negative. Anything mixed is excluded.
5. Context added per stock: **Delivery %** (genuineness), **RSI** (overbought/oversold), **volume ratio**
   (participation) — these feed the AI analysis.
6. **AI analysis:** a rule-based narrative (or a real LLM if a key is set in secrets) + the latest news
   headlines, plus a "Full AI analysis on Gemini" button that opens Google AI Studio with a pre-filled
   prompt (free, no key)."""

# ====================== TAB 8 — STREAK MOVERS ======================
LOGIC_STREAK = """**What it does:** finds stocks that have closed **up (or down) for N days in a row** — persistent
one-way momentum.

**Step-by-step:**
1. Fetch daily candles and compute the direction of every close vs the previous close
   (up = close rose, down = close fell, flat resets the streak).
2. Count the current consecutive run; a stock qualifies if its streak ≥ your minimum (default 5).
3. **Streak move %** = total change from the close before the streak started to the latest close.
4. Same context + AI analysis + news as Strong Direction (delivery %, RSI, volume ratio).

**Why it matters:** long streaks flag strong momentum — but also exhaustion. A 10-day down streak with
low volume and high delivery can mean patient accumulation, while a 10-day up streak with RSI > 75 can
mean an overbought setup due for a pause."""

# ====================== TAB 9 — PEAD ======================
LOGIC_PEAD = """**What it does:** for stocks that have **already declared results**, it scores the result quality and
checks whether the stock is still *drifting* after the announcement (Post-Earnings Announcement Drift).

**Step-by-step:**
1. From Yahoo Finance: the most recent **reported** earnings date, EPS estimate vs actual, and the
   surprise %, plus quarterly Revenue & Net-Income YoY growth.
2. **Result Quality** (points): EPS surprise ≥+5% → +2, 0…5% → +1, −5…0% → −1, ≤−5% → −2;
   Revenue YoY > 0 → +1; Profit YoY > 0 → +1.
   → **Good** (≥2 pts & positive surprise) · **Bad** (≤−2) · **Mixed** (in between).
3. **Reaction %** = first close after results vs the previous close (the immediate market verdict).
4. **Drift %** = latest close vs that first post-result close — is the stock still moving *after* the news?
5. **PEAD label** (drift threshold ±0.5%):
   - Good result + rising drift → **🚀 Running Up (PEAD)**
   - Bad result + falling drift → **🔻 Drifting Down (PEAD)**
   - Good result + falling (or bad + rising) → ⚠️ divergence warning
   - otherwise → ➖ No clear drift
6. Each card shows the quality detail, reaction/drift, clickable news headlines, and the free Gemini AI
   deep-link.

> ℹ️ Symbols without earnings dates in Yahoo are skipped. PEAD only covers stocks that *already* reported —
> use the fundamentals toggle in Tab 1 for pre-result quality checks."""

# ====================== AI ANALYSIS (shared) ======================
LOGIC_AI = """**How the "AI analysis" on the cards works:**
1. **News** — up to 3 latest headlines per stock from Google News RSS (free, fetched in parallel, cached
   30 min). These are shown as clickable links and used as the *possible trigger*.
2. **Narrative** — if an LLM key is set in secrets (OpenAI / Gemini / Anthropic), one batched call per scan
   writes a 2-sentence reason for every stock. Otherwise a **rule-based engine** writes it from the stock's
   own numbers (momentum, delivery %, RSI, volume) — always available, no key needed.
3. **Gemini button** — every card links to Google AI Studio with a pre-filled analysis prompt for that stock
   (free Gemini, Google sign-in, no API key or extension).
4. **Gold & Silver** — the same engine works for metals: one batched LLM call (or the rule-based note)
   explains the likely driver of gold/silver's move, with fresh ≤7-day commodity news as the trigger."""

# ====================== SOCIAL BUZZ ======================
LOGIC_SOCIAL = """**How the 💬 Social Buzz works:**
1. **Sources** (all free, no API key):
   - **Reddit** — posts/comments mentioning the symbol across Indian trading subreddits
     (r/IndianStreetBets, r/IndiaInvestments, r/StockMarketIndia, r/DalalStreetTalks, …).
   - **Google News "social"** — headlines where the stock was being discussed on twitter/social media
     ("viral", "trending"…). Catches tweets that made the news.
   - **X (Twitter) v2 API** — real recent tweets, used automatically *only if* `X_BEARER_TOKEN` is set
     in Streamlit secrets (optional upgrade; the free sources above need nothing).
2. **⏱️ 7-day window** — sirf **last 7 days** ka content dikhaya jaata hai (Reddit `t=week`,
   Google News `when:7d`, aur har item par ek final age-filter). Purani khabar/old tweets nahi —
   kyunki ek hafte purani "news" aaj ke move ka trigger nahi ho sakti.
3. **🎯 Ticker disambiguation** — chhote/ambiguous tickers (ACC, SAIL, IOC, YES, TITAN, M&M…) ke
   liye company ke **asli naam** se search hota hai ("ACC Ltd", "Steel Authority of India",
   "Indian Oil", "Yes Bank"…) + har query mein stock-context words (share/stock/NSE/BSE) + ek
   **relevance filter** jo non-business news (football conference, sailing, Olympics) ko drop
   kar deta hai. ACC = cement company, football team nahi. 😄
4. **Sentiment** — each post/headline is scored with a simple bullish/bearish lexicon; the tab shows
   🟢 Bullish / 🔴 Bearish / ⚪ Neutral tallies and a per-item tone chip.
5. **On cards** — Strong Direction & Streak cards show a compact **💬 SOCIAL BUZZ** strip (top 2 items +
   bullish/bearish tally) as *possible triggers* for the move. It is fetched for the top symbols only
   (capped, cached 10 min) so scans stay fast. Toggle it from the sidebar.
6. **Dedicated tab** — the **💬 Social Buzz** tab lets you search any symbol on demand, shows every item
   with score/comments/age, and downloads the list as CSV.
7. **Best-effort by design** — some sources block cloud IPs (e.g. Reddit). The app reports "source
   unreachable" instead of silently showing nothing, and everything else keeps working.

> ℹ️ Buzz is **informational only** — it never changes the scan score or signal."""

# ====================== MASTER DICT ======================
LOGIC = {
    "intraday": LOGIC_INTRADAY,
    "next_day": LOGIC_NEXT_DAY,
    "sector": LOGIC_SECTOR,
    "metals": LOGIC_METALS,
    "accuracy": LOGIC_ACCURACY,
    "delivery": LOGIC_DELIVERY,
    "strong_direction": LOGIC_STRONG_DIRECTION,
    "streak": LOGIC_STREAK,
    "pead": LOGIC_PEAD,
    "social": LOGIC_SOCIAL,
    "ai": LOGIC_AI,
    "universe": UNIVERSE_LOGIC,
    "scorer": SCORER_LOGIC,
}
