import time
import board
import adafruit_ens160
import Adafruit_DHT

print("Initializing I2C bus and ENS160...")
i2c = board.I2C()  # uses board.SCL and board.SDA

ens = adafruit_ens160.ENS160(i2c)

# Explicitly ensure standard operating mode (MODE_STANDARD = 0x02)
ens.mode = adafruit_ens160.MODE_STANDARD
time.sleep(0.1)

print("Reading AM2302 on GPIO 4...")
hum, temp = Adafruit_DHT.read_retry(Adafruit_DHT.AM2302, 4)  # (Sensor, Pin)

if hum is not None and temp is not None:
    print(f"AM2302 baseline: Temp={temp}°C, Humidity={hum}%")
    ens.temperature_compensation = temp
    ens.humidity_compensation = hum
else:
    print("Warning: AM2302 returned None; using defaults (23°C, 55%)")
    ens.temperature_compensation = 23.0
    ens.humidity_compensation = 55.0

print("\nStarting ENS160 monitoring loop (Ctrl+C to stop)...")
status_map = {0: "Normal Operation", 1: "Warm-Up Phase (first 3 min)", 2: "Initial Startup Phase", 3: "Invalid Output"}

while True:
    validity = getattr(ens, "data_validity", None)
    new_data = getattr(ens, "new_data_available", None)
    status_str = status_map.get(validity, f"Status Code {validity}")

    raw_aqi = getattr(ens, "AQI", None)
    raw_tvoc = getattr(ens, "TVOC", None)
    raw_eco2 = getattr(ens, "eCO2", None)

    print(f"--- Sensor Status: {status_str} (New Data Ready: {new_data}) ---")
    print(f"  AQI (1-5):  {raw_aqi}")
    print(f"  TVOC (ppb): {raw_tvoc}")
    print(f"  eCO2 (ppm): {raw_eco2}")

    hum, temp = Adafruit_DHT.read_retry(Adafruit_DHT.AM2302, 4)
    temp_f = round((temp * 9 / 5) + 32, 1) if temp is not None else None
    print(f"  Indoor:     {temp_f}°F ({temp}°C), {hum}% RH")
    print()

    time.sleep(3)
