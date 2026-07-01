"""Vercel serverless entry point.

Vercel's Python runtime invokes a module-level `handler` that subclasses
`http.server.BaseHTTPRequestHandler`. Our API server (`backend.server.Api`)
already is exactly that, so we simply re-export it. Routing in `vercel.json`
ensures only `/api/*` requests reach this function; the static SPA is served
directly from `frontend/` by Vercel's CDN.
"""
import os
import sys

# make the repo root importable so `backend` resolves inside the lambda
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.server import Api as handler  # noqa: E402  (Vercel looks for `handler`)
