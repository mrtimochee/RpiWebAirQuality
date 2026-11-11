# -*- coding: utf-8 -*-
"""
Reads data from the SQLite database and prints out the last 20 rows.
"""

import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), "..", "air_quality.db")

if not os.path.exists(db_path):
    print(f"Database not found at {db_path}. Run WebAirQuality.py first.")
    exit(1)

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

cur.execute("""
    SELECT id, timestamp, aqi, tvoc, eco2, temp, hum, out_temp, out_hum
    FROM readings
    ORDER BY id DESC
    LIMIT 20
""")

rows = cur.fetchall()
print(f"Total returned: {len(rows)} latest records (newest first):\n")
for r in rows:
    print(dict(r))

conn.close()
