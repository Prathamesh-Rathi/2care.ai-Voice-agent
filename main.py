# ============================================================
# main.py  —  Application entry point
# ============================================================

import sys
import os

sys.path.append(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

import uvicorn

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import HOST, PORT
from database.db import init_db

from backend.routes.health import (
    router as health_router
)

from backend.routes.appointments import (
    router as appt_router
)

from backend.routes.websocket import (
    router as ws_router
)

# ============================================================
# Create FastAPI app
# ============================================================

app = FastAPI(
    title=(
        "Voice AI Agent — "
        "Clinical Appointment System"
    ),

    description=(
        "Real-time multilingual voice "
        "agent for booking appointments."
    ),

    version="1.0.0"
)

# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,

    allow_origins=["*"],

    allow_methods=["*"],

    allow_headers=["*"],
)

# ============================================================
# Mount Routers
# ============================================================

app.include_router(health_router)
app.include_router(appt_router)
app.include_router(ws_router)

# ============================================================
# Startup Event
# ============================================================

@app.on_event("startup")
async def on_startup():

    print("\n" + "=" * 55)

    print("  Voice AI Agent starting up...")

    print("=" * 55)

    # ========================================================
    # Initialize Database
    # ========================================================

    init_db()

    # ========================================================
    # Create Required Directories
    # ========================================================

    os.makedirs(
        "tts_output",
        exist_ok=True
    )

    os.makedirs(
        "logs",
        exist_ok=True
    )

    os.makedirs(
        "memory/session_memory",
        exist_ok=True
    )

    os.makedirs(
        "memory/persistent_memory",
        exist_ok=True
    )

    # ========================================================
    # Startup Info
    # ========================================================

    print(
        f"  Server : "
        f"http://{HOST}:{PORT}"
    )

    print(
        f"  Docs   : "
        f"http://localhost:{PORT}/docs"
    )

    print(
        f"  WS     : "
        f"ws://localhost:{PORT}/ws/voice/{{phone}}"
    )

    print("=" * 55 + "\n")

    # ========================================================
    # Warm Cache (Background)
    # ========================================================

    from services.cache_warmer import (
        warm_cache_background
    )

    # Non-blocking background cache warming
    warm_cache_background()

# ============================================================
# Root Route
# ============================================================

@app.get("/")
def root():

    return {
        "service": "Voice AI Agent",

        "docs": (
            f"http://localhost:{PORT}/docs"
        ),

        "ws": (
            f"ws://localhost:{PORT}"
            f"/ws/voice/{{patient_phone}}"
        ),

        "health": (
            f"http://localhost:{PORT}/health"
        )
    }

# ============================================================
# Run Server
# ============================================================

if __name__ == "__main__":

    uvicorn.run(
        "main:app",

        host=HOST,

        port=PORT,

        reload=True,

        log_level="info"
    )