from pathlib import Path
from datetime import datetime
import pandas as pd

DATA_DIR = Path("data")
LATEST_SCAN_FILE = DATA_DIR / "latest_scan.csv"
SIGNAL_HISTORY_FILE = DATA_DIR / "signal_history.csv"


def ensure_data_files():
    """
    Ensure data folder and required CSV files exist.
    """
    DATA_DIR.mkdir(exist_ok=True)

    if not LATEST_SCAN_FILE.exists():
        pd.DataFrame(columns=[
            "Symbol", "LTP", "Pattern", "Pattern Direction", "Pattern Confidence",
            "TrendScore", "MomentumScore", "VolumeScore", "OI", "OI Note",
            "News Sentiment", "News Strength", "Top Headline", "Score",
            "Bullish %", "Bearish %", "Signal", "Reason"
        ]).to_csv(LATEST_SCAN_FILE, index=False)

    if not SIGNAL_HISTORY_FILE.exists():
        pd.DataFrame(columns=[
            "Timestamp", "Symbol", "Old Signal", "New Signal",
            "Old Score", "New Score", "Alert Sent", "Reason"
        ]).to_csv(SIGNAL_HISTORY_FILE, index=False)


def load_latest_scan():
    """
    Load latest scan CSV safely.
    """
    ensure_data_files()
    try:
        return pd.read_csv(LATEST_SCAN_FILE)
    except Exception:
        return pd.DataFrame()


def save_latest_scan(df: pd.DataFrame):
    """
    Save the latest scan results.
    """
    ensure_data_files()
    try:
        df.to_csv(LATEST_SCAN_FILE, index=False)
    except Exception:
        pass


def append_signal_history(df: pd.DataFrame):
    """
    Compare latest scan with previous scan and append changed signals to history.
    """
    ensure_data_files()

    try:
        previous_df = load_latest_scan()
    except Exception:
        previous_df = pd.DataFrame()

    rows_to_add = []

    previous_map = {}
    if not previous_df.empty and "Symbol" in previous_df.columns:
        try:
            previous_map = previous_df.set_index("Symbol").to_dict("index")
        except Exception:
            previous_map = {}

    for _, row in df.iterrows():
        symbol = row.get("Symbol")
        new_signal = row.get("Signal")
        new_score = row.get("Score")
        reason = row.get("Reason")

        old_row = previous_map.get(symbol, {})
        old_signal = old_row.get("Signal")
        old_score = old_row.get("Score")

        signal_changed = old_signal != new_signal
        score_changed = str(old_score) != str(new_score)

        if signal_changed or score_changed:
            rows_to_add.append({
                "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "Symbol": symbol,
                "Old Signal": old_signal,
                "New Signal": new_signal,
                "Old Score": old_score,
                "New Score": new_score,
                "Alert Sent": "YES" if new_signal in ["BUY", "STRONG BUY", "SELL", "STRONG SELL"] else "NO",
                "Reason": reason
            })

    if rows_to_add:
        try:
            history_df = pd.read_csv(SIGNAL_HISTORY_FILE)
        except Exception:
            history_df = pd.DataFrame(columns=[
                "Timestamp", "Symbol", "Old Signal", "New Signal",
                "Old Score", "New Score", "Alert Sent", "Reason"
            ])

        updated_history = pd.concat([history_df, pd.DataFrame(rows_to_add)], ignore_index=True)
        updated_history.to_csv(SIGNAL_HISTORY_FILE, index=False)


def should_send_alert(symbol: str, signal: str, score, min_score_change: float = 8.0):
    """
    Decide whether a Telegram alert should be sent.
    Sends alert if:
    - symbol not present before
    - signal changed
    - score changed significantly
    """
    previous_df = load_latest_scan()

    if previous_df.empty or "Symbol" not in previous_df.columns:
        return True

    row = previous_df[previous_df["Symbol"] == symbol]
    if row.empty:
        return True

    old_signal = row.iloc[0].get("Signal")
    old_score = row.iloc[0].get("Score")

    if old_signal != signal:
        return True

    try:
        old_score = float(old_score)
        score = float(score)
        if abs(score - old_score) >= min_score_change:
            return True
    except Exception:
        return False

    return False
