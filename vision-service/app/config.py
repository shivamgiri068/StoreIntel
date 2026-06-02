import os
import logging

# Set up logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("vision-service")

# Backend API configuration
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8080/events")
METRICS_URL = os.getenv("METRICS_URL", "http://localhost:8080/metrics")

# Video storage directories
VIDEO_DIR = os.getenv("VIDEO_DIR", "data/videos")
EVENTS_JSON_PATH = os.getenv("EVENTS_JSON_PATH", "data/events.json")

# Model configuration
YOLO_MODEL = os.getenv("YOLO_MODEL", "yolov8n.pt")
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.4"))

# Zone Polygons defined on 1280x720 frame coordinates
ZONES = {
    "Main Entrance": {
        "type": "ENTRY",
        "polygon": [[0, 500], [0, 720], [300, 720], [300, 500]]
    },
    "Checkout Area": {
        "type": "CHECKOUT",
        "polygon": [[900, 500], [900, 720], [1280, 720], [1280, 500]]
    },
    "Lipsticks & Makeup Shelf": {
        "type": "SHELF",
        "polygon": [[100, 200], [100, 450], [500, 450], [500, 200]]
    },
    "Skincare & Serums Shelf": {
        "type": "SHELF",
        "polygon": [[600, 200], [600, 450], [1000, 450], [1000, 200]]
    },
    "Main Exit": {
        "type": "EXIT",
        "polygon": [[1100, 0], [1100, 200], [1280, 200], [1280, 0]]
    }
}

