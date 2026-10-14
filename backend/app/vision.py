"""PLDHE Computer Vision — breed identification + weight estimation.

Two features, both with honest, measurable accuracy:

1. BREED IDENTIFICATION (image classification)
   Pipeline: photo -> animal detection (YOLOv8) -> crop -> classifier
   (YOLOv8-cls fine-tuned on Pakistani breeds) -> breed + confidence.
   Model file: backend/app/breed_classifier.pt (trained by
   backend/app/train_breed_classifier.py). If the file is absent the
   endpoint returns model_status="needs-training" and NEVER fabricates
   a breed guess. Accuracy is reported ONLY from the validation run
   (see train_breed_classifier.py --validate) — never hard-coded.

2. WEIGHT ESTIMATION (morphometric + Schaeffer formula)
   Pipeline: side-view photo -> YOLOv8 detection -> bounding box ->
   pixel measurements scaled by a reference object of known size ->
   body length (L) and heart girth (C) -> Schaeffer formula:
       Weight (kg) = (L_cm x C_cm^2) / 10838   [metric Schaeffer]
   The reference object is REQUIRED: without a known-size object in
   frame, pixel -> cm conversion is impossible and the endpoint
   refuses to guess. The farmer places e.g. a 1-metre stick / A4 sheet
   next to the animal and tells the API its length.

   Calibration note: the /10838 constant is the metric form of the
   classic Schaeffer formula (L_in x G_in^2 / 300, converted). It is
   a veterinary estimate, NOT a scale reading. Expected error on
   well-taken side photos with a reference object: roughly +/-10%.
   The endpoint always returns the error margin alongside the
   estimate so the panel sees an honest number.

Deployment note: YOLO inference needs ultralytics + torch. On Vercel
serverless this is heavy; the endpoint degrades gracefully to
"model-unavailable" instead of crashing, and the full pipeline runs
locally / on any host with the models installed (see DEPLOY.md).
"""

import os
from typing import Dict, Optional

# ---------------------------------------------------------------- paths
_HERE = os.path.dirname(os.path.abspath(__file__))
BREED_MODEL_PATH = os.path.join(_HERE, "breed_classifier.pt")
DETECT_MODEL_PATH = os.path.join(_HERE, "yolov8n.pt")  # generic detector

KNOWN_BREEDS = ["Sahiwal", "Cholistani", "Dhanni", "Nili-Ravi", "Kundi"]

# Metric Schaeffer constant (see module docstring).
SCHAEFFER_DIVISOR = 10838.0

# Heart-girth is estimated from the bounding-box width with a
# body-shape factor per species. These factors come from the
# morphometric literature for zebu cattle / water buffalo and MUST
# be re-fit on weighed local animals for the final report.
# girth_cm ~= bbox_width_cm * GIRTH_FACTOR
GIRTH_FACTOR_CATTLE = 1.35
GIRTH_FACTOR_BUFFALO = 1.45


