# ui_helpers.py — Groww-style UI components for RAO SAHAB
import base64
from pathlib import Path

import streamlit as st
import pandas as pd
from urllib.parse import quote
from html import escape as html_escape

# ====================== GROWW-STYLE DESIGN TOKENS ======================
GREEN = "#00B386"        # Groww positive green
GREEN_DARK = "#00875F"
RED = "#EB5B3C"          # Groww negative red
RED_DARK = "#C93A20"
INK = "var(--ink)"          # primary text
HEADING = "var(--heading)"      # heading text
MUTED = "var(--muted)"        # secondary text
BORDER = "var(--border)"
GREEN_TINT = "#E5F7F0"
RED_TINT = "#FDECE8"
GRAY_TINT = "var(--panel)"
NEUT_BAR = "var(--bar)"
SCORE_MAX = 17.0



# ====================== SU-30 MKI BACKGROUND ======================
_ASSETS_DIR = Path(__file__).resolve().parent / "assets"
JET_OVERLAY = 0.78   # darkness of the overlay on top of the jet photo


@st.cache_data(show_spinner=False)
def _jet_data_uri():
    """Base64 data-URI of the Su-30 MKI backdrop (embedded, no external URL)."""
    try:
        p = _ASSETS_DIR / "su30_background.jpg"
        if p.exists():
            return "data:image/jpeg;base64," + base64.b64encode(p.read_bytes()).decode()
    except Exception:
        pass
    return None


