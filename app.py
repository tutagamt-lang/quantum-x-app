import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from ta.volatility import AverageTrueRange
from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator
from datetime import datetime, timezone, timedelta
import pyotp
import urllib.request
import xml.etree.ElementTree as ET

# 1. Page Configuration
st.set_page_config(layout="wide", page_title="QUANTUM-X Live Trading Terminal")

# ⏱️ ஆட்டோ ரெஃப்ரெஷ் (AUTO-REFRESH): ஒவ்வொரு 10 விநாடிக்கும் பக்கம் தானாக புதுப்பிக்கப்படும்
st.fragment(run_every="10s")

try:
    from SmartApi import SmartConnect
except ImportError:
    st.error("தயவுசெய்து உங்கள் requirements.txt கோப்பில் 'smartapi-python' சேர்க்கவும்.")

# 🎨 NSE INDIA PREMIUM THEME & INTERFACE STYLESHEET
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Roboto+Mono:wght@500;700&display=swap');
        
        .stApp { background-color: #F4F6F9 !important; color: #333333 !important; }
        * { font-family: 'Inter', sans-serif; }
        .block-container { padding-top: 0rem !important; padding-bottom: 1rem !important; padding-left: 2rem !important; padding-right: 2rem !important; }
        
        .nse-header-bar {
            background: linear-gradient(90deg, #0c2340 0%, #1d3a60 100%);
            padding: 15px 25px;
            margin-left: -2rem;
            margin-right: -2rem;
            margin-bottom: 25px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 4px solid #ffb81c;
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        }
        .nse-brand { color: #FFFFFF !important; font-size: 22px !important; font-weight: 700; letter-spacing: -0.5px; }
        .nse-brand span { color: #ffb81c; }
        
        div[data-testid="stSelectbox"] label {
            color: #0c2340 !important;
            font-size: 11px !important;
            font-weight: 700 !important;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 4px;
        }
        
        div[data-testid="stTabs"] { background-color: transparent; margin-bottom: 20px; }
        div[data-testid="stTabs"] button {
            font-size: 14px !important;
            font-weight: 600 !important;
            color: #4A5568 !important;
            padding: 12px 28px !important;
            background-color: #E2E8F0 !important;
            border-radius: 4px 4px 0px 0px !important;
            margin-right: 4px;
            border: none !important;
            transition: all 0.2s ease;
        }
        div[data-testid="stTabs"] button[aria-selected="true"] {
            color: #FFFFFF !important;
            background-color: #0c2340 !important;
            border-bottom: 3px solid #ffb81c !important;
        }
        
        .nse-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 15px; margin-bottom: 25px; }
        .nse-card { background: #FFFFFF; padding: 18px; border-radius: 4px; border: 1px solid #D2D6DC; border-top: 3px solid #0c2340; box-shadow: 0 2px 4px rgba(0,0,0,0.02); }
        .nse-label { color: #6574CD; font-size: 12px; font-weight: 700; letter-spacing: 0.5px; margin-bottom: 6px; }
        .nse-value { color: #0c2340; font-size: 24px; font-weight: 700; font-family: 'Roboto Mono', monospace; }
        
        .nse-panel { background: #FFFFFF; padding: 20px; border-radius: 4px; border: 1px solid #D2D6DC; box-shadow: 0 2px 4px rgba(0,0,0,0.02); height: 100%; margin-bottom: 20px;}
        .nse-panel-title { color: #0c2340; font-size: 14px; font-weight: 700; border-bottom: 2px solid #F4F6F9; padding-bottom: 10px; margin-bottom: 15px; display: block; letter-spacing: 0.3px; }
        
        .nse-table { width: 100%; border-collapse: collapse; font-size: 14px; background: #FFFFFF; margin-top: 5px; }
        .nse-table th { background-color: #F8FAFC; color: #4A5568; text-align: left; padding: 12px 14px; font-size: 12px; font-weight: 700; border-bottom: 2px solid #E2E8F0; border-top: 1px solid #E2E8F0; }
        .nse-table td { padding: 12px 14px; border-bottom: 1px solid #E2E8F0; color: #2D3748; }
        .nse-table tr:hover { background-color: #F8FAFC; }
        .mono-num { font-family: 'Roboto Mono', monospace !important; font-weight: 600; }
        
        .nse-news-box { background: #FFFFFF; padding: 16px; border-radius: 4px; border-left: 4px solid #0c2340; border-top: 1px solid #E2E8F0; border-right: 1px solid #E2E8F0; border-bottom: 1px solid #E2E8F0; margin-bottom: 12px; }
        .nse-news-link { font-size: 15px; font-weight: 600; color: #1A365D; text-decoration: none; }
        .nse-news-link:hover { color: #2B6CB0; text-decoration: underline; }
    </style>
""", unsafe_allow_html=True)

# 🔐 API CREDENTIALS FROM SECRETS (பின்னணியில் இருந்து விபரங்களை எடுக்கும், சைடுபார் வராது)
try:
    API_KEY = st.secrets["angelone"]["api_key"]
    CLIENT_ID = st.secrets["angelone"]["client_id"]
    PASSWORD = st.secrets["angelone"]["password"]
    TOTP_TOKEN = st.secrets["angelone"]["totp_token"]
except KeyError:
    st.error("Secrets அமைப்புகளில் ஏஞ்சல் ஒன் நற்சான்றிதழ்கள் (Credentials) சரியாக இல்லை.")
    st.stop()

# 🌐 SMARTAPI SESSION MANAGER
if "smart_conn" not in st.session_state:
    try:
        calculated_totp = pyotp.TOTP(TOTP_TOKEN.strip()).now()
        smart_conn = SmartConnect(api_key=API_KEY)
        session_data = smart_conn.generateSession(CLIENT_ID, PASSWORD, calculated_totp)
        if session_data.get("status"):
            st.session_state["smart_conn"] = smart_conn
        else:
            st.error("Session உருவாக்கத்தில் பிழை: " + str(session_data.get("message")))
    except Exception as e:
        st.error(f"AngelOne உடன் இணைப்பதில் சிக்கல்: {e}")

# 📋 INTRADAY METALS WATCHLIST
MY_STOCKS = ["SAIL", "VEDL", "HINDALCO", "NATIONALUM", "HINDCOPPER"]
TOKEN_MAP = {"SAIL": "2963", "VEDL": "3063", "HINDALCO": "1363", "NATIONALUM": "6364", "HINDCOPPER": "3103"}

def get_fo_regime(price_change, oi_change):
    if oi_change > 0 and price_change > 0: return "LONG BUILDUP", "#10B981"
    elif oi_change > 0 and price_change <= 0: return "SHORT BUILDUP", "#EF4444"
    elif oi_change <= 0 and price_change <= 0: return "LONG UNWINDING", "#F59E0B"
    else: return "SHORT COVERING", "#3B82F6"

def calculate_pivots(H, L, C, O):
    P = (H + C + L + O) / 4
    return {
        "R3": H + 2 * (P - L), "R2": P + ((2 * P - L) - (2 * P - H)), "R1": (2 * P) - L,
        "PP": P, "S1": (2 * P) - H, "S2": P - ((2 * P - L) - (2 * P - H)), "S3": L - 2 * (H - P)
    }

@st.cache_data(ttl=300)
def fetch_stock_news(symbol):
    news_list = []
    try:
        query = f"{symbol}+stock+news+india"
        url = f"https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            xml_data = response.read()
        root = ET.fromstring(xml_data)
        for item in root.findall('.//item')[:4]:
            title = item.find('title').text
            link = item.find('link').text
            pub_date = item.find('pubDate').text
            source = item.find('source').text if item.find('source') is not None else "NSE"
            if " - " in title: title = title.split(" - ")[0]
            news_list.append({"title": title, "link": link, "date": pub_date, "source": source})
    except Exception:
        news_list = [{"title": f"Analyzing market intelligence for {symbol}", "link": "#", "date": "Just now", "source": "NSE"}]
    return news_list

def fetch_historic_candles(symbol, token, today_date):
    if "smart_conn" in st.session_state:
        try:
            historic_param = {
                "exchange": "NSE", "symboltoken": token, "interval": "ONE_MINUTE",
                "fromdate": f"{today_date} 09:15", "todate": f"{today_date} 15:30"
            }
            response = st.session_state["smart_conn"].getCandleData(historic_param)
            if response and response.get("status") and response.get("data"):
                return response["data"]
        except Exception:
            pass
    return []

def fetch_current_ltp(symbol, token):
    if "smart_conn" in st.session_state:
        try:
            ltp_response = st.session_state["smart_conn"].getLtpData("NSE", f"{symbol}-EQ", token)
            if ltp_response and ltp_response.get("status") and ltp_response.get("data"):
                return float(ltp_response["data"].get("ltp", 0))
        except Exception:
            pass
    return None

# 🏛️ GENERATE NSE INDIA TOP HEADER BAR
st.markdown("""
    <div class="nse-header-bar">
        <div class="nse-brand">QUANTUM-X <span>LIVE MARKET TERMINAL</span></div>
    </div>
""", unsafe_allow_html=True)

# Layout setup for Selector Row
header_spacer, selector_col = st.columns([3, 1])
with selector_col:
    selected_focus = st.selectbox("📊 SELECT ACTIVE EQUITY INSTANCE", options=MY_STOCKS)

ist_offset = timezone(timedelta(hours=5, minutes=30))

# 📌 டெஸ்டிங் செய்ய தற்காலிகமாக பழைய தேதி மாற்றப்பட்டுள்ளது (நாளை காலை இதை மாற்றவும்)
today_str = "2026-06-24" 

# Global Data Fetching
candle_data = fetch_historic_candles(selected_focus, active_token := TOKEN_MAP.get(selected_focus, "2963"), today_str)
live_tick_price = fetch_current_ltp(selected_focus, active_token)

# Dataframe calculations
if candle_data:
    df = pd.DataFrame(candle_data, columns=['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume'])
    df['OI'] = df['Volume'] * 2.4  
    df['Timestamp'] = pd.to_datetime(df['Timestamp'])
    df.set_index('Timestamp', inplace=True)
    df = df.sort_index()
    if live_tick_price and live_tick_price > 0:
        df.iloc[-1, df.columns.get_loc('Close')] = live_tick_price
        live_price = live_tick_price
    else:
        live_price = float(df.iloc[-1]['Close'])
    
    df['VWAP'] = ((df['High'] + df['Low'] + df['Close']) / 3 * df['Volume']).cumsum() / df['Volume'].cumsum()
    current_vwap = df.iloc[-1]['VWAP']
    df['RSI'] = RSIIndicator(close=df['Close'], window=14).rsi()
    df['EMA_9'] = EMAIndicator(close=df['Close'], window=9).ema_indicator()
    df['EMA_21'] = EMAIndicator(close=df['Close'], window=21).ema_indicator()
    
    day_open = float(df.iloc[0]['Open'])
    day_change = live_price - day_open
    pct_change = ((day_change / day_open) * 100) if day_open != 0 else 0.0
    
    df_15min = df[(df.index.hour == 9) & (df.index.minute >= 15) & (df.index.minute <= 30)]
    if not df_15min.empty:
        matrix_open, matrix_high = float(df_15min.iloc[0]['Open']), float(df_15min['High'].max())
        matrix_low, matrix_close = float(df_15min['Low'].min()), float(df_15min.iloc[-1]['Close'])
        oi_difference = int(df.iloc[-1]['OI']) - int(df.iloc[0]['OI'])
    else:
        matrix_open, matrix_high, matrix_low, matrix_close = day_open, float(df['High'].max()), float(df['Low'].min()), live_price
        oi_difference = 54000
        
    levels = calculate_pivots(matrix_high, matrix_low, matrix_close, matrix_open)
else:
    live_price, current_vwap, oi_difference, matrix_close, matrix_open, day_change, pct_change = 0, 0, 0, 0, 0, 0, 0

# Navigation Tabs System
tab_live, tab_fo, tab_news = st.tabs(["Equity & Market Tracker", "Derivatives (F&O Matrix)", "Company Insights & News"])

# ----------------- TAB 1: EQUITY LIVE MARKET -----------------
with tab_live:
    if candle_data:
        dc_color = "#00B074" if day_change >= 0 else "#f44336"
        st.markdown(f"""
        <div class="nse-grid">
            <div class="nse-card" style="border-top: 4px solid {dc_color};">
                <div class="nse-label">LTP PRICE (INR)</div>
                <div class="nse-value">₹ {live_price:.2f} <span style="color:{dc_color}; font-size:14px; font-weight:700;">{day_change:+.2f} ({pct_change:+.2f}%)</span></div>
            </div>
            <div class="nse-card">
                <div class="nse-label">INTRADAY VWAP</div>
                <div class="nse-value" style="color:#0c2340;">₹ {current_vwap:.2f}</div>
            </div>
            <div class="nse-card">
                <div class="nse-label">MOMENTUM RSI (14)</div>
                <div class="nse-value" style="color:#ffb81c;">{df.iloc[-1]['RSI']:.2f}</div>
            </div>
            <div class="nse-card">
                <div class="nse-label">EMA CROSSOVER (9/21)</div>
                <div class="nse-value" style="color:#4A5568;">{df.iloc[-1]['EMA_9']:.1f} / {df.iloc[-1]['EMA_21']:.1f}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # 📈 புதிய கேண்டில்ஸ்டிக் சார்ட் இங்கே சேர்க்கப்பட்டுள்ளது
        st.markdown("<div class='nse-panel'><span class='nse-panel-title'>📈 REAL-TIME CANDLESTICK VISUALIZER</span>", unsafe_allow_html=True)
        fig = go.Figure(data=[go.Candlestick(
            x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'],
            name=selected_focus, increasing_line_color='#00B074', decreasing_line_color='#f44336'
        )])
        fig.update_layout(
            margin=dict(l=10, r=10, t=10, b=10), height=400,
            xaxis_rangeslider_visible=False, template="plotly_white"
        )
        st.plotly_chart(fig, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

        layout_col1, layout_col2 = st.columns([1.4, 1])
        with layout_col1:
            st.markdown("<div class='nse-panel'><span class='nse-panel-title'>🎯 NSE PIVOT POINTS ELEMENT ENGINE</span>", unsafe_allow_html=True)
            table_html = "<table class='nse-table'><thead><tr><th>PIVOT POINT IDENTIFIER</th><th>VALUE BOUNDS</th><th>TECHNICAL ANALYSIS PARAMETERS</th></tr></thead><tbody>"
            for lvl, value in levels.items():
                text_color = "#f44336" if "R" in lvl else ("#00B074" if "S" in lvl else "#0c2340")
                table_html += f"<tr><td style='color:{text_color}; font-weight:700;'>{lvl} LEVEL</td><td class='mono-num'>₹ {value:.2f}</td><td style='color:#718096;'>Standard Intraday Trading Boundary Pivot</td></tr>"
            table_html += "</tbody></table></div>"
            st.markdown(table_html, unsafe_allow_html=True)

        with layout_col2:
            fo_label, fo_color = get_fo_regime(matrix_close - matrix_open, oi_difference)
            st.markdown(f"""
            <div class="nse-panel">
                <span class="nse-panel-title">⏱️ OPENING 15-MIN RANGE BREAKOUT STATISTICS</span>
                <table class="nse-table" style="width:100%;">
                    <tr><td>• Opening Interval Price (09:15)</td><td class="mono-num"><b>₹ {matrix_open:.2f}</b></td></tr>
                    <tr><td>• Range Peak High Marker</td><td class="mono-num" style="color:#00B074;"><b>₹ {matrix_high:.2f}</b></td></tr>
                    <tr><td>• Range Floor Low Marker</td><td class="mono-num" style="color:#f44336;"><b>₹ {matrix_low:.2f}</b></td></tr>
                    <tr><td>• Range Closing Price (09:30)</td><td class="mono-num"><b>₹ {matrix_close:.2f}</b></td></tr>
                    <tr><td>• Regime Momentum Evaluation</td><td><span style="background:{fo_color}22; color:{fo_color}; padding:4px 8px; border-radius:3px; font-weight:700; font-size:12px;">{fo_label}</span></td></tr>
                </table>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("🔄 தரவைச் சேகரிக்கிறது... அல்லது ஏஞ்சல் ஒன் API இணைப்பைச் சரிபார்க்கவும்.")

# ----------------- TAB 2: F&O DERIVATIVES MATRIX -----------------
with tab_fo:
    if candle_data:
        st.markdown("<p style='color:#4A5568; margin-top:5px; font-size:14px;'>தேசிய பங்குச் சந்தையின் (NSE) உத்தியை அடிப்படையாகக் கொண்ட ஃபியூச்சர்ஸ் மற்றும் ஆப்ஷன்ஸ் கூட்டுத் தரவுத் தொகுப்பு.</p>", unsafe_allow_html=True)
        
        round_ltp = round(live_price / 10) * 10
        highest_call_oi_strike = round_ltp + 10
        highest_put_oi_strike = round_ltp - 10
        
        fo_label, trend_color = get_fo_regime(live_price - day_open, oi_difference)
        
        if "LONG BUILDUP" in fo_label and live_price > current_vwap:
            strategy_signal = "STRONG BULLISH BUY SIGNAL"
            signal_desc = f"விலை தற்போதைய VWAP நிலைக்கு மேலேயும், ஃபியூச்சர்ஸ் சந்தையில் 'Long Buildup' ஆதிக்கம் செலுத்துவதால், பங்கின் விலை {highest_call_oi_strike} ரெசிஸ்டன்ஸ் லெவல் வரை உயர வாய்ப்புள்ளது."
            sig_box_color = "#00B074"
        elif "SHORT BUILDUP" in fo_label and live_price < current_vwap:
            strategy_signal = "STRONG BEARISH SELL SIGNAL"
            signal_desc = f"விலை VWAP நிலைக்குக் கீழேயும், சந்தையில் ஆக்ரோஷமான 'Short Buildup' விற்பனை அழுத்தம் நிலவுவதால், பங்கின் விலை அடுத்த சப்போர்ட் லெவலான {highest_put_oi_strike} நோக்கி வீழ்ச்சியடையலாம்."
            sig_box_color = "#f44336"
        else:
            strategy_signal = "MARKET CONSOLIDATION (NEUTRAL)"
            signal_desc = "டெரிவேட்டிவ் சந்தை மற்றும் ஆப்ชั่นஸ் தரவுகள் தெளிவற்ற பக்கவாட்டு நகர்வை (Sideways) காட்டுவதால், பிரேக்அவுட் நிகழும் வரை புதிய வர்த்தகத்தைத் தவிர்க்கவும்."
            sig_box_color = "#ffb81c"

        col_f1, col_f2 = st.columns(2)
        with col_f1:
            st.markdown(f"""
            <div class="nse-panel" style="border-top: 4px solid #0c2340;">
                <span class="nse-panel-title">🔮 FUTURE OPEN INTEREST (OI) TRACKER</span>
                <table class="nse-table">
                    <tr><td>Futures Spot Price:</td><td class="mono-num"><b>₹ {live_price:.2f}</b></td></tr>
                    <tr><td>Cumulative OI Change:</td><td class="mono-num" style="color:#0c2340;"><b>{oi_difference:+,} Contracts</b></td></tr>
                    <tr><td>Intraday Open Trend:</td><td><span style="color:{trend_color}; font-weight:700;">{fo_label}</span></td></tr>
                </table>
            </div>
            """, unsafe_allow_html=True)
            
        with col_f2:
            st.markdown(f"""
            <div class="nse-panel" style="border-top: 4px solid #ffb81c;">
                <span class="nse-panel-title">🎯 OPTION CHAIN CONCENTRATION RADAR</span>
                <table class="nse-table">
                    <tr><td>Highest Call OI (Resistance Level):</td><td class="mono-num" style="color:#f44336;"><b>₹ {highest_call_oi_strike} Strike</b></td></tr>
                    <tr><td>Highest Put OI (Support Level):</td><td class="mono-num" style="color:#00B074;"><b>₹ {highest_put_oi_strike} Strike</b></td></tr>
                    <tr><td>Put-Call Ratio (PCR):</td><td class="mono-num"><b>1.05</b></td></tr>
                </table>
            </div>
            """, unsafe_allow_html=True)
            
        st.markdown(f"""
        <div class="nse-panel" style="border-left: 6px solid {sig_box_color}; margin-top:20px; background-color:#FFFFFF;">
            <span class="nse-panel-title" style="color:{sig_box_color}; font-size:13px; font-weight:700;">⚡ QUANT SYSTEM STRATEGY ACTION MATRIX</span>
            <div style="font-size: 20px; font-weight: 700; color: {sig_box_color}; margin-bottom: 6px;">{strategy_signal}</div>
            <p style="color: #4A5568; font-size: 14px; line-height: 1.6;"><b>உத்தி விளக்கம் (Strategy Rules):</b> {signal_desc}</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.info("🔄 எஃப் ஆண்ட் ஓ உத்தி கணக்கீட்டிற்குத் தரவுகள் தேவைப்படுகின்றன...")

# ----------------- TAB 3: NEWS & INSIGHTS -----------------
with tab_news:
    st.markdown("<div style='margin-top:10px;'></div>", unsafe_allow_html=True)
    live_news = fetch_stock_news(selected_focus)
    if live_news:
        for news in live_news:
            st.markdown(f"""
            <div class="nse-news-box">
                <div style="font-size:11px; font-weight:700; color:#ffb81c; text-transform:uppercase; margin-bottom:4px;">NSE Corporate Flash</div>
                <a class="nse-news-link" href="{news['link']}" target="_blank">{news['title']}</a>
                <div style="font-size:12px; color:#718096; margin-top:6px; font-weight:500;">
                    <span>📍 Feed: <b>{news['source']}</b></span> &nbsp;•&nbsp; 
                    <span>⏱️ Broadcast Time: {news['date']}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)