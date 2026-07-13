# services.py
"""
services.py - Dynamic Universe with Auto-Fetch

Features:
- Auto-fetch live F&O stocks from NSE (best effort)
- Large hardcoded F&O list (~150+ stocks) as fallback
- Caching to avoid repeated calls
- Toggle between live and hardcoded
"""

import pandas as pd
import requests
import time
from typing import List, Dict

# ====================== LARGE F&O LIST (Fallback - ~150 stocks) ======================
LARGE_FO_STOCKS = [
    "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "HINDUNILVR", "SBIN", "BHARTIARTL",
    "ITC", "KOTAKBANK", "LT", "AXISBANK", "ASIANPAINT", "BAJFINANCE", "MARUTI", "HCLTECH",
    "SUNPHARMA", "TITAN", "ULTRACEMCO", "WIPRO", "POWERGRID", "NTPC", "COALINDIA", "TATASTEEL",
    "JSWSTEEL", "ONGC", "BPCL", "INDUSINDBK", "GRASIM", "ADANIENT", "ADANIPORTS", "CIPLA",
    "DRREDDY", "EICHERMOT", "HEROMOTOCO", "M&M", "SHREECEM", "BRITANNIA", "DIVISLAB", "UPL",
    "TATAMOTORS", "BAJAJFINSV", "BAJAJ-AUTO", "HDFCLIFE", "SBILIFE", "TATACONSUM", "TATAELXSI",
    "TECHM", "LTIM", "PERSISTENT", "COFORGE", "MPHASIS", "PIDILITIND", "DABUR", "NESTLEIND",
    "GODREJCP", "COLPAL", "HINDPETRO", "IOC", "GAIL", "ADANIGREEN", "ADANIPOWER", "TATAPOWER",
    "NHPC", "IRCTC", "ZOMATO", "PAYTM", "HDFC", "APOLLOHOSP", "AUROPHARMA", "LUPIN",
    "BIOCON", "GLENMARK", "ALKEM", "TORNTPHARM", "TATACHEM", "DEEPAKNTR", "AARTIIND", "SRF",
    "PIIND", "VEDL", "HINDALCO", "NATIONALUM", "DLF", "GODREJPROP", "AMBUJACEM", "ACC",
    "TVSMOTOR", "ESCORTS", "ASHOKLEY", "BHARATFORG", "CUMMINSIND", "BHEL", "BEL", "HAL",
    "IRFC", "RVNL", "FEDERALBNK", "CANBK", "UNIONBANK", "BANKBARODA", "PNB", "IDFCFIRSTB",
    "RBLBANK", "BANDHANBNK", "SHRIRAMFIN", "CHOLAFIN", "MANAPPURAM", "LALPATHLAB", "METROPOLIS",
    "THYROCARE", "CADILAHC", "GLAXO", "LTI", "LTTS", "HINDCOPPER", "SAIL", "JSL", "APLAPOLLO",
    "MUTHOOTFIN", "MAXHEALTH", "FORTIS", "PRESTIGE", "BRIGADE", "RAMCOCEM", "JKCEMENT",
    "THERMAX", "BDL", "GRSE", "IRCON", "KEC", "PNCINFRA", "TATAINVEST", "M&MFIN",
]

DEFAULT_INDICES = ["NIFTY50", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "SENSEX"]
DEFAULT_COMMODITIES = ["GOLD", "SILVER", "CRUDEOIL", "NATURALGAS", "COPPER"]

# Cache
_last_fetch_time = 0
_cached_fo_stocks: List[str] = []


