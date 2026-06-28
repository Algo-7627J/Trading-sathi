from pathlib import Path
import pandas as pd
from datetime import datetime

DATA_DIR = Path("data")
LATEST_SCAN = DATA_DIR / "latest_scan.csv"
SIGNAL_HISTORY = DATA_DIR / "signal_history.csv"


def ensure_data_files():
    DATA_DIR.mkdir(exist_ok=True)
    if not LATEST_SCAN.exists():
        pd.DataFrame().to_csv(LATEST_SCAN, index=False)
    if not SIGNAL_HISTORY.exists():
        pd.DataFrame(columns=[
            "Timestamp", "Symbol", "Old Signal", "New Signal", "Old Score", "New Score", "Alert Sent", "Reason"
        ]).to_csv(SIGNAL_HISTORY, index=False)


def load_latest_scan():
    ensure_data_files()
    try:
        return pd.read_csv(LATEST_SCAN)
    except Exception:
        return pd.DataFrame()


def save_latest_scan(df: pd.DataFrame):
    ensure_data_files()
    df.to_csv(LATEST_SCAN, index=False)


def append_signal_history(df: pd.DataFrame):
    ensure_data_files()
    prev = load_latest_scan()
    rows = []
    prev_map = {}
    if not prev.empty and "Symbol" in prev.columns:
        prev_map = prev.set_index("Symbol").to_dict("index")

    for _, row in df.iterrows():
        sym = row.get("Symbol")
        new_signal = row.get("Signal")
        new_score = row.get("Score")
        reason = row.get("Reason")
        old = prev_map.get(sym, {})
        old_signal = old.get("Signal")
        old_score = old.get("Score")
        changed = (old_signal != new_signal) or (str(old_score) != str(new_score))
        if changed:
            rows.append({
                "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "Symbol": sym,
                "Old Signal": old_signal,
                "New Signal": new_signal,
                "Old Score": old_score,
                "New Score": new_score,
                "Alert Sent": "YES" if new_signal in ["STRONG BUY", "BUY", "STRONG SELL", "SELL"] else "NO",
                "Reason": reason,
            })

    if rows:
        hist = pd.read_csv(SIGNAL_HISTORY)
        hist = pd.concat([hist, pd.DataFrame(rows)], ignore_index=True)
        hist.to_csv(SIGNAL_HISTORY, index=False)


def should_send_alert(symbol: str, signal: str, score, min_score_change: float = 8.0):
    prev = load_latest_scan()
    if prev.empty or "Symbol" not in prev.columns:
        return True
    row = prev[prev["Symbol"] == symbol]
    if row.empty:
        return True
    old_signal = row.iloc[0].get("Signal")
    old_score = row.iloc[0].get("Score")
    if old_signal != signal:
        return True
    try:
        old_score = float(old_score)
        score = float(score)
        return abs(score - old_score) >= min_score_change
    except Exception:
        return False