def inject_custom_css(dark=False, jet=False):
    """App-wide theme. `dark=True` swaps the palette to the dark theme."""
    base = """
<style>
/* ===================== Theme variables ===================== */
:root {
  --ink: #44475B; --heading: #2B2D3F; --muted: #7C7E8C;
  --border: #E9EBEE; --panel: #F1F2F4; --bar: #EEF0F2;
  --cardbg: #FFFFFF; --appbg: #FFFFFF;
  --cardbull: #EFFCF7; --cardbear: #FFF3F0;
}

html, body { overflow-x: hidden; }

/* ===================== Base ===================== */
.stApp { background-color: var(--appbg); color: var(--ink); }
.block-container { padding-top: 0; max-width: 1180px; }
h1, h2, h3, h4 { color: var(--heading); letter-spacing: -.01em; }
::selection { background: rgba(0,179,134,.22); }

/* ===================== Header / toolbar ===================== */
header[data-testid="stHeader"] { background: transparent; }
[data-testid="stDecoration"] { display: none; }

/* ===================== Scrollbar ===================== */
::-webkit-scrollbar { width: 10px; height: 10px; }
::-webkit-scrollbar-track { background: var(--panel); }
::-webkit-scrollbar-thumb { background: #C7CDD6; border-radius: 999px; border: 2px solid var(--panel); }
::-webkit-scrollbar-thumb:hover { background: #A8B0BB; }

/* ===================== Sidebar — premium dark green ===================== */
section[data-testid="stSidebar"] {
  background: linear-gradient(180deg, #081B14 0%, #0D2A1F 55%, #103528 100%);
  border-right: 1px solid rgba(0,179,134,.18);
  color: #E6F4EE;
}
section[data-testid="stSidebar"] h1, section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3, section[data-testid="stSidebar"] h4 { color: #FFFFFF; }
section[data-testid="stSidebar"] p, section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p { color: #C4E3D3; }
section[data-testid="stSidebar"] .stCaption { color: #8FBBA7; }
section[data-testid="stSidebar"] hr { border-color: rgba(255,255,255,.12); }
section[data-testid="stSidebar"] .stButton > button {
  background: rgba(255,255,255,.07); color: #EAF6F0;
  border: 1px solid rgba(255,255,255,.16); border-radius: 10px; font-weight: 600;
}
section[data-testid="stSidebar"] .stButton > button:hover {
  border-color: #00B386; color: #6FE3BC; background: rgba(0,179,134,.12);
}
section[data-testid="stSidebar"] div[data-testid="stTextInput"] input,
section[data-testid="stSidebar"] div[data-testid="stNumberInput"] input {
  background: rgba(255,255,255,.08); color: #FFFFFF; border-color: rgba(255,255,255,.18);
}
section[data-testid="stSidebar"] div[data-baseweb="select"] > div,
section[data-testid="stSidebar"] [data-testid="stSelectbox"] input[role="combobox"] {
  background: rgba(255,255,255,.08); border-color: rgba(255,255,255,.18); color: #FFFFFF;
}
section[data-testid="stSidebar"] [data-testid="stCheckbox"] label span,
section[data-testid="stSidebar"] [data-testid="stToggle"] label span { color: #D9EDE3; }
section[data-testid="stSidebar"] [data-testid="stExpander"] {
  background: rgba(255,255,255,.04); border-color: rgba(255,255,255,.14);
}

/* ===================== Buttons ===================== */
.stButton > button {
  border-radius: 10px; border: 1px solid var(--border);
  background: var(--cardbg); color: var(--ink);
  font-weight: 700; transition: all .18s ease; box-shadow: 0 1px 2px rgba(23,24,29,.03);
}
.stButton > button:hover {
  border-color: #00B386; color: #00875F;
  box-shadow: 0 3px 10px rgba(0,179,134,.16); transform: translateY(-1px);
}
.stButton > button[kind="primary"] {
  background: linear-gradient(135deg, #00B386, #00C48E); border-color: #00B386;
  color: #FFFFFF; font-weight: 800; box-shadow: 0 3px 10px rgba(0,179,134,.28);
}
.stButton > button[kind="primary"]:hover {
  background: linear-gradient(135deg, #009E76, #00B07E); border-color: #009E76;
  box-shadow: 0 5px 16px rgba(0,179,134,.36); transform: translateY(-1px);
}
.stDownloadButton > button { border-radius: 10px; font-weight: 600; }

/* ===================== Tabs — solid green buttons ===================== */
/* Dual selectors: legacy Streamlit used [data-baseweb="tab*"], while
   Streamlit 1.5x+ (React Aria) uses [role="tablist"] / [data-testid="stTab"]. */
.stTabs [data-baseweb="tab-list"], .stTabs [role="tablist"] {
  gap: 6px; border-bottom: none; padding: 6px 0 10px 0; flex-wrap: wrap; overflow: visible;
}
.stTabs [data-baseweb="tab"], .stTabs [data-testid="stTab"] {
  display: flex !important; align-items: center !important; justify-content: center !important;
  font-weight: 800 !important; font-size: 13px !important; color: #00875F;
  background: var(--cardbg) !important; border: 1.5px solid #00B386 !important;
  border-radius: 10px !important; padding: 8px 14px !important; margin: 0;
  transition: all .15s ease; white-space: nowrap;
}
.stTabs [data-baseweb="tab"] p, .stTabs [data-testid="stTab"] p {
  font-weight: 800 !important; color: inherit !important; margin: 0;
}
.stTabs [data-baseweb="tab"]:hover, .stTabs [data-testid="stTab"]:hover {
  background: #E5F7F0 !important; color: #00875F;
}
.stTabs [data-baseweb="tab"][aria-selected="true"], .stTabs [data-testid="stTab"][data-selected="true"] {
  background: linear-gradient(135deg, #00B386, #00C48E) !important;
  color: #FFFFFF !important; border-color: #00B386 !important;
  box-shadow: 0 4px 12px rgba(0,179,134,.35);
}
.stTabs [data-baseweb="tab-highlight"], .stTabs .react-aria-SelectionIndicator { display: none !important; }
.stTabs [data-baseweb="tab-border"] { background: transparent; }

/* ===================== Inputs & widgets ===================== */
[data-testid="stDataFrame"] { border: 1px solid var(--border); border-radius: 12px; overflow: hidden; box-shadow: 0 1px 3px rgba(23,24,29,.05); }
[data-testid="stExpander"] { border: 1px solid var(--border); border-radius: 12px; background: var(--cardbg); box-shadow: 0 1px 2px rgba(23,24,29,.03); }
[data-testid="stExpander"] summary { font-weight: 700; }
[data-testid="stAlert"] { border-radius: 12px; }
div[data-testid="stTextInput"] input, div[data-testid="stNumberInput"] input,
div[data-baseweb="select"] > div,
[data-testid="stSelectbox"] input[role="combobox"] { border-radius: 10px !important; }
hr { border-color: var(--bar); }
.stCaption, [data-testid="stCaptionContainer"] p { color: var(--muted); }

/* ===================== Hero band (full-width gradient header) ===================== */
.rs-hero {
  width: 100vw; max-width: 100vw; margin-left: calc(50% - 50vw);
  padding: 22px 0 20px 0; position: relative; overflow: hidden;
  background: linear-gradient(120deg, #005E52 0%, #009A74 45%, #00C48E 100%);
  box-shadow: 0 4px 20px rgba(0,90,70,.28); margin-bottom: 18px;
}
.rs-hero::before {
  content: ""; position: absolute; width: 340px; height: 340px; border-radius: 50%;
  background: rgba(255,255,255,.08); top: -170px; right: -80px;
}
.rs-hero::after {
  content: ""; position: absolute; width: 220px; height: 220px; border-radius: 50%;
  background: rgba(255,255,255,.06); bottom: -120px; left: 28%;
}
.rs-hero-inner { max-width: 1180px; margin: 0 auto; padding: 0 26px; display: flex; align-items: center; gap: 16px; position: relative; z-index: 1; }
.rs-hero-logo {
  width: 50px; height: 50px; border-radius: 14px; background: rgba(255,255,255,.16);
  backdrop-filter: blur(4px); display: flex; align-items: center; justify-content: center;
  color: #FFFFFF; font-weight: 800; font-size: 20px; border: 1px solid rgba(255,255,255,.25);
  box-shadow: 0 4px 14px rgba(0,0,0,.18);
}
.rs-hero-title { font-size: 24px; font-weight: 800; color: #FFFFFF; line-height: 1.15; letter-spacing: -.01em; }
.rs-hero-sub { font-size: 13px; color: #CFF3E4; margin-top: 2px; }
.rs-hero-pill {
  margin-left: auto; display: inline-flex; align-items: center; gap: 6px;
  background: rgba(255,255,255,.14); border: 1px solid rgba(255,255,255,.28);
  border-radius: 999px; padding: 6px 14px; font-size: 12.5px; font-weight: 700; color: #FFFFFF;
  backdrop-filter: blur(4px); white-space: nowrap;
}
.rs-hero-pill .dot { font-size: 9px; line-height: 1; }

/* ===================== Cards (gradient-tinted) ===================== */
.opl-card {
  background: var(--cardbg); border: 1px solid var(--border); border-radius: 14px;
  padding: 12px 14px; margin-bottom: 10px; box-shadow: 0 2px 6px rgba(23,24,29,.05);
  transition: border-color .15s ease, box-shadow .15s ease, transform .15s ease;
}
.opl-card.bull { border-left: 4px solid #00B386; background: linear-gradient(135deg, var(--cardbg) 0%, var(--cardbull) 100%); }
.opl-card.bear { border-left: 4px solid #EB5B3C; background: linear-gradient(135deg, var(--cardbg) 0%, var(--cardbear) 100%); }
.opl-sym { font-size: 16px; font-weight: 800; color: var(--heading); letter-spacing: -.01em; }
.opl-sector { font-size: 12px; color: var(--muted); margin-left: 7px; font-weight: 500; }
.opl-price { font-weight: 700; color: var(--ink); font-size: 15px; }
.opl-sub { font-size: 12.5px; color: var(--muted); margin-top: 6px; }

.chip { display: inline-block; padding: 2px 10px; border-radius: 999px; font-size: 12px; font-weight: 700; }
.chip-green { background: #E5F7F0; color: #00875F; }
.chip-red { background: #FDECE8; color: #C93A20; }
.chip-gray { background: var(--panel); color: var(--muted); }

/* ===================== Stat & count tiles ===================== */
.opl-tile {
  background: var(--cardbg); border: 1px solid var(--border); border-radius: 12px;
  padding: 14px 16px; text-align: center; box-shadow: 0 1px 2px rgba(23,24,29,.04);
  transition: transform .18s ease, box-shadow .18s ease;
}
.opl-tile:hover { transform: translateY(-2px); box-shadow: 0 6px 14px rgba(23,24,29,.07); }
.opl-tile .lbl { font-size: 13px; color: var(--muted); font-weight: 700; }
.opl-tile .val { font-size: 30px; font-weight: 800; margin-top: 2px; }

.opl-count { transition: transform .18s ease, box-shadow .18s ease; box-shadow: 0 2px 6px rgba(23,24,29,.05); }
.opl-count:hover { transform: translateY(-2px); box-shadow: 0 6px 16px rgba(23,24,29,.09); }

/* ===================== Section labels ===================== */
.opl-sechead { display: flex; align-items: center; gap: 10px; margin: 18px 0 10px 0; }
.opl-sechead-bar {
  width: 5px; height: 20px; border-radius: 3px;
  background: linear-gradient(180deg, #00B386, #00D09C); box-shadow: 0 0 0 3px rgba(0,179,134,.14);
}
.opl-sechead .t { font-size: 17px; font-weight: 800; color: var(--heading); letter-spacing: -.01em; }

/* ===================== Clickable cards ===================== */
.opl-link { text-decoration: none !important; display: block; }
.opl-link:hover .opl-card { border-color: #00B386; box-shadow: 0 8px 20px rgba(0,179,134,.18); transform: translateY(-1px); cursor: pointer; }
.opl-ext { font-size: 12px; color: #C9CDD4; margin-left: 5px; font-weight: 700; }
.opl-link:hover .opl-ext { color: #00B386; }

/* ===================== Markdown tables (logic docs) ===================== */
[data-testid="stMarkdownContainer"] table { border-collapse: collapse; }
[data-testid="stMarkdownContainer"] th, [data-testid="stMarkdownContainer"] td { border: 1px solid var(--border); padding: 6px 10px; color: var(--ink); }
[data-testid="stMarkdownContainer"] th { background: var(--panel); color: var(--heading); font-weight: 700; }

/* ===================== MOBILE / RESPONSIVE (<= 768px) ===================== */
@media (max-width: 768px) {
  /* use the full screen width with tight padding */
  .block-container { padding: 0.5rem 0.75rem 3.5rem 0.75rem !important; max-width: 100% !important; }

  /* stack EVERY column layout vertically (scan settings, stat tiles, etc.) */
  [data-testid="stHorizontalBlock"] { flex-direction: column !important; gap: 0.35rem !important; }
  [data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] {
    width: 100% !important;
    min-width: 100% !important;
    max-width: 100% !important;
    flex: 1 1 100% !important;
  }

  /* tabs -> 2-column grid of full-width buttons: every tab stays visible & tappable */
  .stTabs [data-baseweb="tab-list"], .stTabs [role="tablist"] { display: grid !important; grid-template-columns: repeat(2, 1fr) !important; gap: 5px !important; overflow: visible !important; }
  .stTabs [data-baseweb="tab"], .stTabs [data-testid="stTab"] { width: 100% !important; justify-content: center !important; padding: 10px 8px !important; white-space: normal !important; text-align: center !important; }
  .stTabs [data-baseweb="tab-border"], .stTabs [data-baseweb="tab-highlight"], .stTabs .react-aria-SelectionIndicator { display: none !important; }

  /* hero band: compact, wraps instead of overflowing */
  .rs-hero { padding: 14px 0 12px 0; }
  .rs-hero-inner { padding: 0 14px; gap: 10px; flex-wrap: wrap; }
  .rs-hero-logo { width: 40px; height: 40px; font-size: 16px; border-radius: 11px; }
  .rs-hero-title { font-size: 18px; }
  .rs-hero-sub { font-size: 11.5px; }
  .rs-hero-pill { margin-left: 0; font-size: 11px; padding: 4px 10px; }

  /* comfortable thumb-sized tap targets */
  .stButton > button, .stDownloadButton > button { min-height: 44px; }
  div[data-baseweb="select"] > div, [data-testid="stSelectbox"] input[role="combobox"] { min-height: 42px; }
  [role="radiogroup"] { flex-wrap: wrap !important; }

  /* compact tiles & cards */
  .opl-tile { padding: 10px 12px; }
  .opl-tile .val { font-size: 22px; }
  .opl-count { padding: 13px 10px; }
  .opl-sechead { margin: 12px 0 8px 0; }
  .opl-sechead .t { font-size: 15px; }
  .opl-sym { font-size: 15px; }
  .opl-card { padding: 10px 12px; }

  /* long markdown tables scroll horizontally instead of overflowing */
  [data-testid="stMarkdownContainer"] table { display: block; overflow-x: auto; white-space: nowrap; }
}
</style>
"""
    dark_css = """
<style>
/* ===================== DARK MODE ===================== */
:root {
  --ink: #D7E3F0; --heading: #EAF1FA; --muted: #8FA1B5;
  --border: #243143; --panel: #1B2635; --bar: #22303F;
  --cardbg: #141F2C; --appbg: #0D1520;
  --cardbull: #0F2A20; --cardbear: #2B1A16;
  --text-color: #D7E3F0; --background-color: #0D1520;
  --secondary-background-color: #141F2C; --primary-color: #00B386;
}
.stApp { background-color: var(--appbg); color: var(--ink); }
header[data-testid="stHeader"] { background: transparent; }
section[data-testid="stSidebar"] { background: linear-gradient(180deg, #050D0A 0%, #0B1F18 60%, #0D2A1F 100%); }
.opl-card { box-shadow: 0 2px 8px rgba(0,0,0,.35); }
.chip-green { background: rgba(0,179,134,.16); color: #3EE6A2; }
.chip-red { background: rgba(235,91,60,.16); color: #FF9078; }
.chip-gray { background: var(--panel); color: var(--muted); }
.opl-ext { color: #4A5A70; }
.stTabs [data-baseweb="tab"], .stTabs [data-testid="stTab"] { background: var(--cardbg) !important; color: #3EE6A2; border-color: rgba(0,179,134,.5) !important; }
.stTabs [data-baseweb="tab"]:hover, .stTabs [data-testid="stTab"]:hover { background: rgba(0,179,134,.12) !important; }
.stTabs [data-baseweb="tab"][aria-selected="true"], .stTabs [data-testid="stTab"][data-selected="true"] { background: linear-gradient(135deg, #00B386, #00C48E) !important; color: #FFFFFF !important; }
[data-testid="stExpander"] { background: var(--cardbg); }
[data-testid="stDataFrame"] { border-color: var(--border); }
div[data-testid="stTextInput"] input, div[data-testid="stNumberInput"] input { background: var(--panel); color: var(--ink); }
div[data-baseweb="select"] > div, [data-testid="stSelectbox"] input[role="combobox"] { background: var(--panel); color: var(--ink); border-color: var(--border); }
.stButton > button { background: var(--cardbg); color: var(--ink); border-color: var(--border); }
.stButton > button:hover { border-color: #00B386; color: #3EE6A2; }
hr { border-color: var(--bar); }
</style>
"""
    jet_css = ""
    if jet:
        uri = _jet_data_uri()
        if uri:
            ov = f"{JET_OVERLAY:.2f}"
            jet_css = f"""
<style>
/* ===================== SU-30 MKI BACKGROUND ===================== */
.stApp {{
  background-color: #07110D;
  background-image: linear-gradient(rgba(7,17,13,{ov}), rgba(7,17,13,{ov})), url("{uri}");
  background-size: cover;
  background-position: center 30%;
  background-attachment: fixed;
}}
[data-testid="stAppViewContainer"] {{ background: transparent !important; }}
[data-testid="stBottomBlockContainer"] {{ background: transparent !important; }}
.rs-hero {{
  background: linear-gradient(120deg, rgba(0,94,82,.55) 0%, rgba(0,154,116,.42) 45%, rgba(0,196,142,.30) 100%);
  box-shadow: none; border-bottom: 1px solid rgba(255,255,255,.12);
}}
/* iOS Safari ignores background-attachment:fixed and would stretch the
   photo across the whole page — use a clean solid dark on phones instead. */
@media (max-width: 768px) {{
  .stApp {{ background-image: none !important; background-color: #07110D !important; }}
}}
</style>
"""
    st.markdown(base + (dark_css if dark else "") + jet_css, unsafe_allow_html=True)


