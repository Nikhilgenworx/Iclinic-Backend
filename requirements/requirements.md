# Requirements Document

## Introduction

This document specifies the requirements for the iClinic AI Front Desk Agent — a single LangGraph-based conversational AI that acts as a clinic front desk receptionist. The agent handles appointment booking, rescheduling, cancellation, doctor lookup, patient information collection, and escalation to human staff. It supports both chat (WebSocket/SSE) and voice (Twilio + Deepgram + ElevenLabs) channels using the same agent pipeline. The implementation uses LangChain + LangGraph with OpenRouter for model-agnostic LLM access, backed by existing FastAPI services and PostgreSQL.

## Glossary

- **Front_Desk_Agent**: The single LangGraph-based AI agent that processes patient conversations and invokes tools to fulfill clinic receptionist tasks.
- **Conversation_Gateway**: The entry point component that receives chat or voice requests and forwards them to the agent pipeline.
- **Conversation_State**: A Pydantic model representing the current state of a conversation session (session_id, active_intent, extracted_entities, current_step, escalation_required, messages).
- **OpenRouter_Client**: The HTTP client that communicates with the OpenRouter API for LLM inference, supporting model selection and retries.
- **LLM_Factory**: A factory component that returns a configured LangChain-compatible LLM instance based on application configuration.
- **Appointment_Tool**: A LangGraph tool that wraps AppointmentService for booking appointments.
- **Availability_Tool**: A LangGraph tool that wraps AppointmentService.get_available_slots for checking doctor availability.
- **Reschedule_Tool**: A LangGraph tool that wraps AppointmentService.reschedule_appointment.
- **Cancellation_Tool**: A LangGraph tool that wraps AppointmentService.cancel_appointment.
- **Doctor_Tool**: A LangGraph tool that wraps DoctorService for finding doctors by specialization or department.
- **Patient_Tool**: A LangGraph tool that wraps PatientService.get_or_create_patient for collecting and retrieving patient information.
- **Escalation_Tool**: A LangGraph tool that marks a conversation for human receptionist handoff.
- **Session_State**: The in-memory state managed by LangGraph's InMemorySaver, storing messages, entities, intent, and workflow step for the duration of a session.
- **System_Prompt**: The structured prompt containing persona instructions, tool-calling rules, scheduling rules, escalation rules, and safety rules for the Front_Desk_Agent.

## Requirements

### Requirement 1: Agent Graph Execution

**User Story:** As a patient, I want to interact with a single AI receptionist, so that I can complete clinic tasks through a natural conversation.

#### Acceptance Criteria

1. WHEN a message is received by the Conversation_Gateway, THE Front_Desk_Agent SHALL execute the LangGraph pipeline in the sequence: Load Session State → Agent Processing → Save Session State, and SHALL produce a response within 30 seconds of message receipt.
2. THE Front_Desk_Agent SHALL operate as a single-agent graph with no multi-agent routing, supervisor graphs, or nested sub-graphs.
3. THE Front_Desk_Agent SHALL select and invoke the tool corresponding to the extracted patient intent (as defined by the active_intent field values in Conversation_State) within a single graph invocation, where a graph invocation includes LLM inference and any resulting tool calls before returning a response.
4. WHEN the Front_Desk_Agent completes processing, THE Conversation_State SHALL persist all updated fields (messages, active_intent, extracted_entities, current_step, escalation_required) to Session_State.
5. IF the Front_Desk_Agent cannot extract a recognizable intent from the patient message, THEN THE Front_Desk_Agent SHALL respond with a clarification request asking the patient to rephrase, without invoking any tool.
6. IF Session_State loading fails for an existing session, THEN THE Front_Desk_Agent SHALL initialize a new Conversation_State with default values and inform the patient that prior context was unavailable.
7. IF Session_State saving fails after agent processing, THEN THE Front_Desk_Agent SHALL still deliver the generated response to the patient and log the persistence failure for operational monitoring.

### Requirement 2: Appointment Booking

