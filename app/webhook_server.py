"""Part 4 student implementation."""

import json

import logging

import os

from concurrent.futures import ThreadPoolExecutor

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from pathlib import Path

from tempfile import TemporaryDirectory

from app.integration import process_request

from app.webex_client import WEBEX_API_BASE, WebexClient

logger = logging.getLogger("ipa2026.webhook")

MAX_BODY_LENGTH = 1_000_000


class WebexEventHandler:
    def __init__(self, client, bot_person_id, processor=None):
        self.client = client
        self.bot_person_id = bot_person_id
        self.processor = processor or process_request

    def handle_event(self, event):
        if not isinstance(event, dict):
            return None
        if event.get("resource") != "messages" or event.get("event") != "created":
            return None

        data = event.get("data")
        if not isinstance(data, dict) or not data.get("id"):
            return None

        # Skip the bot's own messages before any API call when possible.
        if data.get("personId") == self.bot_person_id:
            return None

        message = self.client.get_message(data["id"])
        if not isinstance(message, dict):
            return None
        # Check the fetched author too, to prevent reply loops.
        if message.get("personId") == self.bot_person_id:
            return None

        room_id = message.get("roomId")
        if not room_id:
            return None

        mentioned_people = message.get("mentionedPeople") or []
        files = message.get("files") or []

        try:
            response = self._process(mentioned_people, files)
        except Exception:
            # Always reply: a silent bot fails every remaining Live case.
            logger.exception("Failed to process request")
            response = {"status": "error", "result": "backend_failed"}

        self.client.send_message(room_id, json.dumps(response))
        return response

    def _process(self, mentioned_people, files):
        if len(files) > 1:
            return {"status": "error", "result": "multiple_attachments"}

        if not files:
            return self.processor(mentioned_people, None, self.bot_person_id)

        content = self.client.download_file(files[0])
        # The directory (and the YAML inside) is removed even if processing fails.
        with TemporaryDirectory(prefix="ipa2026-") as tmp:
            path = Path(tmp) / "request.yaml"
            path.write_bytes(content)
            return self.processor(mentioned_people, path, self.bot_person_id)


def make_http_handler(submit_event):
    class WebhookHTTPHandler(BaseHTTPRequestHandler):
        def _send_json(self, status_code, body):
            payload = json.dumps(body).encode("utf-8")
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def _invalid_event(self):
            self._send_json(400, {"status": "error", "result": "invalid_event"})

        def _not_found(self):
            self._send_json(404, {"status": "error", "result": "not_found"})

        def do_GET(self):
            if self.path == "/health":
                self._send_json(200, {"status": "ok", "result": "healthy"})
            else:
                self._not_found()

        def do_POST(self):
            if self.path != "/webhook":
                self._not_found()
                return

            try:
                length = int(self.headers.get("Content-Length", ""))
            except ValueError:
                self._invalid_event()
                return
            if length < 1 or length > MAX_BODY_LENGTH:
                self._invalid_event()
                return

            try:
                event = json.loads(self.rfile.read(length))
            except (ValueError, UnicodeDecodeError):
                self._invalid_event()
                return
            if not isinstance(event, dict):
                self._invalid_event()
                return

            # Acknowledge right away; processing happens in the background.
            submit_event(event)
            self._send_json(200, {"status": "ok", "result": "accepted"})

        def log_message(self, format, *args):
            logger.info("%s - %s", self.address_string(), format % args)

    return WebhookHTTPHandler


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    host = os.environ.get("WEBHOOK_HOST", "0.0.0.0")
    port = int(os.environ.get("WEBHOOK_PORT", "8000"))

    client = WebexClient()
    bot_person_id = client.get_me()["id"]
    logger.info("Resolved bot personId from %s/people/me", WEBEX_API_BASE)

    handler = WebexEventHandler(client, bot_person_id)

    # A single worker processes requests one at a time so router changes never overlap.
    executor = ThreadPoolExecutor(max_workers=1)

    def run_event(event):
        try:
            handler.handle_event(event)
        except Exception:
            logger.exception("Failed to handle Webex event")

    def submit_event(event):
        executor.submit(run_event, event)

    server = ThreadingHTTPServer((host, port), make_http_handler(submit_event))
    logger.info("Webhook server listening on %s:%s", host, port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        executor.shutdown(wait=False)


if __name__ == "__main__":
    main()
