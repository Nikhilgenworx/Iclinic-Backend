from control.models.intent import Intent


class ToolRegistry:
    def __init__(
        self,
        appointment_tool,
        availability_tool,
        doctor_tool,
        patient_tool,
        reschedule_tool,
        cancellation_tool,
        escalation_tool,
        active_bookings_tool=None,
    ):
        self.intent_tool_map = {
            Intent.BOOK_APPOINTMENT: [
                doctor_tool,
                availability_tool,
                patient_tool,
                appointment_tool,
            ],
            Intent.CHECK_AVAILABILITY: [
                doctor_tool,
                availability_tool,
            ],
            Intent.RESCHEDULE_APPOINTMENT: [
                active_bookings_tool,
                availability_tool,
                reschedule_tool,
            ],
            Intent.CANCEL_APPOINTMENT: [
                active_bookings_tool,
                cancellation_tool,
            ],
            Intent.ESCALATE: [
                escalation_tool,
            ],
            Intent.GENERAL: [],
        }

    def get_tools(self, intents):
        tools = {}

        for intent_score in intents:
            intent = intent_score.intent

            for tool in self.intent_tool_map.get(intent, []):
                if tool is None:
                    continue
                tools[tool.name] = tool

        return list(tools.values())

    def get_tool_map(self, intents):
        tool_map = {}

        for intent_score in intents:
            intent = intent_score.intent

            for tool in self.intent_tool_map.get(intent, []):
                if tool is None:
                    continue
                tool_map[tool.name] = tool

        return tool_map
