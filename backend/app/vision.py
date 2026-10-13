"""Phase 2 — Computer Vision hook (breed recognition + weight estimation).

Contract: POST /api/v1/vision/analyze (multipart image) →
    {breed_guess, breed_confidence, weight_kg_estimate, model_status, notes}

Walking skeleton: returns the contract with model_status="stub".
To enable real inference: `pip install ultralytics`, place a trained
`yolov8n-livestock.pt` next to this module, and the YOLO path below
activates automatically. Weight factor MUST be calibrated on local
Sahiwal/Cholistani data before the final defense.
"""

import os
from typing import Dict, Optional

MODEL_PATH = os.path.join(os.path.dirname(__file__), "yolov8n-livestock.pt")

# Placeholder calibration: bbox-area fraction → kg. Replace with a
# regression fit on weighed animals of known breeds.
WEIGHT_FACTOR = 900.0
KNOWN_BREEDS = ["Sahiwal", "Cholistani", "Nili-Ravi", "Desi"]


def analyze_image(image_path: str) -> Dict:
    try:
        from ultralytics import YOLO
    except ImportError:
        return _stub("ultralytics not installed — `pip install ultralytics` to enable.")

    if not os.path.exists(MODEL_PATH):
        return _stub(f"model file missing: {MODEL_PATH}")

    model = YOLO(MODEL_PATH)  # production: load once at startup, not per request
    results = model.predict(image_path, verbose=False)
    if not results or len(results[0].boxes) == 0:
        return _stub("no animal detected in image", model_status="no-detection")

    box = results[0].boxes[0]
    cls_id = int(box.cls[0])
    conf = round(float(box.conf[0]), 2)
    breed = model.names.get(cls_id, "Unknown")

    # Weight from bbox area as a fraction of image area (heuristic).
    x1, y1, x2, y2 = box.xyxy[0].tolist()
    img_h, img_w = results[0].orig_shape[:2]
    area_frac = ((x2 - x1) * (y2 - y1)) / (img_w * img_h)
    weight = round(area_frac * WEIGHT_FACTOR)

    return {
        "model_status": "yolo",
        "breed_guess": breed if breed in KNOWN_BREEDS else breed,
        "breed_confidence": conf,
        "weight_kg_estimate": weight,
        "notes": "Weight is a bbox-area heuristic — calibrate WEIGHT_FACTOR on weighed local animals.",
    }


def _stub(reason: str, model_status: str = "stub") -> Dict:
    return {
        "model_status": model_status,
        "breed_guess": None,
        "breed_confidence": None,
        "weight_kg_estimate": None,
        "notes": reason,
    }
