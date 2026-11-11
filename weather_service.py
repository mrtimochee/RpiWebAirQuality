# -*- coding: utf-8 -*-
"""
Weather service for National Weather Service (NWS) hourly forecast.
Caches hourly forecasts in-memory and provides the closest current outdoor
temperature and humidity.
"""

import requests
import datetime as dt
from typing import Tuple, Optional, Dict, Any, List

# Default gridpoint (user's area: LWX/118,101). Can be configured.
NWS_URL = "https://api.weather.gov/gridpoints/LWX/118,101/forecast/hourly"
HEADERS = {
    "User-Agent": "RpiWebAirQuality/2.0 (Raspberry Pi Air Quality Dashboard, github.com/rpi-air-quality)",
    "Accept": "application/geo+json, application/json"
}

_forecast_cache: List[Dict[str, Any]] = []
_last_fetch_time: Optional[dt.datetime] = None


def update_forecast() -> bool:
    """Fetch hourly forecast from NWS API and update the cache."""
    global _forecast_cache, _last_fetch_time
    try:
        response = requests.get(NWS_URL, headers=HEADERS, timeout=10)
        if response.status_code == 200:
            data = response.json()
            periods = data.get("properties", {}).get("periods", [])
            parsed = []
            for p in periods:
                start_iso = p.get("startTime", "")
                try:
                    # Strip timezone offset for datetime parsing if needed
                    dt_obj = dt.datetime.fromisoformat(start_iso[:-6] if "+" in start_iso or "-" in start_iso[-6:] else start_iso)
                    parsed.append({
                        "time": dt_obj,
                        "temperature": p.get("temperature"),
                        "humidity": p.get("relativeHumidity", {}).get("value", 50),
                        "short_forecast": p.get("shortForecast", "")
                    })
                except Exception:
                    continue

            if parsed:
                _forecast_cache = parsed
                _last_fetch_time = dt.datetime.now()
                print(f"[Weather] Successfully loaded {len(parsed)} forecast periods from NWS.")
                return True
        else:
            print(f"[Weather] NWS API returned HTTP {response.status_code}")
    except Exception as e:
        print(f"[Weather] Could not fetch forecast from NWS: {e}")

    return False


def get_current_outdoor() -> Tuple[Optional[float], Optional[float]]:
    """
    Find outdoor temperature (°F) and humidity (%) closest to the current time.
    Returns (outdoor_temp, outdoor_humidity).
    """
    global _forecast_cache
    if not _forecast_cache:
        # If cache is empty, attempt an initial fetch
        update_forecast()

    if not _forecast_cache:
        return None, None

    now = dt.datetime.now()
    try:
        closest = min(_forecast_cache, key=lambda p: abs(p["time"] - now))
        return float(closest["temperature"]), float(closest["humidity"])
    except Exception as e:
        print(f"[Weather] Error reading closest forecast: {e}")
        return None, None


def get_weather_status() -> Dict[str, Any]:
    """Return status summary of the weather service."""
    outdoor_temp, outdoor_hum = get_current_outdoor()
    return {
        "outdoor_temp": outdoor_temp,
        "outdoor_hum": outdoor_hum,
        "last_fetched": _last_fetch_time.strftime("%Y-%m-%d %H:%M:%S") if _last_fetch_time else None,
        "cached_periods": len(_forecast_cache)
    }
