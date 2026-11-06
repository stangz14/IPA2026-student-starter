"""Part 4 student implementation."""

import yaml

from app.core import validate_request

from app.dispatcher import dispatch_request

from app.request_handler import validate_webex_envelope


def _load_yaml(path):
    """Load the attachment once. Return (data, error_response)."""
    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except (yaml.YAMLError, UnicodeDecodeError):
        return None, {"status": "error", "result": "invalid_yaml"}

    if not isinstance(data, dict):
        return None, {"status": "error", "result": "invalid_yaml"}
    return data, None


def process_request(mentioned_people, attachment_path, bot_person_id):
    """Validate the Webex envelope and YAML, then dispatch accepted requests."""
    error = validate_webex_envelope(
        mentioned_people, attachment_path, bot_person_id
    )
    if error is not None:
        return error

    data, error = _load_yaml(attachment_path)
    if error is not None:
        return error

    validation = validate_request(data)
    if validation.get("status") != "ok":
        return validation

    return dispatch_request(data)
