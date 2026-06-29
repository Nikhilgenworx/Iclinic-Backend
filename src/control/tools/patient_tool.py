from control.tools.base_tool import BaseTool
from pydantic import BaseModel, Field


class PatientLookupInput(BaseModel):
    phone: str = Field(description="Patient phone number to look up")

    first_name: str = Field(
        default="",
        description="Patient first name (used when creating a new patient)",
    )

    last_name: str = Field(
        default="",
        description="Patient last name (used when creating a new patient)",
    )

    email: str = Field(
        default="",
        description="Patient email (optional)",
    )


class PatientTool(BaseTool):
    name = "patient_tool"

    description = (
        "Look up a patient by phone number, or create a new patient record "
        "if not found. Returns patient information including patient_id."
    )

    args_schema = PatientLookupInput

    def __init__(self, patient_service):
        self.patient_service = patient_service

    async def execute(
        self,
        phone: str,
        first_name: str = "",
        last_name: str = "",
        email: str = "",
    ):
        # Try to find existing patient by phone
        patient = self.patient_service.get_patient_by_phone(phone)

        if patient:
            return {
                "found": True,
                "patient_id": str(patient.patient_id),
                "first_name": patient.first_name,
                "last_name": patient.last_name,
                "phone": patient.phone,
                "email": patient.email or "",
            }

        # If name provided, create new patient
        if first_name and last_name:
            try:
                patient = self.patient_service.create_patient(
                    first_name=first_name,
                    last_name=last_name,
                    phone=phone,
                    email=email or None,
                )

                return {
                    "found": False,
                    "created": True,
                    "patient_id": str(patient.patient_id),
                    "first_name": patient.first_name,
                    "last_name": patient.last_name,
                    "phone": patient.phone,
                    "email": patient.email or "",
                }

            except Exception as e:
                return {
                    "found": False,
                    "created": False,
                    "error": str(e.detail) if hasattr(e, "detail") else str(e),
                }

        # Patient not found and no name provided to create
        return {
            "found": False,
            "created": False,
            "message": "Patient not found. Please provide first_name and last_name to register.",
        }
