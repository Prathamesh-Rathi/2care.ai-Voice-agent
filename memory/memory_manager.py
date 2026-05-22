# ============================================================
# memory/memory_manager.py
# Single interface — every other module imports ONLY this file
# ============================================================

from memory.session_memory.session_store import (
    create_session,
    get_session,
    add_turn,
    update_context,
    get_context,
    end_session,
    get_history_for_llm,
)
from memory.persistent_memory.patient_memory import (
    load        as load_patient,
    save        as save_patient,
    add_appointment_summary,
    update_language,
    add_note,
)
from memory.schema import SessionMemory, PatientMemory


class MemoryManager:

    # ── Session (in-RAM) ─────────────────────────────────────

    @staticmethod
    def new_session(patient_phone=None, language="en") -> SessionMemory:
        return create_session(patient_phone, language)

    @staticmethod
    def get_session(session_id: str) -> SessionMemory:
        return get_session(session_id)

    @staticmethod
    def add_turn(session_id: str, role: str, text: str, language: str = "en"):
        add_turn(session_id, role, text, language)

    @staticmethod
    def set_context(session_id: str, key: str, value):
        update_context(session_id, key, value)

    @staticmethod
    def get_context(session_id: str, key: str):
        return get_context(session_id, key)

    @staticmethod
    def llm_history(session_id: str) -> list:
        """Ready-to-use message list for Groq LLM call."""
        return get_history_for_llm(session_id)

    @staticmethod
    def close_session(session_id: str) -> SessionMemory:
        """End session + return final state so caller can archive it."""
        return end_session(session_id)

    # ── Persistent (JSON on disk) ─────────────────────────────

    @staticmethod
    def load_patient(phone: str) -> PatientMemory:
        return load_patient(phone)

    @staticmethod
    def save_patient(memory: PatientMemory):
        save_patient(memory)

    @staticmethod
    def record_appointment(phone, appt_id, doctor, specialty, date, time, status="confirmed"):
        add_appointment_summary(phone, appt_id, doctor, specialty, date, time, status)

    @staticmethod
    def set_language(phone: str, language: str):
        update_language(phone, language)

    @staticmethod
    def write_note(phone: str, note: str):
        add_note(phone, note)