# StoreIntel: Interview Preparation & Technical Cheat Sheet

This guide explains the project in a simple, step-by-step way to help you prepare for technical interviews. It covers the elevator pitch, why we made specific choices, how the code works under the hood, and common questions interviewers will ask.

---

## 1. The 30-Second "Elevator Pitch"
> *"I built **StoreIntel**, an AI-powered spatial analytics system for offline retail stores. It uses existing store security cameras (CCTV) to track customer footfall, monitor which shelves shoppers browse, calculate how long they stand at a shelf (dwell time), and build a conversion funnel (Entrance ➔ Browse ➔ Checkout). It also detects operational issues in real time, like checkout queues building up or staff assistance needed at shelves. It runs completely locally on edge CPUs at 30+ FPS using YOLOv8, ByteTrack, FastAPI, and Streamlit."*

---

## 2. The Core Problem & Our Solution
* **The Problem**: E-commerce stores (like Amazon) know exactly where users click, where they get stuck, and when they drop off. Physical retail stores (like Purplle cosmetics) are completely blind. They only know what was bought at the cash counter, but not how many people walked in, which aisles they visited, or why they walked out without buying.
* **Our Solution**: StoreIntel bridges this gap. By converting raw CCTV video frames into coordinates on a store floor, we reconstruct the physical customer journey automatically.

---

## 3. The Tech Stack: "What We Used & Why"
Interviewers love asking **"Why did you choose X instead of Y?"**. Here are the simple justifications:

| Tech Layer | What We Used | Why We Chose It (The Easy Answer) | What we rejected & why |
| :--- | :--- | :--- | :--- |
| **Object Detection** | **YOLOv8-Nano** | Extremely fast and lightweight. It processes 30+ frames per second on standard CPUs without needing an expensive GPU. We only filter for the `Person` class (Class ID 0). | Larger YOLO models (like YOLOv8x) or R-CNNs because they are too slow and lag on CPUs. |
| **Multi-Object Tracking** | **ByteTrack** | It associates bounding boxes across frames using motion predictions (Kalman Filters) and box overlaps. It is extremely fast. | **DeepSORT** — Because DeepSORT extracts deep learning features for every person, which requires a heavy GPU and runs very slowly on CPUs. |
| **Spatial Calculation** | **Shapely (Python)** | A geometric mathematics library. We define store shelves as polygons, and Shapely lets us check if a customer's feet coordinates are inside a shelf zone using simple coordinate math. | **OpenCV's PointPolygonTest** — OpenCV is great for pixels, but Shapely is much cleaner and faster for managing complex layout maps and mathematical zone overlap checks. |
| **Backend API** | **FastAPI** | High-performance, lightweight, and supports asynchronous operations (meaning it can handle multiple events simultaneously without blocking the server). | **Django** or **Flask** — Django has too much unnecessary overhead. Flask is synchronous and slow under high-volume real-time data flows. |
| **Database** | **SQLite** | A self-contained, zero-configuration database. It stores events and alerts directly in a single local file, making it highly portable. | **PostgreSQL** or **MySQL** — They require installing separate database servers and complex user management, which is overkill for a local edge deployment. |
| **Dashboard UI** | **Streamlit + Plotly** | Let us build a beautiful dark-mode dashboard with interactive charts (funnel, heatmaps, bar charts) in pure Python in under 500 lines of code. | **React/Node.js** — Building a custom React frontend would take days and add complex build toolchains (Webpack/Vite). |

---

## 4. How the Data Flows (Step-by-Step)
If an interviewer asks: *"Explain the pipeline from the camera feed to the dashboard graphs,"* walk them through these 5 steps:

1. **Detection**: YOLOv8-Nano processes a frame and draws a bounding box around every detected person.
2. **Tracking**: ByteTrack looks at where the boxes were in the previous frame and assigns a unique ID (e.g., `Customer #4`) to each person.
3. **Footprint Math**: Instead of using the middle of the box (which changes when a person leans or reaches for a product), we calculate the **bottom-middle coordinate** of the box: `(t_x, t_y) = (x_min + width/2, y_max)`. This represents exactly where the customer's feet touch the store floor.
4. **Zone Containment**: We check if this footprint point is inside our predefined zone polygons (e.g., Makeup shelf, Skincare shelf) using Shapely: `Point(t_x, t_y).within(Polygon(zone_coords))`.
   * When they step in: Emit `ZONE_ENTER`.
   * When they step out: Emit `ZONE_EXIT` (and calculate Dwell Time = Entry Time - Exit Time).
5. **Database & Dashboard**: The events are sent to FastAPI (`POST /events/ingest`) and stored in SQLite. The Streamlit dashboard queries these tables to draw the customer funnel, coordinate heatmap, and active alerts.

---

## 5. Standard Interview Questions & How to Answer Them

### Q1: "How does the system handle shopper occlusion (one person walking behind another)?"
* **Answer**: We use **ByteTrack**, which handles low-score and occluded detections brilliantly. Instead of discarding bounding boxes with low confidence scores (which happens when someone is partially blocked), ByteTrack keeps them and uses Kalman Filters to predict where that person is moving based on their past trajectory. Once they step out from behind the obstacle, it re-associates them with the same Customer ID.

### Q2: "Why did you calculate bottom-middle coordinates instead of the center of the bounding box?"
* **Answer**: If we use the geometric center (centroid) of the box, actions like reaching for a high shelf, bending down, or wearing a hat will shift the center point, causing false zone entries/exits. Using the **bottom-middle coordinate** ensures we are tracking the shopper's physical footsteps on the floor, which is stable and maps accurately to the store layout.

### Q3: "How does your system detect operational anomalies?"
* **Answer**: We have three rule-based scripts running in the background:
  1. **Queue Congestion**: We count the number of unique Customer IDs currently inside the "Checkout Zone". If there are more than 3 unique IDs for over 2 minutes, we write a `QUEUE_SPIKE` alert.
  2. **Loitering Alert**: If a customer stays in a shelf zone for more than 15 seconds (representing a real-world threshold of 10 minutes), we write a `STAFF_ASSISTANCE_REQUIRED` alert.
  3. **CCTV Feed Outage**: If the database does not receive any event for over 180 seconds, we raise a `CCTV_FEED_STALE` health warning.

### Q4: "How would you scale this system from 1 camera in 1 store to 100 cameras across 50 stores?"
* **Answer**: To scale this, I would decouple the processing architecture:
  * **Edge Processing**: Keep YOLOv8 and ByteTrack running locally at each store on a lightweight edge computer (like an Intel NUC or Jetson Nano) to avoid streaming heavy high-res video feeds to the cloud.
  * **Message Queue**: Instead of writing directly to SQLite locally, the edge nodes would stream JSON events to a cloud-based message broker like **Apache Kafka** or **AWS Kinesis**.
  * **Central Database**: A centralized consumer service would read events from Kafka and save them to a distributed database like **PostgreSQL (with TimescaleDB extension)** for time-series analytics, which can easily handle millions of rows.

---

## 6. The "North Star Metric" (Business Value)
* **What is it?**: **Offline Store Conversion Rate**.
* **Formula**: `Conversion Rate = (Customers who purchased) / (Total unique visitors in store)`.
* **Why it matters**: Online stores optimize conversion rates using page clicks. StoreIntel gives offline stores the exact same power. If conversion is low on a specific day, managers can check the dashboard to see if the drop-off happened at the **Shelves** (meaning bad products/pricing) or at the **Checkout Queue** (meaning slow billing service).