# ====================== SMALL FORMATTERS ======================
def _fmt_money(v):
    try:
        return f"₹{float(v):,.2f}"
    except (TypeError, ValueError):
        return f"₹{v}"


def _fmt_qty(v):
    """Compact Indian-style share-count: 15.8L / 1.2Cr / 980K."""
    try:
        v = float(v)
    except (TypeError, ValueError):
        return "—"
    if v >= 1e7:
        return f"{v / 1e7:.2f}Cr"
    if v >= 1e5:
        return f"{v / 1e5:.2f}L"
    if v >= 1e3:
        return f"{v / 1e3:.0f}K"
    return f"{int(v)}"


def _chip(text, tone="gray"):
    return f'<span class="chip chip-{tone}">{text}</span>'


def _tone_for_signal(signal):
    s = str(signal).lower()
    if "buy" in s or "bullish" in s:
        return "green"
    if "sell" in s or "bearish" in s:
        return "red"
    return "gray"


# ====================== FYERS CHART DEEP LINKS ======================
FYERS_INDEX_SYMS = {
    "NIFTY50": "NSE:NIFTY50-INDEX",
    "BANKNIFTY": "NSE:BANKNIFTY-INDEX",
    "FINNIFTY": "NSE:FINNIFTY-INDEX",
    "MIDCPNIFTY": "NSE:MIDCPNIFTY-INDEX",
    "SENSEX": "BSE:SENSEX-INDEX",
}
_FYERS_NO_LINK = {"GOLD", "SILVER", "CRUDEOIL", "NATURALGAS", "COPPER"}


def fyers_chart_link(symbol):
    """Deep-link to the FYERS Web chart (Symbol Details) for a symbol."""
    s = str(symbol or "").upper().strip()
    if not s or s in _FYERS_NO_LINK:
        return None
    if s in FYERS_INDEX_SYMS:
        fsym = FYERS_INDEX_SYMS[s]
    elif ":" in s:
        fsym = s
    else:
        fsym = f"NSE:{s}-EQ"
    return f"https://fyers.in/web/charts?symbol={quote(fsym, safe='')}"


def _linkify(card_html, symbol):
    """Wrap a card in a FYERS chart link (click → new tab)."""
    link = fyers_chart_link(symbol)
    if not link:
        return card_html
    return (
        f'<a href="{link}" target="_blank" rel="noopener noreferrer" '
        f'title="Open {symbol} chart on FYERS ↗" class="opl-link">{card_html}</a>'
    )


# ====================== SHARED CARD EXTRAS (news links + free Gemini AI) ======================
def fyers_wrap(symbol, html):
    """Wrap `html` in the FYERS chart deep-link (or return unchanged).

    Used for the *main body* of cards that also carry news/Gemini links —
    keeping those outside so anchors never nest (invalid nested <a> breaks
    the whole card).
    """
    link = fyers_chart_link(symbol)
    if not link:
        return html
    safe = html_escape(str(link), quote=True)
    sym_safe = html_escape(str(symbol))
    return (f'<a href="{safe}" target="_blank" rel="noopener noreferrer" '
            f'title="Open {sym_safe} chart on FYERS ↗" class="opl-link" '
            f'style="text-decoration:none;color:inherit;">{html}</a>')


def news_links(news, max_items=2):
    """Each headline as its OWN clickable link to the article (Google News)."""
    if not news:
        return ""
    items = ""
    for n in news[:max_items]:
        title = n["title"] if isinstance(n, dict) else str(n)
        link = (n.get("link") or "") if isinstance(n, dict) else ""
        t = html_escape(str(title))
        if link:
            l = html_escape(str(link), quote=True)
            item = (f'<a href="{l}" target="_blank" rel="noopener noreferrer" title="{t}" '
                    f'style="color:{INK};text-decoration:none;border-bottom:1px dotted {BORDER};">'
                    f'{t} ↗</a>')
        else:
            item = t
        items += (f'<div style="font-size:11.5px;color:{MUTED};margin-top:4px;">📰 {item}</div>')
    return items


