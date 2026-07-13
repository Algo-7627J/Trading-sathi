# next_day.py
import pandas as pd
import random

def scan_next_day(fyers, symbols, progress=None):
    """Generate mock next-day outlook results"""
    results = []
    
    for i, symbol in enumerate(symbols):
        if progress:
            progress.progress((i + 1) / len(symbols), text=f"Analyzing {symbol}...")
        
        ltp = round(random.uniform(150, 4500), 2)
        
        # Next day outlook
        outlook_options = ["Bullish", "Bearish", "Neutral", "Strong Bullish", "Strong Bearish"]
        outlook = random.choice(outlook_options)
        
        if "Bullish" in outlook:
            exp_move = f"+{round(random.uniform(0.8, 3.5), 1)}%"
            bias = "Bullish"
            conf = random.randint(65, 92)
        elif "Bearish" in outlook:
            exp_move = f"-{round(random.uniform(0.8, 3.5), 1)}%"
            bias = "Bearish"
            conf = random.randint(65, 92)
        else:
            exp_move = f"±{round(random.uniform(0.4, 1.5), 1)}%"
            bias = "Neutral"
            conf = random.randint(40, 65)
        
        # Key levels
        support = round(ltp * (1 - random.uniform(0.01, 0.04)), 1)
        resistance = round(ltp * (1 + random.uniform(0.01, 0.04)), 1)
        key_levels = f"Support: {support} | Resistance: {resistance}"
        
        results.append({
            "Symbol": symbol,
            "LTP": ltp,
            "Outlook": outlook,
            "Expected_Move": exp_move,
            "Confidence": conf,
            "Bias": bias,
            "Key_Levels": key_levels,
            "Timeframe": "Next Day"
        })
    
    df = pd.DataFrame(results)
    return df

def get_next_day_mock(symbols):
    return scan_next_day(None, symbols)
