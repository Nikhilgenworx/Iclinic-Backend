"""
WorkflowNode — Generic workflow node that can be configured with:
- A system prompt
- A set of tools
- An LLM

Handles the tool-calling loop: LLM call → tool execution → final LLM call.
Also detects and handles models that output tool calls as text instead of
structured tool_calls (e.g. Groq's Llama 3.3).

State contract:
  Reads explicit fields from ConversationState (patient_id, selected_doctor_id, etc.)
  Writes back explicit fields + entities dict for tool outputs.
"""

import json
import re

from control.adapters.tool_adapter import ToolAdapter
from control.tools.base_tool import BaseTool
from langchain_core.messages import AIMessage, SystemMessage, ToolMessage


def _extract_text_tool_calls(content: str) -> list[dict] | None:
    """
    Detect tool calls embedded as text in the response.
    Patterns: <function=tool_name>{"arg": "val"}</function>
    Returns parsed tool calls or None if not found.
    """
    pattern = r"<function=(\w+)>\s*(\{.*?\})\s*</function>"
    matches = re.findall(pattern, content, re.DOTALL)

    if matches:
        calls = []
        for name, args_str in matches:
            try:
                args = json.loads(args_str)
                calls.append({"name": name, "args": args, "id": f"text_call_{name}"})
            except json.JSONDecodeError:
                continue
        return calls if calls else None

    return None


