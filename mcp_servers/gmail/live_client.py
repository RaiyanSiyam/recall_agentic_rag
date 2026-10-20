"""Live API client for Gmail (used when DATA_MODE=live)."""
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


class GmailLiveClient:
    """Client for real Gmail API via OAuth2 refresh token or service credentials."""

    def __init__(self):
        self.client_id = os.getenv("GMAIL_CLIENT_ID", "")
        self.client_secret = os.getenv("GMAIL_CLIENT_SECRET", "")
        self.refresh_token = os.getenv("GMAIL_REFRESH_TOKEN", "")
        self._service = None

    def _get_service(self):
        if self._service is None:
            try:
                from google.oauth2.credentials import Credentials
                from googleapiclient.discovery import build

                creds = Credentials(
                    None,
                    refresh_token=self.refresh_token,
                    token_uri="https://oauth2.googleapis.com/token",
                    client_id=self.client_id,
                    client_secret=self.client_secret,
                    scopes=["https://www.googleapis.com/auth/gmail.readonly"],
                )
                self._service = build("gmail", "v1", credentials=creds)
            except Exception as e:
                logger.error(f"Failed to initialize live Gmail service: {e}")
                raise RuntimeError(
                    f"Live Gmail integration is not configured properly: {e}. "
                    "Set GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET, and GMAIL_REFRESH_TOKEN."
                )
        return self._service

    def search_emails(self, query: str, max_results: int = 5) -> list[dict[str, Any]]:
        service = self._get_service()
        response = (
            service.users()
            .messages()
            .list(userId="me", q=query, maxResults=max_results)
            .execute()
        )
        messages = response.get("messages", [])
        results = []
        for msg in messages:
            detail = (
                service.users()
                .messages()
                .get(userId="me", id=msg["id"], format="metadata")
                .execute()
            )
            headers = {h["name"].lower(): h["value"] for h in detail.get("payload", {}).get("headers", [])}
            results.append(
                {
                    "id": msg["id"],
                    "thread_id": msg.get("threadId", ""),
                    "from": headers.get("from", "Unknown"),
                    "subject": headers.get("subject", "No Subject"),
                    "date": headers.get("date", ""),
                    "snippet": detail.get("snippet", ""),
                }
            )
        return results

    def get_email(self, message_id: str) -> dict[str, Any] | None:
        service = self._get_service()
        detail = (
            service.users()
            .messages()
            .get(userId="me", id=message_id, format="full")
            .execute()
        )
        headers = {h["name"].lower(): h["value"] for h in detail.get("payload", {}).get("headers", [])}
        return {
            "id": message_id,
            "thread_id": detail.get("threadId", ""),
            "from": headers.get("from", "Unknown"),
            "to": [headers.get("to", "")],
            "subject": headers.get("subject", "No Subject"),
            "date": headers.get("date", ""),
            "snippet": detail.get("snippet", ""),
            "body": detail.get("snippet", ""),  # simplified extraction
        }
