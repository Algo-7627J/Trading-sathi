import pandas as pd


def _confidence_from_score(score: float):
    if score >= 0.8:
        return "HIGH"
    if score >= 0.55:
        return "MEDIUM"
    return "LOW"


def detect_range_breakout(df: pd.DataFrame):
    if len(df) < 25:
        return None
    recent = df.tail(21).copy()
    prev = recent.iloc[:-1]
    last = recent.iloc[-1]
    high = prev["h"].max()
    low = prev["l"].min()
    if last["c"] > high * 1.002:
        score = 0.7
        return {"pattern": "Range Breakout", "direction": "BULLISH", "score": score, "confidence": _confidence_from_score(score), "note": "Close above recent range high"}
    if last["c"] < low * 0.998:
        score = 0.7
        return {"pattern": "Range Breakdown", "direction": "BEARISH", "score": -score, "confidence": _confidence_from_score(score), "note": "Close below recent range low"}
    return None


def detect_double_bottom(df: pd.DataFrame):
    if len(df) < 40:
        return None
    recent = df.tail(35).reset_index(drop=True)
    lows = recent["l"]
    min1_idx = lows.idxmin()
    min1 = lows[min1_idx]
    window_exclude = recent.drop(index=range(max(0, min1_idx - 3), min(len(recent), min1_idx + 4)))
    if len(window_exclude) < 10:
        return None
    min2_idx = window_exclude["l"].idxmin()
    min2 = window_exclude.loc[min2_idx, "l"]
    if abs(min1 - min2) / max(min1, 1e-9) < 0.02:
        neckline = recent.loc[min(min1_idx, min2_idx):max(min1_idx, min2_idx), "h"].max()
        last_close = recent["c"].iloc[-1]
        if last_close > neckline * 1.002:
            score = 0.8
            return {"pattern": "Double Bottom", "direction": "BULLISH", "score": score, "confidence": _confidence_from_score(score), "note": "Neckline breakout after two similar lows"}
    return None


def detect_double_top(df: pd.DataFrame):
    if len(df) < 40:
        return None
    recent = df.tail(35).reset_index(drop=True)
    highs = recent["h"]
    max1_idx = highs.idxmax()
    max1 = highs[max1_idx]
    window_exclude = recent.drop(index=range(max(0, max1_idx - 3), min(len(recent), max1_idx + 4)))
    if len(window_exclude) < 10:
        return None
    max2_idx = window_exclude["h"].idxmax()
    max2 = window_exclude.loc[max2_idx, "h"]
    if abs(max1 - max2) / max(max1, 1e-9) < 0.02:
        neckline = recent.loc[min(max1_idx, max2_idx):max(max1_idx, max2_idx), "l"].min()
        last_close = recent["c"].iloc[-1]
        if last_close < neckline * 0.998:
            score = 0.8
            return {"pattern": "Double Top", "direction": "BEARISH", "score": -score, "confidence": _confidence_from_score(score), "note": "Neckline breakdown after two similar highs"}
    return None


def detect_triangle_breakout(df: pd.DataFrame):
    if len(df) < 35:
        return None
    recent = df.tail(25).reset_index(drop=True)
    highs_head = recent["h"].head(12).max()
    highs_tail = recent["h"].tail(12).max()
    lows_head = recent["l"].head(12).min()
    lows_tail = recent["l"].tail(12).min()
    last_close = recent["c"].iloc[-1]
    if highs_tail < highs_head and lows_tail > lows_head:
        upper_band = recent["h"].tail(10).max()
        lower_band = recent["l"].tail(10).min()
        if last_close > upper_band * 1.001:
            score = 0.75
            return {"pattern": "Triangle Breakout", "direction": "BULLISH", "score": score, "confidence": _confidence_from_score(score), "note": "Volatility contraction followed by upside breakout"}
        if last_close < lower_band * 0.999:
            score = 0.75
            return {"pattern": "Triangle Breakdown", "direction": "BEARISH", "score": -score, "confidence": _confidence_from_score(score), "note": "Volatility contraction followed by downside breakdown"}
    return None


