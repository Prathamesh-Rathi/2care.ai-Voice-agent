# ============================================================
# memory/session_memory/session_store.py
# In-memory session state for active conversations
# ============================================================

import sys, os, time, uuid
sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
from config import DEFAULT_LANGUAGE

# ── Global session store (dict in memory) ────────────────────
_sessions: dict = {}

# Session expires after 30 minutes of inactivity
SESSION_TTL_SECONDS = 30 * 60


# ── Session creation ──────────────────────────────────────────
def create_session(patient_id: int,
                   patient_name: str = "Patient",
                   language: str = DEFAULT_LANGUAGE) -> dict:
    """
    Creates a new session and stores it in memory.
    Returns the full session dict.
    """
    session_id = str(uuid.uuid4())
    session = {
        "session_id":   session_id,
        "patient_id":   patient_id,
        "patient_name": patient_name,
        "language":     language,
        "history":      [],        # list of {role, content}
        "context":      {          # pending intent slots
            "intent":    None,
            "specialty": None,
            "date":      None,
            "time_slot": None,
            "appt_id":   None,
        },
        "created_at":   time.time(),
        "last_active":  time.time(),
        "turn_count":   0,
    }
    _sessions[session_id] = session
    print(f"[SESSION] Created: {session_id[:8]}… "
          f"patient={patient_name} lang={language}")
    return session


# ── Session retrieval ─────────────────────────────────────────
def get_session(session_id: str) -> dict | None:
    """Returns session dict or None if expired/not found."""
    session = _sessions.get(session_id)
    if not session:
        return None
    # Expire check
    if time.time() - session["last_active"] > SESSION_TTL_SECONDS:
        delete_session(session_id)
        print(f"[SESSION] Expired: {session_id[:8]}…")
        return None
    return session


def get_or_create_session(session_id: str,
                           patient_id: int,
                           patient_name: str = "Patient",
                           language: str = DEFAULT_LANGUAGE) -> dict:
    """Returns existing session or creates a new one."""
    session = get_session(session_id)
    if session:
        return session
    return create_session(patient_id, patient_name, language)


# ── Session updates ───────────────────────────────────────────
def append_turn(session_id: str, role: str, content: str):
    """
    Adds a conversation turn to session history.
    role: 'user' or 'assistant'
    Keeps last 20 turns to control context window size.
    """
    session = _sessions.get(session_id)
    if not session:
        return
    session["history"].append({"role": role, "content": content})
    # Keep last 20 turns only
    if len(session["history"]) > 20:
        session["history"] = session["history"][-20:]
    session["last_active"] = time.time()
    session["turn_count"]  += 1


def update_language(session_id: str, language: str):
    session = _sessions.get(session_id)
    if session:
        session["language"]    = language
        session["last_active"] = time.time()


def update_context(session_id: str, **kwargs):
    """
    Updates slot-filling context.
    e.g. update_context(session_id, specialty='cardiologist', date='tomorrow')
    """
    session = _sessions.get(session_id)
    if not session:
        return
    for key, val in kwargs.items():
        if key in session["context"] and val is not None:
            session["context"][key] = val
    session["last_active"] = time.time()


def clear_context(session_id: str):
    """Resets the slot-filling context after a completed action."""
    session = _sessions.get(session_id)
    if not session:
        return
    session["context"] = {
        "intent":    None,
        "specialty": None,
        "date":      None,
        "time_slot": None,
        "appt_id":   None,
    }


def get_history(session_id: str,
                max_turns: int = 10) -> list[dict]:
    """Returns last N turns from session history."""
    session = _sessions.get(session_id)
    if not session:
        return []
    return session["history"][-max_turns:]


# ── Session cleanup ───────────────────────────────────────────
def delete_session(session_id: str):
    _sessions.pop(session_id, None)


def cleanup_expired_sessions():
    """Removes all sessions that have exceeded TTL."""
    now     = time.time()
    expired = [
        sid for sid, s in _sessions.items()
        if now - s["last_active"] > SESSION_TTL_SECONDS
    ]
    for sid in expired:
        del _sessions[sid]
    if expired:
        print(f"[SESSION] Cleaned {len(expired)} expired sessions.")
    return len(expired)


def get_active_session_count() -> int:
    cleanup_expired_sessions()
    return len(_sessions)


def get_all_sessions_summary() -> list[dict]:
    """Returns lightweight summary of all active sessions."""
    cleanup_expired_sessions()
    return [
        {
            "session_id":  s["session_id"][:8] + "…",
            "patient":     s["patient_name"],
            "language":    s["language"],
            "turns":       s["turn_count"],
            "idle_mins":   round((time.time() - s["last_active"]) / 60, 1),
        }
        for s in _sessions.values()
    ]