❄️ Windscreen Frost Predictor

A mobile-friendly web application that predicts if your car windscreen will be frozen, frosted, or foggy based on weather data and your specific vehicle type.

Features

Smart Prediction: Uses Temperature, Dew Point, and Humidity to calculate frost risk.

Car Customization: Adjusts "time to leave" based on vehicle size (Van vs. Mini).

Hybrid Data: Shows a single grid containing 10 days of history and 7 days of future forecast.

Mobile Friendly: Built with Streamlit for a responsive UI.

How to Run

Clone the repo

git clone [https://github.com/yourusername/frost-predictor.git](https://github.com/yourusername/frost-predictor.git)
cd frost-predictor


Install dependencies

pip install -r requirements.txt


Run the App

streamlit run app.py


View it
Open your browser to http://localhost:8501. On mobile, ensure your phone is on the same WiFi as your computer and visit http://YOUR_COMPUTER_IP:8501.

Logic

The app calculates the Dew Point Depression (Temperature - Dew Point).

Frost: If Temp ≤ 3°C AND Depression is low.

Ice: If Temp ≤ 0°C AND High Humidity.

Fog: If Temp ≈ Dew Point AND Low Wind.
