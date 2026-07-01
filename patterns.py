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


def detect_inverse_head_and_shoulders(df: pd.DataFrame):
    if len(df) < 50:
        return None
    recent = df.tail(45).reset_index(drop=True)
    lows = recent["l"]
    troughs = lows.nsmallest(3).sort_index()
    if len(troughs) < 3:
        return None
    i1, i2, i3 = troughs.index.tolist()
    p1, p2, p3 = troughs.values.tolist()
    if i1 < i2 < i3 and p2 < p1 and p2 < p3 and abs(p1 - p3) / max(p1, 1e-9) < 0.05:
        neckline = recent.loc[i1:i3, "h"].max()
        last_close = recent["c"].iloc[-1]
        if last_close > neckline * 1.002:
            score = 0.85
            return {"pattern": "Inverse Head and Shoulders", "direction": "BULLISH", "score": score, "confidence": _confidence_from_score(score), "note": "Three-trough reversal with neckline breakout"}
    return None


def detect_rising_wedge(df: pd.DataFrame):
    if len(df) < 35:
        return None
    recent = df.tail(25).reset_index(drop=True)
    highs_head = recent["h"].head(12).max()
    highs_tail = recent["h"].tail(12).max()
    lows_head = recent["l"].head(12).min()
    lows_tail = recent["l"].tail(12).min()
    last_close = recent["c"].iloc[-1]
    # Both bounds rising, but converging (upper rises slower than lower) => rising wedge, bearish
    if highs_tail > highs_head and lows_tail > lows_head:
        upper_rise = highs_tail - highs_head
        lower_rise = lows_tail - lows_head
        if lower_rise > upper_rise > 0:
            support = recent["l"].tail(8).min()
            if last_close < support * 0.998:
                score = 0.7
                return {"pattern": "Rising Wedge", "direction": "BEARISH", "score": -score, "confidence": _confidence_from_score(score), "note": "Converging upward channel breaking down"}
    return None


def detect_falling_wedge(df: pd.DataFrame):
    if len(df) < 35:
        return None
    recent = df.tail(25).reset_index(drop=True)
    highs_head = recent["h"].head(12).max()
    highs_tail = recent["h"].tail(12).max()
    lows_head = recent["l"].head(12).min()
    lows_tail = recent["l"].tail(12).min()
    last_close = recent["c"].iloc[-1]
    # Both bounds falling, but converging (lower falls slower than upper) => falling wedge, bullish
    if highs_tail < highs_head and lows_tail < lows_head:
        upper_fall = highs_head - highs_tail
        lower_fall = lows_head - lows_tail
        if upper_fall > lower_fall > 0:
            resistance = recent["h"].tail(8).max()
            if last_close > resistance * 1.002:
                score = 0.7
                return {"pattern": "Falling Wedge", "direction": "BULLISH", "score": score, "confidence": _confidence_from_score(score), "note": "Converging downward channel breaking out"}
    return None


def detect_rounding_bottom(df: pd.DataFrame):
    if len(df) < 45:
        return None
    recent = df.tail(40).reset_index(drop=True)
    n = len(recent)
    third = n // 3
    first_seg = recent["c"].iloc[:third]
    mid_seg = recent["c"].iloc[third: 2 * third]
    last_seg = recent["c"].iloc[2 * third:]
    if first_seg.empty or mid_seg.empty or last_seg.empty:
        return None
    if first_seg.mean() > mid_seg.mean() and last_seg.mean() > mid_seg.mean():
        resistance = first_seg.max()
        last_close = recent["c"].iloc[-1]
        if last_close > resistance * 1.002 and last_seg.mean() > first_seg.mean() * 0.98:
            score = 0.75
            return {"pattern": "Rounding Bottom", "direction": "BULLISH", "score": score, "confidence": _confidence_from_score(score), "note": "Gradual U-shaped base with breakout above resistance"}
    return None


def detect_bullish_engulfing(df: pd.DataFrame):
    if len(df) < 5:
        return None
    prev = df.iloc[-2]
    last = df.iloc[-1]
    prev_bearish = prev["c"] < prev["o"]
    last_bullish = last["c"] > last["o"]
    if prev_bearish and last_bullish and last["o"] <= prev["c"] and last["c"] >= prev["o"]:
        score = 0.65
        return {"pattern": "Bullish Engulfing", "direction": "BULLISH", "score": score, "confidence": _confidence_from_score(score), "note": "Bullish candle fully engulfs prior bearish candle"}
    return None


def detect_bearish_engulfing(df: pd.DataFrame):
    if len(df) < 5:
        return None
    prev = df.iloc[-2]
    last = df.iloc[-1]
    prev_bullish = prev["c"] > prev["o"]
    last_bearish = last["c"] < last["o"]
    if prev_bullish and last_bearish and last["o"] >= prev["c"] and last["c"] <= prev["o"]:
        score = 0.65
        return {"pattern": "Bearish Engulfing", "direction": "BEARISH", "score": -score, "confidence": _confidence_from_score(score), "note": "Bearish candle fully engulfs prior bullish candle"}
    return None


def detect_morning_star(df: pd.DataFrame):
    if len(df) < 6:
        return None
    c1, c2, c3 = df.iloc[-3], df.iloc[-2], df.iloc[-1]
    body1 = c1["o"] - c1["c"]
    body2 = abs(c2["c"] - c2["o"])
    body3 = c3["c"] - c3["o"]
    c1_bearish = body1 > 0
    c2_small = body2 < abs(body1) * 0.4 if body1 else False
    c3_bullish = body3 > 0
    if c1_bearish and c2_small and c3_bullish and c3["c"] > (c1["o"] + c1["c"]) / 2:
        score = 0.8
        return {"pattern": "Morning Star", "direction": "BULLISH", "score": score, "confidence": _confidence_from_score(score), "note": "Three-candle bullish reversal after downtrend"}
    return None


def detect_evening_star(df: pd.DataFrame):
    if len(df) < 6:
        return None
    c1, c2, c3 = df.iloc[-3], df.iloc[-2], df.iloc[-1]
    body1 = c1["c"] - c1["o"]
    body2 = abs(c2["c"] - c2["o"])
    body3 = c3["o"] - c3["c"]
    c1_bullish = body1 > 0
    c2_small = body2 < abs(body1) * 0.4 if body1 else False
    c3_bearish = body3 > 0
    if c1_bullish and c2_small and c3_bearish and c3["c"] < (c1["o"] + c1["c"]) / 2:
        score = 0.8
        return {"pattern": "Evening Star", "direction": "BEARISH", "score": -score, "confidence": _confidence_from_score(score), "note": "Three-candle bearish reversal after uptrend"}
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
        detect_inverse_head_and_shoulders,
        detect_rising_wedge,
        detect_falling_wedge,
        detect_rounding_bottom,
        detect_bullish_engulfing,
        detect_bearish_engulfing,
        detect_morning_star,
        detect_evening_star,
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
