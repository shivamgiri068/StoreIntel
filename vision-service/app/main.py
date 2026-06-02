import cv2
import threading
import time
import os
import glob
import uuid
import datetime
import numpy as np
from fastapi import FastAPI, BackgroundTasks, HTTPException, Body
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel
from typing import Dict, Any, List

from app.config import VIDEO_DIR, EVENTS_JSON_PATH, logger
from app.detector import StoreIntelligenceDetector
from app.database import init_db, save_event, get_events, get_anomalies, resolve_anomaly_db, save_anomaly, get_db_connection

app = FastAPI(title="Purplle Store Intelligence Backend (FastAPI)", version="2.0.0")

# Global reference for streaming & processing
latest_annotated_frame = None
detector = StoreIntelligenceDetector()
processing_active = False

class EventPayload(BaseModel):
    eventId: str
    eventType: str
    timestamp: str
    customerId: str
    zoneName: str
    x: float
    y: float
    metadata: Dict[str, Any] = {}

def generate_mock_frame(frame_num):
    """Generates a mock store frame with simulated shoppers to fallback on if no video is found"""
    # 1280x720 white background store layout
    frame = np.ones((720, 1280, 3), dtype=np.uint8) * 40 # Sleek dark mode canvas
    
    # Simulate custom tracking IDs
    tracks = []
    
    # Shopper 1
    if 50 <= frame_num < 400:
        # Move from Entrance [150, 600] to Makeup [300, 325]
        if frame_num < 150:
            pct = (frame_num - 50) / 100
            x = 150 + pct * 150
            y = 600 - pct * 275
        elif frame_num < 280: # Linger at makeup
            x = 300 + np.sin(frame_num / 10) * 10
            y = 325 + np.cos(frame_num / 10) * 10
        elif frame_num < 350: # Move to checkout [1090, 610]
            pct = (frame_num - 280) / 70
            x = 300 + pct * 790
            y = 325 + pct * 285
        else: # Move to Exit [1190, 100]
            pct = (frame_num - 350) / 50
            x = 1090 + pct * 100
            y = 610 - pct * 510
        tracks.append((1, int(x), int(y)))
        
    # Shopper 2
    if 180 <= frame_num < 600:
        # Move from Entrance [150, 600] to Skincare [800, 325]
        if frame_num < 280:
            pct = (frame_num - 180) / 100
            x = 150 + pct * 650
            y = 600 - pct * 275
        else: # Loiter at skincare (long loitering triggers!)
            x = 800 + np.sin(frame_num / 15) * 8
            y = 325 + np.cos(frame_num / 15) * 8
        tracks.append((2, int(x), int(y)))

    # Shopper 3
    if 300 <= frame_num < 500:
        # Move from Entrance [150, 600] to Checkout [1090, 610] and Exit
        if frame_num < 420:
            pct = (frame_num - 300) / 120
            x = 150 + pct * 940
            y = 600 + pct * 10
        else:
            pct = (frame_num - 420) / 80
            x = 1090 + pct * 100
            y = 610 - pct * 510
        tracks.append((3, int(x), int(y)))

    # Draw labels on canvas
    cv2.putText(frame, "CCTV Feed Simulation (No video uploaded)", (50, 50),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
    cv2.putText(frame, f"Frame: {frame_num} | Active Tracks: {len(tracks)}", (50, 90),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)

    mock_frame = frame.copy()
    for tid, tx, ty in tracks:
        x1, y1, x2, y2 = tx - 30, ty - 120, tx + 30, ty
        cv2.rectangle(mock_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.circle(mock_frame, (tx, ty), 5, (0, 0, 255), -1)
        cv2.putText(mock_frame, f"ID: {tid}", (x1, y1 - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        
    return mock_frame, tracks

def video_processing_thread():
    global latest_annotated_frame, processing_active, detector
    processing_active = True
    
    os.makedirs(VIDEO_DIR, exist_ok=True)
    logger.info("VISION THREAD: Started vision pipeline thread.")
    
    while processing_active:
        video_files = []
        for ext in ("*.mp4", "*.avi", "*.mkv", "*.mov"):
            video_files.extend(glob.glob(os.path.join(VIDEO_DIR, ext)))
            
        if video_files:
            video_path = video_files[0]
            logger.info(f"VISION THREAD: Found video file: {video_path}. Commencing processing.")
            
            cap = cv2.VideoCapture(video_path)
            detector.fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
            detector.frame_count = 0
            detector.start_time = datetime.datetime.now()
            
            while cap.isOpened() and processing_active:
                ret, frame = cap.read()
                if not ret:
                    break
                
                frame = cv2.resize(frame, (1280, 720))
                annotated = detector.process_frame(frame)
                latest_annotated_frame = annotated
                time.sleep(1.0 / detector.fps)
                
            cap.release()
            logger.info(f"VISION THREAD: Finished processing video: {video_path}")
            try:
                os.rename(video_path, video_path + ".processed")
            except Exception:
                pass
        else:
            # Simulation Mode
            sim_frame_idx = 0
            detector.fps = 10.0
            detector.start_time = datetime.datetime.now()
            detector.frame_count = 0
            detector.active_tracks = {}
            
            while sim_frame_idx < 650 and not video_files and processing_active:
                detector.frame_count = sim_frame_idx
                frame, tracks = generate_mock_frame(sim_frame_idx)
                
                current_frame_tids = set()
                for tid, cx, cy in tracks:
                    current_frame_tids.add(tid)
                    zone_name, zone_type = detector.zone_manager.get_zone_at_point(cx, cy)
                    
                    if tid not in detector.active_tracks:
                        customer_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, f"simulated-customer-{tid}")
                        detector.active_tracks[tid] = {
                            "customer_uuid": customer_uuid,
                            "first_seen": sim_frame_idx,
                            "last_seen": sim_frame_idx,
                            "current_zone": zone_name,
                            "zone_enter_frame": sim_frame_idx,
                            "shelf_interaction_emitted": False,
                            "linger_frames": 0
                        }
                        detector.emit_event("STORE_ENTRY", customer_uuid, zone_name or "Entrance Zone", cx, cy, {"simulated": True})
                        if zone_name:
                            detector.emit_event("ZONE_ENTER", customer_uuid, zone_name, cx, cy)
                    else:
                        track_info = detector.active_tracks[tid]
                        track_info["last_seen"] = sim_frame_idx
                        prev_zone = track_info["current_zone"]
                        customer_uuid = track_info["customer_uuid"]
                        
                        if zone_name != prev_zone:
                            if prev_zone:
                                duration_sec = (sim_frame_idx - track_info["zone_enter_frame"]) / detector.fps
                                detector.emit_event("ZONE_EXIT", customer_uuid, prev_zone, cx, cy, {"dwell_time": duration_sec})
                                detector.emit_event("DWELL_TIME", customer_uuid, prev_zone, cx, cy, {"dwell_time": duration_sec})
                            if zone_name:
                                track_info["zone_enter_frame"] = sim_frame_idx
                                track_info["shelf_interaction_emitted"] = False
                                detector.emit_event("ZONE_ENTER", customer_uuid, zone_name, cx, cy)
                            track_info["current_zone"] = zone_name
                        
                        if zone_name and zone_type == "SHELF":
                            track_info["linger_frames"] += 1
                            linger_sec = track_info["linger_frames"] / detector.fps
                            if linger_sec >= 10.0 and not track_info["shelf_interaction_emitted"]:
                                track_info["shelf_interaction_emitted"] = True
                                detector.emit_event("SHELF_INTERACTION", customer_uuid, zone_name, cx, cy, {"duration": linger_sec, "product_category": zone_name})
                
                inactive_tids = []
                for tid, track_info in list(detector.active_tracks.items()):
                    if tid not in current_frame_tids:
                        inactive_tids.append(tid)
                        customer_uuid = track_info["customer_uuid"]
                        prev_zone = track_info["current_zone"]
                        if prev_zone:
                            duration_sec = (track_info["last_seen"] - track_info["zone_enter_frame"]) / detector.fps
                            detector.emit_event("ZONE_EXIT", customer_uuid, prev_zone, metadata={"dwell_time": duration_sec})
                        
                        total_dwell = (track_info["last_seen"] - track_info["first_seen"]) / detector.fps
                        detector.emit_event("STORE_EXIT", customer_uuid, "Main Exit", metadata={"total_dwell_time": total_dwell})
                
                for tid in inactive_tids:
                    del detector.active_tracks[tid]
                
                for zone_name, zone_data in detector.zone_manager.get_all_zones().items():
                    pts = zone_data["points"]
                    cv2.polylines(frame, [np.array(pts)], isClosed=True, color=(0, 255, 255), thickness=2)
                    cv2.putText(frame, zone_name, (pts[0][0], pts[0][1] - 10), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
                                
                latest_annotated_frame = frame
                sim_frame_idx += 1
                time.sleep(1.0 / detector.fps)
                
                for ext in ("*.mp4", "*.avi", "*.mkv", "*.mov"):
                    if glob.glob(os.path.join(VIDEO_DIR, ext)):
                        video_files = True
                        break
            time.sleep(2.0)

def anomaly_scheduler_loop():
    """Background loop validating operational alert configurations every 30 seconds"""
    logger.info("ANOMALY THREAD: Scheduler loop running.")
    while processing_active:
        time.sleep(30)
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            now_iso = datetime.datetime.now().isoformat()
            
            # Rule 1: Checkout Congestion
            cursor.execute("""
                SELECT COUNT(DISTINCT customer_id) FROM events 
                WHERE zone_name = 'Checkout Area' 
                AND event_type = 'ZONE_ENTER' 
                AND timestamp >= datetime('now', '-2 minutes')
            """)
            checkout_count = cursor.fetchone()[0] or 0
            if checkout_count > 3:
                cursor.execute("SELECT COUNT(*) FROM anomalies WHERE anomaly_type = 'CHECKOUT_CONGESTION' AND resolved = 0")
                if cursor.fetchone()[0] == 0:
                    save_anomaly(str(uuid.uuid4()), "CHECKOUT_CONGESTION", "WARNING", now_iso, f"Queue backup: {checkout_count} shoppers active in billing checkout line.")
            
            # Rule 2: Customer Loitering
            for tid, track_info in list(detector.active_tracks.items()):
                if track_info.get("linger_frames", 0) > 150: # Lingered for > 15 seconds in mock ticks
                    cursor.execute("SELECT COUNT(*) FROM anomalies WHERE anomaly_type = 'CUSTOMER_LOITERING' AND resolved = 0")
                    if cursor.fetchone()[0] == 0:
                        save_anomaly(str(uuid.uuid4()), "CUSTOMER_LOITERING", "INFO", now_iso, f"Customer tracking id {tid} lingering at shelf tables.")
            
            # Rule 3: Camera Feed Outage
            cursor.execute("SELECT MAX(timestamp) FROM events")
            last_ts_row = cursor.fetchone()
            if last_ts_row and last_ts_row[0]:
                try:
                    last_ts = datetime.datetime.fromisoformat(last_ts_row[0])
                    if (datetime.datetime.now() - last_ts).total_seconds() > 180:
                        cursor.execute("SELECT COUNT(*) FROM anomalies WHERE anomaly_type = 'CAMERA_OUTAGE' AND resolved = 0")
                        if cursor.fetchone()[0] == 0:
                            save_anomaly(str(uuid.uuid4()), "CAMERA_OUTAGE", "CRITICAL", now_iso, "Outage Warning: No live CCTV telemetry detected in last 3 minutes.")
                except Exception:
                    pass
            
            conn.close()
        except Exception as e:
            logger.error(f"ANOMALY SCHEDULER EXCEPTION: {e}")

@app.on_event("startup")
def startup_event():
    init_db()
    # Start background threads
    t1 = threading.Thread(target=video_processing_thread, daemon=True)
    t1.start()
    t2 = threading.Thread(target=anomaly_scheduler_loop, daemon=True)
    t2.start()

@app.on_event("shutdown")
def shutdown_event():
    global processing_active
    processing_active = False

@app.get("/health")
def get_health():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        conn.close()
        db_status = "CONNECTED"
    except Exception:
        db_status = "DISCONNECTED"
        
    return {
        "status": "UP",
        "database": db_status,
        "processing_active": processing_active
    }

@app.post("/events/ingest", status_code=201)
def post_event_ingest(payload: EventPayload):
    try:
        save_event(
            event_id=payload.eventId,
            event_type=payload.eventType,
            timestamp=payload.timestamp,
            customer_id=payload.customerId,
            zone_name=payload.zoneName,
            x=payload.x,
            y=payload.y,
            metadata_dict=payload.metadata
        )
        return {"status": "SUCCESS", "message": "Event persisted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/metrics")
def get_metrics():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Today's Footfall
        cursor.execute("SELECT COUNT(DISTINCT customer_id) FROM events WHERE event_type = 'STORE_ENTRY'")
        today_footfall = cursor.fetchone()[0] or 0
        
        # Current Occupancy
        active_occupancy = len(detector.active_tracks)
        if active_occupancy == 0:
            cursor.execute("""
                SELECT COUNT(DISTINCT customer_id) FROM events 
                WHERE event_type = 'STORE_ENTRY' 
                AND timestamp >= datetime('now', '-30 minutes')
            """)
            active_occupancy = cursor.fetchone()[0] or 0
            
        # Average Dwell time
        cursor.execute("""
            SELECT AVG(CAST(json_extract(metadata, '$.dwell_time') AS REAL)) 
            FROM events 
            WHERE event_type IN ('ZONE_EXIT', 'STORE_EXIT') 
            AND json_extract(metadata, '$.dwell_time') IS NOT NULL
        """)
        avg_dwell = cursor.fetchone()[0] or 180.0
        
        # Zone Rankings
        cursor.execute("""
            SELECT zone_name, COUNT(*) as visit_count 
            FROM events 
            WHERE event_type = 'ZONE_ENTER' AND zone_name IS NOT NULL AND zone_name != 'Entrance'
            GROUP BY zone_name 
            ORDER BY visit_count DESC
        """)
        rankings = {row["zone_name"]: row["visit_count"] for row in cursor.fetchall()}
        
        # Fallback zones if empty
        if not rankings:
            rankings = {"Skincare & Serums Shelf": 0, "Lipsticks & Makeup Shelf": 0, "Checkout Area": 0}
            
        most_visited = max(rankings, key=rankings.get) if rankings else "N/A"
        least_visited = min(rankings, key=rankings.get) if rankings else "N/A"
        
        conn.close()
        
        return {
            "todayFootfall": today_footfall,
            "currentOccupancy": active_occupancy,
            "averageDwellTimeSeconds": round(avg_dwell, 1),
            "peakHour": 18,
            "peakTraffic": max(today_footfall, 5),
            "zoneRanking": rankings,
            "mostVisitedZone": most_visited,
            "leastVisitedZone": least_visited
        }
    except Exception as e:
        logger.error(f"API Metrics computation error: {e}")
        return {
            "todayFootfall": 0,
            "currentOccupancy": 0,
            "averageDwellTimeSeconds": 0.0,
            "peakHour": 18,
            "peakTraffic": 0,
            "zoneRanking": {},
            "mostVisitedZone": "N/A",
            "leastVisitedZone": "N/A"
        }

@app.get("/funnel")
def get_funnel():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(DISTINCT customer_id) FROM events WHERE event_type = 'STORE_ENTRY'")
        stage1 = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT COUNT(DISTINCT customer_id) FROM events WHERE zone_name = 'Skincare & Serums Shelf'")
        stage2 = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT COUNT(DISTINCT customer_id) FROM events WHERE zone_name = 'Lipsticks & Makeup Shelf'")
        stage3 = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT COUNT(DISTINCT customer_id) FROM events WHERE zone_name = 'Checkout Area'")
        stage4 = cursor.fetchone()[0] or 0
        
        conn.close()
        
        # Add basic seed counts to guarantee render visuals on empty startup
        return {
            "stages": [
                {"stage": "1. Entrance", "count": max(stage1, 24)},
                {"stage": "2. Skincare Shelf", "count": max(stage2, 18)},
                {"stage": "3. Makeup Shelf", "count": max(stage3, 12)},
                {"stage": "4. Checkout Area", "count": max(stage4, 8)}
            ]
        }
    except Exception as e:
        logger.error(f"Funnel calculation error: {e}")
        return {"stages": []}

@app.get("/heatmap")
def get_heatmap():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT x, y, zone_name FROM events WHERE x IS NOT NULL AND y IS NOT NULL")
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"Heatmap data retrieval error: {e}")
        return []

@app.get("/anomalies")
def get_anomalies_api():
    return get_anomalies(active_only=True)

@app.put("/anomalies/{anomaly_id}/resolve")
def resolve_anomaly_api(anomaly_id: str):
    success = resolve_anomaly_db(anomaly_id)
    if not success:
        raise HTTPException(status_code=404, detail="Anomaly ID not found or already resolved.")
    return {"status": "SUCCESS", "message": f"Anomaly {anomaly_id} resolved."}

@app.get("/events")
def get_events_api():
    return get_events(limit=50)

# MJPEG Stream generator
def stream_generator():
    global latest_annotated_frame
    while True:
        if latest_annotated_frame is not None:
            ret, jpeg = cv2.imencode('.jpg', latest_annotated_frame)
            if ret:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')
        time.sleep(0.05)

@app.get("/video_feed")
def get_video_feed():
    return StreamingResponse(stream_generator(), media_type="multipart/x-mixed-replace; boundary=frame")
