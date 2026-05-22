# ============================================================
# backend/controllers/appointment_controller.py
# Business logic for all appointment operations
# ============================================================

import sys, os
from datetime import date, datetime, timedelta

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from database.db import (
    get_doctors_by_specialty,
    get_doctor_by_id,
    get_available_slots,
    get_slot_by_id,
    mark_slot_booked,
    mark_slot_free,
    create_appointment,
    get_appointment_by_id,
    get_appointments_by_patient,
    cancel_appointment,
    reschedule_appointment,
    get_patient_by_phone,
    create_patient,
)


# ── Utility ───────────────────────────────────────────────────
def resolve_date(date_str: str) -> str:
    """
    Converts natural date words to YYYY-MM-DD.
    Accepts: 'today', 'tomorrow', 'YYYY-MM-DD'
    """
    today = date.today()
    if not date_str:
        return (today + timedelta(days=1)).isoformat()
    d = date_str.strip().lower()
    if d == "today":
        return today.isoformat()
    if d == "tomorrow":
        return (today + timedelta(days=1)).isoformat()
    # Validate it looks like a real date
    try:
        datetime.strptime(d, "%Y-%m-%d")
        return d
    except ValueError:
        # Default to tomorrow if unrecognised
        return (today + timedelta(days=1)).isoformat()


def is_future_date(date_str: str) -> bool:
    """Returns True if date_str is today or in the future."""
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
        return d >= date.today()
    except ValueError:
        return False


# ── Check availability ────────────────────────────────────────
def check_availability(specialty: str = None,
                       doctor_id: int = None,
                       date_str: str = None) -> dict:
    """
    Returns available slots for a doctor or specialty on a date.
    """
    resolved_date = resolve_date(date_str)

    if not is_future_date(resolved_date):
        return {
            "success": False,
            "message": "Cannot check availability for past dates.",
            "slots": []
        }

    # Find doctor(s)
    if doctor_id:
        doctors = [get_doctor_by_id(doctor_id)]
        doctors = [d for d in doctors if d]
    elif specialty:
        doctors = get_doctors_by_specialty(specialty)
    else:
        return {"success": False, "message": "Provide specialty or doctor_id.", "slots": []}

    if not doctors:
        return {
            "success": False,
            "message": f"No doctors found for specialty '{specialty}'.",
            "slots": []
        }

    all_slots = []
    for doc in doctors:
        slots = get_available_slots(doc["id"], resolved_date)
        for slot in slots:
            all_slots.append({
                "schedule_id": slot["id"],
                "doctor_id":   doc["id"],
                "doctor_name": doc["name"],
                "specialty":   doc["specialty"],
                "hospital":    doc["hospital"],
                "date":        resolved_date,
                "time_slot":   slot["time_slot"],
            })

    if not all_slots:
        return {
            "success": True,
            "message": f"No available slots on {resolved_date}.",
            "slots": [],
            "date": resolved_date
        }

    return {
        "success": True,
        "message": f"Found {len(all_slots)} available slot(s) on {resolved_date}.",
        "slots": all_slots,
        "date": resolved_date
    }


# ── Book appointment ──────────────────────────────────────────
def book_appointment(patient_id: int,
                     specialty: str = None,
                     doctor_id: int = None,
                     date_str: str = None,
                     time_slot: str = None,
                     notes: str = "") -> dict:
    """
    Books the first available slot matching the criteria.
    If time_slot is given, tries that exact slot.
    """
    resolved_date = resolve_date(date_str)

    if not is_future_date(resolved_date):
        return {"success": False, "message": "Cannot book appointments in the past."}

    # Get availability first
    avail = check_availability(
        specialty=specialty,
        doctor_id=doctor_id,
        date_str=resolved_date
    )
    if not avail["success"] or not avail["slots"]:
        return {
            "success": False,
            "message": avail.get("message", "No slots available.")
        }

    slots = avail["slots"]

    # Try to match requested time_slot
    chosen = None
    if time_slot:
        for s in slots:
            if s["time_slot"] == time_slot:
                chosen = s
                break
        if not chosen:
            # Requested time not available — suggest alternatives
            alternatives = [s["time_slot"] for s in slots[:3]]
            return {
                "success": False,
                "message": (
                    f"Slot {time_slot} is not available on {resolved_date}. "
                    f"Available slots: {', '.join(alternatives)}."
                ),
                "alternatives": alternatives
            }
    else:
        # Take first available slot
        chosen = slots[0]

    # Book it
    appt_id = create_appointment(
        patient_id=patient_id,
        doctor_id=chosen["doctor_id"],
        schedule_id=chosen["schedule_id"],
        date=resolved_date,
        time_slot=chosen["time_slot"],
        notes=notes
    )
    mark_slot_booked(chosen["schedule_id"])

    return {
        "success": True,
        "message": (
            f"Appointment booked with {chosen['doctor_name']} "
            f"({chosen['specialty']}) on {resolved_date} at {chosen['time_slot']}."
        ),
        "appointment": {
            "id":          appt_id,
            "doctor_name": chosen["doctor_name"],
            "specialty":   chosen["specialty"],
            "hospital":    chosen["hospital"],
            "date":        resolved_date,
            "time_slot":   chosen["time_slot"],
        }
    }


