import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import numpy as np

# --- CONFIGURATION & CONSTANTS ---
st.set_page_config(page_title="Windscreen Frost Predictor", page_icon="❄️", layout="centered")

CAR_TYPES = {
    "Compact / Hatchback": {"factor": 0.8, "icon": "🚗"},
    "Sedan / Saloon": {"factor": 1.0, "icon": "🚙"},
    "SUV / Crossover": {"factor": 1.2, "icon": "🚙"},
    "Van / Truck": {"factor": 1.5, "icon": "🚚"},
}

# --- HELPER FUNCTIONS ---

@st.cache_data(ttl=3600)
def get_weather_data(lat, lon):
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": ["temperature_2m", "relative_humidity_2m", "dew_point_2m", "wind_speed_10m", "weather_code"],
        "timezone": "auto",
        "past_days": 5,
        "forecast_days": 6 
    }
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        hourly = data['hourly']
        df = pd.DataFrame({
            'time': pd.to_datetime(hourly['time']),
            'temp_c': hourly['temperature_2m'],
            'humidity': hourly['relative_humidity_2m'],
            'dew_point_c': hourly['dew_point_2m'],
            'wind_speed_kmh': hourly['wind_speed_10m'],
            'weather_code': hourly['weather_code']
        })
        return df
    except Exception as e:
        st.error(f"Error fetching weather: {e}")
        return pd.DataFrame()

def get_coordinates_from_search(query):
    try:
        clean_query = query.strip().replace(" ", "")
        resp = requests.get(f"https://api.postcodes.io/postcodes/{clean_query}", timeout=3)
        if resp.status_code == 200:
            data = resp.json()['result']
            return data['latitude'], data['longitude'], f"{data['postcode']}, {data.get('admin_district', 'UK')}"
    except:
        pass 

    try:
        resp = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": query, "count": 1, "language": "en", "format": "json"},
            timeout=3
        )
        if resp.status_code == 200:
            data = resp.json()
            if 'results' in data and data['results']:
                res = data['results'][0]
                return res['latitude'], res['longitude'], f"{res['name']}, {res.get('country', '')}"
    except:
        pass
        
    return None, None, None

def calculate_frost_risk(row):
    temp = row['temp_c']
    dew_point = row['dew_point_c']
    wind = row['wind_speed_kmh']
    humidity = row['humidity']
    spread = temp - dew_point
    
    risk_level = "None"
    color = "#e6f4ea" 
    text_color = "green"
    minutes_to_clear = 0
    condition = "Clear"

    if temp <= 3.0: 
        if spread < 2.0 or (temp <= 0 and humidity > 80):
            if temp < -5:
                risk_level = "Severe Ice"
                color = "#fce8e6"
                text_color = "darkred"
                minutes_to_clear = 15
                condition = "Hard Ice"
            elif temp <= 0:
                risk_level = "Frost/Ice"
                color = "#fce8e6"
                text_color = "red"
                minutes_to_clear = 10
                condition = "Icy"
            else:
                risk_level = "Light Frost"
                color = "#fef7e0"
                text_color = "orange"
                minutes_to_clear = 5
                condition = "Frosty"
    elif spread < 2.5 and humidity > 90 and wind < 10:
        risk_level = "Fog"
        color = "#f1f3f4"
        text_color = "gray"
        minutes_to_clear = 2 
        condition = "Foggy"
        
    return pd.Series([risk_level, color, text_color, minutes_to_clear, condition], 
                     index=['risk', 'bg_color', 'text_color', 'base_minutes', 'condition'])

# --- MAIN APP UI ---

st.title("❄️ Windscreen Frost Predictor")

if 'latitude' not in st.session_state:
    st.session_state.latitude = 51.50 
    st.session_state.longitude = -0.12
    st.session_state.location_name = "London, UK"

with st.container():
    col1, col2 = st.columns([3, 1])
    with col1:
        search_query = st.text_input("📍 Location", placeholder="Enter UK Postcode or City")
    with col2:
        st.write("")
        st.write("")
        if st.button("🔎 Search"):
            if search_query:
                lat, lon, name = get_coordinates_from_search(search_query)
                if lat:
                    st.session_state.latitude = lat
                    st.session_state.longitude = lon
                    st.session_state.location_name = name
                    st.rerun()
                else:
                    st.error("Not found.")

    if st.button("Use My Current Location"):
        try:
            loc_req = requests.get('https://ipapi.co/json/', timeout=5)
            loc_data = loc_req.json()
            st.session_state.latitude = float(loc_data.get('latitude'))
            st.session_state.longitude = float(loc_data.get('longitude'))
            st.session_state.location_name = f"{loc_data.get('city')}, {loc_data.get('country_name')}"
            st.rerun()
        except:
            st.warning("Could not detect location.")

    car_choice = st.selectbox("Select Car Type", list(CAR_TYPES.keys()))

lat = st.session_state.latitude
lon = st.session_state.longitude
loc_name = st.session_state.location_name

