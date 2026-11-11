# -*- coding: utf-8 -*-
"""
Air quality logic, categorization, and threshold evaluation.
Fixes logic bugs from legacy version (humidity elif ordering, eCO2 1500 threshold, typos),
handles sensor warm-up (AQI 0), derives fallback AQI from TVOC if needed,
and provides color-coded badges and descriptions for UI rendering.
"""

from typing import Dict, Any, Optional

# Color constants
COLOR_EMERALD = "#10b981"  # Excellent / Ideal
COLOR_BLUE    = "#3b82f6"  # Good / Normal
COLOR_AMBER   = "#f59e0b"  # Moderate / Fair / Elevated / Warming Up
COLOR_ORANGE  = "#f97316"  # Poor / Warm
COLOR_RED     = "#ef4444"  # Unhealthy / Bad / Serious
COLOR_PURPLE  = "#8b5cf6"  # Very High
COLOR_GRAY    = "#6b7280"  # Unknown / Missing


def derive_aqi_from_tvoc(tvoc: Optional[float]) -> Optional[int]:
    """
    Derive German UBA Air Quality Index (1-5) from TVOC (ppb)
    as a robust fallback when the sensor's AQI register is warming up or 0.
    UBA mapping:
    - < 400 ppb: 1 (Excellent)
    - 400 - 1000 ppb: 2 (Good)
    - 1000 - 1500 ppb: 3 (Moderate)
    - 1500 - 2200 ppb: 4 (Poor)
    - >= 2200 ppb: 5 (Unhealthy)
    """
    if tvoc is None:
        return None
    if tvoc < 400:
        return 1
    elif tvoc < 1000:
        return 2
    elif tvoc < 1500:
        return 3
    elif tvoc < 2200:
        return 4
    else:
        return 5


def classify_aqi(aqi: Optional[int]) -> Dict[str, str]:
    """
    Classify Air Quality Index (1 - 5).
    Includes handling for 0 (Warming Up).
    """
    mapping = {
        0: {"label": "Warming Up", "color": COLOR_AMBER,   "bg": "rgba(245, 158, 11, 0.15)"},
        1: {"label": "Excellent",  "color": COLOR_EMERALD, "bg": "rgba(16, 185, 129, 0.15)"},
        2: {"label": "Good",       "color": COLOR_BLUE,    "bg": "rgba(59, 130, 246, 0.15)"},
        3: {"label": "Moderate",   "color": COLOR_AMBER,   "bg": "rgba(245, 158, 11, 0.15)"},
        4: {"label": "Poor",       "color": COLOR_ORANGE,  "bg": "rgba(249, 115, 22, 0.15)"},
        5: {"label": "Unhealthy",  "color": COLOR_RED,     "bg": "rgba(239, 68, 68, 0.15)"}
    }
    if aqi in mapping:
        return mapping[aqi]
    return {"label": "Unknown", "color": COLOR_GRAY, "bg": "rgba(107, 114, 128, 0.15)"}


def classify_tvoc(tvoc: Optional[float]) -> Dict[str, str]:
    """
    Classify Total Volatile Organic Compounds (TVOC in ppb).
    < 400: Normal
    400 - 2200: Elevated (Ventilation advised)
    2200 - 3000: High (Action needed)
    >= 3000: Hazardous
    """
    if tvoc is None:
        return {"label": "N/A", "color": COLOR_GRAY, "bg": "rgba(107, 114, 128, 0.15)"}
    if tvoc < 400:
        return {"label": "Normal", "color": COLOR_EMERALD, "bg": "rgba(16, 185, 129, 0.15)"}
    elif tvoc < 2200:
        return {"label": "Elevated - Ventilate", "color": COLOR_AMBER, "bg": "rgba(245, 158, 11, 0.15)"}
    elif tvoc < 3000:
        return {"label": "High - Take Action", "color": COLOR_RED, "bg": "rgba(239, 68, 68, 0.15)"}
    else:
        return {"label": "Hazardous", "color": "#dc2626", "bg": "rgba(220, 38, 38, 0.2)"}


def classify_eco2(eco2: Optional[float]) -> Dict[str, str]:
    """
    Classify equivalent CO2 (eCO2 in ppm).
    400 - 600: Excellent
    600 - 800: Good
    800 - 1000: Fair
    1000 - 1500: Poor
    >= 1500: Bad (Fixed legacy typo that was 15000)
    """
    if eco2 is None:
        return {"label": "N/A", "color": COLOR_GRAY, "bg": "rgba(107, 114, 128, 0.15)"}
    if eco2 < 600:
        return {"label": "Excellent", "color": COLOR_EMERALD, "bg": "rgba(16, 185, 129, 0.15)"}
    elif eco2 < 800:
        return {"label": "Good", "color": COLOR_BLUE, "bg": "rgba(59, 130, 246, 0.15)"}
    elif eco2 < 1000:
        return {"label": "Fair", "color": COLOR_AMBER, "bg": "rgba(245, 158, 11, 0.15)"}
    elif eco2 < 1500:
        return {"label": "Poor", "color": COLOR_ORANGE, "bg": "rgba(249, 115, 22, 0.15)"}
    else:
        return {"label": "Bad", "color": COLOR_RED, "bg": "rgba(239, 68, 68, 0.15)"}


