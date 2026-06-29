"""
Multi-node LangGraph for the iClinic AI Front Desk Agent.

Architecture:
    START → router_node → (conditional edge) → workflow_node → END

Workflow nodes:
    - book_appointment
    - check_availability
    - reschedule_appointment
    - cancel_appointment
    - general
    - escalate
"""

from control.models.intent import Intent
from control.nodes.router_node import RouterNode
from control.nodes.workflow_node import WorkflowNode
from control.prompts.system_prompt import (
    BOOK_APPOINTMENT_PROMPT,
    CANCEL_PROMPT,
    CHECK_AVAILABILITY_PROMPT,
    ESCALATION_PROMPT,
    GENERAL_PROMPT,
    RESCHEDULE_PROMPT,
)
from control.routing.llm_intent_router import LLMIntentRouter
from control.routing.tool_registry import ToolRegistry
from control.state.conversation_state import ConversationState
from langgraph.checkpoint.memory import MemorySaver

# ─── Checkpointer ───────────────────────────────────────────────────────────────
# LangGraph checkpointer for conversation message history persistence.
# Uses MemorySaver (in-process). Redis is used separately for session state
# and slot locking (see data/clients/redis_client.py).
_shared_memory = MemorySaver()


from langgraph.graph import END, START, StateGraph


def _route_by_intent(state) -> str:
    """Conditional edge function — routes to the correct workflow node."""
    intent = state.get("current_intent", "general")

    routing_map = {
        Intent.BOOK_APPOINTMENT.value: "book_appointment",
        Intent.CHECK_AVAILABILITY.value: "check_availability",
        Intent.RESCHEDULE_APPOINTMENT.value: "reschedule_appointment",
        Intent.CANCEL_APPOINTMENT.value: "cancel_appointment",
        Intent.ESCALATE.value: "escalate",
        Intent.GENERAL.value: "general",
    }

    destination = routing_map.get(intent, "general")
    print(f"\n[GRAPH] Routing to → {destination}")
    return destination


class FrontDeskGraph:
    def __init__(
        self,
        llm,
        intent_router=None,
        tool_registry: ToolRegistry = None,
        db=None,
        router_llm=None,
    ):
        # Create LLM-based intent router (uses fast router LLM if provided)
        llm_router = LLMIntentRouter(router_llm or llm)

        # Get tool groups from registry (using Intent enum directly)
        from control.models.intent_score import IntentScore

        def _get_tools_for_intent(intent: Intent) -> list:
            """Helper to get tools for a single intent."""
            scores = [IntentScore(intent=intent, score=1.0)]
            return tool_registry.get_tools(scores)

        # Build workflow nodes
        book_node = WorkflowNode(
            name="book_appointment",
            llm=llm,
            system_prompt=BOOK_APPOINTMENT_PROMPT,
            tools=_get_tools_for_intent(Intent.BOOK_APPOINTMENT),
        )

        availability_node = WorkflowNode(
            name="check_availability",
            llm=llm,
            system_prompt=CHECK_AVAILABILITY_PROMPT,
            tools=_get_tools_for_intent(Intent.CHECK_AVAILABILITY),
        )

        reschedule_node = WorkflowNode(
            name="reschedule_appointment",
            llm=llm,
            system_prompt=RESCHEDULE_PROMPT,
            tools=_get_tools_for_intent(Intent.RESCHEDULE_APPOINTMENT),
        )

        cancel_node = WorkflowNode(
            name="cancel_appointment",
            llm=llm,
            system_prompt=CANCEL_PROMPT,
            tools=_get_tools_for_intent(Intent.CANCEL_APPOINTMENT),
        )

        escalation_node = WorkflowNode(
            name="escalate",
            llm=llm,
            system_prompt=ESCALATION_PROMPT,
            tools=_get_tools_for_intent(Intent.ESCALATE),
        )

        general_node = WorkflowNode(
            name="general",
            llm=llm,
            system_prompt=GENERAL_PROMPT,
            tools=[],  # General conversation doesn't need tools
        )

        router_node = RouterNode(llm_router)

        # Build state graph
        builder = StateGraph(ConversationState)

        # Add nodes
        builder.add_node("router", router_node)
        builder.add_node("book_appointment", book_node)
        builder.add_node("check_availability", availability_node)
        builder.add_node("reschedule_appointment", reschedule_node)
        builder.add_node("cancel_appointment", cancel_node)
        builder.add_node("escalate", escalation_node)
        builder.add_node("general", general_node)

        # Edges
        builder.add_edge(START, "router")

        builder.add_conditional_edges(
            "router",
            _route_by_intent,
            {
                "book_appointment": "book_appointment",
                "check_availability": "check_availability",
                "reschedule_appointment": "reschedule_appointment",
                "cancel_appointment": "cancel_appointment",
                "escalate": "escalate",
                "general": "general",
            },
        )

        # All workflow nodes go to END
        builder.add_edge("book_appointment", END)
        builder.add_edge("check_availability", END)
        builder.add_edge("reschedule_appointment", END)
        builder.add_edge("cancel_appointment", END)
        builder.add_edge("escalate", END)
        builder.add_edge("general", END)

        # Compile with MemorySaver checkpointer (message history persistence)
        # Redis handles session state + slot locking separately
        self.graph = builder.compile(checkpointer=_shared_memory)

    def get_graph(self):
        return self.graph
