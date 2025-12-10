import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime
import time
import pytz

# Import calculator
try:
    from gex_calculator import EnhancedGEXDEXCalculator, calculate_dual_gex_dex_flow, detect_gamma_flip_zones
    CALCULATOR_AVAILABLE = True
except Exception as e:
    CALCULATOR_AVAILABLE = False
    IMPORT_ERROR = str(e)

# ============================================================================
# AUTHENTICATION
# ============================================================================

def check_password():
    """Handle user authentication"""
    def password_entered():
        username = st.session_state["username"].strip().lower()
        password = st.session_state["password"]
        
        users = {
            "demo": "demo123",
            "premium": "premium123",
            "niyas": "nyztrade123"
        }
        
        if username in users and password == users[username]:
            st.session_state["password_correct"] = True
            st.session_state["authenticated_user"] = username
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False
    
    if "password_correct" not in st.session_state:
        st.markdown("## 🔐 NYZTrade Dashboard Login")
        st.markdown("---")
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.text_input("Username", key="username", placeholder="Enter username")
            st.text_input("Password", type="password", key="password", placeholder="Enter password")
            st.button("Login", on_click=password_entered, use_container_width=True)
            
            st.markdown("---")
            st.info("""
            **Demo Credentials:**
            - Free: `demo` / `demo123`
            - Premium: `premium` / `premium123`
            - Admin: `niyas` / `nyztrade123`
            """)
        return False
    
    elif not st.session_state["password_correct"]:
        st.markdown("## 🔐 NYZTrade Dashboard Login")
        st.error("❌ Incorrect username or password")
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.text_input("Username", key="username")
            st.text_input("Password", type="password", key="password")
            st.button("Login", on_click=password_entered, use_container_width=True)
        return False
    
    return True

def get_user_tier():
    """Get user subscription tier"""
    username = st.session_state.get("authenticated_user", "guest")
    premium_users = ["premium", "niyas"]
    return "premium" if username in premium_users else "basic"

def get_ist_time():
    """Get current time in IST"""
    ist = pytz.timezone('Asia/Kolkata')
    return datetime.now(ist)

# ============================================================================
# PAGE CONFIGURATION
# ============================================================================

