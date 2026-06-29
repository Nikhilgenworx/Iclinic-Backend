import os

from control.tools.base_tool import BaseTool
from pydantic import BaseModel, Field


class EscalationToolInput(BaseModel):
    reason: str = Field(description="Reason for escalation to human staff")

    conversation_id: str = Field(
        default="",
        description="UUID of the current conversation (if available)",
    )


class EscalationTool(BaseTool):
    name = "escalation_tool"

    description = (
        "Escalate the conversation to a human receptionist/staff member. "
        "Use when the patient confirms they want to speak with a human. "
        "Returns the staff phone number for call forwarding or display."
    )

    args_schema = EscalationToolInput

    def __init__(self, conversation_service=None):
        self.conversation_service = conversation_service
        self.escalation_phone = os.getenv("ESCALATION_PHONE", "")

    async def execute(
        self,
        reason: str,
        conversation_id: str = "",
    ):
        # Mark conversation for escalation if possible
        if self.conversation_service and conversation_id:
            from uuid import UUID

            try:
                conv_uuid = UUID(conversation_id)
                self.conversation_service.end_conversation(conv_uuid)
            except (ValueError, Exception):
                pass

        return {
            "escalated": True,
            "reason": reason,
            "forward_call": True,
            "escalation_phone": self.escalation_phone,
            "message": (
                "Escalation confirmed. In voice calls the system will automatically "
                "forward the call. In chat, tell the patient they can reach staff "
                f"directly at {self.escalation_phone}."
            ),
        }