def detect_cup_handle(df: pd.DataFrame):
    if len(df) < 60:
        return None
    recent = df.tail(55).reset_index(drop=True)
    left_high = recent["h"].iloc[:15].max()
    cup_low = recent["l"].iloc[15:40].min()
    right_high = recent["h"].iloc[35:50].max()
    last_close = recent["c"].iloc[-1]
    if left_high > 0 and right_high > 0:
        similarity = abs(left_high - right_high) / left_high
        depth = (left_high - cup_low) / left_high if left_high else 0
        handle_low = recent["l"].iloc[45:54].min()
        handle_depth = (right_high - handle_low) / right_high if right_high else 0
        if similarity < 0.04 and 0.05 < depth < 0.35 and handle_depth < 0.12:
            if last_close > right_high * 1.002:
                score = 0.9
                return {"pattern": "Cup and Handle", "direction": "BULLISH", "score": score, "confidence": _confidence_from_score(score), "note": "Rounded base with shallow handle and breakout"}
    return None


def detect_flag(df: pd.DataFrame):
    if len(df) < 35:
        return None
    recent = df.tail(25).reset_index(drop=True)
    impulse = recent["c"].iloc[8] - recent["c"].iloc[0]
    pullback = recent["c"].iloc[18] - recent["c"].iloc[8]
    last_close = recent["c"].iloc[-1]
    recent_high = recent["h"].iloc[18:24].max()
    recent_low = recent["l"].iloc[18:24].min()
    if impulse > 0 and pullback < 0 and abs(pullback) < abs(impulse) * 0.5 and last_close > recent_high * 1.001:
        score = 0.7
        return {"pattern": "Bull Flag", "direction": "BULLISH", "score": score, "confidence": _confidence_from_score(score), "note": "Impulse move followed by controlled pullback and breakout"}
    if impulse < 0 and pullback > 0 and abs(pullback) < abs(impulse) * 0.5 and last_close < recent_low * 0.999:
        score = 0.7
        return {"pattern": "Bear Flag", "direction": "BEARISH", "score": -score, "confidence": _confidence_from_score(score), "note": "Sharp fall followed by weak bounce and breakdown"}
    return None


def detect_pennant(df: pd.DataFrame):
    if len(df) < 35:
        return None
    recent = df.tail(25).reset_index(drop=True)
    impulse = recent["c"].iloc[7] - recent["c"].iloc[0]
    highs_head = recent["h"].iloc[8:16].max()
    highs_tail = recent["h"].iloc[16:24].max()
    lows_head = recent["l"].iloc[8:16].min()
    lows_tail = recent["l"].iloc[16:24].min()
    last_close = recent["c"].iloc[-1]
    if impulse > 0 and highs_tail < highs_head and lows_tail > lows_head and last_close > highs_tail * 1.001:
        score = 0.72
        return {"pattern": "Bull Pennant", "direction": "BULLISH", "score": score, "confidence": _confidence_from_score(score), "note": "Tight consolidation after strong upmove with breakout"}
    if impulse < 0 and highs_tail < highs_head and lows_tail > lows_head and last_close < lows_tail * 0.999:
        score = 0.72
        return {"pattern": "Bear Pennant", "direction": "BEARISH", "score": -score, "confidence": _confidence_from_score(score), "note": "Tight consolidation after strong downmove with breakdown"}
    return None


def detect_head_and_shoulders(df: pd.DataFrame):
    if len(df) < 50:
        return None
    recent = df.tail(45).reset_index(drop=True)
    highs = recent["h"]
    peaks = highs.nlargest(3).sort_index()
    if len(peaks) < 3:
        return None
    i1, i2, i3 = peaks.index.tolist()
    p1, p2, p3 = peaks.values.tolist()
    if i1 < i2 < i3 and p2 > p1 and p2 > p3 and abs(p1 - p3) / max(p1, 1e-9) < 0.05:
        neckline = recent.loc[i1:i3, "l"].min()
        last_close = recent["c"].iloc[-1]
        if last_close < neckline * 0.998:
            score = 0.85
            return {"pattern": "Head and Shoulders", "direction": "BEARISH", "score": -score, "confidence": _confidence_from_score(score), "note": "Three-peak reversal with neckline breakdown"}
    return None


def detect_patterns(df: pd.DataFrame):
    detectors = [
        detect_cup_handle,
        detect_double_bottom,
        detect_double_top,
        detect_triangle_breakout,
        detect_range_breakout,
        detect_flag,
        detect_pennant,
        detect_head_and_shoulders,
    ]
    found = []
    for fn in detectors:
        try:
            res = fn(df)
            if res:
                found.append(res)
        except Exception:
            continue
    if not found:
        return {"pattern": "None", "direction": "NEUTRAL", "score": 0.0, "confidence": "LOW", "note": "No major multi-candle pattern detected"}
    found = sorted(found, key=lambda x: abs(x["score"]), reverse=True)
    return found[0]
