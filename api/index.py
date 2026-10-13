"""Vercel serverless entrypoint — adapts the FastAPI app via Mangum.

Vercel's Python runtime picks up the `handler` variable automatically.
All routes rewrite here (see vercel.json).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mangum import Mangum  # noqa: E402

from backend.app.main import app  # noqa: E402

handler = Mangum(app, lifespan="auto")
