"""
Interactive Chat with iClinic AI Front Desk Agent — LIVE DB MODE.

This connects to your real PostgreSQL database via the service layer.
Make sure your DB is running and has data (doctors, appointment types, etc.)

Run from Backend/src:
    python -m control.chat_live

Type your messages and chat with the bot.
Type 'quit', 'exit', or 'q' to end the session.
Type 'reset' to start a new conversation.
"""

import asyncio
import os
import sys
from pathlib import Path

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Add Backend/ to path so "src." imports resolve correctly
_backend_dir = Path(__file__).resolve().parents[2]  # Backend/
sys.path.insert(0, str(_backend_dir))
os.chdir(_backend_dir)  # .env resolves from Backend/

from control.factories.llm_factory import LLMFactory
from control.factories.tool_factory import ToolFactory
from control.graphs.frontdesk_graph import FrontDeskGraph
from langchain_core.messages import HumanMessage
from src.data.clients.postgres_client import get_db_session


def build_graph_with_db(db):
    """Build the multi-node graph with REAL DB-backed tools."""
    registry = ToolFactory.create_registry(db)
    llm = LLMFactory.get_llm()
    router_llm = LLMFactory.get_router_llm()

    graph = FrontDeskGraph(
        llm=llm,
        tool_registry=registry,
        router_llm=router_llm,
    ).get_graph()

    return graph


async def chat():
    """Interactive chat loop with real DB.

    Uses get_db_session() for proper transaction management:
    - Session is opened once for the entire chat
    - commit() happens when the session context exits cleanly
    - rollback() happens if any exception propagates
    """
    print("Connecting to database...")

    with get_db_session() as db:
        print("Creating tool registry (real services)...")
        graph = build_graph_with_db(db)

        session_id = "live-session-1"
        config = {"configurable": {"thread_id": session_id}}
        first_message = True

        print("\n" + "=" * 60)
        print("  iClinic AI Front Desk Assistant (LIVE DB)")
        print("  Type your message to chat. Commands:")
        print("    'quit' / 'exit' / 'q'  — end session")
        print("    'reset'                 — start fresh conversation")
        print("=" * 60 + "\n")

        while True:
            try:
                user_input = input("You: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n\nGoodbye!")
                break

            if not user_input:
                continue

            if user_input.lower() in ("quit", "exit", "q"):
                print("\nGoodbye! Have a great day.")
                break

            if user_input.lower() == "reset":
                session_id = f"live-session-{id(object())}"
                config = {"configurable": {"thread_id": session_id}}
                first_message = True
                print("\n[Session reset. Starting fresh conversation.]\n")
                continue

            # Build invocation payload
            invoke_input = {
                "session_id": session_id,
                "messages": [HumanMessage(content=user_input)],
            }

            if first_message:
                invoke_input.update(
                    {
                        "active_intents": [],
                        "entities": {},
                        "current_intent": None,
                        "response": None,
                        "patient_preloaded": False,
                        # Explicit state fields
                        "patient_id": None,
                        "patient_name": None,
                        "patient_phone": None,
                        "patient_email": None,
                        "selected_doctor_id": None,
                        "selected_doctor_name": None,
                        "selected_specialty": None,
                        "selected_slot": None,
                        "selected_appointment_type_id": None,
                        "selected_appointment_type": None,
                        "selected_appointment_id": None,
                        "pending_action": None,
                        "available_slots": None,
                        "available_doctors": None,
                        "active_bookings": None,
                        "booking_history": None,
                    }
                )
                first_message = False

            # Invoke the graph
            try:
                result = await graph.ainvoke(invoke_input, config=config)
                response = result.get("response", "I'm sorry, I couldn't process that.")
                print(f"\nAssistant: {response}\n")
            except Exception as e:
                print(f"\n[Error: {e}]\n")

    # When `with get_db_session()` exits cleanly (no unhandled exception),
    # it auto-commits. If an exception propagated, it auto-rollbacks.
    print("[DB session closed — transaction committed.]")


def main():
    asyncio.run(chat())


if __name__ == "__main__":
    main()
