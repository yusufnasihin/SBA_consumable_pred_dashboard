import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import altair as alt

# --- KONFIGURasi HALAMAN ---
st.set_page_config(
    page_title="Dasbor Stock Material",
    layout="wide",
    initial_sidebar_state='collapsed'
)

st.subheader("📊 Dashboard Pemantauan Bahan Baku Habis Pakai")

# --- KONEKSI ---
conn = st.connection("gsheets", type=GSheetsConnection)

# --- FUNGSI PERHITUNGAN STOK KRONOLOGIS ---
def recalculate_stock_chronologically(log_df):
    """
    Menghitung stok dengan memproses setiap transaksi secara berurutan (kronologis).
    """
    log_df_sorted = log_df.sort_values(by='Posting Date', ascending=True)
    stock_levels = {}

    for _, trx in log_df_sorted.iterrows():
        material_id = trx['Material']
        movement_type = trx['Movement Type Text']
        quantity = trx['Quantity']
        description = trx['Material Description']

        if material_id not in stock_levels:
            stock_levels[material_id] = {
                'Material Description': description,
                'Current Stock': 0.0,
                'Safety Stock': 0.0
            }

        if movement_type == 'GR':
            stock_levels[material_id]['Current Stock'] += quantity
            stock_levels[material_id]['Safety Stock'] = stock_levels[material_id]['Current Stock'] * 0.10
        elif movement_type == 'GI':
            stock_levels[material_id]['Current Stock'] -= quantity
        
        stock_levels[material_id]['Current Stock'] = max(0, stock_levels[material_id]['Current Stock'])

    if not stock_levels:
        return pd.DataFrame(columns=['Material', 'Material Description', 'Current Stock', 'Safety Stock'])

    final_df = pd.DataFrame.from_dict(stock_levels, orient='index')
    final_df.reset_index(inplace=True)
    final_df.rename(columns={'index': 'Material'}, inplace=True)
    return final_df

# --- FUNGSI MEMUAT DATA (DI-CACHE) ---
@st.cache_data(ttl=10)
def load_and_process_data():
    """
    Memuat data dari Google Sheets dan memprosesnya menggunakan fungsi kronologis.
    """
    log_df = conn.read(worksheet='log_transaksi', header=0)
    
    if log_df.empty:
        st.warning("Worksheet 'log_transaksi' kosong.")
        return pd.DataFrame(), pd.DataFrame()

    required_cols = ['Material', 'Material Description', 'Quantity', 'Movement Type Text', 'Posting Date']
    if not all(col in log_df.columns for col in required_cols):
        st.error(f"Pastikan Google Sheet memiliki kolom: {', '.join(required_cols)}")
        st.stop()

    log_df['Quantity'] = pd.to_numeric(log_df['Quantity'], errors='coerce').fillna(0)
    log_df['Posting Date'] = pd.to_datetime(log_df['Posting Date'], errors='coerce')
    log_df.dropna(subset=['Posting Date'], inplace=True)
    
    stock_final = recalculate_stock_chronologically(log_df)
    return stock_final, log_df

# --- FUNGSI PEWARNAAN ---
def style_safety_stock(row):
    """Memberi warna pada baris jika stok di bawah safety stock."""
    if row['Current Stock'] >= 0 and row['Current Stock'] <= row['Safety Stock']:
        return ['background-color: #F8D7DA; color: #58151C'] * len(row)
    return [''] * len(row)

# --- TAMPILKAN DATA DAN SIMPAN KE SESSION STATE ---
try:
    df_stok, raw_data = load_and_process_data()
    
    if not df_stok.empty:
        st.session_state.df_master = df_stok[['Material', 'Material Description']].drop_duplicates().reset_index(drop=True)
        st.session_state.log_transaksi = raw_data
        
        st.subheader("Visualisasi Stok Material")

        # 1. Filter data dan URUTKAN berdasarkan kuantitas terbesar
        df_for_id_chart = df_stok[df_stok['Current Stock'] > 0].sort_values('Current Stock', ascending=False)

        if not df_for_id_chart.empty:
            # 2. Buat chart dengan Altair
            chart = alt.Chart(df_for_id_chart).mark_bar().encode(
                x=alt.X('Material:N', sort=None),  # 'sort=None' adalah kunci untuk mengikuti urutan DataFrame
                y=alt.Y('Current Stock:Q'),
                tooltip=['Material', 'Material Description', 'Current Stock']
            ).properties(
                height=500
            )
            
            # 3. Tampilkan chart di Streamlit
            st.altair_chart(chart, use_container_width=True)

            # --- TAMBAHAN: PERINGATAN RESTOCK ---
            # Filter material yang stoknya di bawah atau sama dengan safety stock (tapi masih ada)
            df_restock_needed = df_stok[
                (df_stok['Current Stock'] >= 0) & 
                (df_stok['Current Stock'] <= df_stok['Safety Stock'])
            ]
            
            # Jika ada material yang perlu di-restock, tampilkan peringatan
            if not df_restock_needed.empty:
                material_list = df_restock_needed['Material'].tolist()
                warning_message = f"**Peringatan Restock:** Material berikut berada di bawah batas aman dan perlu segera dipesan ulang: **{', '.join(material_list)}**."
                st.error(warning_message, icon="⚠️")
            # --- AKHIR BAGIAN TAMBAHAN ---
            
        else:
            st.info("Tidak ada material dengan stok di atas nol untuk divisualisasikan.")
        
        st.markdown("---") # Pemisah visual

        # --- TAMPILKAN TABEL DETAIL STOK ---
        st.markdown("""
            <style>
                .stDataFrame thead tr th {
                    font-weight: bold !important;
                }
            </style>
        """, unsafe_allow_html=True)

        st.subheader("Detail Stok Material")

        display_columns = ['Material', 'Material Description', 'Current Stock', 'Safety Stock']
        st.dataframe(
            df_stok[display_columns].style.apply(style_safety_stock, axis=1).format({
                'Current Stock': '{:,.2f}',
                'Safety Stock': '{:,.2f}'
            }),
            use_container_width=True,
            height=570,
            hide_index=True
        )
    else:
        st.info("Tidak ada data transaksi untuk ditampilkan.")

except Exception as e:
    st.error(f"Terjadi kesalahan yang tidak terduga: {e}")

st.markdown('---')