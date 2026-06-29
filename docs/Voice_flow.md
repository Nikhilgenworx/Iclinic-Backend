# Voice Flow

## Architecture

Patient ↔ Twilio ↔ Server (WebSocket media stream) ↔ ElevenLabs STT/TTS ↔ LangGraph Agent

## Detailed Flow

1. Patient calls the clinic's Twilio phone number

2. Twilio sends POST to `/voice/incoming` webhook

3. Server responds with TwiML — instructs Twilio to open a bidirectional WebSocket stream

4. Twilio connects to `/voice/stream` WebSocket — streams caller audio in real-time (μ-law 8kHz base64)

5. Server identifies patient by caller phone number (Twilio CallerID → patient DB lookup)

6. Agent sends personalized greeting via ElevenLabs TTS → Twilio → patient hears it

7. **Conversation loop:**
   - Server accumulates audio chunks, detects end-of-utterance via silence detection (1.5s pause)
   - Sends audio buffer to ElevenLabs STT → gets transcribed text
   - Feeds text to the same LangGraph FrontDeskGraph (identical to chat)
   - Agent processes intent, calls tools, generates response text
   - Response sent to ElevenLabs TTS (streaming) → audio chunks streamed back to Twilio
   - Patient hears the AI response

8. Call ends → Twilio sends "stop" event → DB session committed

## Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/voice/incoming` | POST | Twilio webhook — returns TwiML |
| `/voice/stream` | WebSocket | Bidirectional media stream |

## Key Design Decisions

- **Same agent graph** as chat — no duplication of logic
- **Patient auto-identification** from Twilio CallerID (phone number lookup)
- **Streaming TTS** for lower latency (audio plays as it generates)
- **Silence-based VAD** (Voice Activity Detection) at 1.5s threshold
- **booking_source = "AI_CALL"** for appointments booked via phone

## Configuration (.env)

```
TWILIO_ACCOUNT_SID=ACxxxxx
TWILIO_AUTH_TOKEN=xxxxx
TWILIO_PHONE_NUMBER=+1XXXXXXXXXX
ELEVENLABS_API_KEY=xxxxx
ELEVENLABS_VOICE_ID=21m00Tcm4TlvDq8ikWAM
ELEVENLABS_MODEL_ID=eleven_turbo_v2_5
SERVER_BASE_URL=https://your-domain.com  (or ngrok in dev)
```

## Setup (Development)

1. Install ngrok: `ngrok http 8000`
2. Copy ngrok URL to `SERVER_BASE_URL` in .env
3. In Twilio Console → Phone Number → Voice Configuration:
   - "A call comes in" → Webhook → `https://xxxx.ngrok-free.app/voice/incoming`
4. Call your Twilio number and talk to Maya
