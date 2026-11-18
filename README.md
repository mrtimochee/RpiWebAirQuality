# RpiWebAirQuality v2.0

A high-performance Raspberry Pi air quality monitor and responsive web dashboard. Samples temperature, humidity, AQI, eCO2, and TVOC from onboard sensors, retrieves outdoor weather forecasts, and serves an interactive real-time dashboard.

---

## Key Improvements in v2.0
- **< 1% CPU Utilization**: Replaced the server-side Plotly rendering pipeline and main-thread busy loop with client-side canvas charting (Chart.js) and a lightweight Flask REST API.
- **Zero SD Card Wear**: Migrated from rewriting monolithic pickle and HTML files every minute to an atomic SQLite database with Write-Ahead Logging (WAL).
- **Dynamic Sensor Compensation**: Feeds live ambient temperature and humidity from the AM2302 directly into the ENS160 registers for maximum VOC and eCO2 measurement accuracy.
- **Responsive Dark-Mode UI**: Mobile-friendly dashboard with live status cards, scale indicators, and interactive synchronized charts with configurable time horizons (6h, 12h, 24h, 3d, 7d).
- **Installable Progressive Web App (PWA)**: Complete with Web App Manifest, Service Worker offline caching, and high-resolution icons. Can be installed directly to home screens on iOS, Android, and Desktop as a standalone app.
- **Mobile-Optimized Touch Experience**: Automatic suppression of sticky hover tooltips on touch devices allowing seamless, frictionless vertical scrolling across graphs.
- **Automatic Legacy Migration**: Seamlessly imports historical data from `aq_data.pkl` into the new SQLite database on first startup.

---

## Hardware
- **Raspberry Pi** (3, 4, 5, or Zero 2 W)
- **ENS160** Air Quality Sensor (I2C)
- **AM2302 / DHT22** Temperature & Humidity Sensor (GPIO Pin 4)

---

## Software & Dependencies
- Python 3.8+
- Flask
- APScheduler
- Requests
- Adafruit_DHT
- adafruit-circuitpython-ens160

### One-Command Setup:
```bash
chmod +x WebAirQuality_dependacies.sh
./WebAirQuality_dependacies.sh
```

Or manually install via pip:
```bash
pip3 install flask apscheduler requests adafruit-circuitpython-ens160 Adafruit_DHT
```

### Hardware Configuration:
Enable I2C on the Raspberry Pi:
```bash
sudo raspi-config
# Navigate to: Interface Options -> I2C -> Enable
```

---

## Usage
Start the dashboard server:
```bash
python3 WebAirQuality.py
```

Access the dashboard from any browser on your local network:
```
http://<raspberrypi-ip>:9999/
# Or via mDNS:
http://raspberrypi.local:9999/
```

Default port is `9999`.

---

## Installing as a Progressive Web App (PWA)
You can install the dashboard directly as a standalone app with its own home screen icon:
- **Android / Chrome / Edge**: Click the **📲 Install App** button in the header, or tap browser menu (⋮) -> **Install app** / **Add to Home screen**.
- **iOS / Safari**: Tap the **Share** button (box with upward arrow) -> **Add to Home Screen**.
- **Desktop (Chrome/Edge)**: Click the install icon in the address bar or the header button.

---

## REST API Endpoints
The backend provides lightweight JSON endpoints for integration into Home Assistant or custom tools:
- `GET /api/current`: Returns the latest sensor readings, outdoor weather, evaluation labels, and badge colors.
- `GET /api/history?hours=24`: Returns time series data points for plotting (supports 6, 12, 24, 72, 168 hours).
- `GET /api/weather`: Returns cached National Weather Service hourly forecast information.
- `GET /api/status`: Returns system diagnostics, database record count, and hardware status.

---

## Running as a System Service (Optional)
To ensure the dashboard runs automatically in the background on system boot:

1. Create a service file:
```bash
sudo nano /etc/systemd/system/airquality.service
```

2. Add the following configuration (adjust paths and user as appropriate):
```ini
[Unit]
Description=Raspberry Pi Web Air Quality Service
After=network.target

[Service]
User=pi
WorkingDirectory=/home/pi/RpiWebAirQuality
ExecStart=/usr/bin/python3 /home/pi/RpiWebAirQuality/WebAirQuality.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

3. Enable and start the service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable airquality
sudo systemctl start airquality
```
