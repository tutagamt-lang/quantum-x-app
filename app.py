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
import threading
import time
import json
import streamlit as st

# 1. Page Configuration
st.set_page_config(layout="centered", page_title="QUANTUM-X Live Trading Terminal")

try:
    from SmartApi import SmartConnect
    from SmartApi.smartWebSocketV2 import SmartWebSocketV2
except ImportError:
    st.error("தயவுசெய்து உங்கள் requirements.txt கோப்பில் 'smartapi-python' சேர்க்கவும்.")

# 🎨 NSE INDIA PREMIUM BOXED THEME
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght=400;500;600;700&family=Roboto+Mono:wght=500;700&display=swap');
        .stApp { background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%) !important; color: #333333 !important; }
        * { font-family: 'Inter', sans-serif; }
        .block-container { 
            max-width: 900px !important; padding-top: 2rem !important; padding-bottom: 2rem !important; 
            background-color: #F8FAFC !important; border-radius: 12px !important;
            box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.3) !important; margin-top: 2rem !important;
        }
        .nse-header-bar {
            background: linear-gradient(90deg, #0c2340 0%, #1d3a60 100%); padding: 18px 25px;
            margin: -2rem -4rem 25px -4rem; display: flex; justify-content: space-between; align-items: center;
            border-top-left-radius: 12px; border-top-right-radius: 12px; border-bottom: 4px solid #ffb81c;
        }
        .nse-brand { color: #FFFFFF !important; font-size: 20px !important; font-weight: 700; }
        .nse-brand span { color: #ffb81c; }
        .nse-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin-bottom: 25px; }
        .nse-card { background: #FFFFFF; padding: 15px; border-radius: 6px; border: 1px solid #E2E8F0; border-top: 3px solid #0c2340; }
        .nse-label { color: #6574CD; font-size: 11px; font-weight: 700; }
        .nse-value { color: #0c2340; font-size: 20px; font-weight: 700; font-family: 'Roboto Mono', monospace; }
        .nse-panel { background: #FFFFFF; padding: 20px; border-radius: 8px; border: 1px solid #E2E8F0; margin-bottom: 20px; }
        .nse-panel-title { color: #0c2340; font-size: 13px; font-weight: 700; border-bottom: 2px solid #F1F5F9; padding-bottom: 10px; margin-bottom: 15px; }
        .nse-table { width: 100%; border-collapse: collapse; font-size: 13px; }
        .nse-table th { background-color: #F8FAFC; color: #4A5568; padding: 10px 12px; font-size: 11px; font-weight: 700; border-bottom: 2px solid #E2E8F0; }
        .nse-table td { padding: 10px 12px; border-bottom: 1px solid #E2E8F0; }
        .mono-num { font-family: 'Roboto Mono', monospace !important; font-weight: 600; }
        .nse-news-box { background: #FFFFFF; padding: 14px; border-radius: 6px; border-left: 4px solid #0c2340; border-bottom: 1px solid #E2E8F0; margin-bottom: 12px; }
        .nse-news-link { font-size: 14px; font-weight: 600; color: #1A365D; text-decoration: none; }
    </style>
""", unsafe_allow_html=True)

# 🔐 API CREDENTIALS FROM SECRETS
try:
    API_KEY = st.secrets["angelone"]["api_key"]
    CLIENT_ID = st.secrets["angelone"]["client_id"]
    PASSWORD = st.secrets["angelone"]["password"]
    TOTP_TOKEN = st.secrets["angelone"]["totp_token"]
except KeyError:
    st.error("Secrets அமைப்புகளில் ஏஞ்சல் ஒன் நற்சான்றிதழ்கள் சரியாக இல்லை.")
    st.stop()

# 🌐 SMARTAPI SESSION MANAGER
if "smart_conn" not in st.session_state:
    try:
        calculated_totp = pyotp.TOTP(TOTP_TOKEN.strip()).now()
        smart_conn = SmartConnect(api_key=API_KEY)
        session_data = smart_conn.generateSession(CLIENT_ID, PASSWORD, calculated_totp)
        if session_data.get("status"):
            st.session_state["smart_conn"] = smart_conn
            st.session_state["jwt_token"] = session_data["data"]["jwtToken"]
            st.session_state["feed_token"] = session_data["data"]["feedToken"]
            st.toast("🎉 Angel One SmartAPI Session இணைக்கப்பட்டது!", icon="✅")
        else:
            st.error(f"❌ Session பிழை: {session_data.get('message')}")
    except Exception as e:
        st.error(f"🚨 AngelOne இணைப்புச் சிக்கல்: {e}")

# 📋 INTRADAY METALS WATCHLIST & TOKEN MAP (DEFAULT STOCKS)
MY_STOCKS = ["SAIL", "VEDL", "HINDALCO", "NATIONALUM", "HINDCOPPER"]
TOKEN_MAP = {"SAIL": "2963", "VEDL": "3063", "HINDALCO": "1363", "NATIONALUM": "6364", "HINDCOPPER": "3103"}

# 🌐 NSE ALL STOCKS TOKEN SEARCH LOADER
@st.cache_data(ttl=86400)
def load_all_nse_tokens():
    try:
        url = "https://margincalculator.angelbroking.com/OpenAPI_ScripMaster/OpenAPIScripMaster.json"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            token_dict = {item['symbol'].replace("-EQ", ""): item['token'] for item in data if item['exch_seg'] == 'NSE' and item['symbol'].endswith('-EQ')}
            return token_dict
    except Exception:
        return TOKEN_MAP

ALL_NSE_TOKENS = load_all_nse_tokens()
ALL_STOCK_KEYS = sorted(list(set(MY_STOCKS + list(ALL_NSE_TOKENS.keys()))))

# ⚡ WEBSOCKET LIVE PRICE BUFFER
if "live_prices" not in st.session_state:
    st.session_state["live_prices"] = {token: 0.0 for token in TOKEN_MAP.values()}

# 📡 WEBSOCKET BACKGROUND THREAD MANAGER
def start_websocket_streaming():
    def on_data(wsapp, msg):
        if msg and 'last_traded_price' in msg:
            token = msg.get('token')
            ltp = float(msg.get('last_traded_price', 0)) / 100
            if token in st.session_state["live_prices"]:
                st.session_state["live_prices"][token] = ltp

    def on_open(wsapp):
        correlation_id = "quantum_x_stream"
        action = 1
        mode = 3
        token_list = [{"exchangeType": 1, "tokens": list(TOKEN_MAP.values())}]
        wsapp.subscribe(correlation_id, action, mode, token_list)

    def on_error(wsapp, error): pass
    def on_close(wsapp, close_status_code, close_msg): pass

    if "ws_started" not in st.session_state and "smart_conn" in st.session_state:
        try:
            sws = SmartWebSocketV2(
                st.session_state["jwt_token"],
                API_KEY,
                CLIENT_ID,
                st.session_state["feed_token"]
            )
            sws.on_open = on_open
            sws.on_data = on_data
            sws.on_error = on_error
            sws.on_close = on_close
            
            t = threading.Thread(target=sws.connect, daemon=True)
            t.start()
            st.session_state["ws_started"] = True
        except Exception: pass

if "smart_conn" in st.session_state:
    start_websocket_streaming()

# --- பழைய உத்தி கணக்கீடு ---
def get_fo_regime(price_change, oi_change):
    if oi_change > 0 and price_change > 0: return "Long Buildup", "#10B981"
    elif oi_change > 0 and price_change <= 0: return "Short Buildup", "#EF4444"
    elif oi_change <= 0 and price_change <= 0: return "Profit Booking", "#F59E0B"
    else: return "Short Covering", "#3B82F6"

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
            news_list.append({"title": title.split(" - ")[0] if " - " in title else title, "link": link, "date": item.find('pubDate').text, "source": item.find('source').text if item.find('source') is not None else "NSE"})
    except Exception:
        news_list = [{"title": f"Analyzing market intelligence for {symbol}", "link": "#", "date": "Just now", "source": "NSE"}]
    return news_list

@st.cache_data(ttl=60)
def fetch_historic_candles(symbol, token, target_date):
    if "smart_conn" in st.session_state:
        try:
            historic_param = {
                "exchange": "NSE", "symboltoken": token, "interval": "ONE_MINUTE",
                "fromdate": f"{target_date} 09:15", "todate": f"{target_date} 15:30"
            }
            response = st.session_state["smart_conn"].getCandleData(historic_param)
            if response and response.get("status") and response.get("data"):
                return response["data"]
        except Exception: pass
    return []

# 🏛️ INTERFACE HEADER
st.markdown('<div class="nse-header-bar"><div class="nse-brand">QUANTUM-X <span>LIVE MARKET TERMINAL</span></div></div>', unsafe_allow_html=True)

# 🔍 ANY NSE STOCKS SELECTOR DRIVER
header_spacer, selector_col = st.columns([1.2, 1])
with selector_col:
    selected_focus = st.selectbox("🔍 SELECT OR SEARCH ANY NSE STOCK", options=ALL_STOCK_KEYS, index=ALL_STOCK_KEYS.index("SAIL") if "SAIL" in ALL_STOCK_KEYS else 0)

ist_offset = timezone(timedelta(hours=5, minutes=30))
today_dt = datetime.now(ist_offset)
today_str = today_dt.strftime("%Y-%m-%d")

# டோக்கன் கண்டறிதல்
active_token = ALL_NSE_TOKENS.get(selected_focus, "2963")

# புதிய ஸ்டாக் என்றால் லைவ் பப்பரில் உடனே சேர்த்தல்
if active_token not in st.session_state["live_prices"]:
    st.session_state["live_prices"][active_token] = 0.0

# 📡 🔄 [மாற்றம்] ஏஞ்சல் ஒன் மார்க்கெட் டேட்டா API மூலம் உண்மையான எக்ஸ்சேஞ்ச் Live Future OI பெறுதல்
exchange_live_oi = 0
if "smart_conn" in st.session_state:
    try:
        # MODE 3 (FULL) அல்லது MODE 1 பயன்படுத்தி ஓப்பன் இன்ட்ரெஸ்ட் எடுக்கப்படுகிறது
        payload = {
            "correlationId": "quantum_x_oi",
            "action": 1,
            "mode": 3,
            "tokenList": [{"exchangeType": 1, "tokens": [active_token]}]
        }
        market_data = st.session_state["smart_conn"].getMarketData(mode="FULL", data=payload)
        if market_data and 'data' in market_data and 'fetched' in market_data['data'] and len(market_data['data']['fetched']) > 0:
            exchange_live_oi = int(market_data['data']['fetched'][0].get('openInterest', 0))
    except Exception:
        pass

candle_data = fetch_historic_candles(selected_focus, active_token, today_str)
if not candle_data:
    for i in range(1, 5):
        fallback_date = (today_dt - timedelta(days=i)).strftime("%Y-%m-%d")
        candle_data = fetch_historic_candles(selected_focus, active_token, fallback_date)
        if candle_data: break

ws_price = st.session_state["live_prices"].get(active_token, 0.0)

# OI மதிப்புகள் ஆரம்பநிலை அமைவு
oi_915 = 0
oi_930 = 0
live_oi_value = 0
live_oi_change = 0

if candle_data:
    df = pd.DataFrame(candle_data, columns=['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume'])
    
    # [மாற்றம்] உங்களின் பழைய 'Volume * 2.4' கணக்கீடு சிதைக்கப்படாமல் OI_Calc ஆக வைக்கப்பட்டுள்ளது
    df['OI_Calc'] = df['Volume'] * 2.4  
    df['Timestamp'] = pd.to_datetime(df['Timestamp'])
    df.set_index('Timestamp', inplace=True)
    df = df.sort_index()
    
    if ws_price > 0:
        live_price = ws_price
        df.iloc[-1, df.columns.get_loc('Close')] = live_price
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
    
    # ⏱️ [மாற்றம்] 9:15 மற்றும் 9:30 OI மதிப்பீடு துல்லியமாகப் பிரிக்கப்படுகிறது
    try:
        oi_915 = int(df.between_time('09:15', '09:16').iloc[0]['OI_Calc'])
    except Exception:
        oi_915 = int(df.iloc[0]['OI_Calc'])

    try:
        oi_930 = int(df.between_time('09:30', '09:31').iloc[0]['OI_Calc'])
    except Exception:
        oi_930 = int(df.iloc[min(15, len(df)-1)]['OI_Calc'])

    # [மாற்றம்] எக்ஸ்சேஞ்ச் உண்மையான Live OI கிடைத்தால் அதுவே முதன்மை; இல்லையேல் Fallback
    live_oi_value = exchange_live_oi if exchange_live_oi > 0 else int(df.iloc[-1]['OI_Calc'])
    live_oi_change = live_oi_value - oi_915
    
    df_15min = df[(df.index.hour == 9) & (df.index.minute >= 15) & (df.index.minute <= 30)]
    if not df_15min.empty:
        matrix_open, matrix_high = float(df_15min.iloc[0]['Open']), float(df_15min['High'].max())
        matrix_low, matrix_close = float(df_15min['Low'].min()), float(df_15min.iloc[-1]['Close'])
        oi_difference = live_oi_change
    else:
        matrix_open, matrix_high, matrix_low, matrix_close = day_open, float(df['High'].max()), float(df['Low'].min()), live_price
        oi_difference = live_oi_change
    levels = calculate_pivots(matrix_high, matrix_low, matrix_close, matrix_open)
else:
    live_price, current_vwap = 150.0, 149.5
    oi_difference = 2500
    oi_915, oi_930, live_oi_value, live_oi_change = 450000, 485000, 510000, 60000
    matrix_open, matrix_close, matrix_high, matrix_low = 148.0, 150.0, 152.0, 147.0
    day_open, day_change, pct_change = 148.0, 2.0, 1.35
    levels = {"R3": 155, "R2": 153, "R1": 151, "PP": 149, "S1": 147, "S2": 145, "S3": 143}
    df = pd.DataFrame([{"RSI": 55.0, "EMA_9": 149.2, "EMA_21": 148.5}])

# Navigation Tabs
tab_live, tab_news = st.tabs(["Equity & Derivatives Terminal", "Company Insights & News"])

with tab_live:
    @st.fragment(run_every="2s")
    def render_live_metrics():
        current_live_price = st.session_state["live_prices"].get(active_token, live_price) if st.session_state["live_prices"].get(active_token, 0.0) > 0 else live_price
        current_change = current_live_price - day_open
        current_pct = ((current_change / day_open) * 100) if day_open != 0 else 0.0
        display_color = "#00B074" if current_change >= 0 else "#f44336"
        
        st.markdown(f"""
        <div class="nse-grid">
            <div class="nse-card" style="border-top: 4px solid {display_color};">
                <div class="nse-label">LTP PRICE ({selected_focus})</div>
                <div class="nse-value" style="color:{display_color};">₹ {current_live_price:.2f} <span style="font-size:11px; font-weight:700;"><br>{current_change:+.2f} ({current_pct:+.2f}%)</span></div>
            </div>
            <div class="nse-card">
                <div class="nse-label">INTRADAY VWAP</div>
                <div class="nse-value">₹ {current_vwap:.2f}</div>
            </div>
            <div class="nse-card">
                <div class="nse-label">MOMENTUM RSI (14)</div>
                <div class="nse-value" style="color:#ffb81c;">{df.iloc[-1]['RSI']:.2f}</div>
            </div>
            <div class="nse-card">
                <div class="nse-label">EMA CROSSOVER (9/21)</div>
                <div class="nse-value" style="font-size:16px; padding-top:4px;">{df.iloc[-1]['EMA_9']:.1f} / {df.iloc[-1]['EMA_21']:.1f}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    render_live_metrics()

    # 2. 🔮 FUTURE OPEN INTEREST (F&O) & OPTION RADAR
    round_ltp = round(live_price / 10) * 10
    h_call, h_put = round_ltp + 10, round_ltp - 10
    fo_label, trend_color = get_fo_regime(live_price - day_open, live_oi_change)

    f_col1, f_col2 = st.columns(2)
    with f_col1:
        st.markdown(f"""
        <div class="nse-panel">
            <b>🔮 FUTURE OPEN INTEREST (F&O)</b>
            <table class="nse-table">
                <tr><td>Spot Price:</td><td><b>₹ {live_price:.2f}</b></td></tr>
                <tr><td>Live Future OI Value:</td><td class="mono-num"><b>{live_oi_value:,}</b></td></tr>
                <tr style="background:#f1f5f9;"><td style="color:#6574CD; font-weight:700;">Live Future OI Changes:</td><td class="mono-num" style="color:{trend_color}; font-weight:700;"><b>{live_oi_change:+,}</b></td></tr>
                <tr><td>Open Trend:</td><td style="color:{trend_color}; font-weight:700;">{fo_label.upper()}</td></tr>
            </table>
        </div>
        """, unsafe_allow_html=True)
    with f_col2:
        st.markdown(f'<div class="nse-panel"><b>🎯 OPTION CHAIN RADAR</b><table class="nse-table"><tr><td>Call OI (Res.):</td><td style="color:#f44336;"><b>₹ {h_call} Str.</b></td></tr><tr><td>Put OI (Supp.):</td><td style="color:#00B074;"><b>₹ {h_put} Str.</b></td></tr><tr><td>PCR Ratio:</td><td><b>1.05</b></td></tr></table></div>', unsafe_allow_html=True)

    # 🆕 image_bd1521.png உத்தி மேட்ரிக்ஸ் பாக்ஸ் (மாற்றங்கள் இன்றி)
    if live_price > df.iloc[-1]['EMA_9'] and pct_change > 0.5: market_trend = "UpTrend"
    elif live_price < df.iloc[-1]['EMA_9'] and pct_change < -0.5: market_trend = "DownTrend"
    else: market_trend = "Sideways"

    if fo_label == "Long Buildup": img_action, img_note = "Buy", "Fresh Positions are coming."
    elif fo_label == "Short Buildup": img_action, img_note = "Sell", "Fresh Positions are coming."
    elif fo_label == "Profit Booking": img_action, img_note = "Buy on Dip", "Existing positions are closing."
    else: img_action, img_note = "Sell on Rise", "Existing positions are closing."

    target_range, tamil_desc = "", ""

    if market_trend == "UpTrend":
        if fo_label == "Long Buildup":
            target_range = f"₹ {levels['R1']:.2f} - ₹ {levels['R2']:.2f}"
            tamil_desc = f"சந்தை ஏற்றத்தில் உள்ளது மற்றும் புதிய வாங்குதல்கள் (Long Buildup) தொடர்தால், விலை {target_range} உடைத்து மேலே செல்ல வாய்ப்பு அதிகம்."
        elif fo_label == "Profit Booking":
            target_range = f"₹ {levels['PP']:.2f} - ₹ {levels['S1']:.2f}"
            tamil_desc = "சந்தை ஏற்றத்தில் இருந்தாலும் தற்காலிக லாபப் பதிவு நடப்பதால், விலை சற்றே சரிந்து மீண்டும் உயரக்கூடும் (Bounce Back)."
        elif fo_label == "Short Covering":
            target_range = f"Gap Up Open -> ₹ {levels['PP']:.2f}"
            tamil_desc = "சந்தை கேப்-அப் ஆகி, பின்னர் சற்றே சரிவைச் சந்திக்கும். எனினும் இது இன்றைய லோ (Low) நிலையைத் தொடாது."
        else: img_action, target_range, tamil_desc = "It won't occur", "N/A", "UpTrend-இல் Short Buildup வாய்ப்பு இல்லை."
    elif market_trend == "DownTrend":
        if fo_label == "Short Buildup":
            target_range = f"₹ {levels['S1']:.2f} - ₹ {levels['S2']:.2f}"
            tamil_desc = f"சந்தை சரிவிலும் புதிய விற்பனை அழுத்தம் அதிகரிப்பதால், விலை {target_range} உடைத்துக் கீழ்நோக்கி வீழும்."
        elif fo_label == "Short Covering":
            target_range = f"₹ {levels['PP']:.2f} -> Fall"
            tamil_desc = "சந்தையில் சிறிய மீட்பு தெரிந்தாலும், அது தற்காலிக ஷார்ட் கவரிங் மட்டுமே. மீண்டும் பலத்த வீழ்ச்சி அடைய வாய்ப்புள்ளது."
        elif fo_label == "Profit Booking":
            target_range = f"₹ {levels['PP']:.2f}"
            tamil_desc = "சந்தை தொடங்கியவுடன் சற்று கீழ்நோக்கிச் சென்று, பின்னர் மீண்டு வரும் (Bounce Back). ஆனால் ஹை நிலையைத் தொடாது."
        else: img_action, target_range, tamil_desc = "It won't occur", "N/A", "DownTrend-இல் Long Buildup வாய்ப்பு இல்லை."
    else: # Sideways
        if fo_label == "Long Buildup":
            target_range = f"₹ {levels['PP']:.2f} -> ₹ {levels['R1']:.2f}"
            tamil_desc = f"சந்தை பக்கவாட்டில் இருந்தாலும் Long Buildup காரணமாக விலை உயர்ந்து ₹ {levels['R1']:.2f} வரை செல்லலாம்."
        elif fo_label == "Short Buildup":
            target_range = f"₹ {levels['PP']:.2f} -> ₹ {levels['S1']:.2f}"
            tamil_desc = f"விற்பனை அழுத்தம் காரணமாக விலை சரிந்து ₹ {levels['S1']:.2f} லெவல் வரை பயணிக்க வாய்ப்புள்ளது."
        elif fo_label == "Profit Booking":
            target_range = f"₹ {levels['S1']:.2f} -> ₹ {levels['R1']:.2f}"
            tamil_desc = f"விலை சப்போர்ட் ₹ {levels['S1']:.2f} ஐத் தொட்டு, பின்னர் அங்கிருந்து மீண்டு ரெசிஸ்டன்ஸ் ₹ {levels['R1']:.2f} ஐ அடைய முயலும்."
        elif fo_label == "Short Covering":
            target_range = f"₹ {levels['R1']:.2f} -> ₹ {levels['S1']:.2f}"
            tamil_desc = f"விலை ரெசிஸ்டன்ஸ் ₹ {levels['R1']:.2f} ஐத் தொட்டு, பின்னர் அங்கிருந்து சரிந்து சப்போர்ட் ₹ {levels['S1']:.2f} ஐ நோக்கி வீழும்."

    box_bg = "#10B981" if "Buy" in img_action else ("#EF4444" if "Sell" in img_action else "#ffb81c")
    
    st.markdown(f"""
    <div class="nse-panel" style="border-left: 6px solid {box_bg}; background-color: #FAFAFA;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
            <span style="font-size: 15px; font-weight: 700; color: #0c2340;">📋 IMAGE_BD1521 STRATEGY RADAR</span>
            <span style="background: {box_bg}22; color: {box_bg}; padding: 3px 8px; border-radius: 4px; font-size: 12px; font-weight: 700; border: 1px solid {box_bg};">SIGNAL: {img_action.upper()}</span>
        </div>
        <table class="nse-table" style="margin-bottom: 10px; background: transparent;">
            <tr style="background: none;"><td style="width: 35%; font-weight: 600;">சந்தை போக்கு (Trend):</td><td><b>{market_trend.upper()}</b></td></tr>
            <tr style="background: none;"><td style="font-weight: 600;">Future Open Interest:</td><td><b style="color:{trend_color};">{fo_label}</b> ({img_note})</td></tr>
            <tr style="background: none;"><td style="font-weight: 600;">குறிப்பிட்ட எல்லை (Range):</td><td class="mono-num" style="color: #0c2340; font-weight: 700;">{target_range}</td></tr>
        </table>
        <div style="font-size: 13px; line-height: 1.5; background: #FFFFFF; padding: 10px; border-radius: 4px; border: 1px dashed #CBD5E1;">
            <b>🎯 தமிழ் உத்தி விளக்கம் (Market Movement):</b> {tamil_desc}
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 3. NSE PIVOT POINTS ELEMENT ENGINE & BREAKOUT
    l_col1, l_col2 = st.columns([1.2, 1])
    with l_col1:
        st.markdown("<div class='nse-panel'><span class='nse-panel-title'>🎯 NSE PIVOT POINTS ELEMENT ENGINE</span>", unsafe_allow_html=True)
        t_html = "<table class='nse-table'><thead><tr><th>IDENTIFIER</th><th>VALUE BOUNDS</th></tr></thead><tbody>"
        for lvl, val in levels.items():
            t_color = "#f44336" if "R" in lvl else ("#00B074" if "S" in lvl else "#0c2340")
            t_html += f"<tr><td style='color:{t_color}; font-weight:700;'>{lvl} LEVEL</td><td class='mono-num'>₹ {val:.2f}</td></tr>"
        st.markdown(t_html + "</tbody></table></div>", unsafe_allow_html=True)

    with l_col2:
        fo_label, fo_color = get_fo_regime(matrix_close - matrix_open, live_oi_change)
        st.markdown(f"""
        <div class="nse-panel">
            <span class="nse-panel-title">⏱️ 15-MIN RANGE BREAKOUT</span>
            <table class="nse-table" style="width:100%;">
                <tr><td>• Opening (09:15)</td><td class="mono-num">₹ {matrix_open:.2f}</td></tr>
                <tr style="background:#f8fafc;"><td>⏱️ Future OI @ 09:15</td><td class="mono-num" style="color:#6574CD; font-weight:700;">{oi_915:,}</td></tr>
                <tr><td>• Closing (09:30)</td><td class="mono-num">₹ {matrix_close:.2f}</td></tr>
                <tr style="background:#f8fafc;"><td>⏱️ Future OI @ 09:30</td><td class="mono-num" style="color:#6574CD; font-weight:700;">{oi_930:,}</td></tr>
                <tr><td>• Peak High Marker</td><td class="mono-num" style="color:#00B074;">₹ {matrix_high:.2f}</td></tr>
                <tr><td>• Floor Low Marker</td><td class="mono-num" style="color:#f44336;">₹ {matrix_low:.2f}</td></tr>
                <tr><td>• Regime</td><td><span style="background:{fo_color}22; color:{fo_color}; padding:3px 6px; border-radius:3px; font-weight:700; font-size:11px;">{fo_label.upper()}</span></td></tr>
            </table>
        </div>
        """, unsafe_allow_html=True)

    # 4. 📈 REAL-TIME NO-LOGIN TRADINGVIEW CHART
    st.markdown("<div class='nse-panel'><span class='nse-panel-title'>📊 REAL-TIME ADVANCED CANDLESTICK TERMINAL</span>", unsafe_allow_html=True)
    
    tradingview_widget_html = f"""
    <iframe src="https://s.tradingview.com/widgetembed/?symbol={selected_focus}&interval=5&symboledit=1&saveimage=1&toolbarbg=f1f3f6&studies=%5B%5D&theme=light&style=1&timezone=Asia%2FKolkata&studies_overrides=%7B%7D&overrides=%7B%7D&enabled_features=%5B%22use_localstorage_for_settings_v2%22%5D&disabled_features=%5B%5D&locale=en" 
    width="100%" height="450" frameborder="0" allowtransparency="true" scrolling="no" allowfullscreen></iframe>
    """
    st.components.v1.html(tradingview_widget_html, height=450)

# TAB 2: NEWS & INSIGHTS
with tab_news:
    live_news = fetch_stock_news(selected_focus)
    for news in live_news:
        st.markdown(f'<div class="nse-news-box"><a class="nse-news-link" href="{news["link"]}" target="_blank">{news["title"]}</a><div style="font-size:11px; color:#718096; margin-top:6px;">📍 Feed: <b>{news["source"]}</b> &nbsp;•&nbsp; ⏱️ Time: {news["date"]}</div></div>', unsafe_allow_html=True)