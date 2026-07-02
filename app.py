import streamlit as st
import pandas as pd

# Set up page layout
st.set_page_config(page_title="Store POD Tracker", layout="wide")
st.title("📦 Store Proof of Delivery (POD) Dashboard")
st.markdown("Filter and track upcoming or historical store deliveries easily.")

# Load the data
@st.cache_data
def load_data():
    df = pd.read_csv("DashboardSummary (11).csv")
    # Clean up column names and string spaces
    df.columns = df.columns.str.strip()
    return df

try:
    df = load_data()

    # --- Live Summary Metrics ---
    total_shipments = len(df)
    in_transit = len(df[df['Status'].str.lower() == 'in transit'])
    st.columns(2)
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric(label="Total Shipments Today", value=total_shipments)
    with col2:
        st.metric(label="In Transit", value=in_transit)

    st.markdown("---")

    # --- Store Filtering ---
    st.subheader("🔍 Find Your Store")
    unique_stores = sorted(df['Business/Recipient name'].unique())
    selected_store = st.selectbox("Select your store branch:", ["All Stores"] + list(unique_stores))

    # Filter dataframe based on selection
    if selected_store != "All Stores":
        filtered_df = df[df['Business/Recipient name'] == selected_store].copy()
    else:
        filtered_df = df.copy()

    # --- Dynamic Carrier Link Generation ---
    # DHL Express typically uses the shipment or tracking number. 
    # Update this URL format based on your specific DHL contract/portal setup.
    def make_clickable(shipment_num):
        url = f"https://www.dhl.com/en/express/tracking.html?AWB={shipment_num}"
        return f'<a href="{url}" target="_blank">🔗 Track on DHL</a>'

    filtered_df['Tracking Link'] = filtered_df['Shipment number'].apply(make_clickable)

    # Reorder columns for optimal readability for store associates
    display_cols = [
        'Business/Recipient name', 'Status', 'Delivery due date', 'ETA', 
        'Tracking Link', 'Number of parcels', 'Weight', 'Shipment number', 'Postal Code'
    ]
    
    # Ensure all columns exist before selecting
    available_cols = [col for col in display_cols if col in filtered_df.columns]

    # Display the interactive styled table
    st.write(f"Showing **{len(filtered_df)}** records:")
    st.write(
        filtered_df[available_cols].to_html(escape=False, index=False), 
        unsafe_allow_html=True
    )

except FileNotFoundError:
    st.error("Could not find 'DashboardSummary (11).csv'. Please place the script and the CSV in the same folder.")