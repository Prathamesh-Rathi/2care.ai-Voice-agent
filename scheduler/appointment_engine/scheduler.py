# ============================================================
# scheduler/appointment_engine/scheduler.py
# Smart scheduling — slot finding, alternatives, suggestions
# ============================================================

import sys, os
from datetime import date, datetime, timedelta

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from database.db import (
    get_connection,
    get_available_slots,
    get_doctors_by_specialty,
    get_doctor_by_id,
    get_appointments_by_patient,
    create_appointment,
    mark_slot_booked,
)
from scheduler.appointment_engine.conflict_detector import (
    validate_booking_request,
    is_past_date,
    is_weekend,
    exceeds_advance_limit,
    CLINIC_OPEN_TIME,
    CLINIC_CLOSE_TIME,
    MAX_ADVANCE_DAYS,
)


# ── Date range generator ──────────────────────────────────────
def get_date_range(start_date: str, days: int = 7) -> list[str]:
    """
    Returns a list of YYYY-MM-DD strings starting from
    start_date for the next `days` working days (skips weekends).
    """
    try:
        current = datetime.strptime(start_date, "%Y-%m-%d").date()
    except ValueError:
        current = date.today() + timedelta(days=1)

    dates   = []
    checked = 0
    while len(dates) < days and checked < days * 3:
        if current.weekday() < 5:   # Mon–Fri only
            dates.append(current.isoformat())
        current += timedelta(days=1)
        checked += 1

    return dates


# ── Find next available slot ──────────────────────────────────
def find_next_available_slot(doctor_id: int,
                              from_date: str,
                              preferred_time: str = None,
                              days_to_search: int = 7) -> dict | None:
    """
    Searches forward from from_date to find the next
    available slot for a doctor.

    Args:
        doctor_id:      Doctor to search for.
        from_date:      Start searching from this date.
        preferred_time: Try to match this time if possible ('HH:MM').
        days_to_search: How many days forward to look.

    Returns:
        Slot dict {schedule_id, doctor_id, date, time_slot, ...}
        or None if nothing found.
    """
    search_dates = get_date_range(from_date, days=days_to_search)

    for search_date in search_dates:
        slots = get_available_slots(doctor_id, search_date)
        if not slots:
            continue

        # Try preferred time first
        if preferred_time:
            for slot in slots:
                if slot["time_slot"] == preferred_time:
                    doctor = get_doctor_by_id(doctor_id)
                    return {
                        "schedule_id": slot["id"],
                        "doctor_id":   doctor_id,
                        "doctor_name": doctor["name"],
                        "specialty":   doctor["specialty"],
                        "hospital":    doctor["hospital"],
                        "date":        search_date,
                        "time_slot":   slot["time_slot"],
                    }

        # Return first available slot on this date
        slot   = slots[0]
        doctor = get_doctor_by_id(doctor_id)
        return {
            "schedule_id": slot["id"],
            "doctor_id":   doctor_id,
            "doctor_name": doctor["name"],
            "specialty":   doctor["specialty"],
            "hospital":    doctor["hospital"],
            "date":        search_date,
            "time_slot":   slot["time_slot"],
        }

    return None


# ── Find alternatives ─────────────────────────────────────────
def find_alternative_slots(specialty: str,
                            requested_date: str,
                            requested_time: str = None,
                            max_results: int = 3) -> list[dict]:
    """
    When a specific slot is unavailable, finds the best
    alternatives across all doctors of that specialty.

    Strategy:
      1. Same date, different time slots
      2. Same date, different doctor (same specialty)
      3. Next available date, any doctor of that specialty

    Returns list of up to max_results slot dicts.
    """
    alternatives = []
    doctors      = get_doctors_by_specialty(specialty)

    if not doctors:
        return []

    # ── Strategy 1 + 2: Same date, any doctor ────────────────
    for doctor in doctors:
        if len(alternatives) >= max_results:
            break
        slots = get_available_slots(doctor["id"], requested_date)
        for slot in slots:
            if len(alternatives) >= max_results:
                break
            # Skip the exact slot that was already requested
            if slot["time_slot"] == requested_time:
                continue
            alternatives.append({
                "schedule_id": slot["id"],
                "doctor_id":   doctor["id"],
                "doctor_name": doctor["name"],
                "specialty":   doctor["specialty"],
                "hospital":    doctor["hospital"],
                "date":        requested_date,
                "time_slot":   slot["time_slot"],
            })

    # ── Strategy 3: Next available date ──────────────────────
    if len(alternatives) < max_results:
        tomorrow = (
            datetime.strptime(requested_date, "%Y-%m-%d").date()
            + timedelta(days=1)
        ).isoformat()

        for doctor in doctors:
            if len(alternatives) >= max_results:
                break
            next_slot = find_next_available_slot(
                doctor_id      = doctor["id"],
                from_date      = tomorrow,
                preferred_time = requested_time,
                days_to_search = 5,
            )
            if next_slot:
                # Avoid duplicate entries
                existing_keys = {
                    (a["doctor_id"], a["date"], a["time_slot"])
                    for a in alternatives
                }
                key = (next_slot["doctor_id"],
                       next_slot["date"],
                       next_slot["time_slot"])
                if key not in existing_keys:
                    alternatives.append(next_slot)

    return alternatives[:max_results]


