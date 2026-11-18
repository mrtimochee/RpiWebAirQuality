# -*- coding: utf-8 -*-
"""
Sensor manager for AM2302 (Temperature & Humidity) and ENS160 (AQI, TVOC, eCO2).
Features dynamic sensor compensation: feeds live AM2302 temperature and humidity
into the ENS160 registers for maximum accuracy.
Includes simulated fallback mode if executed outside Raspberry Pi hardware.
"""

import sys
import random
from typing import Tuple, Optional, Dict, Any

DHT_PIN = 4

# Check for Raspberry Pi GPIO / CircuitPython hardware support
HARDWARE_AVAILABLE = False
sensor_dht = None
ens = None

try:
    import board
    import RPi.GPIO as GPIO
    import Adafruit_DHT
    import adafruit_ens160

    GPIO.setmode(GPIO.BCM)
    sensor_dht = Adafruit_DHT.AM2302

    i2c = board.I2C()
    ens = adafruit_ens160.ENS160(i2c)

    # Initial baseline compensation
    ens.temperature_compensation = 23
    ens.humidity_compensation = 55
    HARDWARE_AVAILABLE = True
    print("[Sensors] Hardware initialized successfully (AM2302 on GPIO 4, ENS160 on I2C).")
except Exception as e:
    HARDWARE_AVAILABLE = False
    print(f"[Sensors] Hardware libraries not loaded ({e}).")
    print("[Sensors] Running in simulation/mock mode for testing.")


def read_am2302() -> Tuple[Optional[float], Optional[float]]:
    """
    Read AM2302 temperature and humidity.
    Returns (temp_f, humidity_percent).
    """
    if not HARDWARE_AVAILABLE:
        # Mock values for development/testing
        sim_temp_f = round(random.uniform(70.0, 74.0), 1)
        sim_hum = round(random.uniform(40.0, 48.0), 1)
        return sim_temp_f, sim_hum

    try:
        humidity, temp_c = Adafruit_DHT.read_retry(sensor_dht, DHT_PIN)
        if humidity is not None and temp_c is not None:
            # Dynamically calibrate ENS160 with ambient conditions
            try:
                ens.temperature_compensation = int(temp_c)
                ens.humidity_compensation = int(humidity)
            except Exception as cal_err:
                print(f"[Sensors] Warning: compensation update failed: {cal_err}")

            temp_f = round((temp_c * 9.0 / 5.0) + 32.0, 1)
            return temp_f, round(humidity, 1)
    except Exception as e:
        print(f"[Sensors] Error reading AM2302: {e}")

    return None, None


def read_ens160() -> Tuple[Optional[int], Optional[float], Optional[float]]:
    """
    Read ENS160 air quality sensor.
    Returns (aqi, tvoc_ppb, eco2_ppm).
    """
    if not HARDWARE_AVAILABLE:
        # Mock values for development/testing
        sim_aqi = random.choice([1, 1, 1, 2])
        sim_tvoc = round(random.uniform(50.0, 250.0), 1)
        sim_eco2 = round(random.uniform(410.0, 580.0), 1)
        return sim_aqi, sim_tvoc, sim_eco2

    try:
        aqi = int(ens.AQI)
        tvoc = float(ens.TVOC)
        eco2 = float(ens.eCO2)
        return aqi, tvoc, eco2
    except Exception as e:
        print(f"[Sensors] Error reading ENS160: {e}")

    return None, None, None


def read_all_sensors() -> Dict[str, Any]:
    """Read all sensors and return a dictionary of results."""
    temp_f, hum = read_am2302()
    aqi, tvoc, eco2 = read_ens160()

    return {
        "aqi": aqi,
        "tvoc": tvoc,
        "eco2": eco2,
        "temp": temp_f,
        "hum": hum,
        "hardware_active": HARDWARE_AVAILABLE
    }
