# ============================================================
# test_scheduler.py  —  Scheduler + conflict detection tests
# Run: python test_scheduler.py
# Make sure DB is seeded first: python database/seed.py
# ============================================================

import sys, os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from datetime import date, timedelta

from scheduler.appointment_engine.scheduler import (
    smart_book_appointment,
    find_alternative_slots,
    find_next_available_slot,
    get_patient_schedule_summary,
    get_doctor_availability_summary,
    format_alternatives_message,
    get_date_range,
)
from scheduler.appointment_engine.conflict_detector import (
    validate_booking_request,
    is_past_date,
    is_past_slot,
    is_weekend,
    is_within_working_hours,
    exceeds_advance_limit,
    patient_has_overlap,
    is_slot_already_booked,
)


def print_section(title: str):
    print(f"\n{'='*58}")
    print(f"  {title}")
    print(f"{'='*58}")


def tomorrow() -> str:
    return (date.today() + timedelta(days=1)).isoformat()

def next_week() -> str:
    return (date.today() + timedelta(days=7)).isoformat()

def yesterday() -> str:
    return (date.today() - timedelta(days=1)).isoformat()


# ── Test 1: Conflict detector rules ──────────────────────────
def test_conflict_rules():
    print_section("TEST 1 — Conflict detection rules")

    # Past date
    result = is_past_date(yesterday())
    print(f"  is_past_date(yesterday)     = {result} (expected True)")

    result = is_past_date(tomorrow())
    print(f"  is_past_date(tomorrow)      = {result} (expected False)")

    # Past slot
    result = is_past_slot(yesterday(), "10:00")
    print(f"  is_past_slot(yesterday)     = {result} (expected True)")

    result = is_past_slot(tomorrow(), "10:00")
    print(f"  is_past_slot(tomorrow)      = {result} (expected False)")

    # Weekend detection
    # Find next Saturday
    today   = date.today()
    sat     = today + timedelta(days=(5 - today.weekday()) % 7 or 7)
    result  = is_weekend(sat.isoformat())
    print(f"  is_weekend(next Saturday)   = {result} (expected True)")

    result  = is_weekend(tomorrow())
    print(f"  is_weekend(tomorrow)        = {result} "
          f"(expected {date.today().weekday() >= 4})")

    # Working hours
    print(f"  is_within_working_hours('09:00') = "
          f"{is_within_working_hours('09:00')} (expected True)")
    print(f"  is_within_working_hours('08:00') = "
          f"{is_within_working_hours('08:00')} (expected False)")
    print(f"  is_within_working_hours('17:00') = "
          f"{is_within_working_hours('17:00')} (expected True)")
    print(f"  is_within_working_hours('18:00') = "
          f"{is_within_working_hours('18:00')} (expected False)")

    # Advance booking limit
    far_future = (date.today() + timedelta(days=35)).isoformat()
    print(f"  exceeds_advance_limit(+35 days) = "
          f"{exceeds_advance_limit(far_future)} (expected True)")
    print(f"  exceeds_advance_limit(tomorrow) = "
          f"{exceeds_advance_limit(tomorrow())} (expected False)")


# ── Test 2: Full validation ───────────────────────────────────
def test_full_validation():
    print_section("TEST 2 — Full booking validation")

    cases = [
        {
            "label":      "Valid booking",
            "patient_id": 2,
            "doctor_id":  1,
            "date":       tomorrow(),
            "time":       "10:00",
            "expect_valid": True,
        },
        {
            "label":      "Past date",
            "patient_id": 2,
            "doctor_id":  1,
            "date":       yesterday(),
            "time":       "10:00",
            "expect_valid": False,
        },
        {
            "label":      "Outside working hours",
            "patient_id": 2,
            "doctor_id":  1,
            "date":       tomorrow(),
            "time":       "07:00",
            "expect_valid": False,
        },
    ]

    for case in cases:
        result = validate_booking_request(
            patient_id = case["patient_id"],
            doctor_id  = case["doctor_id"],
            date_str   = case["date"],
            time_str   = case["time"],
        )
        status = "✓" if result["valid"] == case["expect_valid"] else "✗"
        print(f"  {status} {case['label']}")
        print(f"      valid={result['valid']} | "
              f"errors={result['errors']} | "
              f"warnings={result['warnings']}")


