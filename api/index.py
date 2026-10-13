"""Vercel serverless entrypoint.

Vercel's Python runtime auto-detects ASGI apps: just export the FastAPI
instance as `app`. No Mangum/adapter needed.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app.main import app  # noqa: E402,F401  (re-exported for Vercel)
