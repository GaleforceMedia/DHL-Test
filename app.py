import streamlit as st
import pandas as pd
import glob
import os
from datetime import datetime

# Set up page layout (MUST be the first Streamlit command)
st.set_page_config(page_title="Store POD Portal", layout="wide")

# --- Custom CSS for Brand Identity ---
mamas_and_papas_css = """
<style>
    /* Import geometric sans-serif font */
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@300;400;600&display=swap');

    /* Apply font and soft background to the whole app */
    html, body, [class*="css"]  {
        font-family: 'Montserrat', sans-serif !important;
        background-color: #FAFAFA !important;
        color: #333333 !important;
    }

    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    h1 {
        font-weight: 300 !important;
        letter-spacing: 1px;
        text-transform: uppercase;
        border-bottom: 1px solid #E0E0E0;
        padding-bottom: 20px;
        margin-bottom: 30px;
    }

    h2, h3 {
        font-weight: 400 !important;
        letter-spacing: 0.5px;
    }

    [data-testid="stMetricValue"] {
        font-size: 2rem !important;
        font-weight: 600 !important;
        color: #1A1A1A !important;
    }
    
    table {
        border-collapse: collapse !important;
        width: 100% !important;
        font-size: 0.9rem !important;
    }
    th {
        background-color: #FFFFFF !important;
        font-weight: 600 !important;
        border-bottom: 2px solid #E0E0E0 !important;
        text-transform: uppercase;
        font-size: 0.8rem;
        color: #666666 !important;
        text-align: left !important;
    }
    td {
        background-color: #FFFFFF !important;
        border-bottom: 1px solid #F0F0F0 !important;
        vertical-align: middle !important;
        text-align: left !important;
    }
</style>
"""
st.markdown(mamas_and_papas_css, unsafe_allow_html=True)

# --- Header Section ---
col1, col2 = st.columns([1, 5])
with col1:
    try:
        st.image("logo.png", width=150)
    except FileNotFoundError:
        st.error("Logo missing")
with col2:
    st.title("Store Delivery Portal")

st.markdown("Track and manage network deliveries.")

# Load and combine all CSV data
@st.cache_data(ttl=60)
def load_data():
    all_files = sorted(glob.glob("*.csv"))
    
    timestamp = pd.Timestamp.now('Europe/London')
    last_updated_str = timestamp.strftime("%A, %d %B %Y at %I:%M %p")
    
    if not all_files:
        return pd.DataFrame(), last_updated_str
        
    df_list = []
    for file in all_files:
        try:
            temp_df = pd.read_csv(file)
            
            # --- Dynamic Campaign Tagging ---
            # Get the file name without the .csv extension
            base_name = os.path.basename(file).replace('.csv', '')
            
            # Check if it's a standard dashboard summary export
            if 'dashboard summary' in base_name.lower().replace('dashboardsummary', 'dashboard summary'):
                temp_df['Campaign'] = 'Standard Dispatch'
            else:
                # If it has a specific name (like "A1 Foamex"), use that as the Campaign
                temp_df['Campaign'] = base_name
                
            df_list.append(temp_df)
        except Exception:
            continue
            
    if not df_list:
        return pd.DataFrame(), last_updated_str
        
    master_df = pd.concat(df_list, ignore_index=True)
    master_df.columns = master_df.columns.str.strip()
    
    if 'Shipment number' in master_df.columns:
        master_df = master_df.drop_duplicates(subset=['Shipment number'], keep='last')
        
    if 'Delivery due date' in master_df.columns:
        master_df['Delivery Date Parsed'] = pd.to_datetime(master_df['Delivery due date'], format='%d/%m/%Y', errors='coerce')
        
    return master_df, last_updated_str

