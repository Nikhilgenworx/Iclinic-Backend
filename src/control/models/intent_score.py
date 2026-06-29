from control.models.intent import Intent
from pydantic import BaseModel


class IntentScore(BaseModel):
    intent: Intent

    score: float