**User Story:** As a patient, I want to book an appointment with a doctor, so that I can schedule a visit to the clinic.

#### Acceptance Criteria

1. WHEN a patient requests an appointment, THE Front_Desk_Agent SHALL use the Availability_Tool to verify open time slots before confirming any booking.
2. WHEN available slots are retrieved, THE Front_Desk_Agent SHALL present up to 5 available time slot options to the patient and request confirmation of the selected slot.
3. WHEN the patient confirms a slot, THE Front_Desk_Agent SHALL invoke the Appointment_Tool with the patient_id, doctor_id, appointment_type_id, start_datetime, booking_source, created_by_actor_type, and created_by_actor_id to create the appointment.
4. WHEN the Appointment_Tool successfully creates the appointment, THE Front_Desk_Agent SHALL confirm the booking details (doctor name, date, time, appointment type) to the patient.
5. IF the Appointment_Tool returns a conflict error, THEN THE Front_Desk_Agent SHALL inform the patient that the slot is no longer available and offer alternative slots by re-invoking the Availability_Tool.
6. IF the Availability_Tool returns no available slots for the requested date, THEN THE Front_Desk_Agent SHALL inform the patient that no slots are available and suggest checking an alternative date or a different doctor.
7. IF the Availability_Tool returns a service error, THEN THE Front_Desk_Agent SHALL inform the patient that availability cannot be checked at the moment and offer to retry or escalate to a human receptionist.

### Requirement 3: Appointment Rescheduling

**User Story:** As a patient, I want to reschedule my existing appointment, so that I can change to a more convenient time.

#### Acceptance Criteria

1. WHEN a patient requests to reschedule, THE Front_Desk_Agent SHALL identify the existing appointment by collecting the patient's phone number or appointment reference and querying for appointments with BOOKED status.
2. IF no appointment in BOOKED status is found for the provided patient information, THEN THE Front_Desk_Agent SHALL inform the patient that no reschedulable appointment was found and request corrected details.
3. WHEN the existing appointment is identified, THE Front_Desk_Agent SHALL use the Availability_Tool to retrieve available slots for the same doctor on the patient's requested date.
4. WHEN the patient selects a new time slot, THE Front_Desk_Agent SHALL confirm the rescheduling details (doctor name, original date and time, new date and time) with the patient before invoking the Reschedule_Tool.
5. WHEN the patient confirms the new time slot, THE Front_Desk_Agent SHALL invoke the Reschedule_Tool with the appointment_id and new_start_datetime.
6. WHEN the Reschedule_Tool returns a successful response, THE Front_Desk_Agent SHALL confirm the updated appointment details (doctor name, new date, and new time) to the patient.
7. IF the Reschedule_Tool returns a conflict error, THEN THE Front_Desk_Agent SHALL inform the patient that the selected slot is no longer available and offer alternative time slots using the Availability_Tool.
8. IF the Reschedule_Tool returns a validation error indicating the appointment is not in BOOKED status or the new time is outside working hours, THEN THE Front_Desk_Agent SHALL inform the patient of the specific reason the reschedule was rejected.

### Requirement 4: Appointment Cancellation

**User Story:** As a patient, I want to cancel my appointment, so that I can free up the time slot when I cannot attend.

#### Acceptance Criteria

1. WHEN a patient requests cancellation, THE Front_Desk_Agent SHALL identify the existing appointment using patient information (phone number or appointment details such as doctor name and date).
2. WHEN the appointment is identified, THE Front_Desk_Agent SHALL present the appointment details (doctor name, date, time, and appointment type) and ask the patient to confirm they want to cancel.
3. WHEN the patient confirms cancellation, THE Front_Desk_Agent SHALL invoke the Cancellation_Tool with the appointment_id.
4. WHEN the Cancellation_Tool completes successfully, THE Front_Desk_Agent SHALL confirm to the patient that the appointment (doctor name, date, and time) has been cancelled.
5. IF the Cancellation_Tool returns an error indicating the appointment is already cancelled or completed, THEN THE Front_Desk_Agent SHALL inform the patient of the current appointment status and take no further cancellation action.
6. IF no appointment is found matching the patient-provided information, THEN THE Front_Desk_Agent SHALL inform the patient that no matching appointment was found and request additional identifying details.
7. IF multiple upcoming appointments exist for the patient, THEN THE Front_Desk_Agent SHALL present the list of upcoming appointments with their details (doctor name, date, time) and ask the patient to specify which one to cancel.