try:
    df, last_updated = load_data()

    if df.empty:
        st.warning("No tracking data available. Please upload the latest manifest.")
        st.stop()

    # --- Live Metric Calculations ---
    today = pd.Timestamp.now('Europe/London').normalize()
    start_of_week = today - pd.Timedelta(days=today.dayofweek)
    start_of_month = today.replace(day=1)
    
    df['Clean Status'] = df['Status'].astype(str).str.strip().str.lower()
    
    in_transit = len(df[df['Clean Status'].isin(['in transit', 'out for delivery'])])
    delivered_df = df[df['Clean Status'] == 'delivered']
    
    if 'Delivery Date Parsed' in df.columns:
        parsed_dates = df['Delivery Date Parsed'].dt.tz_localize('Europe/London', ambiguous='NaT', nonexistent='NaT')
        delivered_today = len(delivered_df[parsed_dates == today])
        delivered_week = len(delivered_df[parsed_dates >= start_of_week])
        delivered_month = len(delivered_df[parsed_dates >= start_of_month])
    else:
        delivered_today, delivered_week, delivered_month = 0, 0, 0

    # --- Display Top Metrics ---
    st.markdown("<br>", unsafe_allow_html=True)
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(label="In Transit", value=in_transit)
    with col2:
        st.metric(label="Delivered Today", value=delivered_today)
    with col3:
        st.metric(label="Delivered This Week", value=delivered_week)
    with col4:
        st.metric(label="Delivered This Month", value=delivered_month)

    # --- Display Last Updated Timestamp ---
    if last_updated:
        st.markdown(f"<div style='text-align: center; color: #888888; font-size: 0.85rem; margin-top: 10px; margin-bottom: 20px; font-weight: 400;'>Data last refreshed: {last_updated}</div>", unsafe_allow_html=True)

    st.markdown("<hr><br>", unsafe_allow_html=True)

    # --- Side-by-Side Filtering ---
    # We use st.columns to put the Store and Campaign filters next to each other
    col_filter1, col_filter2 = st.columns(2)
    
    unique_stores = sorted(df['Business/Recipient name'].dropna().unique())
    # Ensure 'Campaign' exists in case of empty initial data frames
    if 'Campaign' in df.columns:
        unique_campaigns = sorted(df['Campaign'].dropna().unique())
    else:
        unique_campaigns = []
        
    with col_filter1:
        selected_store = st.selectbox("SEARCH STORE BRANCH", ["All Stores"] + list(unique_stores))
        
    with col_filter2:
        selected_campaign = st.selectbox("SEARCH CAMPAIGN", ["All Campaigns"] + list(unique_campaigns))

    # Apply both filters to the dataframe
    filtered_df = df.copy()
    if selected_store != "All Stores":
        filtered_df = filtered_df[filtered_df['Business/Recipient name'] == selected_store]
        
    if selected_campaign != "All Campaigns":
        filtered_df = filtered_df[filtered_df['Campaign'] == selected_campaign]

    # --- Dynamic Carrier Link Generation ---
    def make_clickable(shipment_num):
        if pd.isna(shipment_num):
            return ""
        url = f"https://www.dhl.com/en/express/tracking.html?AWB={shipment_num}"
        return f'<a href="{url}" target="_blank" style="color: #666666; text-decoration: underline; font-weight: 600;">Track Order</a>'

    filtered_df['Tracking Link'] = filtered_df['Shipment number'].apply(make_clickable)

    # --- Colour Coded Status Badges ---
    def color_status(status_val):
        val_lower = str(status_val).strip().lower()
        bg_color = "#E0E0E0" 
        text_color = "#333333"
        
        if val_lower == 'delivered':
            bg_color = "#D4EDDA" 
            text_color = "#155724"
        elif val_lower in ['in transit', 'out for delivery']:
            bg_color = "#FFF3CD" 
            text_color = "#856404"
        elif 'exception' in val_lower or 'delay' in val_lower:
            bg_color = "#F8D7DA" 
            text_color = "#721C24"
            
        return f'<span style="background-color: {bg_color}; color: {text_color}; padding: 6px 12px; border-radius: 20px; font-weight: 600; font-size: 0.8rem; text-transform: uppercase;">{status_val}</span>'

    filtered_df['Status'] = filtered_df['Status'].apply(color_status)

    # Reorder columns to put Campaign front and center
    display_cols = [
        'Campaign', 'Business/Recipient name', 'Status', 'Delivery due date', 'ETA', 
        'Tracking Link', 'Number of parcels', 'Weight', 'Shipment number', 'Postal Code'
    ]
    available_cols = [col for col in display_cols if col in filtered_df.columns]

    # Display the interactive styled table
    st.write(
        filtered_df[available_cols].to_html(escape=False, index=False), 
        unsafe_allow_html=True
    )

except Exception as e:
    st.error(f"An error occurred: {e}")