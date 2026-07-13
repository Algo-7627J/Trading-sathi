# analysis.py
import pandas as pd
import random

def scan_universe(fyers, symbols, timeframe_mode="15m", include_news=True, include_fundamental=False, progress=None):
    """Mock intraday scanner. Returns realistic dataframe."""
    results = []
    
    for i, symbol in enumerate(symbols):
        if progress:
            progress.progress((i + 1) / len(symbols), text=f"Scanning {symbol}...")
        
        # Generate realistic mock data
        ltp = round(random.uniform(150, 4500), 2)
        score = round(random.uniform(-12, 12), 1)
        
        if score > 6:
            signal = "Strong Buy"
        elif score > 2:
            signal = "Buy"
        elif score < -6:
            signal = "Strong Sell"
        elif score < -2:
            signal = "Sell"
        else:
            signal = "Neutral"
        
        # Mock patterns
        patterns = ["Bullish Engulfing", "Hammer", "Breakout", "Gap Up", "Double Bottom", 
                    "Bearish Engulfing", "Shooting Star", "Breakdown", "Gap Down", "None"]
        pattern = random.choice(patterns)
        
        mtf_status = random.choice(["Bullish", "Bearish", "Neutral", "Bullish", "Neutral"])
        
        volume = f"{random.randint(1, 45)}M"
        
        # Simulate news impact
        if include_news and random.random() > 0.6:
            if score > 0:
                signal = "Strong Buy"
                score += 1.5
            else:
                signal = "Strong Sell"
                score -= 1.5
        
        results.append({
            "Symbol": symbol,
            "LTP": ltp,
            "Signal": signal,
            "Score": score,
            "Pattern": pattern,
            "MTF Status": mtf_status,
            "Volume": volume,
            "Timeframe": timeframe_mode
        })
    
    df = pd.DataFrame(results)
    
    # Add some sector bias simulation
    df = _apply_mock_sector_bias(df)
    
    return df

def _apply_mock_sector_bias(df):
    """Add realistic sector tilt to scores"""
    sector_biases = {
        "Banking": 1.8, "IT": -1.2, "Energy": 2.1, "Auto": 0.7,
        "Pharma": -0.8, "FMCG": -1.5, "Metals": 3.2, "Power": 0.4
    }
    
    from sectors import get_symbol_sectors
    sector_map = get_symbol_sectors()
    
    df = df.copy()
    for idx, row in df.iterrows():
        sector = sector_map.get(row["Symbol"], "Others")
        bias = sector_biases.get(sector, 0)
        df.loc[idx, "Score"] = round(df.loc[idx, "Score"] + bias, 1)
        
        # Re-evaluate signal
        s = df.loc[idx, "Score"]
        if s > 6:
            df.loc[idx, "Signal"] = "Strong Buy"
        elif s > 2:
            df.loc[idx, "Signal"] = "Buy"
        elif s < -6:
            df.loc[idx, "Signal"] = "Strong Sell"
        elif s < -2:
            df.loc[idx, "Signal"] = "Sell"
        else:
            df.loc[idx, "Signal"] = "Neutral"
    
    return df

def get_mock_intraday_data(symbols):
    """Helper to get quick mock data without full scan"""
    return scan_universe(None, symbols, timeframe_mode="15m")
