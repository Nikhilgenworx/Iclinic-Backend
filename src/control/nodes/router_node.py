"""
Router Node — classifies intent using LLM and sets current_intent in state.
"""

from control.models.intent import Intent


class RouterNode:
    def __init__(self, intent_router):
        """
        Args:
            intent_router: An object with a .route(text) method that returns
                           a RoutingResult (works with LLMIntentRouter or IntentRouter).
        """
        self.intent_router = intent_router

    async def __call__(self, state):
        messages = state["messages"]
        previous_intent = state.get("current_intent", None)

        # Get latest human message
        latest_message = ""
        for msg in reversed(messages):
            if hasattr(msg, "content") and msg.content:
                if msg.type == "human":
                    latest_message = msg.content
                    break

        if not latest_message:
            return {"current_intent": Intent.GENERAL.value}

        # Build compact conversation context (last 4 messages — less tokens = faster)
        recent_messages = []
        for msg in messages[-4:]:
            if hasattr(msg, "content") and msg.content:
                role = "User" if msg.type == "human" else "Assistant"
                # Truncate long assistant messages to save tokens
                content = msg.content[:200] if role == "Assistant" else msg.content
                recent_messages.append(f"{role}: {content}")

        conversation_text = "\n".join(recent_messages)

        # Append previous intent as hint for the router
        if previous_intent:
            conversation_text += f"\n[Previous intent: {previous_intent}]"

        # Route using LLM (async)
        routing_result = await self.intent_router.route(conversation_text)

        if routing_result.intents:
            top_intent = routing_result.intents[0].intent
            print(
                f"[ROUTER] Intent → {top_intent.value} (score: {routing_result.intents[0].score:.3f})"
            )
            return {"current_intent": top_intent.value}

        print("[ROUTER] No intent matched → general")
        return {"current_intent": Intent.GENERAL.value}