# ====================== LIVE NSE FETCH ======================
def fetch_live_nse_fo_stocks(timeout: int = 15) -> List[str]:
    """
    Try to fetch current F&O stocks from NSE.
    Returns list or empty list on failure.
    """
    url = "https://www.nseindia.com/api/equity-stockIndices?index=SECURITIES%20IN%20F%26O"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.nseindia.com/",
    }
    
    try:
        session = requests.Session()
        session.headers.update(headers)
        
        # Warm-up request (NSE needs cookies)
        session.get("https://www.nseindia.com/", timeout=timeout)
        time.sleep(0.6)
        
        resp = session.get(url, timeout=timeout)
        resp.raise_for_status()
        
        data = resp.json()
        symbols = []
        
        for item in data.get("data", []):
            sym = str(item.get("symbol", "")).upper().strip()
            if sym and sym not in ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "SENSEX"]:
                symbols.append(sym)
        
        symbols = sorted(list(set(symbols)))
        
        if len(symbols) >= 80:   # Good enough
            return symbols
        return []
        
    except Exception as e:
        print(f"[services] NSE live fetch failed: {e}")
        return []


# ====================== MAIN FUNCTION ======================
def build_universe(use_live: bool = True, force_refresh: bool = False) -> Dict:
    """
    Returns universe dict with:
    - stocks: list of F&O stocks
    - indices, commodities, all
    - source: 'live_nse', 'live_nse (cached)', 'large_hardcoded', etc.
    """
    global _last_fetch_time, _cached_fo_stocks
    
    stocks = []
    source = "large_hardcoded"
    
    if use_live:
        now = time.time()
        cache_valid = (now - _last_fetch_time) < 900   # 15 minutes cache
        
        if force_refresh or not cache_valid or not _cached_fo_stocks:
            live = fetch_live_nse_fo_stocks()
            if live:
                _cached_fo_stocks = live
                _last_fetch_time = now
                stocks = live
                source = "live_nse"
            else:
                stocks = LARGE_FO_STOCKS.copy()
                source = "large_hardcoded (live failed)"
        else:
            stocks = _cached_fo_stocks.copy()
            source = "live_nse (cached)"
    else:
        stocks = LARGE_FO_STOCKS.copy()
        source = "large_hardcoded"
    
    # Final cleanup
    stocks = sorted(list(set(stocks)))
    
    indices = DEFAULT_INDICES.copy()
    commodities = DEFAULT_COMMODITIES.copy()
    all_syms = stocks + indices + commodities
    
    return {
        "stocks": stocks,
        "indices": indices,
        "commodities": commodities,
        "all": all_syms,
        "source": source,
        "count": len(stocks)
    }


def get_symbol_sectors() -> Dict[str, str]:
    """Sector mapping (extendable)"""
    mapping = {
        "RELIANCE": "Energy", "TCS": "IT", "HDFCBANK": "Banking", "INFY": "IT",
        "ICICIBANK": "Banking", "HINDUNILVR": "FMCG", "SBIN": "Banking", "BHARTIARTL": "Telecom",
        "ITC": "FMCG", "KOTAKBANK": "Banking", "LT": "Capital Goods", "AXISBANK": "Banking",
        "ASIANPAINT": "Consumer Durables", "BAJFINANCE": "NBFC", "MARUTI": "Auto", "HCLTECH": "IT",
        "SUNPHARMA": "Pharma", "TITAN": "Consumer Durables", "ULTRACEMCO": "Cement", "WIPRO": "IT",
        "POWERGRID": "Power", "NTPC": "Power", "COALINDIA": "Mining", "TATASTEEL": "Metals",
        "JSWSTEEL": "Metals", "ONGC": "Energy", "BPCL": "Energy", "INDUSINDBK": "Banking",
        "GRASIM": "Cement", "ADANIENT": "Diversified", "ADANIPORTS": "Logistics",
        "CIPLA": "Pharma", "DRREDDY": "Pharma", "EICHERMOT": "Auto", "HEROMOTOCO": "Auto",
        "M&M": "Auto", "SHREECEM": "Cement", "BRITANNIA": "FMCG", "DIVISLAB": "Pharma",
        "UPL": "Agri", "NIFTY50": "Index", "BANKNIFTY": "Banking Index", "FINNIFTY": "Financials",
        "MIDCPNIFTY": "Midcap", "SENSEX": "Index",
        "GOLD": "Commodities", "SILVER": "Commodities", "CRUDEOIL": "Commodities",
        "NATURALGAS": "Commodities", "COPPER": "Commodities"
    }
    return mapping


# For backward compatibility
def get_default_universe():
    return build_universe(use_live=False)
