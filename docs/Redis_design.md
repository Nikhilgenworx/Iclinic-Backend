# Redis Design

## Purpose

Redis is used for:

- Session Management
- Conversation Context
- Agent State
- Voice Call State

---

## Key Structure

session:{user_id}

Example

{
  "intent":"book_appointment",
  "doctor":"Dr Kumar",
  "date":"2026-06-10",
  "step":"awaiting_time"
}

---

## Expiration

Sliding TTL

Duration:

1 Hour
