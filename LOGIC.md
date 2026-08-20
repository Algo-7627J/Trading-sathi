# RAO SAHAB — Logic Behind Every Section

Ye document app ke **har section ka working logic** plain language mein samjhata hai.
Yahi content app ke andar bhi har tab par **"📖 How does this work?"** expander mein milta hai.

---

## 1. Shared: The Scoring Engine (`analysis.py`)

Sab sections ka dil ek hi **confluence scoring engine** hai — `score_dataframe()` —
jo kisi bhi OHLCV candle series ko **-17 se +17** ka score deta hai. 5 components:

| # | Component | Max pts | Kya check hota hai |
|---|---|---|---|
| 1 | EMA trend | ±6 | Price vs EMA21, EMA9 vs EMA21, EMA21 vs EMA50, EMA21 slope — 4 checks × ±1.5 |
| 2 | MACD | ±3 | Histogram zero se upar/neeche (±1.5) + histogram badh raha/ghat raha (±1.5) |
| 3 | RSI (14) | ±3 | >70 strong (+1), >55 rising (+2), 45–55 flat (0), 30–45 weak (−2), <30 oversold-bounce (+0.5) |
| 4 | Volume | ±2 | Last candle vs 21-period avg: ≥1.5× = ±2, ≥1.2× = ±1 (sign = candle ki direction) |
| 5 | Pattern | ±3 | 16 candlestick patterns (flag, triangle, H&S, engulfing, etc.) × ~3.75 |

**Score → Signal mapping:**
`> +6` **Strong Buy** · `> +2` **Buy** · `−2…+2` **Neutral** · `< −2` **Sell** · `< −6` **Strong Sell**

**Noise filter:** ~0.08% se chhota move score 0 deta hai — chhoti harkatein signal nahi palat-ti.

---

## 2. ⚡ Intraday Scanner (Tab 1)

1. Universe (NSE F&O live / hardcoded fallback + indices + commodities + watchlist) ke har symbol ki
   OHLCV candles fetch (FYERS), chosen timeframe par (1m/5m/15m/1h/1d/1w/1M).
2. Har symbol par scoring engine chalao → score + signal.
3. Optional: News sentiment + Fundamentals (Screener.in) score mein add.
4. Result 🟢 Bullish / 🔴 Bearish / ⚪ Neutral mein split; top 6 "Most Bullish/Bearish" cards.

---

## 3. 📅 Next-Day Outlook (Tab 2)

Intraday jaisa, par **daily candles** par:

1. Daily candles → same scorer → score.
2. **Outlook**: `≥+8` Strong Bullish · `≥+3` Bullish · `≤−8` Strong Bearish · `≤−3` Bearish · else Neutral.
3. **Confidence** = 60–92% (score ki magnitude se); Neutral = 45–60%.
4. **Expected move** = ATR ÷ price (kal ka realistic ±range).
5. **Key levels** = 10-day low (support) / high (resistance).
6. **Last-30min flow**: last 6 × 5-min candles ka up-volume ratio — ≥62% heavy buying, ≤38% heavy selling;
   intensity vs din ki avg 30-min volume (≥1.5× = heavy).
7. **FII/DII banner** (NSE official): dono buying = strongly bullish · FII sell + DII buy = "absorbing"
   (mixed/resilient) · dono selling = bearish.

> Har run Accuracy Tracker (Tab 5) mein auto-log hota hai.

---

## 4. 🏭 Sector Trend (Tab 3)

1. Latest Intraday scan ke stocks ko sector tag karo.
2. Per sector: **Bullish %** (Buy/Strong Buy ka hissa), **Bearish %**, avg score.
3. **Timeframe selector weights** se bias shift — ⚠️ ye hissa *simulated* hai (stable seeded adjustment:
   1D ×1.0, 1W ×1.15, 2W ×0.92, 1M ×1.25), fresh historical re-scan nahi.
4. Sector par click → uske top 10 bullish/bearish stocks (score se ranked).

> Pehle Tab 1 ka scan chalana zaroori hai, warna data hi nahi hoga.

---

## 5. 🥇 Gold & Silver (Tab 4)

Data: Yahoo Finance COMEX futures (`GC=F`, `SI=F`).

1. 15m, daily, weekly, monthly, yearly candles fetch karo.
2. Har timeframe par **same scorer** chalao.
3. **Weighted consensus** (lambi timeframe = zyada weight): 15m ×0.15, daily ×0.20, weekly ×0.20,
   monthly ×0.20, yearly ×0.25 → ek -17…+17 score.
