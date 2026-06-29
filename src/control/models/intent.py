from enum import Enum


class Intent(str, Enum):
    BOOK_APPOINTMENT = "book_appointment"

    CHECK_AVAILABILITY = "check_availability"

    RESCHEDULE_APPOINTMENT = "reschedule_appointment"

    CANCEL_APPOINTMENT = "cancel_appointment"

    ESCALATE = "escalate"

    GENERAL = "general"