### Requirement 5: Doctor Availability Check

**User Story:** As a patient, I want to check when a specific doctor is available, so that I can plan my visit.

#### Acceptance Criteria

1. WHEN a patient asks about a specific doctor's availability and has provided the doctor_id, requested date, and appointment_type_id, THE Front_Desk_Agent SHALL invoke the Availability_Tool with the doctor_id, requested date, and appointment_type_id.
2. IF the patient has not provided the requested date or appointment_type_id when asking about availability, THEN THE Front_Desk_Agent SHALL prompt the patient for the missing information before invoking the Availability_Tool.
3. WHEN available slots are returned, THE Front_Desk_Agent SHALL present up to 5 available time slots to the patient, each showing the start time and end time.
4. IF no slots are available for the requested date, THEN THE Front_Desk_Agent SHALL inform the patient that no slots are available on the requested date and ask whether the patient would like to check availability on a different date.
5. IF the Availability_Tool returns an error indicating the doctor_id is invalid or the doctor is inactive, THEN THE Front_Desk_Agent SHALL inform the patient that the specified doctor was not found or is not currently available and suggest using the Doctor_Tool to find an available doctor.
6. IF the Availability_Tool returns an unexpected error, THEN THE Front_Desk_Agent SHALL inform the patient that availability could not be retrieved due to a temporary issue and suggest trying again.

### Requirement 6: Doctor Search by Specialty

**User Story:** As a patient, I want to find doctors by their specialty, so that I can choose the right doctor for my condition.

#### Acceptance Criteria

1. WHEN a patient asks for a doctor by specialty (e.g., "cardiologist", "dermatologist"), THE Front_Desk_Agent SHALL invoke the Doctor_Tool to search by specialization using a case-insensitive partial match.
2. WHEN matching doctors are found, THE Front_Desk_Agent SHALL present up to 10 matching active doctors with their full names, specializations, and working hours (start time and end time).
3. IF no doctors match the requested specialty, THEN THE Front_Desk_Agent SHALL inform the patient and suggest available specialties by retrieving distinct specializations from all active doctors using get_all_active_doctors.
4. IF the Doctor_Tool returns an error or is unavailable, THEN THE Front_Desk_Agent SHALL inform the patient that the doctor search is temporarily unavailable and suggest trying again later or escalating to a human receptionist.

### Requirement 7: Patient Information Collection

**User Story:** As a clinic, I want the AI to collect patient details before booking, so that the system can identify or register patients.

#### Acceptance Criteria

1. WHEN a booking is requested and patient_id is not present in the Conversation_State extracted_entities, THE Front_Desk_Agent SHALL prompt the patient for their first name, last name, and phone number, collecting each field that has not yet been provided.
2. WHEN the patient has provided their first name, last name, and phone number, THE Front_Desk_Agent SHALL invoke the Patient_Tool with the collected first_name, last_name, and phone to retrieve an existing patient record or create a new one using get_or_create_patient.
3. WHEN the Patient_Tool returns a patient record, THE Front_Desk_Agent SHALL store the resolved patient_id in the Conversation_State extracted_entities for use in subsequent tool calls.
4. WHEN the Patient_Tool returns a patient record, THE Front_Desk_Agent SHALL present the patient's name from the returned record and ask the patient to confirm their identity before proceeding with booking.
5. IF the patient denies the identity confirmation, THEN THE Front_Desk_Agent SHALL discard the resolved patient_id from extracted_entities and ask the patient to re-provide their details.
6. IF the Patient_Tool returns an error or is unavailable, THEN THE Front_Desk_Agent SHALL inform the patient that it is unable to look up their record at this time and offer to escalate to a human receptionist.
7. THE Front_Desk_Agent SHALL validate that the phone number provided by the patient contains between 10 and 15 digits before invoking the Patient_Tool, and SHALL re-prompt the patient if the format is invalid.

