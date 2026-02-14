import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, date
import os
import plotly.express as px
from streamlit_autorefresh import st_autorefresh

# --- 1. CONFIG & SECURITY ---
ACCESS_KEY = "nifty2026" 
LOCK_FILE = "trade_lock.txt"
JOURNAL_FILE = "nifty_journal.csv"
SCREENSHOT_DIR = "trade_screenshots"
LOT_SIZE = 65  
DAILY_LOSS_LIMIT = -5000  

if not os.path.exists(SCREENSHOT_DIR):
    os.makedirs(SCREENSHOT_DIR)

st.set_page_config(page_title="Nifty Master Suite Pro", layout="wide")
st_autorefresh(interval=60000, key="refresh")

if 'authenticated' not in st.session_state:
    st.session_state['authenticated'] = False

# --- 2. CORE UTILITIES ---
def calculate_brokerage(lots, premium):
    qty = lots * LOT_SIZE
    turnover = qty * premium
    fixed_brokerage = 40 
    stt = (turnover * 0.000625) 
    txn_charges = (turnover * 0.0005)
    gst = (fixed_brokerage + txn_charges) * 0.18
    return round(fixed_brokerage + stt + txn_charges + gst, 2)

def log_trade(outcome, pts, net, mood, strategy, premium, lots, screenshot_file=None):
    # Lock the trade for the day
    with open(LOCK_FILE, "w") as f: 
        f.write(str(date.today()))
    
    img_path = "" # Default to empty string instead of "None" string
    if screenshot_file:
        filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        img_path = os.path.join(SCREENSHOT_DIR, filename)
        with open(img_path, "wb") as f:
            f.write(screenshot_file.getbuffer())

    new_data = pd.DataFrame([{
        "Timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 
        "Outcome": outcome, 
        "Strategy": strategy,
        "Points": pts, 
        "Premium": premium,
        "Lots": lots,
        "Net_PnL": round(net, 2),
        "Mindset": mood,
        "Screenshot": img_path
    }])
    
    if not os.path.exists(JOURNAL_FILE):
        new_data.to_csv(JOURNAL_FILE, index=False)
    else:
        new_data.to_csv(JOURNAL_FILE, mode='a', header=False, index=False)

def get_live_price():
    try:
        data = yf.download("^NSEI", period="2d", interval="1m", progress=False)
        return round(data['Close'].iloc[-1], 2)
    except: return 22000.0

def get_todays_pnl():
    if os.path.exists(JOURNAL_FILE):
        df = pd.read_csv(JOURNAL_FILE)
        df['Timestamp'] = pd.to_datetime(df['Timestamp'])
        today_df = df[df['Timestamp'].dt.date == date.today()]
        return today_df['Net_PnL'].sum()
    return 0

# --- 3. LOGIN GATE ---
if not st.session_state['authenticated']:
    st.title("🔐 Secure Trader Login")
    user_input = st.text_input("Enter Key", type="password")
    if st.button("Unlock"):
        if user_input == ACCESS_KEY:
            st.session_state['authenticated'] = True
            st.rerun()
    st.stop()