def gemini_ai_link(symbol, prompt=None):
    """\"🤖 Full AI analysis on Gemini\" deep-link — opens Google AI Studio (free
    Gemini, no API key, Google sign-in) with a pre-filled analysis prompt.
    Pass `prompt` to override the default stock-analysis prompt."""
    if prompt is None:
        prompt = (f"Give a complete technical and fundamental analysis of {symbol} (NSE, India): "
                  f"current trend and momentum, key support/resistance levels, delivery percentage and volume context, "
                  f"recent news and results, and the most likely reasons behind its recent price move. "
                  f"End with a short risk summary. Do not give buy/sell advice.")
    url = "https://aistudio.google.com/prompts/new_chat?prompt=" + quote(prompt)
    return (f'<div style="margin-top:10px;text-align:right;">'
            f'<a href="{url}" target="_blank" rel="noopener noreferrer" '
            f'style="display:inline-block;background:{GREEN_TINT};color:{GREEN_DARK};font-size:12px;font-weight:700;'
            f'padding:4px 11px;border-radius:999px;text-decoration:none;">'
            f'🤖 Full AI analysis on Gemini ↗</a></div>')


# ====================== LAYOUT PIECES ======================
def render_title(title, subtitle, connected=False):
    """Full-width gradient hero band with logo, title and FYERS status pill."""
    if connected:
        dot = '<span class="dot" style="color:#5CE6B8;">●</span>'
        status = "FYERS Connected"
    else:
        dot = '<span class="dot" style="color:#D9F2E8;">○</span>'
        status = "Not Connected"
    st.markdown(f"""
    <div class="rs-hero">
        <div class="rs-hero-inner">
            <div class="rs-hero-logo">RS</div>
            <div>
                <div class="rs-hero-title">{title}</div>
                <div class="rs-hero-sub">{subtitle}</div>
            </div>
            <div class="rs-hero-pill">{dot}{status}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def section_label(text):
    st.markdown(
        f"<div class='opl-sechead'><span class='opl-sechead-bar'></span><span class='t'>{text}</span></div>",
        unsafe_allow_html=True,
    )


def render_stat_row(stats):
    cols = st.columns(len(stats))
    for i, stat in enumerate(stats):
        with cols[i]:
            st.markdown(f"""
            <div class="opl-tile">
                <div class="lbl">{stat['label']}</div>
                <div class="val" style="color:{ink_or(stat)}">{stat['value']}</div>
            </div>
            """, unsafe_allow_html=True)


def ink_or(stat):
    return stat.get("color", INK)


# ====================== COUNT TILES (Strong Buy / Strong Sell etc.) ======================
def render_count_tile(label, count, tone="green", icon=""):
    tones = {
        "green": (GREEN_DARK, GREEN_TINT, "#BFE9D8"),
        "red": (RED_DARK, RED_TINT, "#F3CDC2"),
        "gray": (MUTED, GRAY_TINT, BORDER),
    }
    c, bg, brd = tones.get(tone, tones["gray"])
    st.markdown(f"""
    <div class="opl-count" style="background:{bg}; border:1px solid {brd}; border-radius:14px;
                padding:20px; text-align:center;">
        <div style="font-size:13px; font-weight:700; color:{c}; letter-spacing:.4px;">{icon} {label}</div>
        <div style="font-size:38px; font-weight:800; color:{c}; margin-top:3px; line-height:1.1;">{count}</div>
    </div>
    """, unsafe_allow_html=True)


# ====================== WATCHLIST ======================
def render_watchlist_manager(all_symbols):
    st.markdown("**⭐ Watchlist**")
    watchlist = st.session_state.get("watchlist", [])

    if "watchlist" not in st.session_state:
        st.session_state.watchlist = []

    col1, col2 = st.columns([3, 1])
    with col1:
        new_sym = st.text_input("Add symbol", placeholder="e.g. RELIANCE", label_visibility="collapsed")
    with col2:
        if st.button("Add", use_container_width=True):
            if new_sym and new_sym.upper() not in st.session_state.watchlist:
                st.session_state.watchlist.append(new_sym.upper())
                st.rerun()

    if watchlist:
        st.caption("Current Watchlist:")
        for i, sym in enumerate(watchlist):
            c1, c2 = st.columns([4, 1])
            c1.write(sym)
            if c2.button("✕", key=f"rm_{i}", use_container_width=True):
                st.session_state.watchlist.remove(sym)
                st.rerun()
    else:
        st.caption("No symbols in watchlist")


# ====================== MOST BULLISH / MOST BEARISH ======================
def split_bull_bear(df, top_n=6):
    """
    Return (bullish_df, bearish_df) — top ranked.
    Works for intraday result frames (Signal/Score) and
    next-day frames (Outlook/Bias/Confidence — auto-detected).
    """
    empty = df.head(0) if df is not None else df
    if df is None or df.empty:
        return empty, empty

    if "Outlook" in df.columns:  # ---- NEXT-DAY MODE ----
        bias_col = "Bias" if "Bias" in df.columns else "Outlook"
        bias = df[bias_col].astype(str)
        bull = df[bias.str.contains("Bullish", case=False, na=False)]
        bear = df[bias.str.contains("Bearish", case=False, na=False)]
        sort_col = "Confidence" if "Confidence" in df.columns else None
        if sort_col:
            bull = bull.sort_values(sort_col, ascending=False)
            bear = bear.sort_values(sort_col, ascending=False)
        return bull.head(top_n), bear.head(top_n)

    # ---- INTRADAY MODE ----
    sig = df["Signal"].astype(str) if "Signal" in df.columns else pd.Series("", index=df.index)
    bull = df[sig.str.contains("Buy|Bullish", case=False, na=False)]
    bear = df[sig.str.contains("Sell|Bearish", case=False, na=False)]
    if "Score" in df.columns:
        bull = bull.sort_values("Score", ascending=False)
        bear = bear.sort_values("Score", ascending=True)
    return bull.head(top_n), bear.head(top_n)


def _intraday_stock_card(row):
    symbol = row.get("Symbol", "N/A")
    sector = row.get("Sector", "")
    ltp = _fmt_money(row.get("LTP", "N/A"))
    signal = str(row.get("Signal", "Neutral"))
    pattern = row.get("Pattern", "N/A")
    mtf = row.get("MTF Status", "N/A")
    vol = row.get("Volume", "N/A")
    tone = _tone_for_signal(signal)
    side = "bull" if tone == "green" else "bear" if tone == "red" else ""

    try:
        sval = float(row.get("Score", 0) or 0)
    except (TypeError, ValueError):
        sval = 0.0

    # center-anchored score meter: -17 (full red left) .. 0 .. +17 (full green right)
    w = round(min(abs(sval) / SCORE_MAX, 1.0) * 50, 1)
    if sval >= 0:
        ml, mcol = 50.0, GREEN
    else:
        ml, mcol = round(50.0 - w, 1), RED

    card = f"""
    <div class="opl-card {side}">
        <div style="display:flex; justify-content:space-between; align-items:center;">
            <div><span class="opl-sym">{symbol}</span><span class="opl-ext">↗</span><span class="opl-sector">{sector}</span></div>
            <div class="opl-price">{ltp}</div>
        </div>
        <div style="display:flex; justify-content:space-between; align-items:center; margin-top:7px;">
            <div>{_chip(signal, tone)}</div>
            <div style="font-size:12px; color:{MUTED};">{pattern} • MTF {mtf} • Vol {vol}</div>
        </div>
        <div style="display:flex; align-items:center; gap:10px; margin-top:9px;">
            <div style="position:relative; flex:1; background:{NEUT_BAR}; border-radius:999px; height:6px;">
                <div style="position:absolute; left:50%; top:-2px; width:2px; height:10px; background:#C9CDD4; border-radius:2px;"></div>
                <div style="position:absolute; left:{ml}%; width:{w}%; background:{mcol}; height:6px; border-radius:999px;"></div>
            </div>
            <span style="font-size:12px; color:{MUTED}; white-space:nowrap;">Score <b style="color:{INK};">{sval:.1f}</b> / {int(SCORE_MAX)}</span>
        </div>
    </div>"""
    return _linkify(card, symbol)


def _flow_tone(flow):
    f = str(flow).lower()
    if "buying" in f:
        return GREEN_DARK, GREEN_TINT
    if "selling" in f:
        return RED_DARK, RED_TINT
    return MUTED, GRAY_TINT


def _flow_chip(flow):
    c, bg = _flow_tone(flow)
    return (f"<span style='display:inline-block; background:{bg}; color:{c}; "
            f"font-size:11px; font-weight:700; padding:2px 8px; border-radius:999px;'>"
            f"{flow}</span>")



# ====================== GENUINENESS / DELIVERY BADGES ======================
GENUINE = "#00875F"
GENUINE_BG = "#E5F7F0"
SPEC = "#B7791F"
SPEC_BG = "#FDF3E7"


def genuineness_chip(label):
    """Conviction badge: Genuine (green) / Moderate (gray) / Speculative (amber)."""
    g = str(label).lower()
    if "genuine" in g:
        return (f'<span style="display:inline-block;background:{GENUINE_BG};color:{GENUINE};'
                f'font-size:12px;font-weight:700;padding:2px 9px;border-radius:999px;">✓ {label}</span>')
    if "speculative" in g:
        return (f'<span style="display:inline-block;background:{SPEC_BG};color:{SPEC};'
                f'font-size:12px;font-weight:700;padding:2px 9px;border-radius:999px;">{label}</span>')
    return (f'<span style="display:inline-block;background:{GRAY_TINT};color:{MUTED};'
            f'font-size:12px;font-weight:600;padding:2px 9px;border-radius:999px;">{label}</span>')


def delivery_line(pct):
    """\"📦 Delivery 69.2%\" tinted by conviction level (for momentum/streak cards)."""
    try:
        p = float(pct)
    except (TypeError, ValueError):
        return ""
    if pd.isna(p):
        return ""
    col = GENUINE if p >= 60 else (SPEC if p < 30 else MUTED)
    return f'<span style="font-size:12px;color:{MUTED};">📦 Delivery <b style="color:{col};">{p:.1f}%</b></span>'



def render_fii_dii_banner(fd):
    """Market-wide FII/DII net-flow banner for the Next-Day tab."""
    if not fd:
        return
    tone = fd.get("tone", "gray")
    c = GREEN_DARK if tone == "green" else RED_DARK if tone == "red" else MUTED
    bg = GREEN_TINT if tone == "green" else RED_TINT if tone == "red" else GRAY_TINT

    def fmt(v):
        sign = "+" if v >= 0 else ""
        return f"{sign}{v:,.0f}"

    st.markdown(f"""
    <div style="background:{bg}; border:1px solid {BORDER}; border-radius:14px;
                padding:16px 18px; margin:4px 0 14px 0;">
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px;">
            <div style="font-size:14px; font-weight:700; color:{HEADING};">
                🏦 FII / DII Activity <span style="font-weight:500; color:{MUTED};">({fd.get('date','')})</span>
            </div>
            <div style="font-size:13px; font-weight:600; color:{c};">{fd.get('lean','')}</div>
        </div>
        <div style="display:flex; gap:26px; margin-top:10px; flex-wrap:wrap;">
            <div>
                <div style="font-size:12px; color:{MUTED};">FII Net</div>
                <div style="font-size:20px; font-weight:700; color:{GREEN_DARK if fd.get('fii_net',0)>=0 else RED_DARK};">{fmt(fd.get('fii_net',0))} Cr</div>
            </div>
            <div>
                <div style="font-size:12px; color:{MUTED};">DII Net</div>
                <div style="font-size:20px; font-weight:700; color:{GREEN_DARK if fd.get('dii_net',0)>=0 else RED_DARK};">{fmt(fd.get('dii_net',0))} Cr</div>
            </div>
            <div>
                <div style="font-size:12px; color:{MUTED};">Total Net</div>
                <div style="font-size:20px; font-weight:700; color:{GREEN_DARK if fd.get('net_total',0)>=0 else RED_DARK};">{fmt(fd.get('net_total',0))} Cr</div>
            </div>
        </div>
        <div style="font-size:12px; color:{MUTED}; margin-top:8px;">
            FII Buy {fmt(fd.get('fii_buy',0))} · FII Sell {fmt(fd.get('fii_sell',0))} · DII Buy {fmt(fd.get('dii_buy',0))} · DII Sell {fmt(fd.get('dii_sell',0))} (₹ Cr)
        </div>
    </div>
    """, unsafe_allow_html=True)


def _nextday_stock_card(row):
    symbol = row.get("Symbol", "N/A")
    sector = row.get("Sector", "")
    outlook = str(row.get("Outlook", "Neutral"))
    exp_move = row.get("Expected_Move", "N/A")
    try:
        conf = int(float(row.get("Confidence", 0)))
    except (TypeError, ValueError):
        conf = 0
    key_levels = row.get("Key_Levels", "")
    ltp = row.get("LTP", None)
    flow = row.get("Last30Min", None)
    flow_detail = row.get("Flow_Detail", "")
    tone = _tone_for_signal(outlook)
    side = "bull" if tone == "green" else "bear" if tone == "red" else ""
    bar_col = GREEN if tone == "green" else RED if tone == "red" else "#C9CDD4"
    ltp_html = f'<span class="opl-price" style="margin-right:10px;">{_fmt_money(ltp)}</span>' if ltp is not None else ""

    card = f"""
    <div class="opl-card {side}">
        <div style="display:flex; justify-content:space-between; align-items:center;">
            <div><span class="opl-sym">{symbol}</span><span class="opl-ext">↗</span><span class="opl-sector">{sector}</span></div>
            <div>{ltp_html}{_chip(outlook, tone)}</div>
        </div>
        <div style="display:flex; justify-content:space-between; align-items:center; margin-top:7px;">
            <span style="font-size:13px; color:{INK}; font-weight:600;">Exp. Move: {exp_move}</span>
            <span style="font-size:12px; color:{MUTED};">{key_levels}</span>
        </div>
        <div style="display:flex; align-items:center; gap:8px; margin-top:8px;">
            <span style="font-size:12px; color:{MUTED};">Last 30min:</span>
            {_flow_chip(flow) if flow else ""}
            <span style="font-size:11px; color:{MUTED};">{flow_detail}</span>
        </div>
        <div style="display:flex; align-items:center; gap:8px; margin-top:9px;">
            <div style="flex:1; background:{NEUT_BAR}; border-radius:999px; height:6px;">
                <div style="width:{conf}%; background:{bar_col}; height:6px; border-radius:999px;"></div>
            </div>
            <span style="font-size:12px; color:{MUTED}; white-space:nowrap;">{conf}% conf.</span>
        </div>
    </div>"""
    return _linkify(card, symbol)


def render_delivery_card(row, live=None, news=None):
    """Clickable card for Delivery Combo results (FYERS deep-link).

    Single-line HTML (no blank lines) so Streamlit's markdown renders it
    reliably. Layout: header (symbol + LTP + direction chip) -> delivery
    meter -> info chips (genuineness, signal, score/confidence, flow) -> live strip.
    """
    symbol = row.get("Symbol", "N/A")
    direction = str(row.get("Direction", "Neutral"))
    delv_pct = row.get("DeliveryPct", None)
    # prefer the most descriptive signal: intraday "Signal", then next-day "Outlook", then "Bias"
    signal = row.get("Signal", "") or row.get("Outlook", "") or row.get("Bias", "") or ""
    ltp = row.get("LTP", None)
    score = row.get("Score", None)
    conf = row.get("Confidence", None)
    qty = row.get("QtyTraded", None)
    delv_qty = row.get("DeliverableQty", None)
    flow = row.get("Last30Min", None)
    flow_detail = row.get("Flow_Detail", "")

    tone = _tone_for_signal(direction)          # Bullish->green, Bearish->red, Neutral->gray
    side = "bull" if tone == "green" else "bear" if tone == "red" else ""

    # ---- delivery % (single source of truth) ----
    try:
        dp = float(delv_pct)
        dp_html = f"{dp:.1f}%"
        bar_w = max(0.0, min(dp, 100.0))
    except (TypeError, ValueError):
        dp, dp_html, bar_w = None, "\u2014", 0.0
    bar_col = GREEN if tone == "green" else RED if tone == "red" else "#C9CDD4"

    # ---- LTP ----
    ltp_html = ""
    if ltp is not None:
        try:
            if pd.notna(ltp):
                ltp_html = f'<span class="opl-price">{_fmt_money(ltp)}</span>'
        except (TypeError, ValueError):
            pass

    # ---- delivered / traded caption ----
    qty_txt = ""
    if qty is not None and delv_qty is not None:
        try:
            if pd.notna(qty) and pd.notna(delv_qty):
                qty_txt = (f'<div style="font-size:11px;color:{MUTED};margin-top:4px;">Delivered '
                           f'<b style="color:{INK};font-weight:600;">{_fmt_qty(delv_qty)}</b>&nbsp;·&nbsp;Traded '
                           f'<b style="color:{INK};font-weight:600;">{_fmt_qty(qty)}</b></div>')
        except (TypeError, ValueError):
            pass

    # ---- delivery meter ----
    meter = (f'<div style="margin-top:11px;">'
             f'<div style="display:flex;justify-content:space-between;align-items:baseline;">'
             f'<span style="font-size:11.5px;font-weight:700;letter-spacing:.5px;color:{MUTED};">\U0001F4E6 DELIVERY</span>'
             f'<span style="font-size:17px;font-weight:800;color:{bar_col};">{dp_html}</span></div>'
             f'<div style="margin-top:4px;background:{NEUT_BAR};border-radius:999px;height:7px;">'
             f'<div style="width:{bar_w}%;background:{bar_col};height:7px;border-radius:999px;"></div></div>'
             f'{qty_txt}</div>')

    # ---- info chips ----
    chips = []
    if dp is not None:
        chips.append(genuineness_chip("Genuine Move" if dp >= 60 else ("Moderate Conviction" if dp >= 30 else "Speculative")))

    sig_clean = str(signal).strip()
    if sig_clean and sig_clean.lower() not in (direction.lower(), "nan", "none", ""):
        chips.append(_chip(sig_clean, _tone_for_signal(sig_clean)))

    if score is not None:
        try:
            if pd.notna(score):
                sval = float(score)
                mcol = GREEN_DARK if sval >= 0 else RED_DARK
                chips.append(f'<span style="display:inline-block;background:{GRAY_TINT};border-radius:999px;padding:2px 9px;font-size:12px;color:{MUTED};white-space:nowrap;">Score <b style="color:{mcol};">{sval:+.1f}</b></span>')
        except (TypeError, ValueError):
            pass
    elif conf is not None:
        try:
            if pd.notna(conf):
                cval = int(float(conf))
                chips.append(f'<span style="display:inline-block;background:{GRAY_TINT};border-radius:999px;padding:2px 9px;font-size:12px;color:{MUTED};white-space:nowrap;">Conf <b style="color:{INK};">{cval}%</b></span>')
        except (TypeError, ValueError):
            pass

    if flow and str(flow) not in ("", "N/A", "nan", "Skipped"):
        flow_pill = _flow_chip(flow)
        if flow_detail and str(flow_detail) not in ("", "\u2014", "nan"):
            flow_pill += f'<span style="font-size:11px;color:{MUTED};">{flow_detail}</span>'
        chips.append(flow_pill)

    chips_row = ""
    if chips:
        chips_row = ('<div style="display:flex;align-items:center;gap:8px;margin-top:10px;flex-wrap:wrap;">'
                     + "".join(chips) + '</div>')

    # ---- live-session strip ----
    live_html = ""
    if live:
        status = live.get("Status", "")
        move = live.get("MovePct")
        ltone = live.get("Tone", "gray")
        c = GREEN_DARK if ltone == "green" else RED_DARK if ltone == "red" else MUTED
        bg = GREEN_TINT if ltone == "green" else RED_TINT if ltone == "red" else GRAY_TINT
        brd = "#BFE9D8" if ltone == "green" else "#F3CDC2" if ltone == "red" else BORDER
        if move is not None:
            arrow = "\u25B2" if move > 0 else "\u25BC" if move < 0 else "\u2022"
            mv = f"{move:+.2f}%"
        else:
            arrow, mv = "\u2022", "\u2014"
        live_html = (f'<div style="margin-top:10px;display:flex;align-items:center;justify-content:space-between;'
                     f'background:{bg};border:1px solid {brd};border-radius:8px;padding:6px 11px;">'
                     f'<span style="font-size:11.5px;font-weight:600;color:{MUTED};">\U0001F4E1 Live today</span>'
                     f'<span style="font-size:12.5px;font-weight:700;color:{c};">{arrow} {mv} · {status}</span></div>')

    main = (f'<div style="display:flex;justify-content:space-between;align-items:center;">'
            f'<div><span class="opl-sym">{symbol}</span><span class="opl-ext">\u2197</span></div>'
            f'<div style="display:flex;align-items:center;gap:8px;">{ltp_html}{_chip(direction, tone)}</div></div>'
            f'{meter}{chips_row}{live_html}')

    card = (f'<div class="opl-card {side}">{fyers_wrap(symbol, main)}'
            f'{news_links(news)}{gemini_ai_link(symbol)}</div>')
    return card


def _section_head(emoji, label, count, tone):
    color = GREEN_DARK if tone == "green" else RED_DARK if tone == "red" else MUTED
    return f"""
    <div style="display:flex; align-items:center; gap:8px; margin:10px 0 10px 0;">
        <span style="font-size:18px;">{emoji}</span>
        <span style="font-size:17px; font-weight:700; color:{HEADING};">{label}</span>
        <span class="chip chip-{'green' if tone=='green' else 'red' if tone=='red' else 'gray'}"
              style="margin-left:2px;">{count} stocks</span>
    </div>"""


def render_bull_bear_sections(df, top_n=6, key_prefix="bb"):
    """
    🟢 Most Bullish / 🔴 Most Bearish — side-by-side ranked card columns.
    Auto-detects intraday vs next-day frames.
    """
    if df is None or df.empty:
        return

    bull, bear = split_bull_bear(df, top_n=top_n)
    is_nextday = "Outlook" in df.columns
    card_fn = _nextday_stock_card if is_nextday else _intraday_stock_card

    cb, cs = st.columns(2, gap="large")

    with cb:
        st.markdown(_section_head("🟢", "Most Bullish", len(bull), "green"), unsafe_allow_html=True)
        if bull.empty:
            st.markdown(f'<div class="opl-card"><div class="opl-sub" style="margin:0;">No bullish setups right now.</div></div>', unsafe_allow_html=True)
        for _, row in bull.iterrows():
            st.markdown(card_fn(row), unsafe_allow_html=True)

    with cs:
        st.markdown(_section_head("🔴", "Most Bearish", len(bear), "red"), unsafe_allow_html=True)
        if bear.empty:
            st.markdown(f'<div class="opl-card"><div class="opl-sub" style="margin:0;">No bearish setups right now.</div></div>', unsafe_allow_html=True)
        for _, row in bear.iterrows():
            st.markdown(card_fn(row), unsafe_allow_html=True)


# ====================== FULL RESULT VIEWS ======================
def render_compact_table_view(df):
    if df is None or df.empty:
        return
    display_cols = [c for c in ["Symbol", "Sector", "LTP", "Signal", "Score", "Pattern", "MTF Status", "Volume"] if c in df.columns]
    st.dataframe(df[display_cols], use_container_width=True, hide_index=True, height=400)


def render_compact_cards_view(df):
    if df is None or df.empty:
        return
    for _, row in df.iterrows():
        st.markdown(_intraday_stock_card(row), unsafe_allow_html=True)


def render_next_day_results(df):
    """Render full next-day results (Cards / Table) — Groww light theme."""
    if df is None or df.empty:
        st.info("No next-day outlook data available.")
        return

    view_mode = st.radio("View", ["Cards", "Table"], horizontal=True, key="nd_view_mode")

    if view_mode == "Table":
        display_cols = [c for c in ["Symbol", "Sector", "Outlook", "Expected_Move", "Confidence", "Bias", "Last30Min", "Key_Levels"] if c in df.columns]
        st.dataframe(df[display_cols], use_container_width=True, hide_index=True)
        return

    for _, row in df.iterrows():
        st.markdown(_nextday_stock_card(row), unsafe_allow_html=True)


def sort_by_priority(df):
    if df is None or df.empty or "Score" not in df.columns:
        return df
    return df.sort_values("Score", ascending=False)


# ====================== SECTOR CARD (Tab 3 drill-down) ======================
def render_sector_card(sector, total, bullish, bearish, avg_score, is_bullish=True, key_prefix=""):
    pct = (bullish / total * 100) if total > 0 else 0
    if is_bullish:
        color, bg, brd = GREEN_DARK, GREEN_TINT, "#BFE9D8"
        frac = bullish
    else:
        color, bg, brd = RED_DARK, RED_TINT, "#F3CDC2"
        frac = bearish

    col1, col2 = st.columns([4, 1])
    with col1:
        st.markdown(f"""
        <div style="background:{bg}; border:1px solid {brd}; border-radius:10px;
                    padding:12px 14px; margin-bottom:6px;">
            <div style="display:flex; justify-content:space-between;">
                <div>
                    <span style="font-weight:700; font-size:15px; color:{HEADING};">{sector}</span>
                    <span style="margin-left:8px; font-size:12px; color:{MUTED};">{total} stocks</span>
                </div>
                <div style="text-align:right; font-size:13px;">
                    <span style="color:{color}; font-weight:700;">{frac}</span>
                    <span style="color:{MUTED};"> / {total}</span>
                </div>
            </div>
            <div style="font-size:12px; margin-top:4px; color:{MUTED};">
                Bullish: {bullish} ({pct:.0f}%) • Avg Score: {avg_score:.1f}
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        if st.button("View Stocks", key=f"{key_prefix}_{sector}", use_container_width=True):
            return sector
    return None


def render_sector_stock_row(symbol, score, ltp, signal, is_bull):
    if is_bull:
        bg, brd, txt = GREEN_TINT, "#BFE9D8", GREEN_DARK
    else:
        bg, brd, txt = RED_TINT, "#F3CDC2", RED_DARK
    try:
        score = f"{float(score):.1f}"
    except (TypeError, ValueError):
        pass
    row = f"""
    <div style="background:{bg}; border:1px solid {brd}; border-radius:10px;
                padding:11px 14px; margin-bottom:6px; display:flex; justify-content:space-between;">
        <div>
            <span style="font-weight:700; color:{txt};">{symbol}</span>
            <span class="opl-ext">↗</span>
            <span style="margin-left:10px; font-size:13px; color:{MUTED};">Score: {score}</span>
        </div>
        <div style="font-weight:600; color:{INK};">{_fmt_money(ltp)} • {signal}</div>
    </div>"""
    return _linkify(row, symbol)


# ====================== FOOTER ======================
def render_footer():
    st.divider()
    st.markdown(
        f"<div style='text-align:center; color:#9AA0AC; font-size:12px; padding:4px 0 22px; line-height:1.7;'>"
        "RAO SAHAB ⚡ Intraday &amp; Next-Day Scanner<br>"
        "Data is for analysis &amp; educational purposes only. Not investment advice. Trade at your own risk."
        "</div>",
        unsafe_allow_html=True,
    )


def load_watchlist():
    if "watchlist" not in st.session_state:
        st.session_state.watchlist = []
    return st.session_state.watchlist


# ====================== GOLD & SILVER PANEL ======================
def render_commodity_panel(rep):
    """Full Gold/Silver multi-timeframe panel — Groww style."""
    name, icon, unit = rep["name"], rep["icon"], rep["unit"]
    chg = rep.get("change_pct", 0)
    chg_chip = _chip(f"{'▲' if chg >= 0 else '▼'} {abs(chg)}%", "green" if chg >= 0 else "red")
    sim_chip = _chip("SIMULATED", "gray") if rep.get("simulated") else ""
    qsym = {"GOLD": "GC=F", "SILVER": "SI=F"}.get(name, "GC=F")

    # ---- header ----
    st.markdown(f"""
    <a href="https://finance.yahoo.com/quote/{qsym}" target="_blank" rel="noopener noreferrer"
       title="Open {name} detailed chart ↗" class="opl-link">
    <div class="opl-card" style="padding:16px;">
        <div style="display:flex; align-items:center; gap:10px;">
            <span style="font-size:26px;">{icon}</span>
            <div style="flex:1;">
                <div style="font-size:18px; font-weight:700; color:{HEADING};">{name}<span class="opl-ext">↗</span> {sim_chip}</div>
                <div style="font-size:12px; color:{MUTED};">{unit} • COMEX futures</div>
            </div>
            <div style="text-align:right;">
                <div style="font-size:22px; font-weight:700; color:{INK};">${rep['ltp']:,.2f}</div>
                {chg_chip}
            </div>
        </div>
    </div>
    </a>
    """, unsafe_allow_html=True)

    # ---- multi-timeframe momentum table ----
    rows = ""
    for label, tf in rep["timeframes"].items():
        d = tf["direction"]
        tone = "green" if d == "Bullish" else ("red" if d == "Bearish" else "gray")
        scol = GREEN_DARK if tf["score"] > 0 else (RED_DARK if tf["score"] < 0 else MUTED)
        rows += (
            f'<div style="display:flex; align-items:center; gap:10px; padding:8px 10px; border-bottom:1px solid {GRAY_TINT};">'
            f'<span style="flex:1; font-size:13px; font-weight:600; color:{INK};">{label}</span>'
            f'{_chip(d, tone)}'
            f'<span style="width:78px; text-align:right; font-size:13px; font-weight:700; color:{scol};">{tf["score"]:+.1f} <small style="color:{MUTED}; font-weight:500;">/ 17</small></span>'
            f'</div>'
        )
    st.markdown(f"""
    <div class="opl-card" style="padding:6px 6px 2px 6px;">
        <div style="font-size:13px; font-weight:700; color:{HEADING}; padding:6px 8px 2px;">⏱️ Multi-Timeframe Momentum</div>
        {rows}
    </div>
    """, unsafe_allow_html=True)

    # ---- consensus meter ----
    cons = rep["consensus"]
    w = round(min(abs(cons) / SCORE_MAX, 1.0) * 50, 1)
    if cons >= 0:
        ml, mcol = 50.0, GREEN
    else:
        ml, mcol = round(50.0 - w, 1), RED
    cd = rep["consensus_dir"]
    cd_tone = "green" if "Bullish" in cd else ("red" if "Bearish" in cd else "gray")
    st.markdown(f"""
    <div class="opl-card" style="padding:12px 14px;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
            <span style="font-size:13.5px; font-weight:700; color:{HEADING};">🧭 Multi-TF Consensus</span>
            {_chip(f"{cd} • {cons:+.1f} / 17", cd_tone)}
        </div>
        <div style="position:relative; background:{NEUT_BAR}; border-radius:999px; height:7px;">
            <div style="position:absolute; left:50%; top:-2px; width:2px; height:11px; background:#C9CDD4; border-radius:2px;"></div>
            <div style="position:absolute; left:{ml}%; width:{w}%; background:{mcol}; height:7px; border-radius:999px;"></div>
        </div>
        <div style="font-size:11.5px; color:{MUTED}; margin-top:6px;">🟢 {rep['bull_count']} timeframes bullish • 🔴 {rep['bear_count']} bearish</div>
    </div>
    """, unsafe_allow_html=True)

    # ---- breakout (price + volume) ----
    brk = rep["breakout"]
    if brk["state"] == "up":
        b_icon, b_lbl, b_bg, b_brd, b_col = "🚀", "Upside Breakout", GREEN_TINT, "#BFE9D8", GREEN_DARK
    elif brk["state"] == "down":
        b_icon, b_lbl, b_bg, b_brd, b_col = "⚠️", "Downside Breakdown", RED_TINT, "#F3CDC2", RED_DARK
    else:
        b_icon, b_lbl, b_bg, b_brd, b_col = "⏸️", "Inside 20D Range", GRAY_TINT, BORDER, MUTED
    st.markdown(f"""
    <div style="background:{b_bg}; border:1px solid {b_brd}; border-radius:12px; padding:13px 15px; margin-bottom:10px;">
        <div style="display:flex; justify-content:space-between; align-items:center;">
            <span style="font-size:14px; font-weight:700; color:{b_col};">{b_icon} {b_lbl}</span>
            <span class="chip chip-{'green' if brk['state']=='up' else 'red' if brk['state']=='down' else 'gray'}">{brk['strength']}</span>
        </div>
        <div style="font-size:12.5px; color:{INK}; margin-top:6px;">{brk['note']}</div>
        <div style="font-size:12px; color:{MUTED}; margin-top:3px;">Volume {brk['vol_ratio']}× of 20-day avg • Range {brk['lo20']:,.1f} – {brk['hi20']:,.1f}</div>
    </div>
    """, unsafe_allow_html=True)

    # ---- forecast ----
    with st.container(border=True):
        st.markdown("**🔮 Forecast**")
        st.markdown(rep["forecast"])


# ====================== GOLD & SILVER — AI ANALYSIS CARD ======================
def render_metal_ai_card(rep, analysis=None, news=None):
    """🤖 AI analysis card shown under the Gold/Silver forecast panels.

    Mirrors the AI box on momentum cards: rule-based (or LLM) narrative +
    fresh (≤7 day) news headlines as the likely trigger + free Gemini
    deep-link with a commodity-specific prompt.
    """
    name = rep.get("name", "Metal")
    box = ""
    if analysis:
        box = (f'<div style="margin-top:9px;background:{GRAY_TINT};border-radius:8px;'
               f'padding:9px 11px;font-size:12.5px;color:{INK};line-height:1.55;">'
               f'💡 {html_escape(str(analysis))}</div>')

    gemini_prompt = (
        f"Give a complete technical analysis of {name} (COMEX futures, USD/oz): "
        f"current trend and momentum across 15-minute, daily, weekly, monthly and yearly "
        f"timeframes, key support/resistance levels, recent news and macro drivers "
        f"(Fed policy, USD index, inflation), and the most likely reasons behind its "
        f"recent price move. End with a short risk summary. Do not give buy/sell advice."
    )

    st.markdown(f"""
    <div class="opl-card" style="padding:12px 14px; margin-top:10px;">
        <div style="font-size:12px; font-weight:800; letter-spacing:.6px;
                    color:{MUTED}; margin-bottom:3px;">🤖 AI ANALYSIS</div>
        {box}
        {news_links(news)}
        {gemini_ai_link(name, prompt=gemini_prompt)}
    </div>
    """, unsafe_allow_html=True)


# ====================== JAIPUR BULLION RATES (INR) ======================
def _inr_fmt(n):
    """Indian-style number grouping: 159420 -> '1,59,420'."""
    try:
        s = str(int(n))
    except (TypeError, ValueError):
        return "—"
    if len(s) <= 3:
        return s
    head, tail = s[:-3], s[-3:]
    groups = []
    while head:
        groups.append(head[-2:])
        head = head[:-2]
    return ",".join(reversed(groups)) + "," + tail


def _chg_chip(chg):
    if chg is None:
        return '<span class="chip chip-gray">—</span>'
    if chg >= 0:
        return f'<span class="chip chip-green">▲ ₹{_inr_fmt(chg)}</span>'
    return f'<span class="chip chip-red">▼ ₹{_inr_fmt(abs(chg))}</span>'


def render_jaipur_rates_card(rates):
    """🇮🇳 Today's Jaipur gold/silver INR rates (per 10g / per kg)."""
    date = rates.get("date", "Today")
    derived = rates.get("source") == "derived"
    usd_inr = rates.get("usd_inr")

    src_html = (
        f'<span style="font-size:11px;color:{MUTED};">⚠️ Derived from COMEX × USD/INR'
        f'{" (₹" + f"{usd_inr:,.2f}" + ")" if usd_inr else ""} — indicative, local '
        f'premium may differ</span>'
        if derived else
        f'<a href="{rates.get("url", "#")}" target="_blank" rel="noopener noreferrer" '
        f'style="font-size:11px;color:{MUTED};text-decoration:none;border-bottom:1px dotted {BORDER};">'
        f'Source: GoodReturns · Jaipur ↗</a>'
    )

    def _tile(icon, label, val, chg, sub):
        return (
            f'<div style="flex:1;min-width:120px;background:{GRAY_TINT};border:1px solid {BORDER};'
            f'border-radius:12px;padding:10px 12px;text-align:center;">'
            f'<div style="font-size:11.5px;font-weight:800;letter-spacing:.5px;color:{MUTED};">'
            f'{icon} {label}</div>'
            f'<div style="font-size:21px;font-weight:800;color:{INK};margin-top:3px;">₹{_inr_fmt(val)}</div>'
            f'<div style="font-size:10.5px;color:{MUTED};margin-top:1px;">{sub}</div>'
            f'<div style="margin-top:5px;">{_chg_chip(chg)}</div></div>'
        )

    tiles = "".join([
        _tile("🪙", "GOLD 24K", rates["gold_24k_10g"], rates.get("gold_24k_chg"), "per 10 gram"),
        _tile("🪙", "GOLD 22K", rates["gold_22k_10g"], rates.get("gold_22k_chg"), "per 10 gram"),
        _tile("🥈", "SILVER", rates["silver_kg"], rates.get("silver_chg"), "per 1 kg"),
    ])

    # 7-day trend table
    hist = rates.get("history") or []
    rows_html = ""
    if hist:
        for h in hist:
            rows_html += (
                f'<tr><td style="padding:4px 10px;">{html_escape(str(h.get("date", "")))}</td>'
                f'<td style="padding:4px 10px;text-align:right;">₹{_inr_fmt(h.get("gold_24k"))}</td>'
                f'<td style="padding:4px 10px;text-align:right;">₹{_inr_fmt(h.get("gold_22k"))}</td>'
                f'<td style="padding:4px 10px;text-align:right;">₹{_inr_fmt(h.get("silver"))}</td></tr>'
            )
    details = (
        f'<details style="margin-top:10px;font-size:12px;color:{MUTED};">'
        f'<summary style="cursor:pointer;font-weight:700;color:{INK};">📅 7-day trend (Jaipur)</summary>'
        f'<div style="overflow-x:auto;margin-top:6px;">'
        f'<table style="border-collapse:collapse;width:100%;font-size:12px;color:{INK};">'
        f'<tr style="color:{MUTED};font-size:11px;text-align:left;">'
        f'<th style="padding:4px 10px;">Date</th>'
        f'<th style="padding:4px 10px;text-align:right;">Gold 24K /10g</th>'
        f'<th style="padding:4px 10px;text-align:right;">Gold 22K /10g</th>'
        f'<th style="padding:4px 10px;text-align:right;">Silver /kg</th></tr>'
        f'{rows_html}</table></div></details>'
        if hist else ""
    )

    st.markdown(f"""
    <div class="opl-card" style="padding:12px 14px;margin-bottom:12px;">
        <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:6px;">
            <span style="font-size:14px;font-weight:800;color:{HEADING};">🇮🇳 Jaipur Bullion Rates (INR)</span>
            <span style="font-size:12px;color:{MUTED};font-weight:700;">{html_escape(str(date))}</span>
        </div>
        <div style="display:flex;gap:10px;margin-top:10px;flex-wrap:wrap;">{tiles}</div>
        <div style="margin-top:8px;">{src_html}</div>
        {details}
    </div>
    """, unsafe_allow_html=True)
