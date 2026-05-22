# ============================================================
# database/db.py  —  Connection + all DB operations
# ============================================================

import sqlite3
import sys
import os

# Add project root to path so config.py is always found
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import DB_PATH
from database.models import ALL_TABLES


# ── Connection helper ─────────────────────────────────────────
def get_connection():
    """
    Returns a sqlite3 connection with:
    - Row factory so results come back as dicts
    - Foreign key enforcement enabled
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row   # rows behave like dicts
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# ── Create all tables ─────────────────────────────────────────
def init_db():
    """
    Creates all tables if they do not already exist.
    Safe to call every time the app starts.
    """
    conn = get_connection()
    cursor = conn.cursor()
    for statement in ALL_TABLES:
        cursor.execute(statement)
    conn.commit()
    conn.close()
    print("[DB] All tables created / verified.")


# ── Patient queries ───────────────────────────────────────────
def get_patient_by_phone(phone: str):
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM patients WHERE phone = ?", (phone,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_patient_by_id(patient_id: int):
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM patients WHERE id = ?", (patient_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def create_patient(name: str, phone: str, email: str = "", language: str = "en"):
    conn = get_connection()
    cursor = conn.execute(
        "INSERT INTO patients (name, phone, email, language) VALUES (?, ?, ?, ?)",
        (name, phone, email, language)
    )
    conn.commit()
    patient_id = cursor.lastrowid
    conn.close()
    return patient_id


def update_patient_language(patient_id: int, language: str):
    conn = get_connection()
    conn.execute(
        "UPDATE patients SET language = ? WHERE id = ?",
        (language, patient_id)
    )
    conn.commit()
    conn.close()


# ── Doctor queries ────────────────────────────────────────────
def get_all_doctors():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM doctors").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_doctor_by_id(doctor_id: int):
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM doctors WHERE id = ?", (doctor_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_doctors_by_specialty(specialty: str):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM doctors WHERE LOWER(specialty) LIKE ?",
        (f"%{specialty.lower()}%",)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Schedule / availability queries ──────────────────────────
def get_available_slots(doctor_id: int, date: str):
    """
    Returns all free time slots for a doctor on a given date.
    date format: 'YYYY-MM-DD'
    """
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT * FROM doctor_schedule
        WHERE doctor_id = ? AND date = ? AND is_booked = 0
        ORDER BY time_slot
        """,
        (doctor_id, date)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_slot_by_id(schedule_id: int):
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM doctor_schedule WHERE id = ?", (schedule_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def mark_slot_booked(schedule_id: int):
    conn = get_connection()
    conn.execute(
        "UPDATE doctor_schedule SET is_booked = 1 WHERE id = ?",
        (schedule_id,)
    )
    conn.commit()
    conn.close()


def mark_slot_free(schedule_id: int):
    conn = get_connection()
    conn.execute(
        "UPDATE doctor_schedule SET is_booked = 0 WHERE id = ?",
        (schedule_id,)
    )
    conn.commit()
    conn.close()


# ── Appointment queries ───────────────────────────────────────
def create_appointment(patient_id: int, doctor_id: int,
                       schedule_id: int, date: str,
                       time_slot: str, notes: str = ""):
    conn = get_connection()
    cursor = conn.execute(
        """
        INSERT INTO appointments
            (patient_id, doctor_id, schedule_id, date, time_slot, notes)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (patient_id, doctor_id, schedule_id, date, time_slot, notes)
    )
    conn.commit()
    appt_id = cursor.lastrowid
    conn.close()
    return appt_id


def get_appointment_by_id(appt_id: int):
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM appointments WHERE id = ?", (appt_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_appointments_by_patient(patient_id: int):
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT a.*, d.name as doctor_name, d.specialty, d.hospital
        FROM appointments a
        JOIN doctors d ON a.doctor_id = d.id
        WHERE a.patient_id = ? AND a.status = 'confirmed'
        ORDER BY a.date, a.time_slot
        """,
        (patient_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def cancel_appointment(appt_id: int):
    """Cancels appointment and frees the slot."""
    conn = get_connection()
    # Get schedule_id first
    row = conn.execute(
        "SELECT schedule_id FROM appointments WHERE id = ?", (appt_id,)
    ).fetchone()
    if not row:
        conn.close()
        return False
    schedule_id = row["schedule_id"]
    # Cancel the appointment
    conn.execute(
        """
        UPDATE appointments
        SET status = 'cancelled', updated_at = datetime('now')
        WHERE id = ?
        """,
        (appt_id,)
    )
    # Free the slot
    conn.execute(
        "UPDATE doctor_schedule SET is_booked = 0 WHERE id = ?",
        (schedule_id,)
    )
    conn.commit()
    conn.close()
    return True


def reschedule_appointment(appt_id: int, new_schedule_id: int,
                           new_date: str, new_time_slot: str):
    """
    Cancels old slot, books new slot, updates appointment row.
    Returns True on success, False if appointment not found.
    """
    conn = get_connection()
    # Get old schedule_id
    row = conn.execute(
        "SELECT schedule_id FROM appointments WHERE id = ?", (appt_id,)
    ).fetchone()
    if not row:
        conn.close()
        return False
    old_schedule_id = row["schedule_id"]
    # Free old slot
    conn.execute(
        "UPDATE doctor_schedule SET is_booked = 0 WHERE id = ?",
        (old_schedule_id,)
    )
    # Book new slot
    conn.execute(
        "UPDATE doctor_schedule SET is_booked = 1 WHERE id = ?",
        (new_schedule_id,)
    )
    # Update appointment
    conn.execute(
        """
        UPDATE appointments
        SET schedule_id = ?, date = ?, time_slot = ?,
            status = 'confirmed', updated_at = datetime('now')
        WHERE id = ?
        """,
        (new_schedule_id, new_date, new_time_slot, appt_id)
    )
    conn.commit()
    conn.close()
    return True


# ── Conversation history ──────────────────────────────────────
def save_conversation_turn(patient_id: int, session_id: str,
                           role: str, message: str, language: str = "en"):
    """role = 'user' or 'assistant'"""
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO conversation_history
            (patient_id, session_id, role, message, language)
        VALUES (?, ?, ?, ?, ?)
        """,
        (patient_id, session_id, role, message, language)
    )
    conn.commit()
    conn.close()


def get_conversation_history(patient_id: int, limit: int = 20):
    """Returns last N turns for a patient across all sessions."""
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT role, message, language, created_at
        FROM conversation_history
        WHERE patient_id = ?
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (patient_id, limit)
    ).fetchall()
    conn.close()
    # Return in chronological order
    return [dict(r) for r in reversed(rows)]