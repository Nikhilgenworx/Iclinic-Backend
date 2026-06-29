from datetime import datetime, timedelta

from control.tools.base_tool import BaseTool
from pydantic import BaseModel, Field


class AvailabilityToolInput(BaseModel):
    specialty: str = Field(
        description="Medical specialty such as cardiology or dermatology"
    )

    date: str = Field(
        description="Appointment date. Use YYYY-MM-DD format, or 'today' or 'tomorrow'"
    )

    appointment_type: str = Field(
        default="",
        description=(
            "Type of appointment if patient specified one. "
            "Options: General Consultation (15 min), Follow Up (10 min), "
            "Specialist Consultation (30 min), New Patient (45 min). "
            "Leave empty to default to General Consultation."
        ),
    )

    time_preference: str = Field(
        default="",
        description=(
            "Patient's preferred time of day. "
            "Options: 'morning' (before 12 PM), 'afternoon' (12 PM - 3 PM), "
            "'evening' (3 PM onwards), or a specific time like '10:00 AM'. "
            "Leave empty to return a balanced sample across the day."
        ),
    )


class AvailabilityTool(BaseTool):
    name = "availability_tool"

    description = (
        "Check doctor availability by specialty and date. "
        "Returns a list of pre-computed available time slots. "
        "Only offer slots from this list — never invent times."
    )

    args_schema = AvailabilityToolInput

    def __init__(self, doctor_service, appointment_service):
        self.doctor_service = doctor_service
        self.appointment_service = appointment_service

    def _compute_free_slots(
        self, doctor, target_date: datetime, duration: timedelta
    ) -> list[dict]:
        """
        Compute concrete available slots for a doctor on a given date.

        Algorithm:
            1. Build day boundaries from doctor's working hours.
            2. Gather all blocked intervals (unavailabilities + existing appointments).
            3. Walk from day_start to day_end in `duration`-sized steps.
            4. A slot is free only if it does NOT overlap any blocked interval.
        """
        from src.data.repositories.appointment_repository import AppointmentRepository
        from src.data.repositories.doctor_unavailability_repository import (
            DoctorUnavailabilityRepository,
        )

        db = self.doctor_service.db

        day_start = target_date.replace(
            hour=doctor.working_start_time.hour,
            minute=doctor.working_start_time.minute,
            second=0,
            microsecond=0,
        )
        day_end = target_date.replace(
            hour=doctor.working_end_time.hour,
            minute=doctor.working_end_time.minute,
            second=0,
            microsecond=0,
        )

        # Gather blocked intervals from unavailabilities
        unavailability_repo = DoctorUnavailabilityRepository(db)
        unavailabilities = unavailability_repo.get_by_doctor_and_date_range(
            doctor.doctor_id, day_start, day_end
        )

        # Gather blocked intervals from existing appointments
        appointment_repo = AppointmentRepository(db)
        existing_appointments = appointment_repo.get_by_doctor_and_date_range(
            doctor.doctor_id, day_start, day_end
        )

        # Merge all blocked intervals into a sorted list of (start, end) tuples
        blocked: list[tuple[datetime, datetime]] = []
        for u in unavailabilities:
            blocked.append((u.start_datetime, u.end_datetime))
        for a in existing_appointments:
            blocked.append((a.start_datetime, a.end_datetime))
        blocked.sort(key=lambda x: x[0])

        # Walk through the day and collect free slots
        free_slots: list[dict] = []
        current = day_start

        # Skip slots in the past (if checking today)
        now = datetime.now()
        if target_date.date() == now.date() and current < now:
            # Round up to the next slot boundary
            minutes_past = (now - current).total_seconds() / 60
            steps_to_skip = int(minutes_past // duration.total_seconds() * 60) + 1
            current = current + duration * steps_to_skip
            # Align to slot boundaries
            if current < now:
                current = current + duration

        while current + duration <= day_end:
            slot_end = current + duration

            # Check if this slot overlaps any blocked interval
            is_blocked = False
            for block_start, block_end in blocked:
                # Overlap exists if slot_start < block_end AND slot_end > block_start
                if current < block_end and slot_end > block_start:
                    is_blocked = True
                    break

            if not is_blocked:
                free_slots.append(
                    {
                        "start": current.strftime("%I:%M %p"),
                        "end": slot_end.strftime("%I:%M %p"),
                        "start_iso": current.strftime("%Y-%m-%dT%H:%M:%S"),
                    }
                )

            current += duration

        return free_slots

    def _exclude_redis_locked(self, doctor_id: str, slots: list[dict]) -> list[dict]:
        """
        Remove slots that are locked in Redis (pending bookings not yet committed to DB).
        This ensures other sessions don't see slots that are mid-booking.
        """
        try:
            from src.data.clients.redis_client import SessionStore

            locked_isos = SessionStore.get_locked_slots_for_doctor(doctor_id)
            if not locked_isos:
                return slots

            locked_set = set(locked_isos)
            return [s for s in slots if s.get("start_iso") not in locked_set]
        except Exception:
            # Redis unavailable — return slots as-is (graceful degradation)
            return slots

    def _filter_by_preference(self, slots: list[dict], preference: str) -> list[dict]:
        """
        Filter slots by patient's time preference.

        - 'morning': before 12 PM
        - 'afternoon': 12 PM to 3 PM
        - 'evening': 3 PM onwards
        - specific time (e.g. '10:00'): closest slots around that time
        - empty: return a balanced sample (2 morning, 2 afternoon, 1 evening)
        """
        if not slots:
            return slots

        pref = preference.strip().lower()

        if not pref:
            # No preference — return a balanced sample across the day
            morning = [s for s in slots if self._slot_hour(s) < 12]
            afternoon = [s for s in slots if 12 <= self._slot_hour(s) < 15]
            evening = [s for s in slots if self._slot_hour(s) >= 15]

            sample = []
            sample.extend(morning[:2])
            sample.extend(afternoon[:2])
            sample.extend(evening[:1])

            # If we got less than 3, fill from whatever's available
            if len(sample) < 3:
                for s in slots:
                    if s not in sample:
                        sample.append(s)
                    if len(sample) >= 5:
                        break

            return sample

        if pref == "morning":
            filtered = [s for s in slots if self._slot_hour(s) < 12]
            return self._spread_sample(filtered, 5)

        if pref == "afternoon":
            filtered = [s for s in slots if 12 <= self._slot_hour(s) < 15]
            return self._spread_sample(filtered, 5)

        if pref in ("evening", "late afternoon"):
            filtered = [s for s in slots if self._slot_hour(s) >= 15]
            return self._spread_sample(filtered, 5)

        # Try to parse as a specific time (e.g. "10:00 AM", "2 PM", "14:00")
        target_hour = self._parse_time_preference(pref)
        if target_hour is not None:
            # Return slots within ±1.5 hours of the target, sorted by closeness
            nearby = [s for s in slots if abs(self._slot_hour(s) - target_hour) <= 1.5]
            # Sort by closeness to target time
            nearby.sort(key=lambda s: abs(self._slot_hour(s) - target_hour))
            return nearby[:5]

        # Unrecognized preference — return balanced sample
        return slots[:5]

    def _spread_sample(self, slots: list[dict], count: int) -> list[dict]:
        """
        Return `count` slots evenly spread across the list.
        This ensures the patient sees the full range (e.g. 8AM, 9AM, 10AM, 11AM)
        instead of just the first 5 consecutive slots (8:00, 8:15, 8:30...).
        """
        if len(slots) <= count:
            return slots

        # Pick evenly spaced indices
        step = len(slots) / count
        indices = [int(i * step) for i in range(count)]
        return [slots[i] for i in indices]

    def _slot_hour(self, slot: dict) -> float:
        """Extract hour as a float from a slot's start_iso."""
        iso = slot.get("start_iso", "")
        try:
            dt = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%S")
            return dt.hour + dt.minute / 60.0
        except ValueError:
            return 12.0  # Fallback to noon

    def _parse_time_preference(self, pref: str) -> float | None:
        """Try to parse a time string into an hour float."""
        import re

        # Match patterns like "10:00 AM", "2 PM", "14:00", "10am"
        # Pattern: optional digits:digits, optional AM/PM
        match = re.match(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", pref, re.IGNORECASE)
        if not match:
            return None

        hour = int(match.group(1))
        minutes = int(match.group(2)) if match.group(2) else 0
        ampm = match.group(3)

        if ampm:
            if ampm.lower() == "pm" and hour != 12:
                hour += 12
            elif ampm.lower() == "am" and hour == 12:
                hour = 0

        return hour + minutes / 60.0

    async def execute(
        self,
        specialty: str,
        date: str,
        appointment_type: str = "",
        time_preference: str = "",
    ):
        # Handle relative date strings
        today = datetime.now()
        date_lower = date.strip().lower()

        if date_lower in ("today", "now"):
            target_date = today
        elif date_lower == "tomorrow":
            target_date = today + timedelta(days=1)
        else:
            # Try multiple date formats
            target_date = None
            for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%m/%d/%Y"):
                try:
                    target_date = datetime.strptime(date, fmt)
                    break
                except ValueError:
                    continue

            if target_date is None:
                return {
                    "error": (
                        f"Invalid date format: {date}. "
                        "Use YYYY-MM-DD, DD-MM-YYYY, or words like 'today'/'tomorrow'."
                    )
                }

        # Find doctors by specialty
        doctors = self.doctor_service.get_doctors_by_specialization(specialty)

        if not doctors:
            return {
                "specialty": specialty,
                "date": date,
                "available_slots": [],
                "message": f"No active doctors found for specialty: {specialty}",
            }

        # Find matching appointment type
        from src.data.repositories.appointment_type_repository import (
            AppointmentTypeRepository,
        )

        apt_type_repo = AppointmentTypeRepository(self.doctor_service.db)

        apt_type = None
        if appointment_type:
            apt_type = apt_type_repo.get_by_name(appointment_type)

        if not apt_type:
            apt_type = apt_type_repo.get_by_name("General Consultation")

        if not apt_type:
            active_types = apt_type_repo.get_all_active()
            if not active_types:
                return {"error": "No appointment types configured in the system."}
            apt_type = active_types[0]

        duration = timedelta(minutes=apt_type.default_duration_minutes)

        # Compute pre-calculated available slots per doctor
        doctors_availability = []

        for doctor in doctors:
            free_slots = self._compute_free_slots(doctor, target_date, duration)

            # Also exclude slots locked in Redis (pending bookings not yet committed)
            free_slots = self._exclude_redis_locked(str(doctor.doctor_id), free_slots)

            # Filter by time preference
            filtered_slots = self._filter_by_preference(free_slots, time_preference)

            # Limit to max 5 slots per doctor to avoid overwhelming the LLM
            limited_slots = filtered_slots[:5]

            doctors_availability.append(
                {
                    "doctor_id": str(doctor.doctor_id),
                    "doctor_name": doctor.full_name,
                    "available_slots": limited_slots,
                    "total_available": len(filtered_slots),
                }
            )

        return {
            "specialty": specialty,
            "date": target_date.strftime("%A, %B %d, %Y"),
            "date_iso": target_date.strftime("%Y-%m-%d"),
            "appointment_type": apt_type.name,
            "appointment_type_id": str(apt_type.appointment_type_id),
            "duration_minutes": apt_type.default_duration_minutes,
            "doctors": doctors_availability,
        }