# ── Test 3: Smart booking ─────────────────────────────────────
def test_smart_booking():
    print_section("TEST 3 — Smart booking")

    # Valid booking
    print("\n  Case A: Valid booking — cardiologist tomorrow")
    result = smart_book_appointment(
        patient_id = 2,
        specialty  = "cardiologist",
        date_str   = tomorrow(),
        time_str   = "11:00",
    )
    print(f"  success = {result['success']}")
    print(f"  message = {result['message']}")
    if result["appointment"]:
        print(f"  appt    = {result['appointment']}")
    if result["warnings"]:
        print(f"  warnings= {result['warnings']}")

    # Past date booking
    print("\n  Case B: Past date — should fail with alternatives")
    result = smart_book_appointment(
        patient_id = 2,
        specialty  = "dermatologist",
        date_str   = yesterday(),
        time_str   = "10:00",
    )
    print(f"  success = {result['success']}")
    print(f"  message = {result['message'][:80]}")

    # Weekend booking
    today = date.today()
    sat   = today + timedelta(days=(5 - today.weekday()) % 7 or 7)
    print(f"\n  Case C: Weekend booking ({sat}) — should redirect")
    result = smart_book_appointment(
        patient_id = 2,
        specialty  = "neurologist",
        date_str   = sat.isoformat(),
    )
    print(f"  success = {result['success']}")
    print(f"  message = {result['message']}")


# ── Test 4: Alternative slots ─────────────────────────────────
def test_alternatives():
    print_section("TEST 4 — Alternative slot suggestions")

    alts = find_alternative_slots(
        specialty      = "cardiologist",
        requested_date = tomorrow(),
        requested_time = "10:00",
        max_results    = 3,
    )

    print(f"  Found {len(alts)} alternatives:")
    for alt in alts:
        print(f"    → {alt['doctor_name']} | "
              f"{alt['date']} {alt['time_slot']} | "
              f"{alt['hospital']}")

    # Formatted message
    print("\n  English format:")
    print(format_alternatives_message(alts, "en"))

    print("\n  Hindi format:")
    print(format_alternatives_message(alts, "hi"))

    print("\n  Tamil format:")
    print(format_alternatives_message(alts, "ta"))


# ── Test 5: Next available slot ───────────────────────────────
def test_next_available():
    print_section("TEST 5 — Find next available slot")

    result = find_next_available_slot(
        doctor_id      = 1,
        from_date      = tomorrow(),
        preferred_time = "14:00",
        days_to_search = 7,
    )

    if result:
        print(f"  Next slot for Doctor 1:")
        print(f"    Date:    {result['date']}")
        print(f"    Time:    {result['time_slot']}")
        print(f"    Doctor:  {result['doctor_name']}")
        print(f"    Hospital:{result['hospital']}")
    else:
        print("  No slot found in next 7 days.")


# ── Test 6: Patient schedule summary ─────────────────────────
def test_patient_summary():
    print_section("TEST 6 — Patient schedule summary")

    for pid in [1, 2, 3]:
        summary = get_patient_schedule_summary(pid)
        print(f"\n  Patient {pid}:")
        print(f"    Total appointments : {summary['total']}")
        print(f"    By specialty       : {summary['by_specialty']}")
        if summary["next_appointment"]:
            n = summary["next_appointment"]
            print(f"    Next appointment   : {n['date']} {n['time_slot']} "
                  f"with {n.get('doctor_name', 'N/A')}")


# ── Test 7: Doctor availability summary ──────────────────────
def test_doctor_summary():
    print_section("TEST 7 — Doctor availability summary")

    for doc_id in [1, 2]:
        summary = get_doctor_availability_summary(doc_id, days=3)
        print(f"\n  Doctor {doc_id}: {summary.get('doctor_name')}")
        print(f"    Specialty         : {summary.get('specialty')}")
        print(f"    Total free slots  : {summary.get('total_free_slots')}")
        for d, slots in summary.get("availability", {}).items():
            print(f"    {d}: {len(slots)} slots — {slots[:4]}"
                  f"{'...' if len(slots) > 4 else ''}")


# ── Test 8: Date range generator ─────────────────────────────
def test_date_range():
    print_section("TEST 8 — Working day range generator")
    dates = get_date_range(tomorrow(), days=7)
    print(f"  Next 7 working days from tomorrow:")
    for d in dates:
        from datetime import datetime
        weekday = datetime.strptime(d, "%Y-%m-%d").strftime("%A")
        print(f"    {d} ({weekday})")


# ── Run all ───────────────────────────────────────────────────
if __name__ == "__main__":
    print("\nEnsure DB is seeded: python database/seed.py\n")

    test_conflict_rules()
    test_full_validation()
    test_smart_booking()
    test_alternatives()
    test_next_available()
    test_patient_summary()
    test_doctor_summary()
    test_date_range()

    print(f"\n{'='*58}")
    print("  All scheduler tests complete.")
    print(f"{'='*58}\n")