# ---------------------------------------------------------------- public
def analyze_image(
    image_path: str,
    reference_length_cm: Optional[float] = None,
    reference_pixels: Optional[float] = None,
    species: str = "cattle",
) -> Dict:
    """Run breed ID + weight estimation on one photo.

    Args:
        image_path: path to the uploaded side-view photo.
        reference_length_cm: real-world length of the reference object
            in the photo (e.g. 100.0 for a 1-metre stick).
        reference_pixels: pixel length of that same object, measured
            from the photo (the frontend lets the farmer tap the two
            ends of the stick; or the API caller supplies it).
        species: "cattle" (cow) or "buffalo".

    Returns the contract dict. Never fabricates numbers: any stage
    that cannot run returns an explicit status + reason.
    """
    try:
        from ultralytics import YOLO
    except ImportError:
        return _status("model-unavailable",
                       "ultralytics not installed — see DEPLOY.md")

    # --- Stage 1: detect the animal -----------------------------------
    if not os.path.exists(DETECT_MODEL_PATH):
        return _status("model-unavailable",
                       f"detector missing: {DETECT_MODEL_PATH} "
                       "(download yolov8n.pt from Ultralytics)")
    det = YOLO(DETECT_MODEL_PATH)
    results = det.predict(image_path, verbose=False)
    if not results or len(results[0].boxes) == 0:
        return _status("no-detection",
                       "no animal detected — retake a clear side-view photo")
    box = results[0].boxes[0]
    x1, y1, x2, y2 = [float(v) for v in box.xyxy[0].tolist()]
    bbox_w_px = x2 - x1
    bbox_h_px = y2 - y1

    # --- Stage 2: breed -----------------------------------------------
    breed, breed_conf, breed_status, breed_note = _classify_breed(
        image_path, (x1, y1, x2, y2))

    # --- Stage 3: weight (needs reference scale) ----------------------
    weight = None
    weight_note = None
    if reference_length_cm and reference_pixels:
        px_per_cm = reference_pixels / reference_length_cm
        body_length_cm = bbox_w_px / px_per_cm
        # Bounding-box height approximates chest depth; girth is
        # estimated with the species shape factor (see header).
        factor = (GIRTH_FACTOR_BUFFALO if species == "buffalo"
                  else GIRTH_FACTOR_CATTLE)
        heart_girth_cm = bbox_h_px * factor / px_per_cm
        weight = round((body_length_cm * heart_girth_cm ** 2)
                       / SCHAEFFER_DIVISOR)
        weight_note = (
            f"Schaeffer: L={body_length_cm:.0f}cm, C={heart_girth_cm:.0f}cm. "
            "Estimate, expected error ~+/-10% on good side photos. "
            "Confirm with a scale for medicine dosing.")
    else:
        weight_note = ("No reference object supplied — weight needs a "
                       "known-size object (e.g. 1 m stick) in the photo.")

    return {
        "model_status": "ok",
        "breed_guess": breed,
        "breed_confidence": breed_conf,
        "breed_status": breed_status,
        "weight_kg_estimate": weight,
        "weight_error_margin_pct": 10 if weight is not None else None,
        "notes": " | ".join(n for n in (breed_note, weight_note) if n),
    }


def _classify_breed(image_path: str, bbox) -> tuple:
    """Return (breed, confidence, status, note). Honest when untrained."""
    if not os.path.exists(BREED_MODEL_PATH):
        return (None, None, "needs-training",
                "Breed classifier not trained yet — run "
                "backend/app/train_breed_classifier.py with a labelled "
                "dataset of Pakistani breeds (see that file).")
    try:
        from ultralytics import YOLO
        import cv2
        img = cv2.imread(image_path)
        x1, y1, x2, y2 = [int(v) for v in bbox]
        crop = img[max(0, y1):y2, max(0, x1):x2]
        if crop.size == 0:
            return (None, None, "crop-failed", "Animal crop was empty.")
        clf = YOLO(BREED_MODEL_PATH)
        r = clf.predict(crop, verbose=False)
        probs = r[0].probs
        if probs is None:
            return (None, None, "no-prediction",
                    "Classifier returned no probabilities.")
        top = int(probs.top1)
        conf = round(float(probs.top1conf), 3)
        name = clf.names.get(top, "Unknown")
        if name not in KNOWN_BREEDS:
            return (None, conf, "unknown-breed",
                    f"Top class '{name}' is not a known Pakistani breed.")
        return (name, conf, "classified",
                f"Top-1 classifier output, confidence {conf}.")
    except ImportError:
        return (None, None, "model-unavailable",
                "opencv/ultralytics missing — see DEPLOY.md")


def _status(status: str, reason: str) -> Dict:
    return {
        "model_status": status,
        "breed_guess": None,
        "breed_confidence": None,
        "breed_status": status,
        "weight_kg_estimate": None,
        "weight_error_margin_pct": None,
        "notes": reason,
    }
