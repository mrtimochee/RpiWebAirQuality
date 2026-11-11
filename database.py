# -*- coding: utf-8 -*-
"""
Database module for WebAirQuality.
Uses SQLite with WAL mode for fast, crash-resilient storage with zero SD card wear.
Includes automatic one-time migration from legacy aq_data.pkl if present.
"""

import os
import sqlite3
import datetime as dt
from typing import Optional, Dict, Any, List

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "air_quality.db")
LEGACY_PKL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "aq_data.pkl")


def get_connection() -> sqlite3.Connection:
    """Create a connection to the SQLite database with WAL mode enabled."""
    conn = sqlite3.connect(DB_FILE, timeout=10)
    conn.row_factory = sqlite3.Row
    # Enable Write-Ahead Logging for concurrency and power-loss resilience
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn


def init_db():
    """Initialize SQLite database tables and indexes, and migrate legacy pkl if found."""
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                aqi INTEGER,
                tvoc REAL,
                eco2 REAL,
                temp REAL,
                hum REAL,
                out_temp REAL,
                out_hum REAL
            );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON readings(timestamp);")
        conn.commit()

    # Migrate legacy pickle data if exists
    _migrate_legacy_pickle()


def _migrate_legacy_pickle():
    """Migrate data from legacy aq_data.pkl if present and database is empty."""
    if not os.path.exists(LEGACY_PKL):
        return

    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM readings")
            count = cur.fetchone()[0]
            if count > 0:
                # Database already has data, no migration needed
                return

        # Attempt to import pandas and read the pickle file
        try:
            import pandas as pd
            df = pd.read_pickle(LEGACY_PKL)
            print(f"[Database] Migrating {len(df)} records from legacy {LEGACY_PKL} to SQLite...")

            with get_connection() as conn:
                for idx, row in df.iterrows():
                    ts_str = idx.strftime("%Y-%m-%d %H:%M:%S") if hasattr(idx, 'strftime') else str(idx)
                    conn.execute("""
                        INSERT INTO readings (timestamp, aqi, tvoc, eco2, temp, hum, out_temp, out_hum)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        ts_str,
                        int(row['aqi']) if pd.notnull(row.get('aqi')) else None,
                        float(row['tvoc']) if pd.notnull(row.get('tvoc')) else None,
                        float(row['eco2']) if pd.notnull(row.get('eco2')) else None,
                        float(row['temp']) if pd.notnull(row.get('temp')) else None,
                        float(row['hum']) if pd.notnull(row.get('hum')) else None,
                        float(row['out_temp']) if pd.notnull(row.get('out_temp')) else None,
                        float(row['out_hum']) if pd.notnull(row.get('out_hum')) else None,
                    ))
                conn.commit()

            # Rename pkl to backup
            bak_path = LEGACY_PKL + ".bak"
            if not os.path.exists(bak_path):
                os.rename(LEGACY_PKL, bak_path)
            print("[Database] Legacy pickle migration complete.")
        except Exception as e:
            print(f"[Database] Notice: Legacy pickle migration skipped ({e})")
    except Exception as e:
        print(f"[Database] Migration check failed: {e}")


def add_reading(aqi: Optional[int], tvoc: Optional[float], eco2: Optional[float],
                temp: Optional[float], hum: Optional[float],
                out_temp: Optional[float], out_hum: Optional[float],
                timestamp: Optional[str] = None) -> int:
    """Insert a new sensor reading into the database."""
    if timestamp is None:
        timestamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO readings (timestamp, aqi, tvoc, eco2, temp, hum, out_temp, out_hum)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (timestamp, aqi, tvoc, eco2, temp, hum, out_temp, out_hum))
        conn.commit()
        return cursor.lastrowid


def get_latest_reading() -> Optional[Dict[str, Any]]:
    """Retrieve the single most recent sensor reading."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, timestamp, aqi, tvoc, eco2, temp, hum, out_temp, out_hum
            FROM readings
            ORDER BY id DESC
            LIMIT 1
        """)
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None


def get_history(hours: float = 24.0, max_points: int = 1500) -> Dict[str, List]:
    """
    Retrieve historical readings for the past N hours, downsampling if too many points.
    Returns dictionary with lists suited for charting.
    """
    cutoff = (dt.datetime.now() - dt.timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT timestamp, aqi, tvoc, eco2, temp, hum, out_temp, out_hum
            FROM readings
            WHERE timestamp >= ?
            ORDER BY timestamp ASC
        """, (cutoff,))
        rows = cursor.fetchall()

    total_rows = len(rows)
    # Downsample if count exceeds max_points to keep payload compact & client fast
    step = 1
    if total_rows > max_points:
        step = int(total_rows / max_points) + 1

    selected_rows = rows[::step]

    data = {
        "timestamps": [r["timestamp"] for r in selected_rows],
        "aqi": [r["aqi"] for r in selected_rows],
        "tvoc": [r["tvoc"] for r in selected_rows],
        "eco2": [r["eco2"] for r in selected_rows],
        "temp": [r["temp"] for r in selected_rows],
        "hum": [r["hum"] for r in selected_rows],
        "out_temp": [r["out_temp"] for r in selected_rows],
        "out_hum": [r["out_hum"] for r in selected_rows]
    }
    return data


def prune_old_readings(days: int = 30) -> int:
    """Delete readings older than specified number of days to keep DB compact."""
    cutoff = (dt.datetime.now() - dt.timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM readings WHERE timestamp < ?", (cutoff,))
        conn.commit()
        deleted = cursor.rowcount
        return deleted


def get_db_stats() -> Dict[str, Any]:
    """Get database record count and file size."""
    size_bytes = os.path.getsize(DB_FILE) if os.path.exists(DB_FILE) else 0
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM readings")
        count = cursor.fetchone()[0]
    return {
        "record_count": count,
        "size_kb": round(size_bytes / 1024, 1),
        "db_path": DB_FILE
    }
