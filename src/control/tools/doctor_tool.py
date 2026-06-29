from control.tools.base_tool import BaseTool
from pydantic import BaseModel, Field


class DoctorToolInput(BaseModel):
    specialty: str = Field(
        description="Medical specialty to search for (e.g. cardiology, neurology, orthopedics)"
    )


class DoctorTool(BaseTool):
    name = "doctor_tool"

    description = (
        "Find doctors by specialty. Returns a list of active doctors "
        "matching the given specialization."
    )

    args_schema = DoctorToolInput

    def __init__(self, doctor_service):
        self.doctor_service = doctor_service

    async def execute(self, specialty: str):
        doctors = self.doctor_service.get_doctors_by_specialization(specialty)

        if not doctors:
            # Get available specializations so the LLM can suggest alternatives
            all_doctors = self.doctor_service.get_all_active_doctors()
            available_specializations = sorted(
                set(d.specialization for d in all_doctors)
            )

            return {
                "specialty": specialty,
                "doctors": [],
                "message": f"No active doctors found for specialty: {specialty}",
                "available_specializations": available_specializations,
                "hint": "Try 'general medicine' as a fallback, or ask the patient if one of the available specializations works.",
            }

        doctor_list = []
        for doctor in doctors:
            doctor_list.append(
                {
                    "doctor_id": str(doctor.doctor_id),
                    "full_name": doctor.full_name,
                    "specialization": doctor.specialization,
                    "department_id": str(doctor.department_id),
                    "working_hours": f"{doctor.working_start_time.strftime('%I:%M %p')} - {doctor.working_end_time.strftime('%I:%M %p')}",
                }
            )

        return {
            "specialty": specialty,
            "doctors": doctor_list,
        }
