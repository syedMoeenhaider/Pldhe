"""PLDHE Knowledge Base — retrieval layer for the Saraiki vet assistant.

This is the project's RAG (retrieval-augmented generation) layer, built
honestly:

* SOURCE TODAY: the curated disease knowledge in triage.py (DISEASE_RULES)
  — 7+ diseases with Roman-Urdu/Saraiki/Urdu-script keywords. Every chunk
  carries its source, so the panel can audit where an answer came from.
* SOURCE TOMORROW: a book PDF (e.g. Ganjeena Tib-e-Haiwanat). Run
  `python -m backend.app.knowledge --ingest book.pdf --source "Ganjeena..."`
  to OCR/extract text, chunk it, and append it to the same index.
  Until then, NO chunk claims to come from the book.

Retrieval is keyword-based (normalized Urdu/Roman/English matching), NOT
embeddings. Deliberate choice: with tens of chunks, keyword search is
explainable ("ye chunk is liye mila kyunke 'jhaag' match hua") — a panel
can follow it; a vector DB would be a black box here. If the corpus grows
past a few hundred chunks, swap `_score` for embeddings (see note below).

Saraiki handling: chunks store Urdu + Roman-Urdu + Saraiki keywords.
The Vapi assistant (Saraiki system prompt) receives the retrieved chunk
and GENERATES the Saraiki answer at call time. So: retrieval is
multilingual, generation is Saraiki. That is the "Saraiki conversion".

Storage: backend/app/knowledge.json (generated artifact, committed to
git). Rebuild with: python -m backend.app.knowledge --rebuild
"""

import argparse
import json
import os
import re
import sys
from typing import Dict, List

_HERE = os.path.dirname(os.path.abspath(__file__))
INDEX_PATH = os.path.join(_HERE, "knowledge.json")


def _normalize(text: str) -> str:
    text = text.lower()
    # strip Arabic diacritics / tatweel that break matching
    text = re.sub(r"[\u064b-\u0652\u0640]", "", text)
    return " ".join(text.strip().split())


def _load_disease_rules():
    """Import DISEASE_RULES even without the DB stack (geoalchemy2)."""
    import sys
    import types
    try:
        from .triage import DISEASE_RULES
        return DISEASE_RULES
    except (ImportError, ModuleNotFoundError):
        pass
    # triage.py does `from .models import RiskLevel`, and models.py needs
    # geoalchemy2 (DB-only). Stub just enough for the import to succeed.
    from enum import Enum
    stub = types.ModuleType("backend.app.models")
    class RiskLevel(str, Enum):
        EMERGENCY = "EMERGENCY"; HIGH = "HIGH"
        MEDIUM = "MEDIUM"; LOW = "LOW"
    stub.RiskLevel = RiskLevel
    sys.modules["backend.app.models"] = stub
    from .triage import DISEASE_RULES
    return DISEASE_RULES


def build_from_triage() -> List[Dict]:
    """Convert DISEASE_RULES into searchable knowledge chunks."""
    DISEASE_RULES = _load_disease_rules()
    chunks = []
    for i, rule in enumerate(DISEASE_RULES):
        risk = rule["risk"]
        risk = risk.value if hasattr(risk, "value") else str(risk)
        chunks.append({
            "id": f"triage-{i}",
            "source": "PLDHE triage knowledge base v1 (curated)",
            "title_en": rule["disease_en"],
            "title_ur": rule["disease_ur"],
            "risk": risk,
            "text": (
                f"{rule['disease_en']} / {rule['disease_ur']}. "
                f"Alamat: {', '.join(rule['keywords'][:8])}. "
                f"{rule['tells']}"
            ),
            "keywords": rule["keywords"],
        })
    return chunks


def chunk_text(text: str, source: str, size: int = 600) -> List[Dict]:
    """Split raw book text into sentence-aware chunks."""
    text = re.sub(r"\s+", " ", text).strip()
    # split on sentence boundaries (Urdu + English punctuation)
    sentences = re.split(r"(?<=[۔.!?])\s+", text)
    chunks, cur = [], ""
    for s in sentences:
        if len(cur) + len(s) + 1 <= size:
            cur = (cur + " " + s).strip()
        else:
            if cur:
                chunks.append(cur)
            cur = s
    if cur:
        chunks.append(cur)
    return [
        {"id": f"{source}-{n}", "source": source,
         "title_en": "", "title_ur": "",
         "risk": "", "text": c, "keywords": []}
        for n, c in enumerate(chunks)
    ]


def ingest_pdf(pdf_path: str, source: str) -> int:
    """Extract text from a PDF and append its chunks to the index."""
    try:
        from pypdf import PdfReader
    except ImportError:
        print("pip install pypdf  (PDF text extraction)")
        sys.exit(1)
    reader = PdfReader(pdf_path)
    full = "\n".join((p.extract_text() or "") for p in reader.pages)
    if len(full.strip()) < 200:
        print("[warn] almost no extractable text — the PDF may be scanned "
              "images; OCR (e.g. tesseract with 'urd' traineddata) needed.")
    new_chunks = chunk_text(full, source)
    index = load_index()
    index.extend(new_chunks)
    save_index(index)
    print(f"[ok] ingested {len(new_chunks)} chunks from {pdf_path}")
    return len(new_chunks)


def save_index(chunks: List[Dict]) -> None:
    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=1)


def load_index() -> List[Dict]:
    if not os.path.exists(INDEX_PATH):
        chunks = build_from_triage()
        save_index(chunks)
        return chunks
    with open(INDEX_PATH, encoding="utf-8") as f:
        return json.load(f)


def _score(query: str, chunk: Dict) -> float:
    """Keyword overlap score (explainable)."""
    q = _normalize(query)
    qwords = set(q.split())
    if not qwords:
        return 0.0
    hay = _normalize(chunk["text"] + " " + " ".join(chunk.get("keywords", [])))
    hits = sum(1 for w in qwords if w in hay)
    # phrase bonus: full query as substring
    bonus = 2.0 if q in hay else 0.0
    return hits + bonus


def search(query: str, top_k: int = 3) -> List[Dict]:
    """Return top-k chunks for a farmer's question, with scores."""
    index = load_index()
    scored = [(_score(query, c), c) for c in index]
    scored = [(s, c) for s, c in scored if s > 0]
    scored.sort(key=lambda x: x[0], reverse=True)
    out = []
    for s, c in scored[:top_k]:
        out.append({
            "id": c["id"],
            "source": c["source"],
            "title_en": c.get("title_en", ""),
            "title_ur": c.get("title_ur", ""),
            "risk": c.get("risk", ""),
            "text": c["text"][:600],
            "score": round(s, 2),
        })
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--rebuild", action="store_true")
    ap.add_argument("--ingest", default=None, help="PDF path")
    ap.add_argument("--source", default="book")
    ap.add_argument("--query", default=None)
    args = ap.parse_args()
    if args.rebuild:
        save_index(build_from_triage())
        print(f"[ok] rebuilt {INDEX_PATH}")
    if args.ingest:
        ingest_pdf(args.ingest, args.source)
    if args.query:
        for r in search(args.query):
            print(f"[{r['score']}] {r['title_en']} ({r['source']})")
            print("   ", r["text"][:160], "...")
