# ============================================================
# backend/routes/health.py  —  Health check + DB status
# ============================================================

import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from fastapi import APIRouter
from database.db import get_connection
from config import GROQ_LLM_MODEL, GROQ_WHISPER_MODEL

router = APIRouter()


@router.get("/health")
def health_check():
    """Basic liveness check."""
    return {
        "status": "running",
        "service": "Voice AI Agent",
        "models": {
            "llm":     GROQ_LLM_MODEL,
            "whisper": GROQ_WHISPER_MODEL,
        }
    }


@router.get("/health/db")
def db_health():
    """Checks DB connectivity and returns row counts."""
    try:
        conn = get_connection()
        counts = {}
        for table in ["patients", "doctors", "doctor_schedule", "appointments"]:
            row = conn.execute(f"SELECT COUNT(*) as c FROM {table}").fetchone()
            counts[table] = row["c"]
        conn.close()
        return {"status": "ok", "tables": counts}
    except Exception as e:
        return {"status": "error", "detail": str(e)}
    

@router.get("/health/latency")
def latency_stats():
    """Returns latency statistics for last 50 requests."""
    try:
        from services.latency_logger import get_stats, get_recent_log
        return {
            "stats":      get_stats(50),
            "recent_log": get_recent_log(10),
        }
    except Exception as e:
        return {"error": str(e)}


@router.get("/health/cache")
def cache_stats():
    """Returns TTS cache statistics."""
    try:
        from services.text_to_speech.tts_utils import get_cache_stats
        return get_cache_stats()
    except Exception as e:
        return {"error": str(e)}