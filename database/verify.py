# ============================================================
# database/verify.py  —  Print DB contents for inspection
# ============================================================

import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db import (
    get_connection, get_all_doctors, get_appointments_by_patient
)
from config import DB_PATH


def print_section(title):
    print(f"\n{'─'*50}")
    print(f"  {title}")
    print(f"{'─'*50}")


def verify():
    conn = get_connection()

    print_section("DOCTORS")
    for row in conn.execute("SELECT * FROM doctors").fetchall():
        print(f"  [{row['id']}] {row['name']} — {row['specialty']} @ {row['hospital']}")

    print_section("PATIENTS")
    for row in conn.execute("SELECT * FROM patients").fetchall():
        print(f"  [{row['id']}] {row['name']} | phone: {row['phone']} | lang: {row['language']}")

    print_section("SCHEDULE SLOTS (sample — first 10)")
    rows = conn.execute(
        "SELECT ds.*, d.name as dname FROM doctor_schedule ds "
        "JOIN doctors d ON ds.doctor_id = d.id LIMIT 10"
    ).fetchall()
    for row in rows:
        booked = "BOOKED" if row["is_booked"] else "free"
        print(f"  [{row['id']}] {row['dname']} | {row['date']} {row['time_slot']} | {booked}")

    print_section("APPOINTMENTS")
    for row in conn.execute("SELECT * FROM appointments").fetchall():
        print(
            f"  [{row['id']}] patient={row['patient_id']} "
            f"doctor={row['doctor_id']} | {row['date']} {row['time_slot']} "
            f"| status={row['status']}"
        )

    print_section("TOTAL COUNTS")
    for table in ["patients", "doctors", "doctor_schedule", "appointments"]:
        count = conn.execute(f"SELECT COUNT(*) as c FROM {table}").fetchone()["c"]
        print(f"  {table}: {count} rows")

    conn.close()
    print(f"\n  DB file: {DB_PATH}\n")


if __name__ == "__main__":
    verify()