# ── Format alternatives for response ─────────────────────────
def format_alternatives_message(alternatives: list[dict],
                                  language: str = "en") -> str:
    """
    Formats alternative slots into a human-readable string
    in the appropriate language.
    """
    if not alternatives:
        return {
            "en": "No alternative slots found.",
            "hi": "कोई वैकल्पिक स्लॉट नहीं मिला।",
            "ta": "மாற்று இடங்கள் எதுவும் இல்லை.",
        }.get(language, "No alternative slots found.")

    headers = {
        "en": "Here are available alternatives:",
        "hi": "यहाँ उपलब्ध विकल्प हैं:",
        "ta": "கிடைக்கும் மாற்று விருப்பங்கள்:",
    }

    lines = [headers.get(language, headers["en"])]
    for i, slot in enumerate(alternatives, 1):
        lines.append(
            f"  {i}. {slot['doctor_name']} — "
            f"{slot['date']} at {slot['time_slot']} "
            f"({slot['hospital']})"
        )
    return "\n".join(lines)


# ── Smart book function ───────────────────────────────────────
def smart_book_appointment(patient_id: int,
                            specialty: str,
                            date_str: str,
                            time_str: str = None,
                            doctor_id: int = None,
                            notes: str = "") -> dict:
    """
    Full smart booking with validation + conflict detection
    + automatic alternative suggestions.

    This is the upgraded version of the simple book_appointment
    in the controller. The agent calls this from Phase 7 onwards.

    Returns:
        {
          "success":      bool,
          "message":      str,
          "appointment":  dict | None,
          "alternatives": list | None,
          "warnings":     list,
        }
    """
    # ── Basic date checks ────────────────────────────────────
    if is_past_date(date_str):
        return {
            "success":      False,
            "message":      f"Cannot book for {date_str} — date is in the past.",
            "appointment":  None,
            "alternatives": None,
            "warnings":     [],
        }

    if is_weekend(date_str):
        # Find next Monday automatically
        next_weekday = _next_weekday(date_str)
        return {
            "success":      False,
            "message":      (
                f"{date_str} is a weekend. "
                f"Next available weekday is {next_weekday}."
            ),
            "appointment":  None,
            "alternatives": None,
            "warnings":     [f"Clinic closed on weekends."],
        }

    if exceeds_advance_limit(date_str):
        return {
            "success":      False,
            "message":      (
                f"Cannot book more than {MAX_ADVANCE_DAYS} days "
                f"in advance."
            ),
            "appointment":  None,
            "alternatives": None,
            "warnings":     [],
        }

    # ── Find eligible doctors ─────────────────────────────────
    if doctor_id:
        doctor = get_doctor_by_id(doctor_id)
        doctors = [doctor] if doctor else []
    else:
        doctors = get_doctors_by_specialty(specialty)

    if not doctors:
        return {
            "success":      False,
            "message":      f"No doctors found for specialty '{specialty}'.",
            "appointment":  None,
            "alternatives": None,
            "warnings":     [],
        }

    # ── Try to find and book a slot ───────────────────────────
    chosen_slot   = None
    chosen_doctor = None

    for doctor in doctors:
        slots = get_available_slots(doctor["id"], date_str)
        if not slots:
            continue

        # Try exact time match first
        if time_str:
            for slot in slots:
                if slot["time_slot"] == time_str:
                    chosen_slot   = slot
                    chosen_doctor = doctor
                    break

        # Fall back to first available
        if not chosen_slot and slots:
            chosen_slot   = slots[0]
            chosen_doctor = doctor

        if chosen_slot:
            break

    # ── No slot found — return alternatives ───────────────────
    if not chosen_slot or not chosen_doctor:
        alternatives = find_alternative_slots(
            specialty      = specialty,
            requested_date = date_str,
            requested_time = time_str,
            max_results    = 3,
        )
        alt_msg = format_alternatives_message(alternatives)
        return {
            "success":      False,
            "message":      (
                f"No slots available on {date_str}. "
                f"\n{alt_msg}"
            ),
            "appointment":  None,
            "alternatives": alternatives,
            "warnings":     [],
        }

    # ── Run full validation ───────────────────────────────────
    validation = validate_booking_request(
        patient_id = patient_id,
        doctor_id  = chosen_doctor["id"],
        date_str   = date_str,
        time_str   = chosen_slot["time_slot"],
    )

    if not validation["valid"]:
        alternatives = find_alternative_slots(
            specialty      = specialty,
            requested_date = date_str,
            requested_time = time_str,
        )
        return {
            "success":      False,
            "message":      " | ".join(validation["errors"]),
            "appointment":  None,
            "alternatives": alternatives,
            "warnings":     validation["warnings"],
        }

    # ── Commit the booking ────────────────────────────────────
    appt_id = create_appointment(
        patient_id  = patient_id,
        doctor_id   = chosen_doctor["id"],
        schedule_id = chosen_slot["id"],
        date        = date_str,
        time_slot   = chosen_slot["time_slot"],
        notes       = notes,
    )
    mark_slot_booked(chosen_slot["id"])

    appointment_data = {
        "id":          appt_id,
        "doctor_name": chosen_doctor["name"],
        "specialty":   chosen_doctor["specialty"],
        "hospital":    chosen_doctor["hospital"],
        "date":        date_str,
        "time_slot":   chosen_slot["time_slot"],
    }

    return {
        "success":      True,
        "message":      (
            f"Appointment booked with {chosen_doctor['name']} "
            f"({chosen_doctor['specialty']}) on {date_str} "
            f"at {chosen_slot['time_slot']} at "
            f"{chosen_doctor['hospital']}."
        ),
        "appointment":  appointment_data,
        "alternatives": None,
        "warnings":     validation["warnings"],
    }


