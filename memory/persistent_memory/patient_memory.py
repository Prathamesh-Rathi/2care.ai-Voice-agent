# ============================================================
# memory/persistent_memory/patient_memory.py
# JSON-based long-term memory per patient
# ============================================================

import sys, os, json, time
sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
from config import PERSISTENT_MEMORY_DIR, DEFAULT_LANGUAGE

os.makedirs(PERSISTENT_MEMORY_DIR, exist_ok=True)


# ── File path helper ──────────────────────────────────────────
def _memory_path(patient_id: int) -> str:
    return os.path.join(PERSISTENT_MEMORY_DIR, f"patient_{patient_id}.json")


# ── Default memory structure ──────────────────────────────────
def _default_memory(patient_id: int) -> dict:
    return {
        "patient_id":          patient_id,
        "preferred_language":  DEFAULT_LANGUAGE,
        "preferred_doctor":    None,
        "preferred_hospital":  None,
        "preferred_time":      None,
        "last_specialty":      None,
        "total_appointments":  0,
        "cancelled_count":     0,
        "rescheduled_count":   0,
        "last_appointment":    None,
        "conversation_count":  0,
        "notes":               [],
        "created_at":          time.time(),
        "updated_at":          time.time(),
    }


# ── Load / Save ───────────────────────────────────────────────
def load_memory(patient_id: int) -> dict:
    """
    Loads patient memory from JSON file.
    Creates default memory if file doesn't exist.
    """
    path = _memory_path(patient_id)
    if not os.path.exists(path):
        mem = _default_memory(patient_id)
        save_memory(patient_id, mem)
        return mem
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        mem = _default_memory(patient_id)
        save_memory(patient_id, mem)
        return mem


def save_memory(patient_id: int, memory: dict):
    """Saves memory dict to JSON file."""
    path = _memory_path(patient_id)
    memory["updated_at"] = time.time()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(memory, f, ensure_ascii=False, indent=2)


# ── Memory update helpers ─────────────────────────────────────
def update_language_preference(patient_id: int, language: str):
    """Records which language the patient prefers."""
    mem = load_memory(patient_id)
    mem["preferred_language"] = language
    save_memory(patient_id, mem)
    print(f"[MEMORY] Patient {patient_id} language → {language}")


def record_appointment_booked(patient_id: int,
                               doctor_name: str,
                               specialty: str,
                               hospital: str,
                               date_str: str,
                               time_slot: str):
    """Called after every successful booking."""
    mem = load_memory(patient_id)
    mem["total_appointments"] += 1
    mem["preferred_doctor"]   = doctor_name
    mem["preferred_hospital"] = hospital
    mem["preferred_time"]     = time_slot
    mem["last_specialty"]     = specialty
    mem["last_appointment"]   = {
        "doctor":   doctor_name,
        "specialty": specialty,
        "date":     date_str,
        "time":     time_slot,
    }
    save_memory(patient_id, mem)
    print(f"[MEMORY] Patient {patient_id} booked → {doctor_name} {date_str}")


def record_appointment_cancelled(patient_id: int):
    """Increments cancelled count."""
    mem = load_memory(patient_id)
    mem["cancelled_count"] += 1
    save_memory(patient_id, mem)


def record_appointment_rescheduled(patient_id: int):
    """Increments rescheduled count."""
    mem = load_memory(patient_id)
    mem["rescheduled_count"] += 1
    save_memory(patient_id, mem)


def record_conversation(patient_id: int, language: str):
    """Called at end of each conversation session."""
    mem = load_memory(patient_id)
    mem["conversation_count"] += 1
    mem["preferred_language"]  = language
    save_memory(patient_id, mem)


def add_patient_note(patient_id: int, note: str):
    """Adds a free-text note to patient memory."""
    mem = load_memory(patient_id)
    mem["notes"].append({
        "text": note,
        "time": time.strftime("%Y-%m-%d %H:%M")
    })
    # Keep last 10 notes
    mem["notes"] = mem["notes"][-10:]
    save_memory(patient_id, mem)


# ── Memory retrieval ──────────────────────────────────────────
def get_patient_preferences(patient_id: int) -> dict:
    """
    Returns a compact preferences dict used by the agent
    to personalise responses without loading full memory.
    """
    mem = load_memory(patient_id)
    return {
        "language":         mem["preferred_language"],
        "preferred_doctor": mem["preferred_doctor"],
        "preferred_time":   mem["preferred_time"],
        "last_specialty":   mem["last_specialty"],
        "last_appointment": mem["last_appointment"],
        "total_visits":     mem["total_appointments"],
    }


def build_memory_context_prompt(patient_id: int) -> str:
    """
    Builds a short context string injected into the agent
    system prompt so it can personalise replies.
    e.g. 'Patient prefers Hindi. Last saw Dr. Sharma (cardiology).'
    """
    prefs = get_patient_preferences(patient_id)
    lines = []

    if prefs["preferred_doctor"]:
        lines.append(f"Last doctor: {prefs['preferred_doctor']}")
    if prefs["last_specialty"]:
        lines.append(f"Last specialty: {prefs['last_specialty']}")
    if prefs["preferred_time"]:
        lines.append(f"Preferred time: {prefs['preferred_time']}")
    if prefs["total_visits"] > 0:
        lines.append(f"Total visits: {prefs['total_visits']}")
    if prefs["last_appointment"]:
        la = prefs["last_appointment"]
        lines.append(f"Last appointment: {la['date']} with {la['doctor']}")

    if not lines:
        return "New patient — no history yet."

    return "Patient history: " + " | ".join(lines)


def delete_patient_memory(patient_id: int) -> bool:
    """Deletes the patient's memory file (GDPR / reset)."""
    path = _memory_path(patient_id)
    if os.path.exists(path):
        os.remove(path)
        print(f"[MEMORY] Deleted memory for patient {patient_id}")
        return True
    return False


def list_all_patient_memories() -> list[dict]:
    """Returns summary of all stored patient memories."""
    summaries = []
    for fname in os.listdir(PERSISTENT_MEMORY_DIR):
        if fname.startswith("patient_") and fname.endswith(".json"):
            path = os.path.join(PERSISTENT_MEMORY_DIR, fname)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    mem = json.load(f)
                summaries.append({
                    "patient_id":    mem["patient_id"],
                    "language":      mem["preferred_language"],
                    "total_visits":  mem["total_appointments"],
                    "last_doctor":   mem["preferred_doctor"],
                    "conversations": mem["conversation_count"],
                })
            except Exception:
                pass
    return summaries