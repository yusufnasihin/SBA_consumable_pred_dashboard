import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from streamlit_gsheets import GSheetsConnection

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="DSS: Warehouse Forecasting",
    layout="wide",
    initial_sidebar_state='collapsed'
)

st.title("📦 Intermittent Demand Decision Support System")
st.markdown("Powered by the Syntetos-Boylan Approximation (SBA) & Empirical Quantile Buffering")
st.markdown("---")

# --- KAMUS PARAMETER OPTIMAL ---

# Menyimpan hasil Grid Search statis agar Streamlit tidak berat

OPTIMAL_PARAMS = {
    "AVESTA-ST-STEEL-S31254DIA4IN": {"alpha": 0.35, "beta": 0.30},
    "AT200Y-1/8INX1/2INX25FIT": {"alpha": 0.05, "beta": 0.30},
    "AW106": {"alpha": 0.05, "beta": 0.25},
    "ASNA4018": {"alpha": 0.05, "beta": 0.35},
    "ASNA4022": {"alpha": 0.05, "beta": 0.35},
    "AUTOGLOW": {"alpha": 0.05, "beta": 0.30},
    "ASNA4021": {"alpha": 0.35, "beta": 0.30},
    "ASN502-02": {"alpha": 0.35, "beta": 0.35},
    "ASNA4019": {"alpha": 0.05, "beta": 0.25},
    "AVIOX-FINISH-77702": {"alpha": 0.35, "beta": 0.35},
    "ASNA4017-222ETFAIBLE50CC": {"alpha": 0.35, "beta": 0.30},
    "ASNA4023": {"alpha": 0.35, "beta": 0.35},
    "ASNA4111-00": {"alpha": 0.35, "beta": 0.35},
    "ASNA4110-00": {"alpha": 0.05, "beta": 0.20},
    "B051-65": {"alpha": 0.35, "beta": 0.35}
}

# --- KONEKSI ---
conn = st.connection("gsheets", type=GSheetsConnection)

# --- AMBIL DATA DARI SESSION STATE ---
if 'log_transaksi' not in st.session_state or 'df_master' not in st.session_state:
    st.warning("Data belum dimuat. Silakan kembali ke halaman utama (Dasbor) terlebih dahulu.")
    st.stop()

log_df_raw = st.session_state.log_transaksi
df_master = st.session_state.df_master

# --- DATA PREPARATION ---
@st.cache_data
def process_data(df_raw):
    df = df_raw.copy()
    
    # Ensure necessary columns exist; apply processing
    if 'Movement Type Text' in df.columns and 'Material' in df.columns:
        df[['Movement Type Text', 'Material']] = df[['Movement Type Text', 'Material']].astype('string')
        df = df[df['Movement Type Text'].str.contains('GI', na=False)]
        df = df.drop(columns='Movement Type Text')
        
    if 'Posting Date' in df.columns:
        df['Posting Date'] = pd.to_datetime(df['Posting Date'])
        df = df.groupby(['Posting Date', 'Material'])['Quantity'].sum().reset_index()
        df = df[['Posting Date', 'Material', 'Quantity']]
        df.sort_values(by='Posting Date', inplace=True)
        df = df.reset_index(drop=True)
        
    return df

df = process_data(log_df_raw)

if df.empty:
    st.error("Data log_transaksi kosong atau tidak ada transaksi Goods Issue (GI).")
    st.stop()

# --- ALGORITHM FUNCTIONS ---
def sba_forecast(demand_series, alpha=0.1, beta=0.1):
    """Calculates the SBA daily rate."""
    n = len(demand_series)
    z, p, f = np.zeros(n), np.zeros(n), np.zeros(n)
    non_zero_idx = np.where(demand_series > 0)[0]
    
    if len(non_zero_idx) == 0: return f
    first_idx = non_zero_idx[0]
    z[first_idx], p[first_idx] = demand_series[first_idx], 1.0 
    
    q = 1 
    for t in range(first_idx + 1, n):
        if demand_series[t] > 0:
            z[t] = alpha * demand_series[t] + (1 - alpha) * z[t-1]
            p[t] = beta * q + (1 - beta) * p[t-1]
            q = 1 
        else:
            z[t], p[t], q = z[t-1], p[t-1], q + 1
        f[t] = (1 - (alpha / 2)) * (z[t] / p[t]) # FIXED: Menggunakan alpha untuk koreksi bias
    return f

# --- SELECTION CONTROL ---
st.subheader("📋 Select Material")
materials = sorted(df['Material'].unique())
selected_material = st.selectbox("Choose a Material ID to analyze:", materials)

# Ekstraksi parameter optimal otomatis berdasarkan pilihan material
opt_alpha = OPTIMAL_PARAMS.get(selected_material, {}).get("alpha", 0.10) # Default 0.1 jika tidak ada di kamus
opt_beta = OPTIMAL_PARAMS.get(selected_material, {}).get("beta", 0.10)

# st.caption(f"🔧 **Tuned Parameters in Use:** Alpha (α) = {opt_alpha} | Beta (β) = {opt_beta}")
st.markdown("---")