# ── Patient schedule summary ──────────────────────────────────
def get_patient_schedule_summary(patient_id: int) -> dict:
    """
    Returns a complete schedule summary for a patient.
    Includes upcoming appointments sorted by date + time,
    and a count grouped by specialty.
    """
    appointments = get_appointments_by_patient(patient_id)

    if not appointments:
        return {
            "total":          0,
            "upcoming":       [],
            "by_specialty":   {},
            "next_appointment": None,
        }

    # Sort by date then time
    sorted_appts = sorted(
        appointments,
        key=lambda a: (a["date"], a["time_slot"])
    )

    # Group by specialty
    by_specialty = {}
    for appt in sorted_appts:
        spec = appt.get("specialty", "unknown")
        by_specialty[spec] = by_specialty.get(spec, 0) + 1

    return {
        "total":            len(sorted_appts),
        "upcoming":         sorted_appts,
        "by_specialty":     by_specialty,
        "next_appointment": sorted_appts[0] if sorted_appts else None,
    }


# ── Doctor availability summary ───────────────────────────────
def get_doctor_availability_summary(doctor_id: int,
                                     days: int = 5) -> dict:
    """
    Returns a summary of a doctor's availability
    for the next `days` working days.
    """
    doctor      = get_doctor_by_id(doctor_id)
    if not doctor:
        return {"error": "Doctor not found."}

    start_date  = (date.today() + timedelta(days=1)).isoformat()
    search_dates = get_date_range(start_date, days=days)

    availability = {}
    total_slots  = 0

    for d in search_dates:
        slots = get_available_slots(doctor_id, d)
        availability[d] = [s["time_slot"] for s in slots]
        total_slots += len(slots)

    return {
        "doctor_id":    doctor_id,
        "doctor_name":  doctor["name"],
        "specialty":    doctor["specialty"],
        "hospital":     doctor["hospital"],
        "days_checked": days,
        "total_free_slots": total_slots,
        "availability": availability,
    }


# ── Private helpers ───────────────────────────────────────────
def _next_weekday(date_str: str) -> str:
    """Returns the next Monday after a weekend date."""
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
        days_ahead = 7 - d.weekday()   # days until next Monday
        return (d + timedelta(days=days_ahead % 7 or 7)).isoformat()
    except ValueError:
        return (date.today() + timedelta(days=1)).isoformat()