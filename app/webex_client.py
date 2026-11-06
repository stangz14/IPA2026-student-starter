"""Part 4 student implementation."""

import os

import requests

WEBEX_API_BASE = 'https://webexapis.com/v1'

REQUEST_TIMEOUT = 10


class WebexClient:
    def __init__(self, token=None, session=None):
        token = token or os.environ.get("WEBEX_BOT_TOKEN")
        if not token:
            raise PermissionError("WEBEX_BOT_TOKEN is not set")
        self._token = token
        self.session = session if session is not None else requests.Session()

    @property
    def headers(self):
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }

    def _get(self, url):
        response = self.session.get(
            url, headers=self.headers, timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        return response

    def get_me(self):
        """Return the bot's own person record (used for its personId)."""
        return self._get(f"{WEBEX_API_BASE}/people/me").json()

    def get_message(self, message_id):
        return self._get(f"{WEBEX_API_BASE}/messages/{message_id}").json()

    def download_file(self, file_url):
        return self._get(file_url).content

    def send_message(self, room_id, text):
        response = self.session.post(
            f"{WEBEX_API_BASE}/messages",
            headers=self.headers,
            json={"roomId": room_id, "text": text},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()
