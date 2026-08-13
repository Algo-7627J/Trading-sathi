# accuracy.py — RAO SAHAB prediction-vs-reality tracker
# ------------------------------------------------------------------
# Every "Next-Day Outlook" run is logged to data/predictions.csv.
# On demand, this module fetches the actual next trading day's close
# for each logged prediction and scores it Correct / Wrong / Sideways
# / Pending, then caches results to data/accuracy_results.csv.
#
# Scoring rule (direction-only, matches the app's Bias signal):
#   Bullish  -> Correct if next-day move >  +MOVE_THRESHOLD %
#               Wrong   if next-day move <  -MOVE_THRESHOLD %
#   Bearish  -> Correct if next-day move <  -MOVE_THRESHOLD %
#               Wrong   if next-day move >  +MOVE_THRESHOLD %
#   Neutral  -> Correct if |move| <= MOVE_THRESHOLD %, else Wrong
# ------------------------------------------------------------------
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from storage import DATA_DIR
from analysis import to_fyers_symbol

PREDICTIONS_FILE = DATA_DIR / "predictions.csv"
RESULTS_FILE = DATA_DIR / "accuracy_results.csv"

# A move within +/- this % is treated as "flat" (sideways).
MOVE_THRESHOLD = 0.30

IST = timezone(timedelta(hours=5, minutes=30))

PRED_COLUMNS = [
    "Prediction_Date", "Symbol", "LTP", "Bias", "Outlook",
    "Confidence", "Expected_Move", "Key_Levels", "Last30Min",
]
RESULT_COLUMNS = [
    "Prediction_Date", "Symbol", "Bias", "Base_Close",
    "Next_Date", "Next_Close", "Actual_Move_Pct", "Verdict",
]

CORRECT, WRONG, SIDEWAYS, PENDING = "Correct", "Wrong", "Sideways", "Pending"


# ------------------------------------------------------------------
# Predictions storage
# ------------------------------------------------------------------
def ensure_files():
    DATA_DIR.mkdir(exist_ok=True)
    if not PREDICTIONS_FILE.exists():
        pd.DataFrame(columns=PRED_COLUMNS).to_csv(PREDICTIONS_FILE, index=False)
    if not RESULTS_FILE.exists():
        pd.DataFrame(columns=RESULT_COLUMNS).to_csv(RESULTS_FILE, index=False)


def save_predictions(df: pd.DataFrame, pred_date=None):
    """
    Log a next-day scan result. One row per symbol per date; re-running
    on the same day overwrites that day's row for each symbol.
    """
    ensure_files()
    if df is None or df.empty:
        return

    if pred_date is None:
        pred_date = datetime.now(IST).date()
    pred_date = str(pred_date)

    keep = ["Symbol", "LTP", "Bias", "Outlook", "Confidence",
            "Expected_Move", "Key_Levels", "Last30Min"]
    cols = [c for c in keep if c in df.columns]
    if not cols:
        return

    new_rows = df[cols].copy()
    new_rows.insert(0, "Prediction_Date", pred_date)

    try:
        old = pd.read_csv(PREDICTIONS_FILE)
    except Exception:
        old = pd.DataFrame(columns=PRED_COLUMNS)

    # Drop any existing rows for this date so re-runs don't duplicate.
    if not old.empty and "Prediction_Date" in old.columns:
        old = old[old["Prediction_Date"].astype(str) != pred_date]

    if old.empty:
        merged = new_rows
    else:
        merged = pd.concat([old, new_rows], ignore_index=True)
    merged = merged[[c for c in PRED_COLUMNS if c in merged.columns]]
    merged.to_csv(PREDICTIONS_FILE, index=False)


def load_predictions() -> pd.DataFrame:
    ensure_files()
    try:
        return pd.read_csv(PREDICTIONS_FILE)
    except Exception:
        return pd.DataFrame(columns=PRED_COLUMNS)


def load_results() -> dict:
    """Return cached results keyed by (Prediction_Date, Symbol)."""
    ensure_files()
    out = {}
    try:
        df = pd.read_csv(RESULTS_FILE)
        for _, r in df.iterrows():
            out[(str(r["Prediction_Date"]), str(r["Symbol"]))] = r.to_dict()
    except Exception:
        pass
    return out


def save_results(df: pd.DataFrame):
    ensure_files()
    try:
        df[[c for c in RESULT_COLUMNS if c in df.columns]].to_csv(
            RESULTS_FILE, index=False)
    except Exception:
        pass


# ------------------------------------------------------------------
# Actual-move computation (daily candles, timestamps preserved)
# ------------------------------------------------------------------
def _ts_to_date(ts):
    try:
        ts = float(ts)
        if ts > 1e12:                      # milliseconds -> seconds
            ts /= 1000.0
        return datetime.fromtimestamp(ts, tz=IST).date()
    except Exception:
        return None