# ── Cancel appointment ────────────────────────────────────────
def cancel_appointment_ctrl(appointment_id: int,
                             patient_id: int) -> dict:
    """
    Cancels an appointment.
    Verifies the appointment belongs to this patient.
    """
    appt = get_appointment_by_id(appointment_id)

    if not appt:
        return {"success": False, "message": f"Appointment #{appointment_id} not found."}

    if appt["patient_id"] != patient_id:
        return {"success": False, "message": "This appointment does not belong to you."}

    if appt["status"] == "cancelled":
        return {"success": False, "message": "Appointment is already cancelled."}

    success = cancel_appointment(appointment_id)

    if success:
        return {
            "success": True,
            "message": (
                f"Appointment #{appointment_id} on {appt['date']} "
                f"at {appt['time_slot']} has been cancelled."
            )
        }
    return {"success": False, "message": "Failed to cancel appointment."}


# ── Reschedule appointment ────────────────────────────────────
def reschedule_appointment_ctrl(appointment_id: int,
                                patient_id: int,
                                new_date_str: str,
                                new_time_slot: str = None) -> dict:
    """
    Reschedules an existing appointment to a new date/time.
    """
    appt = get_appointment_by_id(appointment_id)

    if not appt:
        return {"success": False, "message": f"Appointment #{appointment_id} not found."}

    if appt["patient_id"] != patient_id:
        return {"success": False, "message": "This appointment does not belong to you."}

    if appt["status"] == "cancelled":
        return {"success": False, "message": "Cannot reschedule a cancelled appointment."}

    resolved_date = resolve_date(new_date_str)

    if not is_future_date(resolved_date):
        return {"success": False, "message": "Cannot reschedule to a past date."}

    # Get available slots on new date for same doctor
    slots = get_available_slots(appt["doctor_id"], resolved_date)

    if not slots:
        return {
            "success": False,
            "message": f"No available slots on {resolved_date} for this doctor."
        }

    # Try exact time match
    chosen = None
    if new_time_slot:
        for s in slots:
            if s["time_slot"] == new_time_slot:
                chosen = s
                break
        if not chosen:
            alternatives = [s["time_slot"] for s in slots[:3]]
            return {
                "success": False,
                "message": (
                    f"Slot {new_time_slot} not available on {resolved_date}. "
                    f"Try: {', '.join(alternatives)}."
                ),
                "alternatives": alternatives
            }
    else:
        chosen = slots[0]

    success = reschedule_appointment(
        appt_id=appointment_id,
        new_schedule_id=chosen["id"],
        new_date=resolved_date,
        new_time_slot=chosen["time_slot"]
    )

    doctor = get_doctor_by_id(appt["doctor_id"])

    if success:
        return {
            "success": True,
            "message": (
                f"Appointment rescheduled to {resolved_date} "
                f"at {chosen['time_slot']} with {doctor['name']}."
            ),
            "appointment": {
                "id":          appointment_id,
                "doctor_name": doctor["name"],
                "date":        resolved_date,
                "time_slot":   chosen["time_slot"],
            }
        }
    return {"success": False, "message": "Failed to reschedule appointment."}


# ── Get patient appointments ──────────────────────────────────
def get_patient_appointments(patient_id: int) -> dict:
    appointments = get_appointments_by_patient(patient_id)
    if not appointments:
        return {
            "success": True,
            "message": "No upcoming appointments found.",
            "appointments": []
        }
    return {
        "success": True,
        "message": f"Found {len(appointments)} appointment(s).",
        "appointments": appointments
    }


# ── Get or create patient ─────────────────────────────────────
def get_or_create_patient(phone: str, name: str = "Patient",
                          language: str = "en") -> dict:
    patient = get_patient_by_phone(phone)
    if not patient:
        pid = create_patient(name=name, phone=phone, language=language)
        patient = {"id": pid, "name": name, "phone": phone, "language": language}
    return patient