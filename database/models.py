# ============================================================
# database/models.py  —  SQL table definitions
# ============================================================

# Stores all registered patients
CREATE_PATIENTS_TABLE = """
CREATE TABLE IF NOT EXISTS patients (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    phone       TEXT    UNIQUE NOT NULL,
    email       TEXT,
    language    TEXT    DEFAULT 'en',
    created_at  TEXT    DEFAULT (datetime('now'))
);
"""

# Stores all doctors and their specialty
CREATE_DOCTORS_TABLE = """
CREATE TABLE IF NOT EXISTS doctors (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    specialty   TEXT    NOT NULL,
    hospital    TEXT    NOT NULL,
    created_at  TEXT    DEFAULT (datetime('now'))
);
"""

# Each row = one available time slot for a doctor
# is_booked: 0 = free, 1 = taken
CREATE_DOCTOR_SCHEDULE_TABLE = """
CREATE TABLE IF NOT EXISTS doctor_schedule (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    doctor_id   INTEGER NOT NULL,
    date        TEXT    NOT NULL,
    time_slot   TEXT    NOT NULL,
    is_booked   INTEGER DEFAULT 0,
    FOREIGN KEY (doctor_id) REFERENCES doctors(id)
);
"""

# Stores confirmed appointments
# status: 'confirmed' | 'cancelled' | 'completed' | 'rescheduled'
CREATE_APPOINTMENTS_TABLE = """
CREATE TABLE IF NOT EXISTS appointments (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id      INTEGER NOT NULL,
    doctor_id       INTEGER NOT NULL,
    schedule_id     INTEGER NOT NULL,
    date            TEXT    NOT NULL,
    time_slot       TEXT    NOT NULL,
    status          TEXT    DEFAULT 'confirmed',
    notes           TEXT,
    created_at      TEXT    DEFAULT (datetime('now')),
    updated_at      TEXT    DEFAULT (datetime('now')),
    FOREIGN KEY (patient_id)  REFERENCES patients(id),
    FOREIGN KEY (doctor_id)   REFERENCES doctors(id),
    FOREIGN KEY (schedule_id) REFERENCES doctor_schedule(id)
);
"""

# Stores all conversation turns for persistent memory
CREATE_CONVERSATION_HISTORY_TABLE = """
CREATE TABLE IF NOT EXISTS conversation_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id  INTEGER NOT NULL,
    session_id  TEXT    NOT NULL,
    role        TEXT    NOT NULL,
    message     TEXT    NOT NULL,
    language    TEXT    DEFAULT 'en',
    created_at  TEXT    DEFAULT (datetime('now')),
    FOREIGN KEY (patient_id) REFERENCES patients(id)
);
"""

# All table creation statements in order (respects FK deps)
ALL_TABLES = [
    CREATE_PATIENTS_TABLE,
    CREATE_DOCTORS_TABLE,
    CREATE_DOCTOR_SCHEDULE_TABLE,
    CREATE_APPOINTMENTS_TABLE,
    CREATE_CONVERSATION_HISTORY_TABLE,
]