def fetch_daily_history(fyers, symbol, days=120):
    """
    Fetch daily OHLCV candles keeping the timestamp -> date mapping.
    Returns DataFrame[date, o, h, l, c, v] or None.
    """
    if fyers is None:
        return None
    fsym = to_fyers_symbol(symbol)
    if not fsym:
        return None

    to_date = datetime.now(IST).date()
    from_date = to_date - timedelta(days=days)

    payload = {
        "symbol": fsym,
        "resolution": "D",
        "date_format": "1",
        "range_from": from_date.strftime("%Y-%m-%d"),
        "range_to": to_date.strftime("%Y-%m-%d"),
        "cont_flag": "1",
    }
    try:
        resp = fyers.history(data=payload)
    except Exception:
        return None

    if not isinstance(resp, dict) or resp.get("s") != "ok":
        return None

    candles = resp.get("candles") or []
    if not candles:
        return None

    rows = []
    for c in candles:
        d = _ts_to_date(c[0])
        if d is None:
            continue
        rows.append({
            "date": d,
            "o": float(c[1]), "h": float(c[2]), "l": float(c[3]),
            "c": float(c[4]), "v": float(c[5]) if len(c) > 5 else 0.0,
        })

    if not rows:
        return None
    df = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)
    return df


def _actual_move(candles, pred_date):
    """
    Given daily candles and a prediction date, compute the actual next-day
    move. Returns (pct, base_close, next_date, next_close). pct is None if
    the next trading day hasn't happened yet (pending).
    """
    if candles is None or candles.empty:
        return None, None, None, None

    try:
        pd_date = pd.Timestamp(pred_date).date()
    except Exception:
        return None, None, None, None

    dates = candles["date"]
    base = candles[dates <= pd_date]
    if base.empty:
        return None, None, None, None
    base_close = float(base.iloc[-1]["c"])

    nxt = candles[dates > pd_date]
    if nxt.empty:
        return None, base_close, None, None

    next_date = nxt.iloc[0]["date"]
    next_close = float(nxt.iloc[0]["c"])
    pct = (next_close - base_close) / base_close * 100.0 if base_close else None
    return pct, base_close, next_date, next_close


def verdict_for(bias, pct):
    if pct is None:
        return PENDING
    b = str(bias).strip().lower()
    if b == "bullish":
        if pct > MOVE_THRESHOLD:
            return CORRECT
        if pct < -MOVE_THRESHOLD:
            return WRONG
        return SIDEWAYS
    if b == "bearish":
        if pct < -MOVE_THRESHOLD:
            return CORRECT
        if pct > MOVE_THRESHOLD:
            return WRONG
        return SIDEWAYS
    # neutral
    if abs(pct) <= MOVE_THRESHOLD:
        return CORRECT
    return WRONG


# ------------------------------------------------------------------
# Scoring + summary
# ------------------------------------------------------------------
def score_predictions(fyers, progress=None):
    """
    Compute verdicts for all logged predictions. Cached per
    (date, symbol); only 'Pending' / missing rows are (re)fetched.
    """
    ensure_files()
    preds = load_predictions()
    cached = load_results()

    rows = []
    symbol_cache = {}

    total = len(preds)
    for i, (_, p) in enumerate(preds.iterrows()):
        p_date = str(p["Prediction_Date"])
        symbol = str(p["Symbol"])
        key = (p_date, symbol)

        c = cached.get(key)
        if c is not None and c.get("Verdict") != PENDING:
            rows.append(c)
            continue

        if symbol not in symbol_cache:
            symbol_cache[symbol] = fetch_daily_history(fyers, symbol)
        candles = symbol_cache[symbol]

        pct, base_close, next_date, next_close = _actual_move(candles, p_date)
        verdict = verdict_for(p.get("Bias"), pct)

        rows.append({
            "Prediction_Date": p_date,
            "Symbol": symbol,
            "Bias": p.get("Bias"),
            "Base_Close": round(base_close, 2) if base_close is not None else None,
            "Next_Date": str(next_date) if next_date else None,
            "Next_Close": round(next_close, 2) if next_close is not None else None,
            "Actual_Move_Pct": round(pct, 3) if pct is not None else None,
            "Verdict": verdict,
        })

        if progress and (i + 1) % 25 == 0:
            progress.progress((i + 1) / total, text=f"Checking {symbol}…")

    result_df = pd.DataFrame(rows)
    if not result_df.empty:
        save_results(result_df)
    return result_df


def accuracy_summary(df: pd.DataFrame) -> dict:
    if df is None or df.empty:
        return {
            "total": 0, "correct": 0, "wrong": 0, "sideways": 0,
            "pending": 0, "accuracy": None,
        }
    correct = int((df["Verdict"] == CORRECT).sum())
    wrong = int((df["Verdict"] == WRONG).sum())
    sideways = int((df["Verdict"] == SIDEWAYS).sum())
    pending = int((df["Verdict"] == PENDING).sum())
    total = len(df)
    decided = correct + wrong
    accuracy = (correct / decided * 100.0) if decided else None
    return {
        "total": total, "correct": correct, "wrong": wrong,
        "sideways": sideways, "pending": pending, "accuracy": accuracy,
    }
