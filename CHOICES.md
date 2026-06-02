# Technical Choice Justifications (CHOICES.md)

This document provides explanations for the technology stack chosen for the **StoreIntel** retail analytics application, highlighting trade-offs and engineering rationale.

---

## 1. Bounding Box Detection: YOLOv8
* **Alternative Considered**: Faster R-CNN, SSD (Single Shot MultiBox Detector).
* **Trade-off Decision**:
  * Faster R-CNN offers slightly higher bounding box accuracy but runs at less than 5 FPS on edge CPUs.
  * SSD is lightweight but lacks detection accuracy for overlapping shoppers or smaller objects.
  * **YOLOv8 nano** provides a balanced solution, running at ~30 FPS on standard edge CPUs while maintaining a mean Average Precision (mAP) above 37.3%.

---

## 2. Multi-Object Tracking: ByteTrack
* **Alternative Considered**: DeepSORT.
* **Trade-off Decision**:
  * DeepSORT uses a deep learning feature extractor to calculate Re-identification (Re-ID) embeddings for each detected box, reducing processing speed on edge devices.
  * **ByteTrack** matches detection boxes by combining motion prediction (Kalman Filters) with bounding box overlap (IoU) similarities, maintaining higher frame rates.

---

## 3. API Framework: FastAPI
* **Alternative Considered**: Django, Flask.
* **Trade-off Decision**:
  * Django is feature-rich but has higher overhead.
  * Flask is simple but lacks native async request support.
  * **FastAPI** provides a lightweight asynchronous design, built-in Pydantic validation, and automated Swagger UI generation, suitable for real-time edge integration.

---

## 4. Local Persistence: SQLite
* **Alternative Considered**: PostgreSQL, MongoDB.
* **Trade-off Decision**:
  * PostgreSQL and MongoDB require independent database containers, adding complexity and resource usage.
  * **SQLite** is self-contained, requires no configuration, and stores data in a single local file. This simplifies deployments and is well-suited for edge devices.

---

## 5. Visual Dashboard: Streamlit
* **Alternative Considered**: React.js / Vue.js.
* **Trade-off Decision**:
  * Building a custom React or Vue dashboard requires a front-end build pipeline and more development time.
  * **Streamlit** allows rapid creation of interactive, dark-themed analytical dashboards directly in Python. It includes native integration for Plotly charts, suited for hackathon timelines.