st.set_page_config(
    page_title="NYZTrade - GEX Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Check authentication
if not check_password():
    st.stop()

user_tier = get_user_tier()

# ============================================================================
# CUSTOM CSS
# ============================================================================

st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 1rem;
    }
    .success-box {
        background-color: #d4edda;
        border-left: 5px solid #28a745;
        padding: 1rem;
        margin: 1rem 0;
    }
    .warning-box {
        background-color: #fff3cd;
        border-left: 5px solid #ffc107;
        padding: 1rem;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# HEADER
# ============================================================================

st.markdown('<p class="main-header">📊 NYZTrade - Advanced GEX + DEX Analysis</p>', unsafe_allow_html=True)
st.markdown("**Real-time Gamma & Delta Exposure Analysis for Indian Markets**")

# Display user tier
if user_tier == "premium":
    st.sidebar.success("👑 **Premium Member**")
else:
    st.sidebar.info(f"🆓 **Free Tier**")

# Logout button
if st.sidebar.button("🚪 Logout"):
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

# ============================================================================
# DHAN CREDENTIALS
# ============================================================================

try:
    DHAN_CLIENT_ID = st.secrets["dhan_client_id"]
    DHAN_ACCESS_TOKEN = st.secrets["dhan_access_token"]
    st.sidebar.success(f"✅ DhanHQ Connected")
    st.sidebar.caption(f"Client: {DHAN_CLIENT_ID}")
except:
    DHAN_CLIENT_ID = None
    DHAN_ACCESS_TOKEN = None
    st.sidebar.error("❌ DhanHQ Not Connected")
    st.error("""
    ### ⚠️ DhanHQ API Credentials Required
    
    Please configure your DhanHQ credentials in Streamlit Secrets:
```toml
    dhan_client_id = "YOUR_CLIENT_ID"
    dhan_access_token = "YOUR_ACCESS_TOKEN"
```
    """)
    st.stop()

# ============================================================================
# SIDEBAR CONTROLS
# ============================================================================

st.sidebar.markdown("---")
st.sidebar.header("⚙️ Dashboard Settings")

symbol = st.sidebar.selectbox(
    "Select Index",
    ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"],
    index=0
)

strikes_range = st.sidebar.slider(
    "Strikes Range",
    min_value=5,
    max_value=20,
    value=12,
    help="Number of strikes above and below current price"
)

expiry_index = st.sidebar.selectbox(
    "Expiry Selection",
    [0, 1, 2],
    format_func=lambda x: ["Current Weekly", "Next Weekly", "Monthly"][x],
    index=0
)

st.sidebar.markdown("---")

# Manual refresh
if st.sidebar.button("🔄 Refresh Data", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

# ============================================================================
# DATA FETCHING
# ============================================================================

@st.cache_data(ttl=60, show_spinner=False)
def fetch_data(symbol, strikes_range, expiry_index, client_id, access_token):
    """Fetch and calculate GEX/DEX data"""
    if not CALCULATOR_AVAILABLE:
        return None, None, None, None, f"Calculator unavailable: {IMPORT_ERROR}"
    
    if not client_id or not access_token:
        return None, None, None, None, "DhanHQ credentials not configured"
    
    try:
        calculator = EnhancedGEXDEXCalculator(
            client_id=client_id,
            access_token=access_token
        )
        
        df, futures_ltp, fetch_method, atm_info = calculator.fetch_and_calculate_gex_dex(
            symbol=symbol,
            strikes_range=strikes_range,
            expiry_index=expiry_index
        )
        
        return df, futures_ltp, fetch_method, atm_info, None
        
    except Exception as e:
        return None, None, None, None, str(e)

# ============================================================================
# FETCH DATA
# ============================================================================

st.markdown("---")

with st.spinner(f"🔄 Fetching live {symbol} data from DhanHQ..."):
    df, futures_ltp, fetch_method, atm_info, error = fetch_data(
        symbol, strikes_range, expiry_index, DHAN_CLIENT_ID, DHAN_ACCESS_TOKEN
    )

if error:
    st.error(f"❌ Error: {error}")
    
    with st.expander("🔧 Troubleshooting"):
        st.markdown("""
        **Common Issues:**
        
        1. **Market Closed**: Try during 9:15 AM - 3:30 PM IST
        2. **Token Expired**: Access tokens expire every 24 hours. Regenerate at https://www.dhan.co/
        3. **Rate Limit**: DhanHQ allows 1 request per 3 seconds
        4. **Data APIs**: Ensure Data APIs are enabled in your Dhan account
        """)
    st.stop()

if df is None or len(df) == 0:
    st.error("❌ No data available")
    st.stop()

# ============================================================================
# KEY METRICS
# ============================================================================

st.subheader("📊 Key Metrics")

col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    total_gex = float(df['Net_GEX_B'].sum())
    delta_text = "🟢 Bullish" if total_gex > 0 else "🔴 Volatile"
    st.metric("Total Net GEX", f"{total_gex:.4f}B", delta=delta_text)

with col2:
    call_gex = float(df['Call_GEX'].sum() / 1e9)
    st.metric("Call GEX", f"{call_gex:.4f}B")

with col3:
    put_gex = float(df['Put_GEX'].sum() / 1e9)
    st.metric("Put GEX", f"{put_gex:.4f}B")

with col4:
    st.metric("Futures LTP", f"₹{futures_ltp:,.2f}")

with col5:
    if atm_info:
        st.metric("ATM Straddle", f"₹{atm_info['atm_straddle_premium']:.2f}")

# ============================================================================
# FLOW ANALYSIS
# ============================================================================

try:
    flow_metrics = calculate_dual_gex_dex_flow(df, futures_ltp)
    
    if flow_metrics:
        st.markdown("---")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            gex_bias = flow_metrics['gex_near_bias']
            if "BULLISH" in gex_bias:
                st.markdown(f'<div class="success-box"><b>GEX Bias:</b> {gex_bias}</div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="warning-box"><b>GEX Bias:</b> {gex_bias}</div>', unsafe_allow_html=True)
        
        with col2:
            dex_bias = flow_metrics['dex_near_bias']
            st.info(f"**DEX Bias:** {dex_bias}")
        
        with col3:
            combined_bias = flow_metrics['combined_bias']
            st.info(f"**Combined:** {combined_bias}")
except Exception as e:
    flow_metrics = None

# ============================================================================
# GAMMA FLIP ZONES
# ============================================================================

try:
    gamma_flip_zones = detect_gamma_flip_zones(df)
    if gamma_flip_zones:
        st.warning(f"⚡ **{len(gamma_flip_zones)} Gamma Flip Zone(s) Detected!**")
except:
    gamma_flip_zones = []

# ============================================================================
# CHARTS
# ============================================================================

st.markdown("---")

tab1, tab2, tab3, tab4 = st.tabs([
    "📊 GEX Profile",
    "📈 DEX Profile",
    "📋 Data Table",
    "💡 Strategies"
])

# TAB 1: GEX Profile
with tab1:
    st.subheader(f"{symbol} Gamma Exposure Profile")
    
    fig = go.Figure()
    colors = ['green' if x > 0 else 'red' for x in df['Net_GEX_B']]
    
    fig.add_trace(go.Bar(
        y=df['Strike'],
        x=df['Net_GEX_B'],
        orientation='h',
        marker_color=colors,
        name='Net GEX',
        hovertemplate='<b>Strike:</b> %{y}<br><b>GEX:</b> %{x:.4f}B<extra></extra>'
    ))
    
    fig.add_hline(
        y=futures_ltp,
        line_dash="dash",
        line_color="blue",
        line_width=3,
        annotation_text=f"Current: ₹{futures_ltp:,.0f}"
    )
    
    fig.update_layout(
        height=600,
        xaxis_title="Net GEX (Billions)",
        yaxis_title="Strike Price",
        template='plotly_white'
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Interpretation
    if total_gex > 0.5:
        st.success("🟢 **Strong Positive GEX**: Market likely sideways to bullish. Consider premium selling.")
    elif total_gex < -0.5:
        st.error("🔴 **Negative GEX**: High volatility expected. Consider volatility strategies.")
    else:
        st.warning("⚖️ **Neutral GEX**: Mixed signals. Follow DEX for direction.")

# TAB 2: DEX Profile
with tab2:
    st.subheader(f"{symbol} Delta Exposure Profile")
    
    fig2 = go.Figure()
    dex_colors = ['green' if x > 0 else 'red' for x in df['Net_DEX_B']]
    
    fig2.add_trace(go.Bar(
        y=df['Strike'],
        x=df['Net_DEX_B'],
        orientation='h',
        marker_color=dex_colors,
        name='Net DEX',
        hovertemplate='<b>Strike:</b> %{y}<br><b>DEX:</b> %{x:.4f}B<extra></extra>'
    ))
    
    fig2.add_hline(y=futures_ltp, line_dash="dash", line_color="blue", line_width=3)
    
    fig2.update_layout(
        height=600,
        xaxis_title="Net DEX (Billions)",
        yaxis_title="Strike Price",
        template='plotly_white'
    )
    
    st.plotly_chart(fig2, use_container_width=True)

# TAB 3: Data Table
with tab3:
    st.subheader("Strike-wise Analysis")
    
    display_cols = ['Strike', 'Call_OI', 'Put_OI', 'Net_GEX_B', 'Net_DEX_B', 'Total_Volume']
    st.dataframe(df[display_cols], use_container_width=True, height=400)
    
    csv = df.to_csv(index=False)
    ist_time = get_ist_time()
    st.download_button(
        label="📥 Download CSV",
        data=csv,
        file_name=f"NYZTrade_{symbol}_{ist_time.strftime('%Y%m%d_%H%M')}.csv",
        mime="text/csv"
    )

# TAB 4: Strategies
with tab4:
    st.subheader("💡 Trading Strategies")
    
    if flow_metrics and atm_info:
        gex_val = flow_metrics['gex_near_total']
        
        if gex_val > 50:
            st.success("### 🟢 Iron Condor Strategy")
            st.markdown(f"""
            **Setup:** Sell {symbol} {int(futures_ltp)} CE + PE, Buy {int(futures_ltp + 200)} CE + {int(futures_ltp - 200)} PE
            
            **Risk:** Moderate | **Best Range:** ±₹100
            """)
        elif gex_val < -50:
            st.error("### 🔴 Long Straddle Strategy")
            st.markdown(f"""
            **Setup:** Buy {symbol} {atm_info['atm_strike']} CE + PE
            
            **Cost:** ₹{atm_info['atm_straddle_premium']:.2f} | **Risk:** High
            """)
        else:
            st.warning("### ⚖️ Wait for Clarity")

# ============================================================================
# FOOTER
# ============================================================================

st.markdown("---")

col1, col2, col3, col4 = st.columns(4)
ist_time = get_ist_time()

with col1:
    st.info(f"⏰ {ist_time.strftime('%H:%M:%S')} IST")
with col2:
    st.info(f"📅 {ist_time.strftime('%d %b %Y')}")
with col3:
    st.info(f"📊 {symbol}")
with col4:
    st.success(f"✅ {fetch_method}")

st.markdown(f"**💡 NYZTrade YouTube | Powered by DhanHQ**")
