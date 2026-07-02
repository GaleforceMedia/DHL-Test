import streamlit as st
import pandas as pd
import glob
import os

# Set up page layout
st.set_config(page_title="Store POD Portal", layout="wide")

# --- Custom CSS for Brand Identity ---
mamas_and_papas_css = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@300;400;600&display=swap');
    html, body, [class*="css"] { font-family: 'Montserrat', sans-serif !important; background-color: #FAFAFA !important; color: #333333 !important; }
    #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
    h1 { font-weight: 300 !important; letter-spacing: 1px; text-transform: uppercase; border-bottom: 1px solid #E0E0E0; padding-bottom: 20px; margin-bottom: 30px; }
    [data-testid="stMetricValue"] { font-size: 2rem !important; font-weight: 600 !important; color: #1A1A1A !important; }
    table { border-collapse: collapse !important; width: 100% !important; font-size: 0.9rem !important; }
    th { background-color: #FFFFFF !important; font-weight: 600 !important; border-bottom: 2px solid #E0E0E0 !important; text-transform: uppercase; font-size: 0.8rem; color: #666666 !important; text-align: left !important; }
    td { background-color: #FFFFFF !important; border-bottom: 1px solid #F0F0F0 !important; vertical-align: middle !important; text-align: left !important; }
</style>
"""
st.markdown(mamas_and_papas_css, unsafe_allow_html=True)

# --- Header Section ---
col1, col2 = st.columns([1, 5])
with col1:
    if os.path.exists("logo.png"): st.image("logo.png", width=150)
with col2: st.title("Store Delivery Portal")

# Load and combine all CSV data
@st.cache_data(ttl=60)
def load_data():
    all_files = sorted(glob.glob("*.csv"))
    timestamp = pd.Timestamp.now('Europe/London')
    last_updated_str = timestamp.strftime("%A, %d %B %Y at %I:%M %p")
    
    if not all_files: return pd.DataFrame(), last_updated_str
        
    df_list = []
    for file in all_files:
        try:
            # Force 'Shipment number' and 'Customer reference' to string to protect data
            temp_df = pd.read_csv(file, dtype={'Shipment number': str, 'Customer reference': str})
            base_name = os.path.basename(file).replace('.csv', '')
            temp_df['Campaign'] = 'Standard Dispatch' if 'dashboard summary' in base_name.lower().replace('dashboardsummary', 'dashboard summary') else base_name
            df_list.append(temp_df)
        except Exception: continue
            
    master_df = pd.concat(df_list, ignore_index=True)
    master_df.columns = master_df.columns.str.strip()
    
    # Standardize Dispatch Date for metrics
    if 'Dispatch date' in master_df.columns:
        master_df['Date For Metrics'] = pd.to_datetime(master_df['Dispatch date'], format='%d/%m/%Y', errors='coerce')
        
    return master_df, last_updated_str

try:
    df, last_updated = load_data()
    if df.empty: st.warning("No data found."); st.stop()

    # --- Metrics (Using Dispatch Date) ---
    today = pd.Timestamp.now('Europe/London').normalize()
    start_of_week = today - pd.Timedelta(days=today.dayofweek)
    start_of_month = today.replace(day=1)
    
    # Filter for Delivered items
    delivered = df[df['Status'].astype(str).str.strip().lower() == 'delivered'].copy()
    
    delivered_today = len(delivered[delivered['Date For Metrics'] == today])
    delivered_week = len(delivered[delivered['Date For Metrics'] >= start_of_week])
    delivered_month = len(delivered[delivered['Date For Metrics'] >= start_of_month])
    
    in_transit = len(df[df['Status'].astype(str).str.strip().lower().isin(['in transit', 'out for delivery'])])

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("In Transit", in_transit)
    col2.metric("Delivered Today", delivered_today)
    col3.metric("Delivered This Week", delivered_week)
    col4.metric("Delivered This Month", delivered_month)

    st.markdown(f"<div style='text-align: center; color: #888888; font-size: 0.85rem; margin-top: 10px; margin-bottom: 20px;'>Data last refreshed: {last_updated}</div>", unsafe_allow_html=True)
    st.markdown("<hr><br>", unsafe_allow_html=True)

    # --- Filters ---
    c1, c2, c3, c4 = st.columns(4)
    selected_store = c1.selectbox("SEARCH STORE BRANCH", ["All Stores"] + sorted(df['Business/Recipient name'].dropna().unique().tolist()))
    search_postcode = c2.text_input("SEARCH POSTCODE")
    search_ref = c3.text_input("SEARCH JOB NO.")
    selected_campaign = c4.selectbox("SEARCH CAMPAIGN", ["All Campaigns"] + sorted(df['Campaign'].unique().tolist()))

    filtered_df = df.copy()
    if selected_store != "All Stores": filtered_df = filtered_df[filtered_df['Business/Recipient name'] == selected_store]
    if search_postcode.strip(): filtered_df = filtered_df[filtered_df['Postal Code'].astype(str).str.contains(search_postcode.strip(), case=False, na=False)]
    if search_ref.strip() and 'Customer reference' in filtered_df.columns: filtered_df = filtered_df[filtered_df['Customer reference'].astype(str).str.contains(search_ref.strip(), case=False, na=False)]
    if selected_campaign != "All Campaigns": filtered_df = filtered_df[filtered_df['Campaign'] == selected_campaign]

    # --- Display Table ---
    # Convert status to badge
    def color_status(val):
        v = str(val).strip().lower()
        c = "#D4EDDA" if v == 'delivered' else "#FFF3CD" if v in ['in transit', 'out for delivery'] else "#F8D7DA" if 'exception' in v or 'delay' in v else "#E0E0E0"
        t = "#155724" if v == 'delivered' else "#856404" if v in ['in transit', 'out for delivery'] else "#721C24" if 'exception' in v or 'delay' in v else "#333333"
        return f'<span style="background-color: {c}; color: {t}; padding: 6px 12px; border-radius: 20px; font-weight: 600; font-size: 0.8rem; text-transform: uppercase;">{val}</span>'

    filtered_df['Status'] = filtered_df['Status'].apply(color_status)
    filtered_df['Tracking Link'] = filtered_df['Shipment number'].apply(lambda x: f'<a href="https://www.dhl.com/en/express/tracking.html?AWB={x}" target="_blank" style="color: #666666; text-decoration: underline; font-weight: 600;">Track Order</a>' if pd.notna(x) else "")

    st.write(filtered_df[['Campaign', 'Customer reference', 'Business/Recipient name', 'Status', 'Delivery due date', 'ETA', 'Tracking Link', 'Number of parcels', 'Weight', 'Shipment number', 'Postal Code']].to_html(escape=False, index=False), unsafe_allow_html=True)
except Exception as e: st.error(f"Error: {e}")