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

@st.cache_data(ttl=3600)  # Cache data for 1 hour to prevent spamming the API
def get_weather_data(lat, lon):
    """
    Fetches 10 days of history and 7 days of forecast in a single call 
    using Open-Meteo's 'past_days' feature.
    """
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": ["temperature_2m", "relative_humidity_2m", "dew_point_2m", "wind_speed_10m", "weather_code"],
        "timezone": "auto",
        "past_days": 10,
        "forecast_days": 7
    }
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        # Process Hourly Data
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
        st.error(f"Error fetching weather data: {e}")
        return pd.DataFrame()

def calculate_frost_risk(row):
    """
    Determines frost/fog risk based on physics.
    """
    temp = row['temp_c']
    dew_point = row['dew_point_c']
    wind = row['wind_speed_kmh']
    humidity = row['humidity']
    
    # Dew Point Depression (Spread)
    spread = temp - dew_point
    
    risk_level = "None"
    color = "green"
    minutes_to_clear = 0
    condition = "Clear"

    # 1. ICE / FROST LOGIC
    # If temp is near freezing and close to dew point
    if temp <= 3.0: 
        if spread < 2.0 or (temp <= 0 and humidity > 80):
            if temp < -5:
                risk_level = "Severe Ice"
                color = "purple"
                minutes_to_clear = 15
                condition = "Hard Ice"
            elif temp <= 0:
                risk_level = "Frost/Ice"
                color = "red"
                minutes_to_clear = 10
                condition = "Icy"
            else:
                risk_level = "Light Frost"
                color = "orange"
                minutes_to_clear = 5
                condition = "Frosty"

    # 2. FOG LOGIC
    # High humidity, low wind, small spread
    elif spread < 2.5 and humidity > 90 and wind < 10:
        risk_level = "Fog"
        color = "gray"
        minutes_to_clear = 2 # Mostly for visibility check
        condition = "Foggy"
        
    return pd.Series([risk_level, color, minutes_to_clear, condition], 
                     index=['risk', 'color', 'base_minutes', 'condition'])

# --- MAIN APP UI ---

st.title("❄️ Windscreen Frost Predictor")
st.markdown("Plan your morning commute based on **Location**, **Weather**, and **Car Type**.")

# 1. INPUTS
with st.container():
    col1, col2 = st.columns(2)
    with col1:
        # Default to London, UK roughly
        lat = st.number_input("Latitude", value=51.50, format="%.4f")
    with col2:
        lon = st.number_input("Longitude", value=-0.12, format="%.4f")
        
    car_choice = st.selectbox("Select Car Type", list(CAR_TYPES.keys()))
    
    # Get Location Button (Mock functionality for web app)
    if st.button("📍 Use My Location (GeoIP Estimate)"):
        # Simple IP-based lookup for convenience
        try:
            loc_req = requests.get('https://ipapi.co/json/')
            loc_data = loc_req.json()
            lat = loc_data.get('latitude', 51.50)
            lon = loc_data.get('longitude', -0.12)
            st.success(f"Updated to: {loc_data.get('city')}, {loc_data.get('country_name')}")
            st.rerun()
        except:
            st.warning("Could not fetch location automatically.")

# 2. DATA PROCESSING
if lat and lon:
    df_raw = get_weather_data(lat, lon)
    
    if not df_raw.empty:
        # Apply Logic
        risk_cols = df_raw.apply(calculate_frost_risk, axis=1)
        df = pd.concat([df_raw, risk_cols], axis=1)
        
        # Filter for "Morning Commute" hours (e.g., 6 AM - 9 AM) for the summary
        # But we keep all data for the grid
        df['date'] = df['time'].dt.date
        df['hour'] = df['time'].dt.hour
        
        # Calculate Adjustments
        car_factor = CAR_TYPES[car_choice]['factor']
        df['total_delay'] = (df['base_minutes'] * car_factor).round().astype(int)

        # 3. TOMORROW'S PREDICTION (Hero Section)
        tomorrow = datetime.now().date() + timedelta(days=1)
        tomorrow_data = df[(df['date'] == tomorrow) & (df['hour'] == 7)] # Check 7 AM
        
        if not tomorrow_data.empty:
            row = tomorrow_data.iloc[0]
            delay = row['total_delay']
            
            st.divider()
            st.subheader(f"Tomorrow Morning (7:00 AM)")
            
            # Dynamic Banner
            if delay > 0:
                msg = f"❄️ LEAVE {delay} MINUTES EARLY"
                st.error(msg, icon="⚠️")
                st.markdown(f"**Forecast:** {row['condition']} ({row['temp_c']}°C). High chance of {row['risk'].lower()} on your {car_choice}.")
            else:
                st.success("✅ No Delays Expected", icon="🚗")
                st.markdown(f"**Forecast:** {row['condition']} ({row['temp_c']}°C). Windscreen should be clear.")
            st.divider()

        # 4. GRID VIEW (History & Future)
        st.subheader("📅 17-Day Overview (7 AM Snapshot)")
        
        # Filter to show only 7 AM for the grid to keep it clean (or average of morning)
        morning_df = df[df['hour'] == 7].copy()
        
        # Select columns for display
        display_df = morning_df[['date', 'temp_c', 'humidity', 'risk', 'total_delay']].copy()
        display_df['temp_c'] = display_df['temp_c'].apply(lambda x: f"{x}°C")
        display_df['humidity'] = display_df['humidity'].apply(lambda x: f"{x}%")
        display_df['total_delay'] = display_df['total_delay'].apply(lambda x: f"+{x} min" if x > 0 else "-")
        display_df.columns = ["Date", "Temp", "Humidity", "Risk", "Extra Time"]
        
        # Style the dataframe for the grid
        def color_risk(val):
            if val == "Severe Ice": color = '#ffcccb' # Red tint
            elif val == "Frost/Ice": color = '#ffe5b4' # Orange tint
            elif val == "Light Frost": color = '#fff9c4' # Yellow tint
            elif val == "Fog": color = '#f5f5f5' # Grey tint
            else: color = 'white'
            return f'background-color: {color}; color: black'

        # Show current day marker
        today_date = datetime.now().date()
        
        # Display editable grid (interactive) or static table
        st.dataframe(
            display_df.style.applymap(color_risk, subset=['Risk']),
            use_container_width=True,
            hide_index=True,
            height=500
        )
        
        st.caption("Note: Predictions are based on 7:00 AM weather conditions. Past data is historical, future data is forecasted.")
