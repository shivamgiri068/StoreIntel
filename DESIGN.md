# StoreIntel Architecture & Design Specifications (DESIGN.md)

This document details the internal design and architectural components of the **StoreIntel** retail analytics system.

---

## 1. Core System Architecture

StoreIntel is designed with a **decoupled edge-ingestion paradigm**. The system isolates computationally heavy video processing from high-availability analytical APIs.

```
+-----------------------------------------------------------------------------------+
|                            FASTAPI BACKEND SERVICE                                |
|                                                                                   |
|  +---------------------------+            +------------------------------------+  |
|  |  Background Video Thread  |            |        Main FastAPI Thread         |  |
|  |                           |            |                                    |  |
|  |   - Ingests CCTV Frame    |            |   - POST /events/ingest            |  |
|  |   - YOLOv8 Person Class   |            |   - GET /metrics (Analytics)       |  |
|  |   - ByteTrack Track IDs   |            |   - GET /funnel                    |  |
|  |   - Shapely Zone Collision|            |   - GET /heatmap                   |  |
|  |   - Save Event (SQLite)   |            |   - GET /anomalies & /resolve      |  |
|  +-------------+-------------+            +-----------------+------------------+  |
|                |                                            ^                     |
|                v                                            |                     |
|       [SQLite Database] <-----------------------------------+                     |
|       (store_intelligence.db)                                                     |
+-----------------------------------------------------------------------------------+
```

### 1.1 Multi-Threaded Model Execution
* **Video Ingestion Thread**: Instantiated on system startup. It reads active frames from `.mp4` files or RTSP streams, executes detection, performs polygon intersection checks, and updates state.
* **REST API Thread**: Serves dashboard queries, funnel aggregations, and heatmap coordinate requests on Port 8000 using asynchronous FastAPI workers.
* **Background Scheduler Thread**: Runs every 30 seconds to evaluate operational alerts (Checkout queue sizes, loitering durations) against logged historical event data in SQLite.

---

## 2. Spatial Mapping & Collision Math

We utilize **Shapely** to compute spatial coordinate intersections. Shopper location is represented by a single bottom-middle coordinate of the YOLO detection bounding box (representing the shopper's feet contact point on the floor).

```
   +-----------------------------+
   |                             |
   |                             | (YOLO Person Box)
   |                             |
   |              x (Centroid)   |
   +-------------#---------------+
                 |
                 v
         (tx, ty) Centroid Footprint
```

* **Zone Check**: Let $P_z$ represent the polygon coordinates of a store zone. The centroid $(t_x, t_y)$ triggers a `ZONE_ENTER` event if and only if:
  $$(t_x, t_y) \in P_z$$
* **State Transition Machine**:
  * **First Track ID Bounding Box**: Emit `STORE_ENTRY`.
  * **Zone Change**: If $(t_x, t_y)$ moves from $P_{A}$ to $P_{B}$, emit `ZONE_EXIT` for $P_A$ (adding elapsed duration calculation), and `ZONE_ENTER` for $P_B$.
  * **Track Loss**: If Bounding Box is lost for more than 30 frames, emit `STORE_EXIT`.

---

## 3. SQLite Database Schema

We use SQLite for local persistence. The schema definition contains index keys optimized for time-series range scans.

```sql
-- Zone Boundaries configuration
CREATE TABLE zones (
    name TEXT PRIMARY KEY,
    type TEXT,
    polygon_coordinates TEXT
);

-- Event Telemetry
CREATE TABLE events (
    id TEXT PRIMARY KEY,
    event_type TEXT,
    timestamp TEXT,
    customer_id TEXT,
    zone_name TEXT,
    x REAL,
    y REAL,
    metadata TEXT
);

-- Operational Alerts
CREATE TABLE anomalies (
    id TEXT PRIMARY KEY,
    anomaly_type TEXT,
    severity TEXT,
    timestamp TEXT,
    description TEXT,
    resolved INTEGER DEFAULT 0
);
```

---

## 4. Anomaly Rules Calculations

1. **Queue Congestion**:
   $$N_{\text{checkout}} = \text{Count}(\text{Unique Customer IDs}) \text{ in last 2 minutes within "Checkout Area"}$$
   Triggered if $N_{\text{checkout}} > 3$.
2. **Customer Loitering**:
   Triggered if a customer is tracked inside a shelf boundary for more than 15 seconds in simulated time (representing a real-world loitering threshold of 10 minutes).
3. **Camera Outage**:
   $$\Delta T_{\text{last\_event}} = T_{\text{current}} - T_{\text{last\_event\_logged}}$$
   Triggered if $\Delta T_{\text{last\_event}} > 180 \text{ seconds}$.
