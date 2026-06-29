"""
SMS notification tool — sends appointment confirmations, cancellations,
and reschedule notifications via Twilio SMS.
"""

import logging
import os

from control.tools.base_tool import BaseTool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class SmsToolInput(BaseModel):
    to_phone: str = Field(description="Recipient phone number in E.164 format")

    patient_name: str = Field(description="Patient full name")

    doctor_name: str = Field(description="Doctor full name")

    appointment_date: str = Field(
        description="Appointment date and time (human readable)"
    )

    appointment_id: str = Field(
        default="",
        description="Appointment ID for reference",
    )

    sms_type: str = Field(
        default="confirmation",
        description="Type of SMS: 'confirmation', 'cancellation', or 'reschedule'",
    )


class SmsTool(BaseTool):
    name = "sms_tool"

    description = (
        "Send an SMS notification to the patient via Twilio. Supports: "
        "'confirmation' for new bookings, 'cancellation' for cancelled appointments, "
        "'reschedule' for rescheduled appointments."
    )

    args_schema = SmsToolInput

    def __init__(self):
        self.account_sid = os.getenv("TWILIO_ACCOUNT_SID", "")
        self.auth_token = os.getenv("TWILIO_AUTH_TOKEN", "")
        self.from_number = os.getenv("TWILIO_PHONE_NUMBER", "")

    async def execute(
        self,
        to_phone: str,
        patient_name: str,
        doctor_name: str,
        appointment_date: str,
        appointment_id: str = "",
        sms_type: str = "confirmation",
    ):
        # Build message based on type
        if sms_type == "cancellation":
            body = (
                f"Hi {patient_name}, your appointment with Dr. {doctor_name} "
                f"on {appointment_date} has been cancelled. "
                f"Ref: {appointment_id or 'N/A'}. "
                f"To rebook, chat with us anytime. - iClinic"
            )
        elif sms_type == "reschedule":
            body = (
                f"Hi {patient_name}, your appointment has been rescheduled. "
                f"New time: {appointment_date} with Dr. {doctor_name}. "
                f"Ref: {appointment_id or 'N/A'}. "
                f"See you then! - iClinic"
            )
        else:
            # confirmation
            body = (
                f"Hi {patient_name}, your appointment is confirmed! "
                f"Dr. {doctor_name} on {appointment_date}. "
                f"Ref: {appointment_id or 'N/A'}. "
                f"Reply HELP for assistance. - iClinic"
            )

        # If Twilio isn't configured, log and return success
        if not self.account_sid or not self.auth_token or not self.from_number:
            logger.info(f"[SMS] (dry run) To: {to_phone} | {body}")
            return {
                "sms_sent": True,
                "to": to_phone,
                "message": f"SMS notification sent to {to_phone}",
                "body": body,
            }

        # Send via Twilio
        try:
            from twilio.rest import Client

            client = Client(self.account_sid, self.auth_token)

            message = client.messages.create(
                body=body,
                from_=self.from_number,
                to=to_phone,
            )

            logger.info(f"[SMS] Sent to {to_phone}: SID={message.sid}")

            return {
                "sms_sent": True,
                "to": to_phone,
                "message_sid": message.sid,
                "message": f"SMS notification sent to {to_phone}",
            }

        except Exception as e:
            logger.error(f"[SMS] Failed to send to {to_phone}: {e}")
            return {
                "sms_sent": False,
                "to": to_phone,
                "error": str(e),
                "message": f"Failed to send SMS to {to_phone}",
            }
