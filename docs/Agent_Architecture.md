# Agent Architecture

## Components

### Conversation Gateway

Responsible for:

- Receiving requests
- Loading session context
- Forwarding to LangGraph

---

### Session Manager

Redis stores:

- User context
- Conversation state
- Current workflow

---

### LangGraph Agent

Responsible for:

- Intent Detection
- Tool Selection
- State Management
- Response Generation

---

### Tools

#### Appointment Tool

Handles:

- Booking
- Rescheduling
- Cancellation

#### Doctor Tool

Handles:

- Doctor Lookup
- Availability Lookup

#### FAQ Tool

Handles clinic questions.