def classify_temp(temp_f: Optional[float]) -> Dict[str, str]:
    """Classify indoor temperature in Fahrenheit."""
    if temp_f is None:
        return {"label": "N/A", "color": COLOR_GRAY, "bg": "rgba(107, 114, 128, 0.15)"}
    if temp_f < 60:
        return {"label": "Very Low", "color": "#38bdf8", "bg": "rgba(56, 189, 248, 0.15)"}
    elif temp_f < 68:
        return {"label": "Cool", "color": COLOR_BLUE, "bg": "rgba(59, 130, 246, 0.15)"}
    elif temp_f <= 76:
        return {"label": "Ideal", "color": COLOR_EMERALD, "bg": "rgba(16, 185, 129, 0.15)"}
    elif temp_f < 80:
        return {"label": "Warm", "color": COLOR_AMBER, "bg": "rgba(245, 158, 11, 0.15)"}
    else:
        return {"label": "Very High", "color": COLOR_RED, "bg": "rgba(239, 68, 68, 0.15)"}


def get_recommended_humidity(outside_temp_f: Optional[float]) -> int:
    """Calculate recommended indoor relative humidity (%) based on outdoor temperature (°F)."""
    if outside_temp_f is None:
        return 45
    if outside_temp_f >= 40:
        return 45
    elif outside_temp_f >= 30:
        return 40
    elif outside_temp_f >= 20:
        return 35
    elif outside_temp_f >= 10:
        return 30
    elif outside_temp_f >= 0:
        return 25
    elif outside_temp_f >= -10:
        return 20
    else:
        return 15


def classify_humidity(humidity: Optional[float], outside_temp_f: Optional[float]) -> Dict[str, Any]:
    """
    Classify indoor humidity against weather-adjusted target.
    Fixes the inverted condition order from the legacy script.
    """
    if humidity is None:
        return {"label": "N/A", "color": COLOR_GRAY, "bg": "rgba(107, 114, 128, 0.15)", "target": 45}

    target = get_recommended_humidity(outside_temp_f)
    diff = humidity - target

    # Evaluate largest deviations first to prevent shadowing
    if abs(diff) > 10:
        label = "Very High" if diff > 0 else "Very Low"
        color = COLOR_RED
    elif abs(diff) > 5:
        label = "High" if diff > 0 else "Low"
        color = COLOR_AMBER
    elif abs(diff) > 3:
        label = "Ok"
        color = COLOR_BLUE
    else:
        label = "Optimal"
        color = COLOR_EMERALD

    bg = color.replace("#", "")
    r, g, b = int(bg[:2], 16), int(bg[2:4], 16), int(bg[4:], 16)
    return {
        "label": label,
        "color": color,
        "bg": f"rgba({r}, {g}, {b}, 0.15)",
        "target": target,
        "difference": round(diff, 1)
    }


def enrich_reading(reading: Dict[str, Any]) -> Dict[str, Any]:
    """Take a raw reading dict from the DB and augment it with evaluation labels and colors."""
    raw_aqi = reading.get("aqi")
    tvoc = reading.get("tvoc")

    # If AQI is None or 0 (warming up), try deriving from TVOC so dashboard always has an AQI
    effective_aqi = raw_aqi
    if (effective_aqi is None or effective_aqi == 0) and tvoc is not None:
        effective_aqi = derive_aqi_from_tvoc(tvoc)

    aqi_eval = classify_aqi(effective_aqi)
    tvoc_eval = classify_tvoc(tvoc)
    eco2_eval = classify_eco2(reading.get("eco2"))
    temp_eval = classify_temp(reading.get("temp"))
    hum_eval = classify_humidity(reading.get("hum"), reading.get("out_temp"))

    return {
        "timestamp": reading.get("timestamp"),
        "aqi": effective_aqi if effective_aqi is not None else raw_aqi,
        "aqi_label": aqi_eval["label"],
        "aqi_color": aqi_eval["color"],
        "aqi_bg": aqi_eval["bg"],

        "tvoc": tvoc,
        "tvoc_label": tvoc_eval["label"],
        "tvoc_color": tvoc_eval["color"],
        "tvoc_bg": tvoc_eval["bg"],

        "eco2": reading.get("eco2"),
        "eco2_label": eco2_eval["label"],
        "eco2_color": eco2_eval["color"],
        "eco2_bg": eco2_eval["bg"],

        "temp": reading.get("temp"),
        "temp_label": temp_eval["label"],
        "temp_color": temp_eval["color"],
        "temp_bg": temp_eval["bg"],

        "hum": reading.get("hum"),
        "hum_label": hum_eval["label"],
        "hum_color": hum_eval["color"],
        "hum_bg": hum_eval["bg"],
        "hum_target": hum_eval.get("target"),

        "out_temp": reading.get("out_temp"),
        "out_hum": reading.get("out_hum")
    }
