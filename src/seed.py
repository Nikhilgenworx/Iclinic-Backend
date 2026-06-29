"""
Seed script for iClinic Backend database.

Run from Backend/src:
    python seed.py

Tables seeded (in dependency order):
1. departments (no FK)
2. staff (no FK)
3. appointment_types (no FK)
4. doctors (FK → departments)
5. patients (no FK)

All PKs are UUIDs generated here. All created_at use NOW().
Unique constraints respected: name in departments/appointment_types, email/auth_user_id in doctors/staff, phone in patients.
"""

import os
import sys
import uuid
from pathlib import Path

# Resolve paths
_this_dir = Path(__file__).resolve().parent
os.chdir(_this_dir.parent)  # cd to Backend/ so .env resolves
sys.path.insert(0, str(_this_dir))

from config.settings import settings
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

DATABASE_URL = (
    f"postgresql+psycopg2://"
    f"{settings.POSTGRES_USER}:"
    f"{settings.POSTGRES_PASSWORD}@"
    f"{settings.POSTGRES_HOST}:"
    f"{settings.POSTGRES_PORT}/"
    f"{settings.POSTGRES_DB}"
)

engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)


def seed():
    db = Session()

    try:
        # ============================================================
        # Check if already seeded
        # ============================================================
        result = db.execute(text("SELECT COUNT(*) FROM departments"))
        if result.scalar() > 0:
            print("Database already seeded. Skipping.")
            print("(To re-seed, truncate the tables first.)")
            return

        # ============================================================
        # 1. DEPARTMENTS (no FK dependencies)
        # Columns: department_id (UUID PK), name (unique), description, created_at
        # ============================================================
        print("Seeding departments...")
        dept_ids = {}
        departments = [
            ("Cardiology", "Heart and cardiovascular system"),
            ("Neurology", "Brain, spine, and nervous system"),
            ("Orthopedics", "Bones, joints, and muscles"),
            ("Dermatology", "Skin, hair, and nails"),
            ("General Medicine", "General health and primary care"),
        ]
        for name, desc in departments:
            did = str(uuid.uuid4())
            dept_ids[name] = did
            db.execute(
                text(
                    """INSERT INTO departments (department_id, name, description, created_at)
                   VALUES (:id, :name, :desc, NOW())"""
                ),
                {"id": did, "name": name, "desc": desc},
            )

        # ============================================================
        # 2. STAFF (no FK dependencies)
        # Columns: staff_id (UUID PK), auth_user_id (unique), full_name, email (unique), phone, active, created_at
        # ============================================================
        print("Seeding staff...")
        staff_data = [
            ("auth-staff-001", "Maya Receptionist", "maya@iclinic.com", "9000000001"),
        ]
        for auth_id, name, email, phone in staff_data:
            sid = str(uuid.uuid4())
            db.execute(
                text(
                    """INSERT INTO staff (staff_id, auth_user_id, full_name, email, phone, active, created_at)
                   VALUES (:id, :auth_id, :name, :email, :phone, true, NOW())"""
                ),
                {
                    "id": sid,
                    "auth_id": auth_id,
                    "name": name,
                    "email": email,
                    "phone": phone,
                },
            )

        # ============================================================
        # 3. APPOINTMENT_TYPES (no FK dependencies)
        # Columns: appointment_type_id (UUID PK), name (unique), default_duration_minutes, is_emergency, active, created_at
        # ============================================================
        print("Seeding appointment types...")
        apt_types = [
            ("General Consultation", 15, False),
            ("Follow Up", 10, False),
            ("Specialist Consultation", 30, False),
            ("New Patient", 45, False),
        ]
        for name, duration, is_emergency in apt_types:
            atid = str(uuid.uuid4())
            db.execute(
                text(
                    """INSERT INTO appointment_types (appointment_type_id, name, default_duration_minutes, is_emergency, active, created_at)
                   VALUES (:id, :name, :duration, :is_emergency, true, NOW())"""
                ),
                {
                    "id": atid,
                    "name": name,
                    "duration": duration,
                    "is_emergency": is_emergency,
                },
            )

        # ============================================================
        # 4. DOCTORS (FK → departments.department_id)
        # Columns: doctor_id (UUID PK), department_id (FK), auth_user_id (unique),
        #          full_name, specialization, email (unique), phone,
        #          working_start_time (TIME), working_end_time (TIME), active, created_at
        # ============================================================
        print("Seeding doctors...")
        doctors = [
            (
                dept_ids["Cardiology"],
                "auth-doc-001",
                "Dr. Sarah Khan",
                "Cardiology",
                "sarah.khan@iclinic.com",
                "9876543210",
                "09:00",
                "17:00",
            ),
            (
                dept_ids["Cardiology"],
                "auth-doc-002",
                "Dr. James Patel",
                "Cardiology",
                "james.patel@iclinic.com",
                "9876543211",
                "09:00",
                "17:00",
            ),
            (
                dept_ids["Neurology"],
                "auth-doc-003",
                "Dr. Priya Sharma",
                "Neurology",
                "priya.sharma@iclinic.com",
                "9876543212",
                "09:00",
                "17:00",
            ),
            (
                dept_ids["Orthopedics"],
                "auth-doc-004",
                "Dr. Raj Mehta",
                "Orthopedics",
                "raj.mehta@iclinic.com",
                "9876543213",
                "10:00",
                "18:00",
            ),
            (
                dept_ids["Dermatology"],
                "auth-doc-005",
                "Dr. Ananya Verma",
                "Dermatology",
                "ananya.verma@iclinic.com",
                "9876543214",
                "09:00",
                "16:00",
            ),
            (
                dept_ids["General Medicine"],
                "auth-doc-006",
                "Dr. Vikram Singh",
                "General Medicine",
                "vikram.singh@iclinic.com",
                "9876543215",
                "08:00",
                "17:00",
            ),
        ]
        for dept_id, auth_id, name, spec, email, phone, start_time, end_time in doctors:
            doc_id = str(uuid.uuid4())
            db.execute(
                text(
                    """INSERT INTO doctors (doctor_id, department_id, auth_user_id, full_name, specialization, email, phone, working_start_time, working_end_time, active, created_at)
                   VALUES (:doc_id, :dept_id, :auth_id, :name, :spec, :email, :phone, CAST(:start_time AS time), CAST(:end_time AS time), true, NOW())"""
                ),
                {
                    "doc_id": doc_id,
                    "dept_id": dept_id,
                    "auth_id": auth_id,
                    "name": name,
                    "spec": spec,
                    "email": email,
                    "phone": phone,
                    "start_time": start_time,
                    "end_time": end_time,
                },
            )

        # ============================================================
        # 5. PATIENTS (no FK dependencies)
        # Columns: patient_id (UUID PK), first_name, last_name, phone (unique), email (unique nullable), dob, gender, created_at
        # ============================================================
        print("Seeding sample patients...")
        patients = [
            ("Nikhil", "Varma", "9123456789", "nikhil.varma@gmail.com", None, "Male"),
            ("Priya", "Nair", "9123456790", "priya.nair@gmail.com", None, "Female"),
        ]
        for first, last, phone, email, dob, gender in patients:
            pid = str(uuid.uuid4())
            db.execute(
                text(
                    """INSERT INTO patients (patient_id, first_name, last_name, phone, email, dob, gender, created_at)
                   VALUES (:id, :first, :last, :phone, :email, :dob, :gender, NOW())"""
                ),
                {
                    "id": pid,
                    "first": first,
                    "last": last,
                    "phone": phone,
                    "email": email,
                    "dob": dob,
                    "gender": gender,
                },
            )

        # ============================================================
        # COMMIT
        # ============================================================
        db.commit()
        print("\nSeed complete!")
        print(f"  - {len(departments)} departments")
        print(f"  - {len(staff_data)} staff")
        print(f"  - {len(apt_types)} appointment types")
        print(f"  - {len(doctors)} doctors")
        print(f"  - {len(patients)} patients")

    except Exception as e:
        db.rollback()
        print(f"\nSeed failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
