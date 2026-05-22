# ============================================================
# backend/routes/appointments.py  —  REST endpoints
# ============================================================

import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from backend.controllers.appointment_controller import (
    check_availability,
    book_appointment,
    cancel_appointment_ctrl,
    reschedule_appointment_ctrl,
    get_patient_appointments,
    get_or_create_patient,
)

router = APIRouter(prefix="/appointments", tags=["appointments"])


# ── Request / Response models ─────────────────────────────────
class CheckAvailabilityRequest(BaseModel):
    specialty:  Optional[str] = None
    doctor_id:  Optional[int] = None
    date:       Optional[str] = None


class BookRequest(BaseModel):
    patient_phone: str
    patient_name:  Optional[str] = "Patient"
    specialty:     Optional[str] = None
    doctor_id:     Optional[int] = None
    date:          Optional[str] = None
    time_slot:     Optional[str] = None
    notes:         Optional[str] = ""


class CancelRequest(BaseModel):
    patient_phone:  str
    appointment_id: int


class RescheduleRequest(BaseModel):
    patient_phone:  str
    appointment_id: int
    new_date:       str
    new_time_slot:  Optional[str] = None


# ── Endpoints ─────────────────────────────────────────────────
@router.post("/check-availability")
def api_check_availability(req: CheckAvailabilityRequest):
    result = check_availability(
        specialty=req.specialty,
        doctor_id=req.doctor_id,
        date_str=req.date
    )
    return result


@router.post("/book")
def api_book(req: BookRequest):
    patient = get_or_create_patient(req.patient_phone, req.patient_name)
    result = book_appointment(
        patient_id=patient["id"],
        specialty=req.specialty,
        doctor_id=req.doctor_id,
        date_str=req.date,
        time_slot=req.time_slot,
        notes=req.notes
    )
    return result


@router.post("/cancel")
def api_cancel(req: CancelRequest):
    patient = get_or_create_patient(req.patient_phone)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found.")
    result = cancel_appointment_ctrl(
        appointment_id=req.appointment_id,
        patient_id=patient["id"]
    )
    return result


@router.post("/reschedule")
def api_reschedule(req: RescheduleRequest):
    patient = get_or_create_patient(req.patient_phone)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found.")
    result = reschedule_appointment_ctrl(
        appointment_id=req.appointment_id,
        patient_id=patient["id"],
        new_date_str=req.new_date,
        new_time_slot=req.new_time_slot
    )
    return result


@router.get("/patient/{phone}")
def api_get_patient_appointments(phone: str):
    patient = get_or_create_patient(phone)
    return get_patient_appointments(patient["id"])