4. **20-day breakout**: close > 20D high = upside breakout, < 20D low = downside breakdown;
   volume ≥1.3× avg = *Confirmed*, warna *Low-Volume*.
5. Output: per-timeframe arrows, consensus meter, breakout, ATR-based expected move + support/resistance.
6. **🤖 AI analysis** (har panel ke neeche): rule-based analyst note (ya LLM, agar secret key hai) jo
   consensus, breakout state, RSI, ATR aur support/resistance se move ki *likely reason* likhta hai +
   **fresh news headlines (≤7 din)** possible trigger ke roop mein + free Gemini deep-link.

> Strongest setup = sab 5 arrows same direction **aur** volume-confirmed breakout.

---

## 6. 🎯 Accuracy Report (Tab 5)

1. Har Next-Day run `data/predictions.csv` mein save hota hai.
2. Refresh par: prediction date ka close (base) + **agle trading din** ka close → actual move %.
3. **Verdict** (sideways band = ±0.30%):

| Bias | Correct | Wrong | Sideways |
|---|---|---|---|
| Bullish | move > +0.30% | move < −0.30% | beech mein |
| Bearish | move < −0.30% | move > +0.30% | beech mein |
| Neutral | \|move\| ≤ 0.30% | \|move\| > 0.30% | — |

4. **Accuracy** = Correct ÷ (Correct + Wrong). Pending (agle din abhi close nahi hua) skip.

---

## 7. 📦 Delivery Combo (Tab 6)

**Delivery % = (Deliverable Qty ÷ Total Traded Qty) × 100** — NSE MTO archive (market close ke baad publish).

- High % = log delivery le rahe (real conviction); Low % = intraday churn.

Steps:
1. Latest delivery file fetch (10 din tak walk-back, cached).
2. Chosen scan (Intraday/Next-Day) se symbol se merge.
3. **Direction**: Bias → Signal → Score sign.
4. Filter `DeliveryPct ≥ min%`, delivery % se sort desc (sabse zyada conviction pehle), Top N.
5. **Genuineness badge**: ≥60% Genuine · 30–60% Moderate · <30% Speculative.
6. **Live check**: aaj ka move vs prev close — Bullish combo aaj up hona chahiye (✓), Bearish down (✓).

> High delivery akela bullish NAHI hai — direction scan signal se aata hai.

---

## 8. 🧭 Strong Direction (Tab 7)

1. ~1 saal ki daily candles (FYERS → Yahoo fallback).
2. **1D** = last session, **1W** = 5 sessions, **1M** = 21 sessions ka % move.
3. Direction sirf tab count hoti hai jab move > ±0.2% (noise filter).
4. **Strong Up** = teeno positive **aur** har ek ≥ min-move (default 0.5%); **Strong Down** = teeno negative.
   Mixed = excluded.
5. Context: **Delivery %** (genuineness), **RSI**, **volume ratio** → AI analysis ke inputs.
6. **AI analysis** + news + Gemini link (neeche section 11 dekho).

---

## 9. 🔥 Streak Movers (Tab 8)

1. Daily candles → har close ka direction (up/down/flat).
2. Current consecutive run count karo; streak ≥ min (default 5) = qualify.
3. **Streak move %** = streak shuru hone se pehle ke close → latest close.
4. Same context + AI analysis + news.

> Lambi streak = strong momentum, par exhaustion ka signal bhi (e.g. 10-day up streak + RSI >75 =
> overbought, pause possible).

---

## 10. 📢 PEAD Tool (Tab 9)

Post-Earnings Announcement Drift — un stocks ke liye jinhone **results declare kar diye**:

1. Yahoo se: latest **reported** earnings date, EPS estimate vs actual + surprise %, Revenue/Profit YoY.
2. **Result Quality** (points): EPS surprise ≥+5% → +2, 0…5% → +1, −5…0% → −1, ≤−5% → −2;
   Revenue YoY >0 → +1; Profit YoY >0 → +1.
   → **Good** (≥2 pts + positive surprise) · **Bad** (≤−2) · **Mixed**.
3. **Reaction %** = results ke baad pehla close vs previous close.
4. **Drift %** = latest close vs wo pehla post-result close.
5. **PEAD label** (drift threshold ±0.5%):
   - Good + rising drift → 🚀 **Running Up (PEAD)**
   - Bad + falling drift → 🔻 **Drifting Down (PEAD)**
   - Good + falling (ya Bad + rising) → ⚠️ divergence
   - else → ➖ No clear drift