# --- 4. SIDEBAR ---
with st.sidebar:
    st.header("💰 Risk Management")
    capital = st.number_input("Trading Capital (₹)", value=100000)
    risk_pct = st.slider("Risk per Trade %", 0.5, 5.0, 1.0)
    
    if os.path.exists(JOURNAL_FILE):
        df_stats = pd.read_csv(JOURNAL_FILE)
        if not df_stats.empty:
            win_rate = len(df_stats[df_stats['Net_PnL'] > 0]) / len(df_stats)
            avg_win = df_stats[df_stats['Net_PnL'] > 0]['Net_PnL'].mean() or 1
            avg_loss = df_stats[df_stats['Net_PnL'] < 0]['Net_PnL'].abs().mean() or 1
            rrr = avg_win / avg_loss if avg_loss > 0 else 1.0
            st.divider()
            st.subheader("🛡️ Survival Metrics")
            st.metric("Win Rate", f"{win_rate*100:.1f}%")
            st.metric("Recovery Factor", f"{rrr:.2f} RR")

    st.divider()
    st.subheader("Position Sizer")
    prem_input = st.number_input("Option Premium (₹)", value=100.0)
    risk_amt = capital * (risk_pct/100)
    calc_lots = max(1, int(risk_amt // (prem_input * LOT_SIZE)))
    
    st.metric("Max Risk ₹", f"{risk_amt}")
    st.metric("Rec. Lots", f"{calc_lots} ({calc_lots*LOT_SIZE} Qty)")
    
    if st.button("Reset Daily Lock (Admin)"):
        if os.path.exists(LOCK_FILE): os.remove(LOCK_FILE)
        st.rerun()

# --- 5. MAIN DASHBOARD ---
cmp = get_live_price()
todays_pnl = get_todays_pnl()
is_blown = todays_pnl <= DAILY_LOSS_LIMIT
has_traded = os.path.exists(LOCK_FILE) and open(LOCK_FILE).read() == str(date.today())

tab1, tab2 = st.tabs(["🚀 Live Execution", "📈 Performance Analytics"])

with tab1:
    st.title(f"Nifty Spot: {cmp}")
    pnl_color = "red" if todays_pnl < 0 else "green"
    st.markdown(f"### Today's PnL: :{pnl_color}[₹{todays_pnl}]")
    
    if is_blown:
        st.error("🛑 HARD LOCK: Daily loss limit reached.")
    elif has_traded:
        st.warning("🚫 ONE & DONE: Trade logged for today.")
    else:
        st.divider()
        c_m, c_s, c_u = st.columns([1,1,2])
        with c_m: mood = st.selectbox("Mindset", ["Calm", "Anxious", "Neutral", "Confident"])
        with c_s: strat = st.selectbox("Strategy", ["5-EMA", "9-EMA", "VBP", "Inside Bar", "Scalp"])
        with c_u: chart_img = st.file_uploader("Upload Chart Screenshot (Optional)", type=['png', 'jpg'])
        
        rule_follow = st.checkbox("I have followed all my rules for this setup.")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ TARGET (+20 pts)", use_container_width=True, disabled=not rule_follow):
                fees = calculate_brokerage(calc_lots, prem_input)
                net = (20 * calc_lots * LOT_SIZE) - fees
                log_trade("Target Hit", 20, net, mood, strat, prem_input, calc_lots, chart_img)
                st.rerun()
        with col2:
            if st.button("❌ SL (-10 pts)", use_container_width=True, disabled=not rule_follow):
                fees = calculate_brokerage(calc_lots, prem_input)
                net = (-10 * calc_lots * LOT_SIZE) - fees
                log_trade("SL Hit", 10, net, mood, strat, prem_input, calc_lots, chart_img)
                st.rerun()

with tab2:
    if os.path.exists(JOURNAL_FILE):
        df = pd.read_csv(JOURNAL_FILE)
        # Ensure Screenshot column is treated as string and handles NaNs
        df['Screenshot'] = df['Screenshot'].fillna("")
        
        st.header("📋 Trade Logs")
        st.dataframe(df.sort_values(by="Timestamp", ascending=False), use_container_width=True)
        
        st.divider()
        st.subheader("View Trade Setup")
        selected_trade = st.selectbox("Select Trade by Timestamp:", df['Timestamp'].unique())
        
        # Filter row safely
        row = df[df['Timestamp'] == selected_trade].iloc[0]
        img_path = str(row['Screenshot'])
        
        # KEY FIX: Check if path exists and is not empty before rendering image
        if img_path and img_path.strip() != "" and os.path.exists(img_path):
            st.image(img_path, caption=f"Setup for {row['Strategy']} at {selected_trade}")
        else:
            st.info("No screenshot available for this specific trade.")
    else:
        st.info("No trades logged yet.")
