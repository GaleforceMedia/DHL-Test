import urllib.request
import urllib.error
import json
import time
import os
import glob
import pandas as pd
import re

DHL_API_KEY = os.environ.get("DHL_API_KEY", "").strip()
if not DHL_API_KEY:
    DHL_API_KEY = "i043Uc7SRU6Zxs2GfxGk4QmWa4SxA6Ac" # Fallback key

CACHE_FILE = "m_and_p_tracking_cache.json"

def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_cache(cache_data):
    try:
        with open(CACHE_FILE, 'w') as f:
            json.dump(cache_data, f, indent=4)
    except Exception as e:
        print(f"Error saving cache: {e}")

def get_active_tracking_numbers():
    all_files = sorted(glob.glob("*.csv"))
    if not all_files:
        return []
        
    df_list = []
    for file in all_files:
        try:
            temp_df = pd.read_csv(file, dtype={'Shipment number': str})
            df_list.append(temp_df)
        except Exception:
            continue
            
    if not df_list:
        return []
        
    master_df = pd.concat(df_list, ignore_index=True)
    master_df.columns = master_df.columns.str.strip()
    
    if 'Shipment number' not in master_df.columns or 'Status' not in master_df.columns:
        return []

    master_df['Shipment number'] = master_df['Shipment number'].astype(str).str.replace(r'\.0$', '', regex=True)
    master_df['Shipment number'] = master_df['Shipment number'].apply(lambda x: re.sub(r'[^A-Za-z0-9]', '', str(x)))
    master_df = master_df.drop_duplicates(subset=['Shipment number'], keep='last')
    
    active_mask = master_df['Status'].astype(str).str.strip().str.lower() != 'delivered'
    active_parcels = master_df[active_mask]['Shipment number'].unique().tolist()
    
    return [trk for trk in active_parcels if len(trk) >= 10 and trk.lower() != 'nan']

def fetch_with_backoff(tracking_num, max_retries=4):
    url = f"https://api-eu.dhl.com/track/shipments?trackingNumber={tracking_num}"
    headers = {
        "DHL-API-Key": DHL_API_KEY,
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)"
    }
    
    delay = 2.0  
    
    for attempt in range(max_retries):
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode())
                    for shipment in data.get('shipments', []):
                        status_obj = shipment.get('status', {})
                        
                        code = status_obj.get('statusCode', '').lower()
                        text = status_obj.get('status', '')
                        
                        if not text:
                            text = code.replace('-', ' ').title()
                            
                        # Extract and format the Estimated Time of Delivery
                        raw_eta = shipment.get('estimatedTimeOfDelivery', '')
                        formatted_eta = ""
                        if raw_eta and len(raw_eta) >= 10:
                            date_part = raw_eta[:10]
                            try:
                                parts = date_part.split('-')
                                if len(parts) == 3:
                                    formatted_eta = f"{parts[2]}/{parts[1]}/{parts[0]}" # DD/MM/YYYY
                            except:
                                formatted_eta = raw_eta
                            
                        return {"code": code, "text": text, "eta": formatted_eta}
        except urllib.error.HTTPError as e:
            if e.code in [429, 503]: 
                print(f"⚠️ DHL Limit on {tracking_num}. Backing off for {delay}s (Attempt {attempt + 1})...")
                time.sleep(delay)
                delay *= 2 
            elif e.code == 404:
                print(f"⚠️ {tracking_num} not found on DHL yet (Pre-dispatch).")
                return None
            else:
                print(f"HTTP Error {e.code} on {tracking_num}")
                break
        except Exception as e:
            print(f"Connection error on {tracking_num}: {e}")
            break
            
    return None

def run_sync():
    print("Initiating Mamas & Papas background sync...")
    active_numbers = get_active_tracking_numbers()
    
    if not active_numbers:
        print("No active tracking numbers found. Exiting.")
        return
        
    print(f"Found {len(active_numbers)} active parcels to check.")
    cache = load_cache()
    current_time = time.time()
    
    for trk in active_numbers:
        if cache.get(trk, {}).get('status', '').lower() == 'delivered' or cache.get(trk, {}).get('code') == 'delivered':
            continue
            
        print(f"Checking {trk}...")
        result = fetch_with_backoff(trk)
        
        if result:
            # Save the text, code, and the new ETA to the vault
            cache[trk] = {
                'status': result['text'], 
                'code': result['code'],
                'eta': result['eta'],
                'timestamp': current_time
            }
                
        time.sleep(1.0)
        
    save_cache(cache)
    print("Sync complete. Cache updated.")

if __name__ == "__main__":
    run_sync()
