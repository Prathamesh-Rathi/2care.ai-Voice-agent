# ============================================================
# memory/schema.py  —  Pydantic shapes for session + persistent memory
# ============================================================

from pydantic import BaseModel
from typing import Optional, List


# ── One turn in a conversation ────────────────────────────────
class Turn(BaseModel):
    role:       str    # "user" or "assistant"
    text:       str
    language:   str = "en"
    timestamp:  str


# ── Active session (lives in RAM, cleared after call ends) ────
class SessionMemory(BaseModel):
    session_id:     str
    patient_phone:  Optional[str] = None
    language:       str = "en"
    turns:          List[Turn] = []
    context:        dict = {}        # scratch space for the agent


# ── Persistent record (saved to JSON file per patient) ────────
class PatientMemory(BaseModel):
    patient_phone:      str
    patient_name:       Optional[str] = None
    preferred_language: str = "en"
    past_appointments:  List[dict] = []   # lightweight summaries
    last_seen:          Optional[str] = None
    notes:              List[str] = []    # agent can write freeform notes