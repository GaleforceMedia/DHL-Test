import streamlit as st
import pandas as pd
import glob
from datetime import datetime

# Set up page layout
st.set_page_config(page_title="Store POD Tracker", layout="wide")
st.title("📦 Store Proof of Delivery (POD) Dashboard")
st.markdown("Filter and track upcoming or historical store deliveries easily.")

# Load and combine all CSV data
@st.cache_data(ttl=60) # Refreshes cache every 60 seconds
def load_data():
    all_files = sorted(glob.glob("*.csv"))
    
    if not all_files:
        return pd.DataFrame()
        
    df_list = []
    for file in all_files:
        try:
            temp_df = pd.read_csv(file)
            df_list.append(temp_df)
        except Exception:
            continue
            
    if not df_list:
        return pd.DataFrame()
        
    master_df = pd.concat(df_list, ignore_index=True)
    master_df.columns = master_df.columns.str.strip()
    
    if 'Shipment number' in master_df.columns:
        master_df = master_df.drop_duplicates(subset=['Shipment number'], keep='last')
        
    if 'Delivery due date' in master_df.columns:
        master_df['Delivery Date Parsed'] = pd.to_datetime(master_df['Delivery due date'], format='%d/%m/%Y', errors='coerce')
        
    return master_df

try:
    df = load_data()

    if df.empty:
        st.warning("No CSV data found. Please upload a spreadsheet to the repository.")
        st.stop()

    # --- Live Metric Calculations ---
    today = pd.Timestamp.today().normalize()
    start_of_week = today - pd.Timedelta(days=today.dayofweek)
    start_of_month = today.replace(day=1)
    
    df['Clean Status'] = df['Status'].astype(str).str.strip().str.lower()
    
    in_transit = len(df[df['Clean Status'].isin(['in transit', 'out for delivery'])])
    delivered_df = df[df['Clean Status'] == 'delivered']
    
    delivered_today = len(delivered_df[delivered_df['Delivery Date Parsed'] == today])
    delivered_week = len(delivered_df[delivered_df['Delivery Date Parsed'] >= start_of_week])
    delivered_month = len(delivered_df[delivered_df['Delivery Date Parsed'] >= start_of_month])

    # --- Display Top Metrics ---
    st.subheader("📊 Network Delivery Overview")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(label="🚚 In Transit", value=in_transit)
    with col2:
        st.metric(label="✅ Delivered Today", value=delivered_today)
    with col3:
        st.metric(label="📅 Delivered This Week", value=delivered_week)
    with col4:
        st.metric(label="📆 Delivered This Month", value=delivered_month)

    st.markdown("---")

    # --- Store Filtering ---
    st.subheader("🔍 Find Your Store")
    unique_stores = sorted(df['Business/Recipient name'].dropna().unique())
    selected_store = st.selectbox("Select your store branch:", ["All Stores"] + list(unique_stores))

    if selected_store != "All Stores":
        filtered_df = df[df['Business/Recipient name'] == selected_store].copy()
    else:
        filtered_df = df.copy()

    # --- Dynamic Carrier Link Generation ---
    def make_clickable(shipment_num):
        if pd.isna(shipment_num):
            return ""
        url = f"https://www.dhl.com/en/express/tracking.html?AWB={shipment_num}"
        return f'<a href="{url}" target="_blank">🔗 Track on DHL</a>'

    filtered_df['Tracking Link'] = filtered_df['Shipment number'].apply(make_clickable)

    # --- Colour Coded Status Badges ---
    def color_status(status_val):
        val_lower = str(status_val).strip().lower()
        # Default styling
        bg_color = "#6c757d" # Grey for unknown statuses
        text_color = "white"
        
        if val_lower == 'delivered':
            bg_color = "#198754" # Green
        elif val_lower in ['in transit', 'out for delivery']:
            bg_color = "#fd7e14" # Orange
        elif 'exception' in val_lower or 'delay' in val_lower:
            bg_color = "#dc3545" # Red
            
        return f'<span style="background-color: {bg_color}; color: {text_color}; padding: 4px 8px; border-radius: 4px; font-weight: bold;">{status_val}</span>'

    filtered_df['Status'] = filtered_df['Status'].apply(color_status)

    # Reorder columns for optimal readability
    display_cols = [
        'Business/Recipient name', 'Status', 'Delivery due date', 'ETA', 
        'Tracking Link', 'Number of parcels', 'Weight', 'Shipment number', 'Postal Code'
    ]
    available_cols = [col for col in display_cols if col in filtered_df.columns]

    # Display the interactive styled table
    st.write(f"Showing **{len(filtered_df)}** records:")
    st.write(
        filtered_df[available_cols].to_html(escape=False, index=False), 
        unsafe_allow_html=True
    )

except Exception as e:
    st.error(f"An error occurred: {e}")