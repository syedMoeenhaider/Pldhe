"""Vercel serverless entrypoint.

Vercel routes every /api/* request to this function with the ORIGINAL path,
and its Python runtime serves the exported FastAPI app as native ASGI.
No vercel.json rewrites, no Mangum needed.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app.main import app  # noqa: E402,F401  (re-exported for Vercel)


@app.get("/api/health", include_in_schema=False)
def _vercel_health():
    return {"status": "ok"}
