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

from backend.server import Api  # noqa: E402


# Vercel's Python builder statically scans for a top-level class named `handler`
# (a BaseHTTPRequestHandler subclass). An `import ... as handler` alias isn't
# recognized, so we declare it explicitly.
class handler(Api):  # noqa: N801  (name required verbatim by the runtime)
    pass

