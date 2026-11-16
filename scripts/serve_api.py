"""Run the Sentinel API for the web UI.

Secret comes from SENTINEL_JWT_SECRET (required). Demo users are created only for local development so
the UI has something to log in with; in production, load users from a real store.
"""

import os

import uvicorn

from sentinel.api.app import create_app
from sentinel.api.auth import hash_password
from sentinel.api.store import User

DEMO_USERS = {
    "admin": User("admin", hash_password(os.environ.get("SENTINEL_DEMO_PW", "sentinel-demo")), "acme", "admin"),
    "analyst": User("analyst", hash_password(os.environ.get("SENTINEL_DEMO_PW", "sentinel-demo")), "acme", "analyst"),
    "viewer": User("viewer", hash_password(os.environ.get("SENTINEL_DEMO_PW", "sentinel-demo")), "acme", "viewer"),
}


def build():
    secret = os.environ.get("SENTINEL_JWT_SECRET", "")
    if not secret:
        raise SystemExit("set SENTINEL_JWT_SECRET (>=32 chars) before serving")
    origins = os.environ.get("SENTINEL_CORS", "http://localhost:5173").split(",")
    return create_app(secret, DEMO_USERS, cors_origins=origins)


if __name__ == "__main__":
    uvicorn.run(build(), host="0.0.0.0", port=8000)
