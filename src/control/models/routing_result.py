from control.models.intent_score import IntentScore
from pydantic import BaseModel


class RoutingResult(BaseModel):
    intents: list[IntentScore]