if lat and lon:
    df_raw = get_weather_data(lat, lon)
    
    if not df_raw.empty:
        risk_cols = df_raw.apply(calculate_frost_risk, axis=1)
        df = pd.concat([df_raw, risk_cols], axis=1)
        
        df['date'] = df['time'].dt.date
        df['hour'] = df['time'].dt.hour
        
        car_factor = CAR_TYPES[car_choice]['factor']
        df['total_delay'] = (df['base_minutes'] * car_factor).round().astype(int)

        morning_df = df[df['hour'] == 7].copy()
        
        st.divider()
        st.markdown(f"### Report for **{loc_name}**")
        
        tomorrow = datetime.now().date() + timedelta(days=1)
        tomorrow_row = morning_df[morning_df['date'] == tomorrow]
        
        if not tomorrow_row.empty:
            row = tomorrow_row.iloc[0]
            delay = row['total_delay']
            
            col_hero_1, col_hero_2 = st.columns([2,1])
            with col_hero_1:
                st.subheader("Tomorrow Morning (7:00 AM)")
                if delay > 0:
                    st.error(f"❄️ Plan for +{delay} minutes delay")
                    st.markdown(f"**{row['condition']}** expected. Temp: **{row['temp_c']}°C**")
                else:
                    st.success("✅ Clear Windscreen Expected")
                    st.markdown(f"**{row['condition']}** expected. Temp: **{row['temp_c']}°C**")
            with col_hero_2:
                st.metric("Risk Level", row['risk'])

        st.divider()

        # --- HORIZONTAL SCROLLABLE TIMELINE ---
        st.subheader("📅 11-Day Forecast")
        st.caption("Swipe left/right to view all days")
        
        today_date = datetime.now().date()
        
        cards_html = ""
        for index, row in morning_df.iterrows():
            date_diff = (row['date'] - today_date).days
            
            # Logic: Past/Future=Small, Yest/Tom=Medium, Today=Big
            if date_diff == 0:
                size_class = "card-today"
                badge = "TODAY"
            elif date_diff == 1 or date_diff == -1:
                size_class = "card-medium"
                badge = row['date'].strftime('%a %d')
            else:
                size_class = "card-small"
                badge = row['date'].strftime('%a %d')

            bg_color = row['bg_color']
            text_color = row['text_color']
            
            cards_html += f"""
            <div class="weather-card {size_class}" style="background-color: {bg_color};">
                <div class="card-badge">{badge}</div>
                <div class="card-temp">{row['temp_c']}°C</div>
                <div class="card-risk" style="color: {text_color};">{row['risk']}</div>
                <div class="card-delay">{row['total_delay']}m</div>
            </div>
            """

        # CSS: Uses 'inline-block' method which is much more robust than flexbox for this
        st.markdown(f"""
        <style>
        .scroll-outer-wrapper {{
            display: block;
            width: 100%;
            overflow-x: auto;
            white-space: nowrap;
            padding: 10px 0 20px 0; /* padding bottom for scrollbar */
            -webkit-overflow-scrolling: touch;
        }}
        
        /* The cards as inline blocks - this forces them into a single line */
        .weather-card {{
            display: inline-block !important;
            vertical-align: middle; /* Align them by their middle */
            margin-right: 12px;
            white-space: normal; /* Allow text inside to wrap if needed */
            text-align: center;
            border-radius: 12px;
            border: 1px solid #ddd;
            background-color: white;
            box-shadow: 0 2px 5px rgba(0,0,0,0.05);
            /* Important: Prevents squishing */
            flex-shrink: 0; 
        }}

        /* Specific Sizes with !important to ensure they stick */
        .card-small {{
            width: 85px !important;
            height: 100px !important;
            padding-top: 10px;
        }}
        .card-small .card-temp {{ font-size: 0.9rem; font-weight: bold; }}
        .card-small .card-risk {{ font-size: 0.7rem; }}
        
        .card-medium {{
            width: 110px !important;
            height: 120px !important;
            padding-top: 15px;
            border: 1px solid #bbb;
        }}
        .card-medium .card-temp {{ font-size: 1.1rem; font-weight: bold; }}
        .card-medium .card-risk {{ font-size: 0.8rem; }}
        
        .card-today {{
            width: 150px !important;
            height: 160px !important;
            padding-top: 20px;
            border: 3px solid #2962ff !important;
            background: #fff;
            box-shadow: 0 5px 15px rgba(41, 98, 255, 0.2);
            z-index: 2;
        }}
        .card-today .card-temp {{ font-size: 1.5rem; font-weight: 900; }}
        .card-today .card-risk {{ font-size: 1rem; font-weight: bold; }}

        .card-badge {{ font-weight: bold; margin-bottom: 5px; font-size: 0.85rem; }}
        .card-delay {{ opacity: 0.7; font-size: 0.8rem; margin-top: 5px; }}

        /* Scrollbar styling */
        .scroll-outer-wrapper::-webkit-scrollbar {{
            height: 8px;
        }}
        .scroll-outer-wrapper::-webkit-scrollbar-track {{
            background: #f1f1f1;
            border-radius: 4px;
        }}
        .scroll-outer-wrapper::-webkit-scrollbar-thumb {{
            background: #ccc;
            border-radius: 4px;
        }}
        </style>

        <div class="scroll-outer-wrapper">
            {cards_html}
        </div>
        """, unsafe_allow_html=True)
