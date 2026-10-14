"""Train the PLDHE breed classifier (YOLOv8-cls) on Pakistani breeds.

DATASET LAYOUT (YOLO classification format):
    data/breeds/
        train/
            Sahiwal/*.jpg
            Cholistani/*.jpg
            Dhanni/*.jpg
            Nili-Ravi/*.jpg
            Kundi/*.jpg
        val/
            <same 5 folders>

HOW TO COLLECT DATA (honest minimum for a defensible FYP):
  * 100+ photos per breed (train) + 20 per breed held out for val.
  * Side / three-quarter view, whole animal visible, varied backgrounds.
  * Sources: your own farm visits in Layyah, university dairy farm,
    Wikimedia Commons (check licence), breed-association pages.
  * NEVER train on 10 images and claim 90% — the panel will test it.

USAGE:
    pip install ultralytics
    python train_breed_classifier.py --data data/breeds --epochs 30
    python train_breed_classifier.py --validate   # reports REAL accuracy

OUTPUT:
    backend/app/breed_classifier.pt  (loaded automatically by vision.py)
    runs/classify/...                (training curves + confusion matrix)

ACCURACY: the --validate run prints top-1 accuracy on the held-out
val/ set plus a confusion matrix. THAT number — not a guess — is what
goes in the FYP report and the defense slides. If it is below 90%,
say so and explain why (dataset size, photo quality, similar breeds),
then improve the dataset. A panel respects a measured 82% with a
confusion matrix far more than an invented 90%.
"""

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_MODEL = os.path.join(HERE, "breed_classifier.pt")


def train(data: str, epochs: int, model: str = "yolov8n-cls.pt"):
    from ultralytics import YOLO
    clf = YOLO(model)  # pretrained nano classifier, fine-tuned below
    clf.train(data=data, epochs=epochs, imgsz=224, batch=16,
              project="runs/classify", name="pldhe-breeds",
              patience=10, verbose=True)
    best = clf.trainer.best if hasattr(clf, "trainer") else None
    src = os.path.join("runs", "classify", "pldhe-breeds", "weights", "best.pt")
    if os.path.exists(src):
        import shutil
        shutil.copyfile(src, OUT_MODEL)
        print(f"[ok] saved {OUT_MODEL}")
    else:
        print(f"[warn] expected weights at {src} not found")


def validate(model_path: str = OUT_MODEL, data: str = "data/breeds"):
    from ultralytics import YOLO
    if not os.path.exists(model_path):
        print(f"[error] no model at {model_path} — train first.")
        sys.exit(1)
    clf = YOLO(model_path)
    metrics = clf.val(data=data, split="val")
    top1 = metrics.results_dict.get("metrics/accuracy_top1", None)
    top5 = metrics.results_dict.get("metrics/accuracy_top5", None)
    print(f"[result] val top-1 accuracy: {top1}")
    print(f"[result] val top-5 accuracy: {top5}")
    print("[result] confusion matrix saved under runs/classify/ — "
          "paste it into the FYP report.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/breeds")
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument("--validate", action="store_true")
    ap.add_argument("--model", default="yolov8n-cls.pt")
    args = ap.parse_args()
    if args.validate:
        validate(data=args.data)
    else:
        train(args.data, args.epochs, args.model)
