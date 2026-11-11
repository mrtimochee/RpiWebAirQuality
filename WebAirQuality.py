# -*- coding: utf-8 -*-
"""
WebAirQuality v2.0
Created on Tue Dec 19 21:24:38 2023
Modernized for high performance, zero SD card wear, and low CPU usage.

@author: Tim Mallen
"""

import os
import sys
import signal
import socket
import logging
from datetime import datetime
from flask import Flask, render_template, jsonify, request
from apscheduler.schedulers.background import BackgroundScheduler

# Internal modules
import database
import sensor_manager
import weather_service
import air_quality_logic

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("WebAirQuality")

# Initialize Flask app
app = Flask(__name__, template_folder="templates", static_folder="static")

# Sampling interval in seconds (safe for hardware, zero freeze-up)
SAMPLE_INTERVAL_SEC = 60
WEATHER_INTERVAL_HOURS = 1
PORT = 9999


def get_local_ip() -> str:
    """Detect the local IP address for console display."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Doesn't actually connect, just identifies preferred outbound route
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


# ============================================================================
# Scheduled Background Jobs
# ============================================================================

def job_sensor_sample():
    """Scheduled task: read sensors, query outdoor weather, and record to SQLite."""
    try:
        # 1. Read sensors (AM2302 & ENS160 with dynamic compensation)
        sensors = sensor_manager.read_all_sensors()

        # 2. Get outdoor conditions from weather service
        out_temp, out_hum = weather_service.get_current_outdoor()

        # 3. Store reading in SQLite
        row_id = database.add_reading(
            aqi=sensors.get("aqi"),
            tvoc=sensors.get("tvoc"),
            eco2=sensors.get("eco2"),
            temp=sensors.get("temp"),
            hum=sensors.get("hum"),
            out_temp=out_temp,
            out_hum=out_hum
        )
        logger.info(
            f"Sample #{row_id}: AQI={sensors.get('aqi')}, TVOC={sensors.get('tvoc')} ppb, "
            f"eCO2={sensors.get('eco2')} ppm, Temp={sensors.get('temp')}°F, Hum={sensors.get('hum')}% "
            f"(Out: {out_temp}°F, {out_hum}%)"
        )
    except Exception as e:
        logger.error(f"Error during sensor sample job: {e}", exc_info=True)


def job_weather_update():
    """Scheduled task: refresh NWS hourly forecast cache."""
    try:
        logger.info("Updating NWS weather forecast cache...")
        weather_service.update_forecast()
    except Exception as e:
        logger.error(f"Error updating weather forecast: {e}")


def job_db_prune():
    """Scheduled task: prune readings older than 30 days to keep database compact."""
    try:
        deleted = database.prune_old_readings(days=30)
        if deleted > 0:
            logger.info(f"Database maintenance: pruned {deleted} records older than 30 days.")
    except Exception as e:
        logger.error(f"Error pruning database: {e}")


# ============================================================================
# Flask Web Routes & REST API
# ============================================================================

@app.route('/')
def index():
    """Serve the modern dark-mode air quality dashboard."""
    return render_template('index.html')


@app.route('/api/current')
def api_current():
    """Return latest reading enriched with status labels and color badges."""
    latest = database.get_latest_reading()
    if not latest:
        # If DB is empty, read sensors on the fly
        sensors = sensor_manager.read_all_sensors()
        out_temp, out_hum = weather_service.get_current_outdoor()
        raw = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "aqi": sensors.get("aqi"),
            "tvoc": sensors.get("tvoc"),
            "eco2": sensors.get("eco2"),
            "temp": sensors.get("temp"),
            "hum": sensors.get("hum"),
            "out_temp": out_temp,
            "out_hum": out_hum
        }
        return jsonify(air_quality_logic.enrich_reading(raw))

    return jsonify(air_quality_logic.enrich_reading(latest))


@app.route('/api/history')
def api_history():
    """
    Return time series historical data for charting.
    Query parameter: ?hours=24 (default: 24 hours).
    """
    try:
        hours = float(request.args.get('hours', 24.0))
    except ValueError:
        hours = 24.0

    history = database.get_history(hours=hours)
    return jsonify(history)


@app.route('/api/weather')
def api_weather():
    """Return status of outdoor weather forecast."""
    return jsonify(weather_service.get_weather_status())


@app.route('/api/status')
def api_status():
    """Return system diagnostic and health status."""
    db_stats = database.get_db_stats()
    return jsonify({
        "status": "online",
        "hardware_active": sensor_manager.HARDWARE_AVAILABLE,
        "sample_interval_sec": SAMPLE_INTERVAL_SEC,
        "database": db_stats
    })


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == '__main__':
    logger.info("=" * 60)
    logger.info("Starting WebAirQuality Dashboard Server v2.0")
    logger.info("=" * 60)

    # 1. Initialize SQLite database & check for legacy migration
    database.init_db()

    # 2. Pre-fetch weather forecast
    weather_service.update_forecast()

    # 3. Take initial sensor sample immediately so dashboard has data right away
    logger.info("Taking initial sensor baseline reading...")
    job_sensor_sample()

    # 4. Start BackgroundScheduler
    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(job_sensor_sample, 'interval', seconds=SAMPLE_INTERVAL_SEC, max_instances=1, replace_existing=True)
    scheduler.add_job(job_weather_update, 'interval', hours=WEATHER_INTERVAL_HOURS, max_instances=1, replace_existing=True)
    scheduler.add_job(job_db_prune, 'cron', hour=3, minute=0, max_instances=1, replace_existing=True)  # Daily at 3 AM
    scheduler.start()
    logger.info(f"Interval scheduler active: sampling every {SAMPLE_INTERVAL_SEC}s.")

    # 5. Display access URL
    local_ip = get_local_ip()
    logger.info("=" * 60)
    logger.info(f"Dashboard available at: http://{local_ip}:{PORT}/")
    logger.info(f"Local loopback:         http://localhost:{PORT}/")
    logger.info("=" * 60)

    # 6. Graceful shutdown handler
    def shutdown_handler(signum, frame):
        logger.info("Received termination signal. Shutting down scheduler...")
        scheduler.shutdown(wait=False)
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    # 7. Start Flask server (handles requests concurrently without busy loops)
    try:
        app.run(host="0.0.0.0", port=PORT, debug=False, use_reloader=False)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Server terminated.")
        scheduler.shutdown(wait=False)