### Requirement 8: Conversation Context Management

**User Story:** As a patient, I want the AI to remember what I said earlier in our conversation, so that I do not have to repeat information.

#### Acceptance Criteria

1. THE Front_Desk_Agent SHALL maintain the full message history (patient and AI messages) in the Conversation_State for the duration of the session, up to a maximum of 50 messages.
2. THE Front_Desk_Agent SHALL update the active_intent field in the Conversation_State on each turn where the patient expresses a new or different goal, setting it to one of the defined intent values.
3. THE Front_Desk_Agent SHALL store extracted_entities (patient_id, doctor_id, preferred_date, appointment_type) in the Conversation_State, and SHALL overwrite a previously stored entity value when the patient provides a new value for the same entity.
4. WHEN a session is loaded, THE Front_Desk_Agent SHALL restore the Conversation_State from Session_State using LangGraph InMemorySaver.
5. THE Front_Desk_Agent SHALL use the current_step field to track multi-turn workflow progress, setting it to one of: "collecting_info", "checking_availability", "confirming_action", "completed", or null when no workflow is active.
6. WHEN the patient changes their goal mid-conversation (e.g., switches from booking to cancellation), THE Front_Desk_Agent SHALL update the active_intent field to the new intent and retain all previously extracted_entities that remain relevant to the new intent.

### Requirement 9: Escalation to Human Receptionist

**User Story:** As a patient, I want to be transferred to a human receptionist when the AI cannot help me, so that my issue is resolved.

#### Acceptance Criteria

1. WHEN the patient's message contains a request to speak with a human, receptionist, real person, or staff member, THE Front_Desk_Agent SHALL invoke the Escalation_Tool.
2. WHEN the patient's message contains emergency-related phrases (such as chest pain, difficulty breathing, severe bleeding, loss of consciousness, or allergic reaction), THE Front_Desk_Agent SHALL immediately invoke the Escalation_Tool without asking further questions and without providing any medical advice or guidance.
3. WHEN the Front_Desk_Agent has asked 2 consecutive clarifying questions for the same patient request and the patient's intent remains unresolved, THE Front_Desk_Agent SHALL offer to escalate to a human receptionist.
4. WHEN the Escalation_Tool is invoked, THE Front_Desk_Agent SHALL set escalation_required to true in the Conversation_State, update the CONVERSATION status to ESCALATED, and inform the patient that a human receptionist will assist them shortly.
5. IF the patient declines the escalation offer presented in criterion 3, THEN THE Front_Desk_Agent SHALL acknowledge the patient's preference, ask the patient to rephrase their request, and continue the conversation without resetting the clarification attempt count.

### Requirement 10: OpenRouter LLM Integration

**User Story:** As a system administrator, I want to switch between LLM models without code changes, so that the clinic can optimize cost and performance.

#### Acceptance Criteria

1. THE OpenRouter_Client SHALL send inference requests to the OpenRouter API with the model identifier specified in the OPENROUTER_MODEL environment variable and a request timeout of the value specified in OPENROUTER_TIMEOUT (default: 30 seconds).
2. THE LLM_Factory SHALL return a LangChain-compatible chat model instance (using ChatOpenAI pointed at the OpenRouter base URL) configured with the model specified in OPENROUTER_MODEL.
3. WHEN the OpenRouter API returns an error response (HTTP 5xx or 429) or the request exceeds the configured timeout, THE OpenRouter_Client SHALL retry the request up to OPENROUTER_MAX_RETRIES attempts (default: 3) with exponential backoff starting at 1 second base delay.
4. IF all retry attempts fail, THEN THE OpenRouter_Client SHALL raise an exception that the Front_Desk_Agent handles by sending the patient a message indicating a temporary service issue and suggesting the patient try again shortly or request escalation to a human receptionist.
5. THE LLM_Factory SHALL support switching between models (GPT-4.1, Claude Sonnet, Gemini, DeepSeek) by changing the OPENROUTER_MODEL environment variable only, with no code modifications required.
6. IF the OPENROUTER_API_KEY or OPENROUTER_MODEL environment variable is missing or empty at application startup, THEN THE LLM_Factory SHALL raise a configuration error that prevents the application from starting and logs an error message indicating the missing variable.

