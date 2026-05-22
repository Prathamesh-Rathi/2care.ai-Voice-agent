# ============================================================
# database/seed.py  —  Insert sample data for testing
# ============================================================

import sqlite3
import sys
import os
from datetime import date, timedelta

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import DB_PATH
from database.db import init_db, get_connection


# ── Sample doctors ────────────────────────────────────────────
DOCTORS = [
    {"name": "Dr. Arjun Sharma",   "specialty": "cardiologist",   "hospital": "Apollo Hospital"},
    {"name": "Dr. Priya Nair",     "specialty": "dermatologist",  "hospital": "Fortis Hospital"},
    {"name": "Dr. Ramesh Kumar",   "specialty": "neurologist",    "hospital": "Apollo Hospital"},
    {"name": "Dr. Sunita Patel",   "specialty": "orthopedist",    "hospital": "Manipal Hospital"},
    {"name": "Dr. Kavitha Menon",  "specialty": "general physician", "hospital": "City Clinic"},
]

# ── Sample patients ───────────────────────────────────────────
PATIENTS = [
    {"name": "Rahul Verma",   "phone": "9876543210", "email": "rahul@example.com",  "language": "hi"},
    {"name": "Ananya Singh",  "phone": "9123456789", "email": "ananya@example.com", "language": "en"},
    {"name": "Murugan Raj",   "phone": "9988776655", "email": "murugan@example.com","language": "ta"},
]

# ── Time slots offered each day ───────────────────────────────
DAILY_SLOTS = [
    "09:00", "09:30", "10:00", "10:30",
    "11:00", "11:30", "14:00", "14:30",
    "15:00", "15:30", "16:00", "16:30",
]


def seed_doctors(conn):
    print("[SEED] Inserting doctors...")
    doctor_ids = []
    for doc in DOCTORS:
        cursor = conn.execute(
            "INSERT OR IGNORE INTO doctors (name, specialty, hospital) VALUES (?, ?, ?)",
            (doc["name"], doc["specialty"], doc["hospital"])
        )
        # Fetch id whether inserted or already existed
        row = conn.execute(
            "SELECT id FROM doctors WHERE name = ?", (doc["name"],)
        ).fetchone()
        doctor_ids.append(row["id"])
        print(f"  Doctor: {doc['name']} ({doc['specialty']}) → id={row['id']}")
    return doctor_ids


def seed_patients(conn):
    print("[SEED] Inserting patients...")
    patient_ids = []
    for pat in PATIENTS:
        conn.execute(
            """
            INSERT OR IGNORE INTO patients (name, phone, email, language)
            VALUES (?, ?, ?, ?)
            """,
            (pat["name"], pat["phone"], pat["email"], pat["language"])
        )
        row = conn.execute(
            "SELECT id FROM patients WHERE phone = ?", (pat["phone"],)
        ).fetchone()
        patient_ids.append(row["id"])
        print(f"  Patient: {pat['name']} (lang={pat['language']}) → id={row['id']}")
    return patient_ids


def seed_schedules(conn, doctor_ids):
    """Generate slots for next 5 days for every doctor."""
    print("[SEED] Inserting doctor schedules (next 5 days)...")
    today = date.today()
    count = 0
    for offset in range(1, 6):           # tomorrow … +5 days
        slot_date = (today + timedelta(days=offset)).isoformat()
        for doc_id in doctor_ids:
            for slot_time in DAILY_SLOTS:
                # Only insert if not already present
                exists = conn.execute(
                    """
                    SELECT id FROM doctor_schedule
                    WHERE doctor_id = ? AND date = ? AND time_slot = ?
                    """,
                    (doc_id, slot_date, slot_time)
                ).fetchone()
                if not exists:
                    conn.execute(
                        """
                        INSERT INTO doctor_schedule (doctor_id, date, time_slot, is_booked)
                        VALUES (?, ?, ?, 0)
                        """,
                        (doc_id, slot_date, slot_time)
                    )
                    count += 1
    print(f"  {count} schedule slots inserted.")


def seed_appointments(conn, patient_ids, doctor_ids):
    """Create 2 sample confirmed appointments."""
    print("[SEED] Inserting sample appointments...")
    today = date.today()
    appt_date = (today + timedelta(days=1)).isoformat()   # tomorrow

    # Appointment 1: Rahul → Dr. Sharma (cardiologist) at 10:00
    schedule_row = conn.execute(
        """
        SELECT id FROM doctor_schedule
        WHERE doctor_id = ? AND date = ? AND time_slot = ? AND is_booked = 0
        """,
        (doctor_ids[0], appt_date, "10:00")
    ).fetchone()

    if schedule_row:
        conn.execute(
            """
            INSERT INTO appointments
                (patient_id, doctor_id, schedule_id, date, time_slot, notes)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (patient_ids[0], doctor_ids[0], schedule_row["id"],
             appt_date, "10:00", "Routine cardiac checkup")
        )
        conn.execute(
            "UPDATE doctor_schedule SET is_booked = 1 WHERE id = ?",
            (schedule_row["id"],)
        )
        print(f"  Appt 1: {PATIENTS[0]['name']} → {DOCTORS[0]['name']} on {appt_date} at 10:00")

    # Appointment 2: Ananya → Dr. Nair (dermatologist) at 14:00
    schedule_row2 = conn.execute(
        """
        SELECT id FROM doctor_schedule
        WHERE doctor_id = ? AND date = ? AND time_slot = ? AND is_booked = 0
        """,
        (doctor_ids[1], appt_date, "14:00")
    ).fetchone()

    if schedule_row2:
        conn.execute(
            """
            INSERT INTO appointments
                (patient_id, doctor_id, schedule_id, date, time_slot, notes)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (patient_ids[1], doctor_ids[1], schedule_row2["id"],
             appt_date, "14:00", "Skin consultation")
        )
        conn.execute(
            "UPDATE doctor_schedule SET is_booked = 1 WHERE id = ?",
            (schedule_row2["id"],)
        )
        print(f"  Appt 2: {PATIENTS[1]['name']} → {DOCTORS[1]['name']} on {appt_date} at 14:00")


def run_seed():
    print("\n" + "="*55)
    print("  SEEDING DATABASE")
    print("="*55)

    # Make sure tables exist first
    init_db()

    conn = get_connection()

    doctor_ids  = seed_doctors(conn)
    patient_ids = seed_patients(conn)
    seed_schedules(conn, doctor_ids)
    seed_appointments(conn, patient_ids, doctor_ids)

    conn.commit()
    conn.close()

    print("="*55)
    print("  SEED COMPLETE")
    print("="*55 + "\n")


if __name__ == "__main__":
    run_seed()