class WorkflowNode:
    def __init__(
        self,
        name: str,
        llm,
        system_prompt: str,
        tools: list[BaseTool],
    ):
        self.name = name
        self.llm = llm
        self.system_prompt = system_prompt
        self.tools = tools
        self.tool_map = {tool.name: tool for tool in tools}

    def _build_state_context(self, state: dict) -> str:
        """Build a structured summary from explicit state fields."""
        lines = []

        # ─── Patient identity ───────────────────────────────────────────────────
        patient_id = state.get("patient_id")
        patient_name = state.get("patient_name")
        patient_phone = state.get("patient_phone")
        patient_email = state.get("patient_email")
        patient_preloaded = state.get("patient_preloaded", False)

        if patient_name:
            if patient_id:
                lines.append(
                    f"- PATIENT IDENTIFIED: {patient_name} (patient_id: {patient_id})"
                )
            else:
                lines.append(f"- Patient name: {patient_name}")
        if patient_phone:
            lines.append(f"- Phone: {patient_phone}")
        if patient_email:
            lines.append(f"- Email: {patient_email}")

        # ─── Current selections ─────────────────────────────────────────────────
        if state.get("selected_specialty"):
            lines.append(f"- Specialty: {state['selected_specialty']}")

        if state.get("selected_doctor_name"):
            lines.append(
                f"- Selected doctor: {state['selected_doctor_name']} "
                f"(doctor_id: {state.get('selected_doctor_id', '?')})"
            )

        if state.get("selected_appointment_type"):
            lines.append(
                f"- Appointment type: {state['selected_appointment_type']} "
                f"(ID: {state.get('selected_appointment_type_id', '?')})"
            )

        if state.get("selected_slot"):
            lines.append(f"- Selected time slot: {state['selected_slot']}")

        if state.get("selected_appointment_id"):
            lines.append(
                f"- Appointment being modified: {state['selected_appointment_id']}"
            )

        # ─── Pending action (what we last asked the patient) ────────────────────
        pending = state.get("pending_action")
        if pending:
            pending_map = {
                "confirm_booking": "WAITING FOR: Patient to confirm the booking (yes/no)",
                "confirm_cancel": "WAITING FOR: Patient to confirm cancellation (yes/no)",
                "confirm_reschedule": "WAITING FOR: Patient to confirm reschedule (yes/no)",
                "confirm_appointment_type": "WAITING FOR: Patient to confirm the appointment type",
                "choose_slot": "WAITING FOR: Patient to pick a time slot from the list",
                "choose_doctor": "WAITING FOR: Patient to pick a doctor from the list",
                "choose_appointment": "WAITING FOR: Patient to pick which appointment to modify",
            }
            lines.append(f"\n{pending_map.get(pending, f'WAITING FOR: {pending}')}")

        # ─── Available options (for "the first one" disambiguation) ─────────────
        available_doctors = state.get("available_doctors")
        if available_doctors and isinstance(available_doctors, list):
            lines.append("")
            lines.append("DOCTORS SHOWN TO PATIENT (numbered):")
            for i, d in enumerate(available_doctors[:6], 1):
                lines.append(
                    f"  {i}. {d.get('full_name', d.get('doctor_name', '?'))} "
                    f"(doctor_id: {d.get('doctor_id', '?')})"
                )

        available_slots = state.get("available_slots")
        if available_slots and isinstance(available_slots, list):
            lines.append("")
            lines.append(
                "SLOTS SHOWN TO PATIENT (this is a SAMPLE — more slots may exist. If patient asks for a different time, call availability_tool again):"
            )
            for i, s in enumerate(available_slots[:8], 1):
                doctor_label = (
                    f" with {s['doctor_name']}" if s.get("doctor_name") else ""
                )
                lines.append(
                    f"  {i}. {s.get('start', '?')}{doctor_label} "
                    f"(start_iso: {s.get('start_iso', '?')})"
                )

        active_bookings = state.get("active_bookings")
        if active_bookings and isinstance(active_bookings, list):
            lines.append("")
            lines.append(
                "PATIENT'S ACTIVE BOOKINGS (numbered — use appointment_id for cancel/reschedule):"
            )
            for i, b in enumerate(active_bookings, 1):
                lines.append(
                    f"  {i}. {b.get('start_datetime', '?')} with {b.get('doctor_name', '?')} "
                    f"(appointment_id: {b.get('appointment_id', '?')})"
                )

        # ─── Booking history ────────────────────────────────────────────────────
        booking_history = state.get("booking_history")
        if booking_history and isinstance(booking_history, list):
            active_from_history = [
                h for h in booking_history if h.get("status") == "BOOKED"
            ]
            past_bookings = [h for h in booking_history if h.get("status") != "BOOKED"]

            if active_from_history:
                lines.append("")
                lines.append("UPCOMING APPOINTMENTS (awareness only):")
                for h in active_from_history:
                    lines.append(
                        f"  - {h.get('date', '?')} with {h.get('doctor_name', '?')} "
                        f"({h.get('specialty', '?')})"
                    )

            if past_bookings:
                lines.append("")
                lines.append("PAST VISITS (use for doctor recommendations):")
                for h in past_bookings:
                    lines.append(
                        f"  - {h.get('date', '?')} with {h.get('doctor_name', '?')} "
                        f"({h.get('specialty', '?')}) — {h.get('status', '?')}"
                    )

        if not lines:
            return ""

        # ─── Instructions about missing info ────────────────────────────────────
        if patient_id and patient_preloaded:
            lines.append("")
            lines.append(
                "PATIENT IS PRE-IDENTIFIED (logged in user). "
                "Do NOT ask for name, phone, or email. Use the patient_id above directly."
            )
        elif not patient_id:
            missing = []
            if not patient_name:
                missing.append("patient's full name")
            if not patient_phone:
                missing.append("patient's phone number")
            if not patient_email:
                missing.append("patient's email address")
            if missing:
                lines.append("")
                lines.append(
                    "STILL NEEDED FROM PATIENT (ASK, do NOT invent): "
                    + ", ".join(missing)
                )

        return "\n".join(lines)

    def _extract_state_updates(self, tool_name: str, result: dict) -> dict:
        """
        Map tool outputs to explicit state fields.
        Returns a dict of state fields to update.
        """
        updates = {}

        if tool_name == "patient_tool" and isinstance(result, dict):
            if result.get("patient_id"):
                updates["patient_id"] = result["patient_id"]
                first = result.get("first_name", "")
                last = result.get("last_name", "")
                if first:
                    updates["patient_name"] = f"{first} {last}".strip()
                if result.get("phone"):
                    updates["patient_phone"] = result["phone"]
                if result.get("email"):
                    updates["patient_email"] = result["email"]

        elif tool_name == "doctor_tool" and isinstance(result, dict):
            doctors = result.get("doctors")
            if doctors and isinstance(doctors, list):
                updates["available_doctors"] = doctors
                if result.get("specialty"):
                    updates["selected_specialty"] = result["specialty"]
                updates["pending_action"] = "choose_doctor"

        elif tool_name == "availability_tool" and isinstance(result, dict):
            # Flatten all doctors' slots into a single list with doctor info
            doctors_data = result.get("doctors", [])
            flat_slots = []
            for doc in doctors_data:
                for slot in doc.get("available_slots", []):
                    flat_slots.append(
                        {
                            **slot,
                            "doctor_id": doc.get("doctor_id"),
                            "doctor_name": doc.get("doctor_name"),
                        }
                    )
            if flat_slots:
                updates["available_slots"] = flat_slots
                updates["pending_action"] = "choose_slot"
            if result.get("appointment_type_id"):
                updates["selected_appointment_type_id"] = result["appointment_type_id"]
            if result.get("appointment_type"):
                updates["selected_appointment_type"] = result["appointment_type"]
            if result.get("specialty"):
                updates["selected_specialty"] = result["specialty"]

        elif tool_name == "appointment_tool" and isinstance(result, dict):
            if result.get("success"):
                updates["selected_appointment_id"] = result.get("appointment_id")
                updates["pending_action"] = None
                updates["available_slots"] = None

        elif tool_name == "active_bookings_tool" and isinstance(result, dict):
            bookings = result.get("active_bookings")
            if bookings and isinstance(bookings, list):
                updates["active_bookings"] = bookings
                updates["pending_action"] = "choose_appointment"

        elif tool_name == "reschedule_tool" and isinstance(result, dict):
            if result.get("success"):
                updates["pending_action"] = None
                updates["selected_slot"] = None

        elif tool_name == "cancellation_tool" and isinstance(result, dict):
            if result.get("success"):
                updates["pending_action"] = None
                updates["selected_appointment_id"] = None

        elif tool_name == "escalation_tool":
            updates["pending_action"] = None

        return updates

    async def __call__(self, state):
        messages = state["messages"]
        entities = state.get("entities", {})

        # Adapt tools for LangChain
        llm_tools = [ToolAdapter.adapt(tool) for tool in self.tools]
        llm = self.llm.bind_tools(llm_tools) if llm_tools else self.llm

        # Build context from explicit state fields
        state_context = self._build_state_context(state)

        # Inject today's date so the LLM doesn't hallucinate dates
        from datetime import datetime as _dt

        today_str = _dt.now().strftime("%Y-%m-%d")
        today_readable = _dt.now().strftime("%A, %B %d, %Y")

        # Build message list with system prompt + state context
        prompt_with_context = self.system_prompt
        prompt_with_context += f"\n\nTODAY'S DATE: {today_readable} ({today_str})"

        if state_context:
            prompt_with_context += (
                "\n\nCURRENT CONTEXT (what you already know — do NOT re-ask):\n"
                f"{state_context}\n\n"
                "RULES:\n"
                "- Read conversation history. If patient already answered, don't re-ask.\n"
                "- If patient is PRE-IDENTIFIED, don't ask for name/phone/email.\n"
                "- If WAITING FOR a response, interpret their reply in that context.\n"
                "- Use UUIDs from context when calling tools.\n"
                "- Emergency symptoms → tell them to call 911, then escalate."
            )

        llm_messages = [SystemMessage(content=prompt_with_context)]
        # Only pass last 6 messages to LLM to reduce token count
        llm_messages.extend(messages[-6:])

        # First LLM call
        try:
            response = await llm.ainvoke(llm_messages)
        except Exception as e:
            error_str = str(e)
            if "failed_generation" in error_str or "tool_use_failed" in error_str:
                import json as _json

                try:
                    raw_json = (
                        error_str.split(" - ", 1)[1] if " - " in error_str else "{}"
                    )
                    err_data = _json.loads(raw_json)
                    failed_gen = err_data.get("error", {}).get("failed_generation", "")
                    text_calls = _extract_text_tool_calls(failed_gen)
                    if text_calls:
                        from langchain_core.messages import AIMessage as _AIM

                        response = _AIM(content=failed_gen)
                        response.tool_calls = []
                    else:
                        print(
                            f"[{self.name.upper()}] tool_use_failed but no parseable calls, returning fallback"
                        )
                        return {
                            "response": "I'm sorry, I encountered an issue processing that. Could you try again?"
                        }
                except (ValueError, KeyError, _json.JSONDecodeError):
                    print(
                        f"[{self.name.upper()}] Error parsing failed_generation, returning fallback"
                    )
                    return {
                        "response": "I'm sorry, I encountered an issue processing that. Could you try again?"
                    }
            else:
                raise

        # Check for text-based tool calls
        text_tool_calls = None
        if not response.tool_calls and response.content:
            text_tool_calls = _extract_text_tool_calls(response.content)
            if text_tool_calls:
                print(
                    f"\n[{self.name.upper()}] Detected text-based tool calls: {[c['name'] for c in text_tool_calls]}"
                )

        tool_calls = response.tool_calls or text_tool_calls

        print(f"\n[{self.name.upper()}] LLM response (tool_calls: {bool(tool_calls)})")

        # No tool calls — return direct response
        if not tool_calls:
            content = response.content or ""
            content = re.sub(
                r"<function=\w+>\s*\{[^}]*\}\s*</function>", "", content
            ).strip()
            # Also strip <think>...</think> tags from reasoning models
            content = re.sub(
                r"<think>.*?</think>", "", content, flags=re.DOTALL
            ).strip()

            if not content:
                # LLM returned empty — provide a helpful fallback
                content = "Sure, I can help with that. Could you give me a bit more detail on what you need?"

            return {
                "messages": [AIMessage(content=content)],
                "response": content,
            }

        # Execute tool calls and collect state updates
        llm_messages.append(response)
        updated_entities = dict(entities)
        state_updates: dict = {}

        for tool_call in tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]

            print(f"[{self.name.upper()}] Tool call: {tool_name}({tool_args})")

            tool = self.tool_map.get(tool_name)

            if tool is None:
                result = {
                    "error": f"Tool '{tool_name}' not available in this workflow."
                }
            else:
                try:
                    result = await tool.execute(**tool_args)
                except Exception as e:
                    result = {"error": str(e)}

            print(f"[{self.name.upper()}] Tool result: {result}")

            # Update legacy entities
            if isinstance(result, dict):
                updated_entities.update(result)

            # Extract explicit state updates
            if isinstance(result, dict):
                tool_state_updates = self._extract_state_updates(tool_name, result)
                state_updates.update(tool_state_updates)

            tool_call_id = tool_call.get("id", f"call_{tool_name}")
            llm_messages.append(
                ToolMessage(
                    content=str(result),
                    tool_call_id=tool_call_id,
                )
            )

        # Final LLM call with tool results
        try:
            final_response = await llm.ainvoke(llm_messages)
        except Exception:
            try:
                final_response = await self.llm.ainvoke(llm_messages)
            except Exception:
                final_response = None

        print(f"[{self.name.upper()}] Final response generated")

        # Handle chained tool calls
        max_chains = 2
        chain_count = 0
        while (
            final_response
            and getattr(final_response, "tool_calls", None)
            and chain_count < max_chains
        ):
            chain_count += 1
            llm_messages.append(final_response)
            for tc in final_response.tool_calls:
                t_name = tc["name"]
                t_args = tc["args"]
                print(
                    f"[{self.name.upper()}] Chained tool call #{chain_count}: {t_name}({t_args})"
                )
                t = self.tool_map.get(t_name)
                if t:
                    try:
                        r = await t.execute(**t_args)
                    except Exception as ex:
                        r = {"error": str(ex)}
                    if isinstance(r, dict):
                        updated_entities.update(r)
                        tool_updates = self._extract_state_updates(t_name, r)
                        state_updates.update(tool_updates)
                    print(f"[{self.name.upper()}] Chained result: {r}")
                    llm_messages.append(
                        ToolMessage(
                            content=str(r), tool_call_id=tc.get("id", f"chain_{t_name}")
                        )
                    )
                else:
                    llm_messages.append(
                        ToolMessage(
                            content=str({"error": f"Tool '{t_name}' not found"}),
                            tool_call_id=tc.get("id", f"chain_{t_name}"),
                        )
                    )

            try:
                final_response = await llm.ainvoke(llm_messages)
            except Exception:
                final_response = None
                break

        # Extract text content
        if (
            final_response
            and getattr(final_response, "content", None)
            and final_response.content.strip()
        ):
            response_content = final_response.content
        else:
            if updated_entities.get("status") == "CANCELLED":
                response_content = "Done, your appointment has been cancelled. I've sent you a confirmation message."
            elif updated_entities.get("escalated"):
                response_content = (
                    "I've flagged this for our team. Someone will be with you shortly."
                )
            elif updated_entities.get("success") is True:
                # Determine what kind of success based on workflow name
                if self.name == "cancel_appointment":
                    response_content = "Done, your appointment has been cancelled."
                elif self.name == "reschedule_appointment":
                    response_content = "All set! Your appointment has been rescheduled. I've sent you a confirmation."
                else:
                    response_content = "All done! Your appointment has been confirmed. I've sent you a confirmation message."
            elif updated_entities.get("sms_sent"):
                response_content = (
                    "All set! I've sent you a confirmation with the details."
                )
            else:
                # No specific completion detected — generate a contextual fallback
                # based on what tools were called
                last_tool_names = (
                    [tc["name"] for tc in tool_calls] if tool_calls else []
                )
                if "doctor_tool" in last_tool_names:
                    doctors = updated_entities.get("doctors", [])
                    if doctors:
                        names = [d.get("full_name", "Unknown") for d in doctors[:3]]
                        response_content = f"I found {', '.join(names)}. When would you like to come in — morning, afternoon, or evening?"
                    else:
                        response_content = "I couldn't find doctors in that specialty. Could you tell me more about what you need?"
                elif "availability_tool" in last_tool_names:
                    response_content = (
                        "I've checked the schedule. What time works best for you?"
                    )
                elif "active_bookings_tool" in last_tool_names:
                    response_content = "I've pulled up your appointments. Which one are you referring to?"
                else:
                    response_content = "How would you like to proceed?"

        # Strip any function tags from final response
        response_content = re.sub(
            r"<function=\w+>\s*\{[^}]*\}\s*</function>", "", response_content
        ).strip()

        # Build final return with explicit state fields + legacy entities
        output = {
            "messages": [AIMessage(content=response_content)],
            "response": response_content,
            "entities": updated_entities,
        }
        # Merge explicit state field updates
        output.update(state_updates)

        return output
