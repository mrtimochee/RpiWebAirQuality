# -*- coding: utf-8 -*-
"""
Sensor manager for AM2302 (Temperature & Humidity) and ENS160 (AQI, TVOC, eCO2).
Features dynamic sensor compensation: feeds live AM2302 temperature and humidity
into the ENS160 registers for maximum accuracy.
Includes robust fallback for sensor warm-up states and simulation mode for testing.
"""

import sys
import random
import time
from typing import Tuple, Optional, Dict, Any

from air_quality_logic import derive_aqi_from_tvoc

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

    # Ensure sensor is in active standard gas sensing mode (MODE_STANDARD = 0x02)
    try:
        ens.mode = adafruit_ens160.MODE_STANDARD
        time.sleep(0.05)
    except Exception as mode_err:
        print(f"[Sensors] Notice: setting mode: {mode_err}")

    # Initial baseline compensation
    ens.temperature_compensation = 23.0
    ens.humidity_compensation = 55.0
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
                if ens is not None:
                    ens.temperature_compensation = float(round(temp_c, 1))
                    ens.humidity_compensation = float(round(humidity, 1))
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
    Handles warm-up status safely without crashing on None or 0.
    """
    if not HARDWARE_AVAILABLE or ens is None:
        # Mock values for development/testing
        sim_tvoc = round(random.uniform(50.0, 250.0), 1)
        sim_aqi = derive_aqi_from_tvoc(sim_tvoc) or 1
        sim_eco2 = round(random.uniform(410.0, 580.0), 1)
        return sim_aqi, sim_tvoc, sim_eco2

    aqi = None
    tvoc = None
    eco2 = None

    try:
        # Check if sensor has data ready or validity flag
        validity = getattr(ens, "data_validity", 0)

        # Read TVOC and eCO2 first
        raw_tvoc = getattr(ens, "TVOC", None)
        if raw_tvoc is not None:
            tvoc = float(raw_tvoc)

        raw_eco2 = getattr(ens, "eCO2", None)
        if raw_eco2 is not None:
            eco2 = float(raw_eco2)

        # Read AQI
        raw_aqi = getattr(ens, "AQI", None)
        if raw_aqi is not None:
            try:
                val = int(raw_aqi)
                if 1 <= val <= 5:
                    aqi = val
                elif val == 0:
                    # Sensor is in warm-up (0). Derive AQI from TVOC if TVOC is available
                    aqi = derive_aqi_from_tvoc(tvoc) if tvoc is not None else 0
                else:
                    aqi = val
            except (ValueError, TypeError):
                aqi = derive_aqi_from_tvoc(tvoc)
        elif tvoc is not None:
            # Fallback when raw_aqi is None
            aqi = derive_aqi_from_tvoc(tvoc)

        return aqi, tvoc, eco2
    except Exception as e:
        print(f"[Sensors] Error reading ENS160: {e}")

    return aqi, tvoc, eco2


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
