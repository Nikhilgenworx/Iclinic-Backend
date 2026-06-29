"""
Voice configuration — Twilio and ElevenLabs settings.
"""

from pathlib import Path

from pydantic_settings import BaseSettings

_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"


class VoiceConfig(BaseSettings):
    """Configuration for Twilio voice + ElevenLabs STT/TTS."""

    # Twilio
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_phone_number: str = ""  # Your Twilio phone number (E.164 format)

    # ElevenLabs
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = "21m00Tcm4TlvDq8ikWAM"  # Default: Rachel
    elevenlabs_model_id: str = "eleven_turbo_v2_5"  # Fast model for real-time

    # Server base URL (for Twilio webhooks — use ngrok in dev)
    server_base_url: str = "http://localhost:8000"

    class Config:
        env_file = str(_ENV_FILE)
        extra = "ignore"


voice_config = VoiceConfig()