> Yahoo mein earnings date na ho toh symbol skip. PEAD sirf *already-reported* stocks ke liye hai.

---

## 11. 🤖 AI Analysis + News (Tabs 7, 8, 9 cards)

1. **News** — Google News RSS se har stock ki 2–3 headlines (parallel fetch, 30-min cache) → clickable links.
2. **Narrative** — LLM key ho (OpenAI/Gemini/Anthropic secrets mein) toh ek batched call per scan sab stocks
   ka reason likhta hai; warna **rule-based engine** stock ke apne numbers (momentum, delivery %, RSI, volume)
   se analysis banata hai — bina key ke bhi hamesha kaam karta hai.
3. **Gemini button** — har card Google AI Studio kholta hai pre-filled prompt ke saath
   (free Gemini, Google sign-in, koi API key/extension nahi).

---

## 12. 💬 Social Buzz (Tab 10 + cards on Tabs 7, 8)

**Sources (sab free, koi API key nahi chahiye):**
1. **Reddit** — Indian trading subreddits (r/IndianStreetBets, r/IndiaInvestments, r/StockMarketIndia,
   r/DalalStreetTalks, …) mein symbol ki recent posts/comments.
2. **Google News "social"** — headlines jahan stock twitter/social media par discuss ho raha tha
   ("viral", "trending", "twitter"). Tweets jo news ban gaye unhe pakad leta hai.
3. **X (Twitter) v2 API** — real tweets, sirf tab chalti hai jab `X_BEARER_TOKEN` Streamlit secrets
   mein ho (optional upgrade; upar wale do sources bina kisi key ke chalte hain).

**⏱️ 7-day window** — sirf **last 7 days** ka content dikhta hai: Reddit search `t=week` use karta hai,
Google News `when:7d`, aur har item par ek final age-filter lagta hai. Ek hafte se purani news/tweets
drop ho jaati hain — purani "news" aaj ke move ka trigger nahi hoti.

**🎯 Ticker disambiguation** — chhote/ambiguous tickers ke liye company ke **asli naam** se search:
`ACC → "ACC Ltd"` (cement company, US football conference nahi!), `SAIL → "Steel Authority of India"`,
`IOC → "Indian Oil"` (Olympics nahi), `YES → "Yes Bank"`, `TITAN → "Titan Company"` (anime nahi),
`M&M → "Mahindra & Mahindra"`, `HAL → "Hindustan Aeronautics"`, … + har query mein stock-context
words (share/stock/NSE/BSE) + ek **relevance filter** jo bina business-context wali news
(football, sailing, Olympics) ko drop kar deta hai. ~45 tickers map hain, baaki universe ke liye
default stock-context query chalti hai.

**Sentiment** — simple bullish/bearish lexicon (buy/breakout/rally vs sell/crash/downgrade + Hinglish
market slang) har post/headline par tone chip lagata hai. Tab 🟢/🔴/⚪ tallies dikhata hai.

**Cards par** — Strong Direction & Streak cards par compact **💬 SOCIAL BUZZ** strip (top 2 items +
bullish/bearish tally) — move ka *possible trigger*. Sirf top 8 symbols ke liye fetch hota hai
(capped, 10-min cache) taaki scan fast rahe. Sidebar se on/off.

**Golden rule:** buzz **sirf informational** hai — score/signal kabhi nahi badalta. Aur har source
best-effort hai: Reddit kuch cloud IPs block karta hai, toh app "source unreachable" bata deta hai
bajaye chupchaap khaali dikhane ke.

---

## 13. Data Sources & Fallbacks

| Data | Source | Fallback |
|---|---|---|
| Intraday/daily candles | FYERS API | Yahoo Finance (daily) |
| F&O universe | NSE live API | ~180 hardcoded symbols |
| Delivery % | NSE MTO archive | cached CSV |
| FII/DII | NSE API | — |
| Fundamentals/results | Screener.in | — (N/A) |
| Earnings dates/estimates | Yahoo Finance | — (skip) |
| News headlines | Google News RSS | — |
| Social buzz | Reddit JSON + Google News RSS | X API (agar key ho) |
| Gold/Silver | Yahoo Finance (COMEX) | SIMULATED badge |

**Golden rule:** jab koi source fail ho, sections ya toh agla source try karte hain, ya result ko
**SIMULATED** mark karte hain — kabhi bhi fake numbers ko real nahi dikhaya jaata.
