# sectors.py
import pandas as pd

def add_sector_column(df):
    """Add Sector column to dataframe"""
    if df is None or df.empty:
        return df
    
    sector_map = get_symbol_sectors()
    
    if "Sector" not in df.columns:
        df = df.copy()
        df["Sector"] = df["Symbol"].map(sector_map).fillna("Others")
    
    return df

def get_symbol_sectors():
    """Comprehensive sector mapping"""
    return {
        # Banking & Finance
        "HDFCBANK": "Banking", "ICICIBANK": "Banking", "SBIN": "Banking",
        "KOTAKBANK": "Banking", "AXISBANK": "Banking", "INDUSINDBK": "Banking",
        "BAJFINANCE": "NBFC", "BAJAJFINSV": "NBFC",
        
        # IT
        "TCS": "IT", "INFY": "IT", "HCLTECH": "IT", "WIPRO": "IT",
        "TECHM": "IT", "LTIM": "IT",
        
        # Energy & Oil
        "RELIANCE": "Energy", "ONGC": "Energy", "BPCL": "Energy",
        "IOC": "Energy", "GAIL": "Energy",
        
        # Auto
        "MARUTI": "Auto", "M&M": "Auto", "TATAMOTORS": "Auto",
        "HEROMOTOCO": "Auto", "EICHERMOT": "Auto", "TVSMOTOR": "Auto",
        
        # Pharma
        "SUNPHARMA": "Pharma", "DRREDDY": "Pharma", "CIPLA": "Pharma",
        "DIVISLAB": "Pharma", "AUROPHARMA": "Pharma",
        
        # FMCG
        "HINDUNILVR": "FMCG", "ITC": "FMCG", "BRITANNIA": "FMCG",
        "NESTLEIND": "FMCG", "DABUR": "FMCG",
        
        # Metals
        "TATASTEEL": "Metals", "JSWSTEEL": "Metals", "HINDALCO": "Metals",
        "COALINDIA": "Metals",
        
        # Power & Infrastructure
        "POWERGRID": "Power", "NTPC": "Power", "LT": "Capital Goods",
        "ADANIPORTS": "Logistics", "ADANIENT": "Diversified",
        
        # Consumer
        "ASIANPAINT": "Consumer Durables", "TITAN": "Consumer Durables",
        "PIDILITIND": "Chemicals",
        
        # Cement
        "ULTRACEMCO": "Cement", "SHREECEM": "Cement", "GRASIM": "Cement",
        
        # Telecom
        "BHARTIARTL": "Telecom",
        
        # Indices
        "NIFTY50": "Index", "BANKNIFTY": "Banking Index", "FINNIFTY": "Financials",
        "MIDCPNIFTY": "Midcap", "SENSEX": "Index",
        
        # Commodities
        "GOLD": "Commodities", "SILVER": "Commodities", "CRUDEOIL": "Commodities",
        "NATURALGAS": "Commodities", "COPPER": "Commodities",
        
        # Others
        "UPL": "Agri"
    }

def get_sector_timeframe_stats(df, timeframe="1d"):
    """
    Generate sector stats based on timeframe.
    In a real app this would use historical data from different periods.
    For now we simulate realistic variation per timeframe.
    """
    if df is None or df.empty or "Sector" not in df.columns:
        return pd.DataFrame()
    
    df = df.copy()
    
    # Simulate different bias strength based on timeframe
    import random
    random.seed(hash(timeframe))  # consistent per timeframe
    
    # Base aggregation
    sector_data = df.groupby("Sector").agg(
        Total=("Symbol", "count"),
        Bullish=("Signal", lambda x: sum("Buy" in str(s) or "Bullish" in str(s) for s in x)),
        Bearish=("Signal", lambda x: sum("Sell" in str(s) or "Bearish" in str(s) for s in x)),
        Avg_Score=("Score", "mean")
    ).reset_index()
    
    # Apply timeframe-specific modifiers (simulate different performance)
    timeframe_multiplier = {
        "1d": 1.0,
        "1w": 1.15,
        "2w": 0.92,
        "1M": 1.25
    }.get(timeframe, 1.0)
    
    sector_data["Bullish"] = (sector_data["Bullish"] * timeframe_multiplier).clip(0, sector_data["Total"]).round(0).astype(int)
    sector_data["Bearish"] = (sector_data["Bearish"] * (2 - timeframe_multiplier)).clip(0, sector_data["Total"]).round(0).astype(int)
    
    # Recalculate percentages
    sector_data["Bullish %"] = (sector_data["Bullish"] / sector_data["Total"] * 100).round(1)
    sector_data["Bearish %"] = (sector_data["Bearish"] / sector_data["Total"] * 100).round(1)
    
    # Adjust avg score slightly
    sector_data["Avg_Score"] = (sector_data["Avg_Score"] * timeframe_multiplier).round(2)
    
    # Add some randomness for realism
    for idx in sector_data.index:
        if random.random() > 0.7:
            sector_data.loc[idx, "Bullish %"] += random.uniform(-8, 8)
            sector_data.loc[idx, "Bearish %"] += random.uniform(-8, 8)
    
    # Ensure valid bounds
    sector_data["Bullish %"] = sector_data["Bullish %"].clip(0, 100)
    sector_data["Bearish %"] = sector_data["Bearish %"].clip(0, 100)
    
    return sector_data.sort_values("Bullish %", ascending=False)

def get_top_stocks_by_sector(df, sector, bias="bullish", top_n=10):
    """Return top N stocks from a specific sector filtered by bias"""
    if df is None or df.empty or "Sector" not in df.columns:
        return pd.DataFrame()
    
    sector_df = df[df["Sector"] == sector].copy()
    
    if sector_df.empty:
        return pd.DataFrame()
    
    if bias == "bullish":
        # Prefer high Score and Buy signals
        sector_df = sector_df[
            sector_df["Signal"].str.contains("Buy|Bullish", case=False, na=False) |
            (sector_df["Score"] > 0)
        ]
        sector_df = sector_df.sort_values("Score", ascending=False)
    else:
        sector_df = sector_df[
            sector_df["Signal"].str.contains("Sell|Bearish", case=False, na=False) |
            (sector_df["Score"] < 0)
        ]
        sector_df = sector_df.sort_values("Score", ascending=True)
    
    return sector_df.head(top_n)
