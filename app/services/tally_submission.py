"""
Tally.so form submission service for appointment booking.

This service handles submission of appointment bookings to Tally.so forms
using their widget API endpoint.
"""

import httpx
import os
from loguru import logger
from typing import Optional, Dict, Any


class TallySubmissionService:
    """Service for submitting appointment bookings to Tally.so"""

    def __init__(self):
        """Initialize Tally.so submission service"""
        # Tally form details
        self.form_id = "eqe11o"
        self.workspace_id = "nGLP0e"

        # Tally API key (required for authenticated submissions)
        self.api_key = os.getenv("TALLY_API_KEY", "")

        # Use authenticated API endpoint
        self.submission_endpoint = f"https://api.tally.so/forms/{self.form_id}/responses"

        # Field UUIDs from Tally form inspection
        self.field_ids = {
            "first_name": "9f9ccc37-aaab-4aa4-8818-16cf23bd0201",
            "last_name": "38ac8997-ef4a-4dce-b160-5a7ff5b925e6",
            "email": "07a7e484-e5d8-46fb-b636-dec371b35115",
            "submitted_by": "40cbe6a4-0722-45c9-b9db-3f022fa505d2"
        }

        self._client: Optional[httpx.AsyncClient] = None

        if not self.api_key:
            logger.warning("⚠️ TALLY_API_KEY not set - appointment submissions will fail")

    async def _get_client(self) -> httpx.AsyncClient:
        """
        Get or create shared HTTP client with connection pooling.

        Returns:
            Configured httpx.AsyncClient instance
        """
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(10.0, connect=5.0),
                limits=httpx.Limits(max_connections=5, max_keepalive_connections=2),
                follow_redirects=True
            )
        return self._client

    async def submit_appointment(
        self,
        first_name: str,
        last_name: str,
        email: str
    ) -> Dict[str, Any]:
        """
        Submit appointment booking to Tally.so.

        Args:
            first_name: User's first name
            last_name: User's last name
            email: User's email address

        Returns:
            Dictionary with:
                - success (bool): Whether submission was successful
                - message (str): Success message (if success=True)
                - error (str): Error message (if success=False)

        Example:
            >>> service = TallySubmissionService()
            >>> result = await service.submit_appointment(
            ...     first_name="John",
            ...     last_name="Smith",
            ...     email="john.smith@example.com"
            ... )
            >>> print(result)
            {'success': True, 'message': "Great! I've scheduled your appointment..."}
        """
        try:
            if not self.api_key:
                logger.error("TALLY_API_KEY not configured")
                return {
                    "success": False,
                    "error": "Appointment system not configured. Please contact us at contact@nesterlabs.com"
                }

            client = await self._get_client()

            # Tally API v1 submission format
            # See: https://tally.so/help/api
            payload = {
                "fields": [
                    {"field_id": self.field_ids["first_name"], "value": first_name},
                    {"field_id": self.field_ids["last_name"], "value": last_name},
                    {"field_id": self.field_ids["email"], "value": email},
                    {"field_id": self.field_ids["submitted_by"], "value": "Nester AI"}
                ]
            }

            logger.info(
                f"Submitting appointment to Tally.so for {first_name} {last_name} ({email})"
            )
            logger.debug(f"Tally.so payload: {payload}")

            response = await client.post(
                self.submission_endpoint,
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "Authorization": f"Bearer {self.api_key}"
                }
            )

            response.raise_for_status()

            logger.info(
                f"Tally.so submission successful: {response.status_code} for {email}"
            )

            return {
                "success": True,
                "message": f"Great! I've scheduled your appointment. You'll receive a confirmation at {email}."
            }

        except httpx.TimeoutException:
            logger.error("Tally.so submission timeout")
            return {
                "success": False,
                "error": "I'm having trouble submitting the form right now. Could you try again in a moment?"
            }

        except httpx.HTTPStatusError as e:
            logger.error(
                f"Tally.so HTTP error: {e.response.status_code} - {e.response.text}"
            )
            return {
                "success": False,
                "error": "Something went wrong with the booking. Let me try that again."
            }

        except Exception as e:
            logger.error(f"Tally.so submission error: {type(e).__name__}: {e}")
            return {
                "success": False,
                "error": "I encountered an error while submitting. Could you please contact us directly at contact@nesterlabs.com?"
            }

    async def close(self):
        """Close HTTP client and clean up resources"""
        if self._client and not self._client.is_closed:
            logger.debug("Closing Tally.so HTTP client")
            await self._client.aclose()
