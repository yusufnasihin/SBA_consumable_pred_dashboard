import streamlit as st
import pandas as pd
import datetime

from streamlit_gsheets import GSheetsConnection

st.set_page_config(
    page_title="Riwayat Transaksi",
    layout="wide",
    initial_sidebar_state='collapsed'
)
st.title("📝 Manajemen Riwayat Transaksi")
st.subheader("➕ Tambah Transaksi Baru")
# --- KONEKSI ---
conn = st.connection("gsheets", type=GSheetsConnection)

# --- AMBIL DATA DARI SESSION STATE ---
if 'log_transaksi' not in st.session_state or 'df_master' not in st.session_state:
    st.warning("Data belum dimuat. Silakan kembali ke halaman utama (Dasbor) terlebih dahulu.")
    st.stop()

log_df_raw = st.session_state.log_transaksi
df_master = st.session_state.df_master

# Kamus biaya pesan per vendor (disingkat untuk keringkasan)
biaya_pesan_dict = {
    'VND001': 11, 'VND002': 8, 'VND003': 13, 'VND004': 13, 'VND005': 13,
    'VND006': 14, 'VND007': 9, 'VND008': 11, 'VND009': 12, 'VND010': 15,
    'VND011': 8, 'VND012': 8, 'VND013': 9, 'VND014': 12, 'VND015': 14,
    'VND016': 10, 'VND017': 13, 'VND018': 11, 'VND019': 8, 'VND020': 12,
    'VND021': 8, 'VND022': 13, 'VND023': 9, 'VND024': 12, 'VND025': 11,
    'VND026': 10, 'VND027': 8, 'VND028': 10, 'VND029': 9, 'VND030': 11,
    'VND031': 14, 'VND032': 10, 'VND033': 12, 'VND034': 12, 'VND035': 14,
    'VND036': 8, 'VND037': 10, 'VND038': 9, 'VND039': 8, 'VND040': 15,
    'VND041': 15, 'VND042': 10, 'VND043': 11, 'VND044': 9, 'VND045': 14
}

unit_map = {
    'ASNA4018': 'EA',
    'ASNA4019': 'EA',
    'ASNA4021': 'EA',
    'ASNA4022': 'EA',
    'ASNA4023': 'EA',
    'AW106': 'G',
    'AUTOGLOW': 'KG',
    'B051-65': 'EA',
    'ASNA4017-222ETFAIBLE50CC': 'EA',
    'AVIOX-FINISH-77702': 'L',
    'AVESTA-ST-STEEL-S31254DIA4IN': 'EA',
    'ASNA4110-00': 'EA',
    'ASNA4111-00': 'EA',
    'ASN502-02': 'EA',
    'AT200Y-1/8INX1/2INX25FIT': 'ROL'
}

def proses_log_transaksi(df):
    df = df.copy()
    df['Price'] = pd.to_numeric(df['Price'], errors='coerce').fillna(0)
    df['Quantity'] = pd.to_numeric(df['Quantity'], errors='coerce').fillna(0)
    if 'Posting Date' in df.columns:
        df['Posting Date'] = pd.to_datetime(df['Posting Date'], errors='coerce')
        df['Year'] = df['Posting Date'].dt.year
    else:
        df['Year'] = None
    if 'Quantity' in df.columns and 'Price' in df.columns:
        df['Total_Price'] = df['Quantity'] * df['Price']
    else:
        df['Total_Price'] = None
    if 'Price' in df.columns:
        df['biaya_penyimpanan'] = 0.1 * df['Price'].astype(float)
    else:
        df['biaya_penyimpanan'] = None
    if 'Vendor_ID' in df.columns:
        df['biaya_pesan'] = df['Vendor_ID'].map(biaya_pesan_dict)
    else:
        df['biaya_pesan'] = None
    if 'Unit' in df.columns:
        df['Unit'] = df['Material'].map(unit_map)
    return df

