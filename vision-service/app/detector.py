import cv2
import datetime
import uuid
import json
import os
from ultralytics import YOLO
from app.config import YOLO_MODEL, CONFIDENCE_THRESHOLD, EVENTS_JSON_PATH, logger
from app.zones import ZoneManager
from app.database import save_event

class StoreIntelligenceDetector:
    def __init__(self):
        self.model = YOLO(YOLO_MODEL)
        self.zone_manager = ZoneManager()
        self.active_tracks = {}
        self.frame_count = 0
        self.fps = 30.0
        self.start_time = datetime.datetime.now()

    def send_event_to_backend(self, event_data):
        """Save event directly to local SQLite database"""
        try:
            save_event(
                event_id=event_data["event_id"],
                event_type=event_data["event_type"],
                timestamp=event_data["timestamp"],
                customer_id=event_data["customer_id"],
                zone_name=event_data["zone"],
                x=event_data.get("x"),
                y=event_data.get("y"),
                metadata_dict=event_data["metadata"]
            )
            logger.info(f"SQLITE SAVE SUCCESS: Emitted {event_data['event_type']} to DB.")
        except Exception as e:
            logger.error(f"SQLITE SAVE ERROR: Failed to save event: {e}")

    def send_metrics_to_backend(self, fps, latency_ms):
        """Performance metrics can be logged locally or pushed to DB"""
        pass

    def log_event_locally(self, event_data):
        """Append event to local JSON line file"""
        try:
            with open(EVENTS_JSON_PATH, "a") as f:
                f.write(json.dumps(event_data) + "\n")
        except Exception as e:
            logger.error(f"Failed to save event locally: {e}")

    def emit_event(self, event_type, customer_id, zone_name, x=None, y=None, metadata=None):
        if metadata is None:
            metadata = {}
        
        # Calculate current timestamp based on video frame relative time
        elapsed_seconds = self.frame_count / self.fps
        event_time = self.start_time + datetime.timedelta(seconds=elapsed_seconds)
        
        event = {
            "event_id": str(uuid.uuid4()),
            "event_type": event_type,
            "timestamp": event_time.isoformat(),
            "customer_id": str(customer_id),
            "zone": zone_name,
            "x": x,
            "y": y,
            "metadata": metadata
        }
        logger.info(f"EVENT GENERATED: {event_type} - Customer {customer_id} in {zone_name or 'Store'}")
        
        # Log to file and push to API
        self.log_event_locally(event)
        self.send_event_to_backend(event)

    def process_frame(self, frame):
        """
        Runs YOLOv8 detector + ByteTrack on a single frame, updates tracking state,
        generates spatial events, and returns annotated frame.
        """
        t_start = datetime.datetime.now()
        self.frame_count += 1
        
        # Run tracking. Classes = 0 is 'person' in COCO dataset
        results = self.model.track(
            frame, 
            persist=True, 
            classes=[0], 
            conf=CONFIDENCE_THRESHOLD,
            tracker="bytetrack.yaml", 
            verbose=False
        )
        
        annotated_frame = frame.copy()
        current_frame_tracks = set()
        
        # Draw Zones
        for zone_name, zone_data in self.zone_manager.get_all_zones().items():
            pts = zone_data["points"]
            import numpy as np
            cv2.polylines(annotated_frame, [np.array(pts)], isClosed=True, color=(0, 255, 255), thickness=2)
            # Label zones
            cv2.putText(annotated_frame, zone_name, (pts[0][0], pts[0][1] - 10), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)

        result = results[0]
        boxes = result.boxes
        
        if boxes is not None and len(boxes) > 0:
            for box in boxes:
                # If there are track IDs
                if box.id is None:
                    continue
                
                track_id = int(box.id[0].item())
                current_frame_tracks.add(track_id)
                
                # Bounding box coordinates
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                conf = box.conf[0].item()
                
                # Centroid represents the bottom-middle coordinate of the customer (where they stand)
                cx = int((x1 + x2) / 2)
                cy = int(y2)
                
                # Map to zones
                zone_name, zone_type = self.zone_manager.get_zone_at_point(cx, cy)
                
                # State checking for active tracks
                if track_id not in self.active_tracks:
                    # Brand new customer session
                    customer_uuid = uuid.uuid4()
                    self.active_tracks[track_id] = {
                        "customer_uuid": customer_uuid,
                        "first_seen": self.frame_count,
                        "last_seen": self.frame_count,
                        "current_zone": zone_name,
                        "zone_enter_frame": self.frame_count,
                        "shelf_interaction_emitted": False,
                        "linger_frames": 0
                    }
                    # Emit entry event
                    self.emit_event(
                        "STORE_ENTRY", 
                        customer_uuid, 
                        zone_name or "Entrance Zone", 
                        cx, cy, 
                        {"confidence": conf}
                    )
                    
                    if zone_name:
                        self.emit_event("ZONE_ENTER", customer_uuid, zone_name, cx, cy)
                else:
                    # Existing customer session
                    track_info = self.active_tracks[track_id]
                    track_info["last_seen"] = self.frame_count
                    prev_zone = track_info["current_zone"]
                    customer_uuid = track_info["customer_uuid"]
                    
                    # Track coordinates reporting
                    # Emit coordinates as an event or let it be saved by backend during processing
                    
                    if zone_name != prev_zone:
                        # Zone Transition
                        if prev_zone:
                            # Zone Exit
                            duration_frames = self.frame_count - track_info["zone_enter_frame"]
                            duration_sec = duration_frames / self.fps
                            self.emit_event(
                                "ZONE_EXIT", 
                                customer_uuid, 
                                prev_zone, 
                                cx, cy, 
                                {"dwell_time": duration_sec}
                            )
                            self.emit_event(
                                "DWELL_TIME", 
                                customer_uuid, 
                                prev_zone, 
                                cx, cy, 
                                {"dwell_time": duration_sec}
                            )
                            
                        if zone_name:
                            # Zone Enter
                            track_info["zone_enter_frame"] = self.frame_count
                            track_info["shelf_interaction_emitted"] = False
                            self.emit_event("ZONE_ENTER", customer_uuid, zone_name, cx, cy)
                            
                        track_info["current_zone"] = zone_name
                    
                    # Shelf linger calculations
                    if zone_name and zone_type == "SHELF":
                        track_info["linger_frames"] += 1
                        linger_duration = track_info["linger_frames"] / self.fps
                        if linger_duration >= 10.0 and not track_info["shelf_interaction_emitted"]:
                            track_info["shelf_interaction_emitted"] = True
                            self.emit_event(
                                "SHELF_INTERACTION", 
                                customer_uuid, 
                                zone_name, 
                                cx, cy, 
                                {"duration": linger_duration, "product_category": zone_name}
                            )

                # Draw track annotation boxes
                color = (0, 255, 0) if zone_name else (255, 0, 0)
                cv2.rectangle(annotated_frame, (int(x1), int(y1)), (int(x2), int(y2)), color, 2)
                cv2.circle(annotated_frame, (cx, cy), 5, (0, 0, 255), -1)
                cv2.putText(annotated_frame, f"ID: {track_id} {zone_name or ''}", (int(x1), int(y1) - 5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

        # Handle missing tracks (people who exited)
        inactive_track_ids = []
        for track_id, track_info in self.active_tracks.items():
            # If track was missing for more than 45 frames (1.5 seconds)
            if track_id not in current_frame_tracks and (self.frame_count - track_info["last_seen"]) > 45:
                inactive_track_ids.append(track_id)
                customer_uuid = track_info["customer_uuid"]
                prev_zone = track_info["current_zone"]
                
                # Emit exits
                if prev_zone:
                    duration_frames = track_info["last_seen"] - track_info["zone_enter_frame"]
                    duration_sec = duration_frames / self.fps
                    self.emit_event(
                        "ZONE_EXIT", 
                        customer_uuid, 
                        prev_zone, 
                        metadata={"dwell_time": duration_sec}
                    )
                
                total_duration = (track_info["last_seen"] - track_info["first_seen"]) / self.fps
                self.emit_event(
                    "STORE_EXIT", 
                    customer_uuid, 
                    zone_name="Main Exit", 
                    metadata={"total_dwell_time": total_duration}
                )
                
        for tid in inactive_track_ids:
            del self.active_tracks[tid]

        # 7. Check Crowd Surge in Zone (Real-time check)
        checkout_count = sum(1 for t in self.active_tracks.values() if t["current_zone"] == "Checkout Area")
        if checkout_count >= 4 and self.frame_count % 300 == 0: # Check every 10 seconds (300 frames at 30 fps)
            # Emit Crowd Surge warning
            self.emit_event(
                "CROWD_SURGE", 
                uuid.uuid4(), 
                "Checkout Area", 
                metadata={"occupancy": checkout_count, "description": "Checkout Area overcrowding"}
            )

        t_end = datetime.datetime.now()
        latency_ms = (t_end - t_start).total_seconds() * 1000
        current_fps = 1.0 / max(0.001, (t_end - t_start).total_seconds())
        
        # Publish metrics
        if self.frame_count % 90 == 0: # Every 3 seconds
            self.send_metrics_to_backend(current_fps, latency_ms)

        return annotated_frame
