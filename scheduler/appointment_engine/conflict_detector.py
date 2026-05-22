# ============================================================
# scheduler/appointment_engine/conflict_detector.py
# All validation and conflict detection logic lives here
# ============================================================

import sys, os
from datetime import datetime, date, timedelta

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
from database.db import (
    get_connection,
    get_available_slots,
    get_appointments_by_patient,
    get_doctor_by_id,
)


# ── Time slot helpers ─────────────────────────────────────────
def parse_slot_datetime(date_str: str, time_str: str) -> datetime | None:
    """
    Parses date + time strings into a datetime object.
    date_str: 'YYYY-MM-DD'
    time_str: 'HH:MM'
    Returns None on parse failure.
    """
    try:
        return datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    except ValueError:
        return None


def slot_to_minutes(time_str: str) -> int | None:
    """
    Converts 'HH:MM' to minutes since midnight.
    e.g. '09:30' → 570
    Returns None on failure.
    """
    try:
        h, m = map(int, time_str.split(":"))
        return h * 60 + m
    except Exception:
        return None


def minutes_between_slots(slot_a: str, slot_b: str) -> int:
    """
    Returns absolute minute difference between two time slots.
    e.g. '09:00' and '10:30' → 90
    """
    a = slot_to_minutes(slot_a)
    b = slot_to_minutes(slot_b)
    if a is None or b is None:
        return 999
    return abs(a - b)


# ── Rule 1: Past date/time check ─────────────────────────────
def is_past_slot(date_str: str, time_str: str) -> bool:
    """
    Returns True if the slot is in the past.
    Blocks any booking for a time that has already passed.
    """
    slot_dt = parse_slot_datetime(date_str, time_str)
    if not slot_dt:
        return True   # treat unparseable as invalid
    return slot_dt < datetime.now()


def is_past_date(date_str: str) -> bool:
    """Returns True if the date is strictly before today."""
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
        return d < date.today()
    except ValueError:
        return True


# ── Rule 2: Double booking check ─────────────────────────────
def is_slot_already_booked(doctor_id: int,
                           date_str: str,
                           time_str: str) -> bool:
    """
    Returns True if the doctor already has a confirmed
    appointment in this exact slot.
    """
    conn = get_connection()
    row  = conn.execute(
        """
        SELECT a.id FROM appointments a
        JOIN doctor_schedule ds ON a.schedule_id = ds.id
        WHERE a.doctor_id = ?
          AND a.date      = ?
          AND a.time_slot = ?
          AND a.status    = 'confirmed'
        """,
        (doctor_id, date_str, time_str)
    ).fetchone()
    conn.close()
    return row is not None


# ── Rule 3: Patient overlap check ────────────────────────────
def patient_has_overlap(patient_id: int,
                        date_str: str,
                        time_str: str,
                        buffer_minutes: int = 30) -> dict:
    """
    Checks if patient already has an appointment within
    buffer_minutes of the requested slot on the same day.

    Returns:
        {"conflict": bool, "existing_slot": str | None,
         "existing_doctor": str | None}
    """
    appointments = get_appointments_by_patient(patient_id)
    new_minutes  = slot_to_minutes(time_str)

    if new_minutes is None:
        return {"conflict": False, "existing_slot": None,
                "existing_doctor": None}

    for appt in appointments:
        if appt["date"] != date_str:
            continue
        existing_minutes = slot_to_minutes(appt["time_slot"])
        if existing_minutes is None:
            continue
        if abs(new_minutes - existing_minutes) < buffer_minutes:
            return {
                "conflict":        True,
                "existing_slot":   appt["time_slot"],
                "existing_doctor": appt.get("doctor_name", "another doctor"),
            }

    return {"conflict": False, "existing_slot": None,
            "existing_doctor": None}


# ── Rule 4: Working hours check ──────────────────────────────
CLINIC_OPEN_TIME  = "09:00"
CLINIC_CLOSE_TIME = "17:00"

def is_within_working_hours(time_str: str) -> bool:
    """
    Returns True if the time slot falls within clinic hours.
    Clinic hours: 09:00 – 17:00
    """
    slot    = slot_to_minutes(time_str)
    open_t  = slot_to_minutes(CLINIC_OPEN_TIME)
    close_t = slot_to_minutes(CLINIC_CLOSE_TIME)

    if slot is None or open_t is None or close_t is None:
        return False
    return open_t <= slot <= close_t


# ── Rule 5: Weekend check ─────────────────────────────────────
def is_weekend(date_str: str) -> bool:
    """
    Returns True if date falls on Saturday or Sunday.
    Weekends have no clinic availability.
    """
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
        return d.weekday() >= 5   # 5=Saturday, 6=Sunday
    except ValueError:
        return False


# ── Rule 6: Advance booking limit ────────────────────────────
MAX_ADVANCE_DAYS = 30

def exceeds_advance_limit(date_str: str) -> bool:
    """
    Returns True if the booking is more than MAX_ADVANCE_DAYS away.
    Prevents booking too far into the future.
    """
    try:
        d     = datetime.strptime(date_str, "%Y-%m-%d").date()
        delta = (d - date.today()).days
        return delta > MAX_ADVANCE_DAYS
    except ValueError:
        return True


# ── Master validation function ────────────────────────────────
def validate_booking_request(patient_id: int,
                              doctor_id: int,
                              date_str: str,
                              time_str: str) -> dict:
    """
    Runs all validation rules against a booking request.
    Returns a result dict — check 'valid' key first.

    Returns:
        {
          "valid":   bool,
          "errors":  [str, ...],
          "warnings": [str, ...]
        }
    """
    errors   = []
    warnings = []

    # Rule 1: Past date
    if is_past_date(date_str):
        errors.append(f"Date {date_str} is in the past.")

    # Rule 2: Past time slot
    elif is_past_slot(date_str, time_str):
        errors.append(f"Slot {date_str} {time_str} has already passed.")

    # Rule 3: Weekend
    if is_weekend(date_str):
        errors.append(f"{date_str} is a weekend. Clinic is closed.")

    # Rule 4: Working hours
    if time_str and not is_within_working_hours(time_str):
        errors.append(
            f"Slot {time_str} is outside clinic hours "
            f"({CLINIC_OPEN_TIME}–{CLINIC_CLOSE_TIME})."
        )

    # Rule 5: Advance booking limit
    if exceeds_advance_limit(date_str):
        errors.append(
            f"Cannot book more than {MAX_ADVANCE_DAYS} days in advance."
        )

    # Rule 6: Doctor double booking
    if not errors and is_slot_already_booked(doctor_id, date_str, time_str):
        errors.append(
            f"Slot {time_str} on {date_str} is already booked "
            f"for this doctor."
        )

    # Rule 7: Patient overlap (warning, not error)
    if not errors:
        overlap = patient_has_overlap(patient_id, date_str, time_str)
        if overlap["conflict"]:
            warnings.append(
                f"You already have an appointment at "
                f"{overlap['existing_slot']} with "
                f"{overlap['existing_doctor']} on the same day."
            )

    return {
        "valid":    len(errors) == 0,
        "errors":   errors,
        "warnings": warnings,
    }