# --- FILTER DATA FOR SELECTED MATERIAL ---
mat_df = df[df['Material'] == selected_material].copy()

if mat_df.empty:
    st.warning(f"Tidak ada data pergerakan untuk material {selected_material}.")
    st.stop()

start_date, end_date = mat_df['Posting Date'].min(), mat_df['Posting Date'].max()
full_calendar = pd.date_range(start=start_date, end=end_date, freq='D')

# Safe reindexing
mat_df.set_index('Posting Date', inplace=True)
mat_df = mat_df.reindex(full_calendar)
mat_df['Quantity'] = mat_df['Quantity'].fillna(0)
mat_df['Material'] = mat_df['Material'].fillna(selected_material)
mat_df = mat_df.reset_index()
mat_df.rename(columns={'index': 'Date'}, inplace=True)

# --- FEATURE 1: AUTOMATED DIAGNOSTIC ENGINE ---
non_zero_demands = mat_df[mat_df['Quantity'] > 0]['Quantity']
total_periods = len(mat_df)

if len(non_zero_demands) > 1:
    adi = total_periods / len(non_zero_demands)
    cv2 = (np.std(non_zero_demands) / np.mean(non_zero_demands)) ** 2
    
    if adi > 1.32 and cv2 > 0.49: classification = "LUMPY (High Risk)"
    elif adi > 1.32 and cv2 <= 0.49: classification = "INTERMITTENT"
    elif adi <= 1.32 and cv2 > 0.49: classification = "ERRATIC"
    else: classification = "SLOW MOVING"
else:
    adi, cv2, classification = 0, 0, "INSUFFICIENT DATA"

st.subheader(f"🔍 Diagnostics: {selected_material}")
col1, col2, col3 = st.columns(3)
col1.metric("Average Demand Interval (ADI)", f"{adi:.2f} days", delta="> 1.32 is Intermittent" if adi > 1.32 else "< 1.32 is Frequent", delta_color="inverse")
col2.metric("Size Variance (CV²)", f"{cv2:.2f}", delta="> 0.49 is Highly Variable" if cv2 > 0.49 else "< 0.49 is Stable", delta_color="inverse")

if "LUMPY" in classification:
    col3.error(f"**Classification:** {classification}")
else:
    col3.success(f"**Classification:** {classification}")

st.markdown("---")

# --- FEATURE 2 & 3: ALGORITHM COMPARISON & SCENARIO PLANNER ---
demand_array = mat_df['Quantity'].values

# INJEKSI PARAMETER OPTIMAL KE ALGORITMA
sba_rates = sba_forecast(demand_array, alpha=opt_alpha, beta=opt_beta)

mat_df['SBA_Daily_Rate'] = sba_rates
mat_df['Moving_Avg_30D'] = mat_df['Quantity'].rolling(window=30, min_periods=1).mean()

st.subheader("📊 Historical Transaction Demand")
fig = go.Figure()

fig.add_trace(go.Bar(
    x=mat_df['Date'], 
    y=mat_df['Quantity'], 
    name='Actual Daily Demand', 
    marker_color='royalblue'
))

fig.update_layout(
    height=400, 
    template='plotly_white', 
    xaxis_title="Date",
    yaxis_title="Quantity Issued",
    showlegend=False,
    bargap=0.05
)

st.plotly_chart(fig, use_container_width=True)

st.markdown("---")

# --- USER CONTROLS ---
st.subheader("🛡️ Risk Management & Scenario Planner")
st.markdown("Adjust your desired service level to see how the safety buffer impacts your final order quantity.")
csl_target = st.slider("Target Service Level (CSL) %", min_value=50, max_value=99, value=85, step=1, 
                       help="Higher CSL prevents stockouts but increases holding costs.")

# Calculate Final Output based on slider input
base_sba_monthly = sba_rates[-1] * 30 if len(sba_rates) > 0 else 0

monthly_historical = mat_df.set_index('Date').resample('ME')['Quantity'].sum()
required_inventory = np.percentile(monthly_historical, csl_target) if not monthly_historical.empty else 0
safety_buffer = max(0, required_inventory - base_sba_monthly)
final_order_qty = base_sba_monthly + safety_buffer

# --- FEATURE 4: ACTIONABLE OUTPUT ---
st.subheader("🎯 Actionable Restock Recommendation")
st.info(f"To achieve a **{csl_target}% Service Level**, the system recommends the following restock parameters for the upcoming month:")

r_col1, r_col2, r_col3 = st.columns(3)
r_col1.metric("Base SBA Monthly Forecast", f"{base_sba_monthly:.0f} units", help="The mathematical burn rate of the material.")
r_col2.metric(f"Safety Buffer (CSL {csl_target}%)", f"{safety_buffer:.0f} units", help="Extra stock held to cover historical extreme spikes.")
r_col3.metric("FINAL ORDER QUANTITY", f"{final_order_qty:.0f} units", help="Base Forecast + Safety Buffer")