### Requirement 11: Chat Channel Support

**User Story:** As a patient, I want to chat with the AI assistant from the clinic's web interface, so that I can manage my appointments online.

#### Acceptance Criteria

1. WHEN a chat message arrives via WebSocket or SSE, THE Conversation_Gateway SHALL extract the session_id and message content, validate that the message content does not exceed 2000 characters, and forward them to the Front_Desk_Agent pipeline.
2. WHEN the Front_Desk_Agent generates a response, THE Conversation_Gateway SHALL deliver the response text back to the patient through the same channel (WebSocket or SSE) within 30 seconds of receiving the original message.
3. IF no existing session is found for the provided session_id, THEN THE Conversation_Gateway SHALL create a new Conversation record with channel set to CHAT and status set to active, and store it in PostgreSQL before processing the message.
4. WHEN a chat message is sent by the patient or a response is generated by the Front_Desk_Agent, THE Conversation_Gateway SHALL persist the message to the CONVERSATION_MESSAGE table with the appropriate sender_type (PATIENT or AI) and message content before delivering the response.
5. IF the incoming chat message is missing the session_id, contains an empty message content, or exceeds the 2000-character limit, THEN THE Conversation_Gateway SHALL reject the message and return an error indication specifying the validation failure reason without forwarding to the Front_Desk_Agent pipeline.
6. IF the Front_Desk_Agent pipeline fails to produce a response within 30 seconds, THEN THE Conversation_Gateway SHALL return an error indication to the patient through the same channel informing that the request could not be processed.

### Requirement 12: Voice Channel Support

**User Story:** As a patient, I want to call the clinic and talk to the AI assistant by phone, so that I can manage appointments without using a computer.

#### Acceptance Criteria

1. WHEN a voice call is received via Twilio, THE Conversation_Gateway SHALL use Deepgram to convert speech audio to text before forwarding to the Front_Desk_Agent pipeline.
2. WHEN the Front_Desk_Agent generates a text response for a voice session, THE Conversation_Gateway SHALL use ElevenLabs to convert the text to speech audio.
3. WHEN the text-to-speech audio is synthesized, THE Conversation_Gateway SHALL return the audio to Twilio for playback to the patient and store the conversation in the CONVERSATION table with channel set to VOICE.
4. THE Front_Desk_Agent SHALL use the same agent pipeline and tools for voice sessions as for chat sessions, with no channel-specific logic in the agent layer.
5. IF Deepgram fails to produce a transcript from the patient's speech audio (service unavailable or unintelligible input), THEN THE Conversation_Gateway SHALL play a pre-recorded audio prompt asking the patient to repeat their message, and retry transcription up to 2 additional times before escalating to a human receptionist.
6. IF ElevenLabs fails to synthesize speech audio from the agent's text response, THEN THE Conversation_Gateway SHALL fall back to Twilio's built-in text-to-speech to deliver the response to the patient.

### Requirement 13: System Prompt and Safety Rules

**User Story:** As a clinic owner, I want the AI to behave professionally and safely, so that patients receive accurate information and are never put at risk.

#### Acceptance Criteria

