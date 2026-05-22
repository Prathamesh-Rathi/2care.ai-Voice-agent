# ============================================================
# config.py  —  All configuration and API keys live here
# ============================================================

# ── Groq API (LLM + Whisper STT) ────────────────────────────
# Get your free key at https://console.groq.com
GROQ_API_KEY = "your keyu"

# ── Groq model names ─────────────────────────────────────────
# LLM for agent reasoning
GROQ_LLM_MODEL = "llama-3.3-70b-versatile"

# Whisper model for speech-to-text
GROQ_WHISPER_MODEL = "whisper-large-v3"

# ── Database ─────────────────────────────────────────────────
# SQLite file will be created automatically in the project root
DB_PATH = "voice_agent.db"

# ── Memory files (JSON-based) ─────────────────────────────────
SESSION_MEMORY_DIR  = "memory/session_memory"
PERSISTENT_MEMORY_DIR = "memory/persistent_memory"

# ── Server settings ───────────────────────────────────────────
HOST = "0.0.0.0"
PORT = 8000

# ── Supported languages ───────────────────────────────────────
SUPPORTED_LANGUAGES = {
    "en": "English",
    "hi": "Hindi",
    "ta": "Tamil",
}

# Default fallback language
DEFAULT_LANGUAGE = "en"

# ── Latency target (milliseconds) ────────────────────────────
LATENCY_TARGET_MS = 450

# ── TTS settings ─────────────────────────────────────────────
TTS_OUTPUT_DIR = "tts_output"

# ── Agent system prompt (used in Phase 5) ────────────────────
AGENT_SYSTEM_PROMPT = """
You are a multilingual healthcare appointment assistant.
You help patients book, reschedule, and cancel appointments.
Always respond in the same language the patient used.
Be concise, warm, and professional.

Supported languages: English, Hindi, Tamil.

When you need to perform an action, respond ONLY with a JSON object like:
{
  "intent": "book" | "cancel" | "reschedule" | "check_availability" | "chitchat",
  "doctor_specialty": "cardiologist" | "dermatologist" | ...,
  "doctor_name": "Dr Sharma" | null,
  "date": "YYYY-MM-DD" | "tomorrow" | "today" | null,
  "time": "HH:MM" | null,
  "appointment_id": null | <id for cancel/reschedule>,
  "patient_response": "<your friendly reply to the patient in their language>"
}

If you need more information to complete the action, set intent to "clarify" and ask in patient_response.
"""