# --- 1. Create a SINGLE container with a border for all inputs ---
with st.container(border=True):
    # --- ROW 1 ---
    row1_col1, row1_col2, row1_col3 = st.columns(3)

    with row1_col1:
        tanggal = st.date_input("Posting Date", datetime.date.today())

    with row1_col2:
        material = st.selectbox(
            "Material",
            df_master['Material'].unique(),
            index=None,
            placeholder="Select Material",
            key="material_selector"
        )

    with row1_col3:
        movement = st.selectbox(
            "Movement Type",
            ["GR", "GI"], # Goods Receipt, Goods Issue
            index=None,
            placeholder="Select Movement Type",
            key="movement_selector"
        )

    # --- ROW 2 ---
    row2_col1, row2_col2, row2_col3 = st.columns(3)
    
    # Define default values for controlled fields
    vendor = None
    price = 0.0

    with row2_col1:
        qty = st.number_input("Quantity", min_value=0.0, step=1.0)

    # Conditionally display the Vendor selector in the second column
    with row2_col2:
        if movement == 'GR': # Only show Vendor for Goods Receipt
            if material:
                vendor_options = log_df_raw[log_df_raw['Material'] == material]['Vendor_ID'].unique().tolist()
                vendor_placeholder = "Select Vendor"
                is_disabled = False
            else:
                vendor_options = []
                vendor_placeholder = "Select Material first"
                is_disabled = True
            
            vendor = st.selectbox(
                "ID Vendor",
                vendor_options,
                index=None,
                placeholder=vendor_placeholder,
                disabled=is_disabled,
                key="vendor_selector"
            )
        else:
            # Display a disabled placeholder to maintain layout
            st.text_input("ID Vendor", "N/A for GI", disabled=True)

    # Conditionally display the Price input in the third column
    with row2_col3:
        if movement == 'GR': # Only show Price for Goods Receipt
            price = st.number_input("Price", min_value=0.0, step=1000.0)
        else:
            # Display a disabled placeholder to maintain layout
            st.number_input("Price", 0.0, disabled=True)

    # --- SUBMISSION BUTTON ---
    # We use a standard button now, not a form submit button.
    if st.button("✔️ Tambah Transaksi", use_container_width=True):
        # Updated logic to handle both GR and GI cases
        gr_valid = (movement == 'GR' and material and vendor)
        gi_valid = (movement == 'GI' and material)

        if gr_valid or gi_valid:
            material_description = df_master[df_master['Material'] == material]['Material Description'].iloc[0]
            new_row = pd.DataFrame([{
                "Posting Date": pd.to_datetime(tanggal).strftime('%Y-%m-%d %H:%M:%S'),
                "Material": material, "Material Description": material_description,
                "Quantity": qty,
                "Price": price, # Will be 0.0 for GI
                "Currency": "USD",
                "Vendor_ID": vendor, # Will be None for GI
                "Movement Type Text": movement
            }])
            new_row_aligned = new_row.reindex(columns=log_df_raw.columns)
            updated_log_df = pd.concat([log_df_raw, new_row_aligned], ignore_index=True)
            conn.update(worksheet='log_transaksi', data=updated_log_df)
            st.session_state.log_transaksi = updated_log_df
            st.cache_data.clear()
            st.success("Transaksi baru berhasil ditambahkan!")
            st.rerun()
        else:
            st.warning("Harap isi semua field yang diperlukan sebelum menambah transaksi.")

st.markdown("---")

# --- READ, UPDATE, & AUTO-DELETE ---
if not log_df_raw.empty:
    log_df = proses_log_transaksi(log_df_raw)
    log_df = log_df.sort_values(by="Posting Date", ascending=False).reset_index(drop=True)
    if 'Material Description' in log_df.columns:
        log_df = log_df.drop(columns=['Material Description'])
    log_display = log_df.merge(
        df_master[['Material', 'Material Description']], on='Material', how='left'
    )
    log_display['Hapus'] = False

    st.subheader("📜 Riwayat Transaksi")

    edited_df = st.data_editor(
        log_display,
        use_container_width=True,
        height=600,
        disabled=['Posting Date', 'Material', 'Material Description', 'Unit', 'Currency', 'Year', 'Total_Price', 'biaya_penyimpanan', 'biaya_pesan'],
        column_order=[
            'Hapus', 'Posting Date', 'Year', 'Material', 'Material Description', 'Quantity', 'Unit',
            'Price', 'Total_Price', 'Currency', 'Vendor_ID', 'Movement Type Text','biaya_penyimpanan', 'biaya_pesan'
        ],
        column_config={
            "Hapus": st.column_config.CheckboxColumn("Hapus", help="Centang untuk menghapus baris ini secara langsung.", default=False),
            "Price": st.column_config.NumberColumn("Price", format="%.2f"),
            "Total_Price": st.column_config.NumberColumn("Total", format="%.2f"),
            "biaya_penyimpanan": st.column_config.NumberColumn("Biaya Simpan", format="%.2f"),
            "biaya_pesan": st.column_config.NumberColumn("Biaya Pesan", format="%.2f"),
            "Year": st.column_config.NumberColumn("Tahun"),
        },
        key="data_editor_transaksi"
    )

    # --- LOGIKA HAPUS OTOMATIS (SAAT DICENTANG) ---
    # Cek apakah ada baris yang baru saja dicentang untuk dihapus
    rows_marked_for_deletion = edited_df[edited_df['Hapus'] == True]

    if not rows_marked_for_deletion.empty:
        # Filter untuk menyimpan data yang TIDAK dicentang
        df_after_delete = edited_df[edited_df['Hapus'] == False]
        
        # Buang kolom 'Hapus' karena tidak ada di Google Sheet
        df_after_delete = df_after_delete.drop(columns=['Hapus'])

        # Pastikan kolom sesuai dengan sheet asli sebelum update
        df_to_update = df_after_delete[log_df_raw.columns]

        # Update Google Sheet
        conn.update(worksheet='log_transaksi', data=df_to_update)
        
        # Update session state dan bersihkan cache
        st.session_state.log_transaksi = df_to_update
        st.cache_data.clear()
        
        # Tampilkan notifikasi singkat (toast) sebelum halaman di-refresh
        st.toast(f"{len(rows_marked_for_deletion)} transaksi telah dihapus!")
        
        # Jalankan ulang aplikasi untuk menampilkan tabel yang sudah diperbarui
        st.rerun()