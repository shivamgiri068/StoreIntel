import sqlite3
import json
import os
import uuid
from datetime import datetime

DB_PATH = os.getenv("DB_PATH", "/app/data/store_intelligence.db")

def get_db_connection():
    db_dir = os.path.dirname(DB_PATH)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create tables
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS zones (
        name TEXT PRIMARY KEY,
        type TEXT,
        polygon_coordinates TEXT
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS events (
        id TEXT PRIMARY KEY,
        event_type TEXT,
        timestamp TEXT,
        customer_id TEXT,
        zone_name TEXT,
        x REAL,
        y REAL,
        metadata TEXT
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS anomalies (
        id TEXT PRIMARY KEY,
        anomaly_type TEXT,
        severity TEXT,
        timestamp TEXT,
        description TEXT,
        resolved INTEGER DEFAULT 0
    )
    """)
    
    conn.commit()
    
    # Seed zones if empty
    cursor.execute("SELECT COUNT(*) FROM zones")
    if cursor.fetchone()[0] == 0:
        default_zones = [
            ("Entrance", "ENTRY", json.dumps([[0, 500], [1280, 500], [1280, 720], [0, 720]])),
            ("Skincare & Serums Shelf", "SHELF", json.dumps([[600, 100], [1200, 100], [1200, 450], [600, 450]])),
            ("Lipsticks & Makeup Shelf", "SHELF", json.dumps([[100, 100], [550, 100], [550, 450], [100, 450]])),
            ("Checkout Area", "CHECKOUT", json.dumps([[900, 500], [1280, 500], [1280, 720], [900, 720]]))
        ]
        cursor.executemany("INSERT INTO zones VALUES (?, ?, ?)", default_zones)
        conn.commit()
        
    conn.close()

def save_event(event_id, event_type, timestamp, customer_id, zone_name, x, y, metadata_dict):
    conn = get_db_connection()
    cursor = conn.cursor()
    metadata_json = json.dumps(metadata_dict) if metadata_dict else "{}"
    try:
        cursor.execute(
            "INSERT INTO events VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (event_id, event_type, timestamp, customer_id, zone_name, x, y, metadata_json)
        )
        conn.commit()
    except Exception as e:
        print(f"Error saving event: {e}")
    finally:
        conn.close()

def get_events(limit=50):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM events ORDER BY timestamp DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_anomalies(active_only=True):
    conn = get_db_connection()
    cursor = conn.cursor()
    if active_only:
        cursor.execute("SELECT * FROM anomalies WHERE resolved = 0 ORDER BY timestamp DESC")
    else:
        cursor.execute("SELECT * FROM anomalies ORDER BY timestamp DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def resolve_anomaly_db(anomaly_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE anomalies SET resolved = 1 WHERE id = ?", (anomaly_id,))
    conn.commit()
    rows_affected = cursor.rowcount
    conn.close()
    return rows_affected > 0

def save_anomaly(anomaly_id, anomaly_type, severity, timestamp, description):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO anomalies (id, anomaly_type, severity, timestamp, description, resolved) VALUES (?, ?, ?, ?, ?, 0)",
            (anomaly_id, anomaly_type, severity, timestamp, description)
        )
        conn.commit()
    except Exception as e:
        print(f"Error saving anomaly: {e}")
    finally:
        conn.close()
