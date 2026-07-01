"""
Sector classification for NSE F&O stocks, index futures and commodities.

Sector data is stored in data/sector_map.csv so it can be hand-edited /
extended without touching code. Falls back to "Others" for any symbol
not found in the map.
"""
from pathlib import Path
import pandas as pd
import streamlit as st

from services import base_name_from_symbol

SECTOR_MAP_FILE = Path("data/sector_map.csv")

DEFAULT_SECTOR = "Others"

# Preferred display order - known sectors first, "Others" always last.
SECTOR_ORDER = [
    "Banking & Financial Services",
    "IT",
    "Auto & Auto Ancillary",
    "Pharma & Healthcare",
    "FMCG",
    "Metals & Mining",
    "Energy & Oil/Gas",
    "Power",
    "Infrastructure & Construction",
    "Cement",
    "Chemicals & Fertilizers",
    "Telecom",
    "Realty",
    "Consumer Durables",
    "Media & Entertainment",
    "Capital Goods & Industrials",
    "Defense",
    "Textiles",
    "Aviation",
    "Retail & Consumer",
    "New Age & Internet",
    "Diversified / Conglomerate",
    "Index",
    "Commodity",
    DEFAULT_SECTOR,
]


@st.cache_data(ttl=3600)
def load_sector_map() -> dict:
    """Load Symbol -> Sector mapping from CSV. Cached for the session."""
    mapping = {}
    try:
        if SECTOR_MAP_FILE.exists():
            df = pd.read_csv(SECTOR_MAP_FILE)
            for _, row in df.iterrows():
                sym = str(row.get("Symbol", "")).strip().upper()
                sector = str(row.get("Sector", "")).strip()
                if sym and sector:
                    mapping[sym] = sector
    except Exception:
        pass
    return mapping


def get_sector(symbol: str) -> str:
    """Return sector for a full FYERS symbol (e.g. NSE:RELIANCE-EQ)."""
    mapping = load_sector_map()
    base = base_name_from_symbol(symbol)
    return mapping.get(base, DEFAULT_SECTOR)


def add_sector_column(df: pd.DataFrame, symbol_col: str = "Symbol") -> pd.DataFrame:
    """Attach a 'Sector' column to a scan-results dataframe."""
    if df is None or df.empty:
        return df
    df = df.copy()
    df["Sector"] = df[symbol_col].apply(get_sector)
    return df


def ordered_sectors(present_sectors) -> list:
    """Return sectors in preferred display order, only those present in data."""
    present = set(present_sectors)
    ordered = [s for s in SECTOR_ORDER if s in present]
    # Any sector not in our preferred list (shouldn't normally happen) goes at the end.
    extras = sorted(present - set(ordered))
    return ordered + extras