1. THE System_Prompt SHALL instruct the Front_Desk_Agent to always verify availability through the Availability_Tool before confirming any booking to the patient.
2. THE System_Prompt SHALL instruct the Front_Desk_Agent to confirm appointment details (doctor, date, time, type) with the patient before invoking the Appointment_Tool.
3. THE System_Prompt SHALL instruct the Front_Desk_Agent to escalate immediately via the Escalation_Tool, without further conversation, when the patient's message indicates a medical emergency such as chest pain, difficulty breathing, severe bleeding, loss of consciousness, stroke symptoms, or allergic reaction.
4. THE System_Prompt SHALL instruct the Front_Desk_Agent to respond in no more than 3 sentences per turn for standard interactions, use polite greetings, address the patient by name when known, and avoid slang or emojis.
5. THE System_Prompt SHALL prohibit the Front_Desk_Agent from fabricating doctor schedules, inventing appointment slots, suggesting diagnoses, recommending treatments or medications, or providing any health-related recommendations.
6. THE System_Prompt SHALL instruct the Front_Desk_Agent to restrict responses to clinic receptionist tasks (appointment management, doctor lookup, patient info collection, escalation) and decline unrelated requests by informing the patient that the request is outside the scope of clinic scheduling services.
7. IF the Availability_Tool or any other tool is unreachable or returns an error, THEN THE System_Prompt SHALL instruct the Front_Desk_Agent to inform the patient that it cannot retrieve the requested information at this time and offer to escalate to a human receptionist, rather than fabricating or guessing any data.

### Requirement 14: Conversation State Model

**User Story:** As a developer, I want a well-defined state model, so that the agent can track multi-turn conversations reliably.

#### Acceptance Criteria

1. THE Conversation_State SHALL be defined as a Pydantic model containing the fields: session_id (str), active_intent (str or null), extracted_entities (dict with allowed keys: patient_id, doctor_id, appointment_id, appointment_type_id, preferred_date, preferred_time), current_step (str or null), escalation_required (bool), and messages (list of LangChain BaseMessage objects).
2. THE Conversation_State SHALL validate that session_id is a non-empty string with a maximum length of 128 characters.
3. WHEN a new session is created, THE Conversation_State SHALL default escalation_required to false, extracted_entities to an empty dictionary, active_intent to null, current_step to null, and messages to an empty list.
4. WHEN the Front_Desk_Agent updates the active_intent, THE Conversation_State SHALL accept only values from the set: "book_appointment", "reschedule_appointment", "cancel_appointment", "check_availability", "find_doctor", "collect_patient_info", "escalate", or null.
5. IF an invalid value is provided for active_intent or current_step, THEN THE Conversation_State SHALL reject the update by raising a validation error.
6. WHEN the Front_Desk_Agent updates the current_step, THE Conversation_State SHALL accept only values from the set: "collecting_info", "checking_availability", "confirming_booking", "confirming_cancellation", "confirming_reschedule", "escalating", or null.

### Requirement 15: Session Memory with InMemorySaver

**User Story:** As a developer, I want session memory handled by LangGraph's built-in checkpointer, so that conversation state persists across turns without external memory stores.

#### Acceptance Criteria

1. THE Front_Desk_Agent SHALL use LangGraph InMemorySaver as the sole session checkpointer for storing Conversation_State between turns.
2. WHEN a message is received with a session_id that has no existing checkpoint in InMemorySaver, THE InMemorySaver SHALL initialize a fresh Conversation_State with default values (escalation_required set to false, extracted_entities set to empty dictionary, messages set to empty list) and associate it with a thread_id equal to the session_id.
3. WHEN a session message is processed, THE InMemorySaver SHALL checkpoint the full graph state (including updated Conversation_State) after each graph node completes execution, using the session_id as the thread_id key.
4. THE Front_Desk_Agent SHALL NOT use Redis, MongoDB, or vector databases for session memory storage.
5. IF the InMemorySaver fails to load an existing checkpoint for a given session_id, THEN THE Front_Desk_Agent SHALL treat the session as new by initializing a fresh Conversation_State with default values and continuing processing.
6. THE InMemorySaver SHALL store state in-process memory only; all session state SHALL be lost when the server process restarts, and no persistence to disk or external store is required.
