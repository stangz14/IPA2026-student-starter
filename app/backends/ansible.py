import json
import os
import subprocess
from pathlib import Path

from app.backends.common import (
    error,
    error_from_exception,
    ok,
    split_cidr,
)


ANSIBLE_DIR = Path(__file__).resolve().parents[2] / "ansible"
PLAYBOOK = ANSIBLE_DIR / "apply_interface.yml"
INVENTORY = ANSIBLE_DIR / "inventory.ini"
TIMEOUT = 120

AUTH_FAILED_MARKERS = (
    "authentication failed",
    "auth failed",
    "permission denied",
)
CONNECTION_FAILED_MARKERS = (
    "unreachable",
    "timed out",
    "timeout",
    "connection refused",
    "no route to host",
    "unable to connect",
    "could not connect",
)


def _default_run_playbook(variables):
    """Run the apply playbook; credentials come from ROUTER_USER/ROUTER_PASS."""

    env = dict(os.environ)
    env["ANSIBLE_HOST_KEY_CHECKING"] = "False"

    try:
        completed = subprocess.run(
            [
                "ansible-playbook",
                "-i", str(INVENTORY),
                str(PLAYBOOK),
                "-e", json.dumps(variables),
            ],
            capture_output=True,
            text=True,
            env=env,
            timeout=TIMEOUT,
        )
    except subprocess.TimeoutExpired as exc:
        raise TimeoutError("ansible-playbook timed out") from exc

    if completed.returncode == 0:
        return

    output = (completed.stdout + completed.stderr).lower()

    if any(marker in output for marker in AUTH_FAILED_MARKERS):
        raise PermissionError("ansible authentication failed")

    if any(marker in output for marker in CONNECTION_FAILED_MARKERS):
        raise ConnectionError("ansible could not reach router")

    raise RuntimeError("ansible playbook failed")


def apply_interface(
    router,
    desired_interface,
    run_playbook=None,
):
    """Apply complete desired interface state using Ansible."""

    if run_playbook is None:
        run_playbook = _default_run_playbook

    try:
        ipv4_address, netmask = split_cidr(desired_interface["ipv4"])
    except (KeyError, ValueError):
        return error("backend_failed")

    variables = {
        "router": router,
        "interface_name": desired_interface["name"],
        "description": desired_interface["description"],
        "ipv4_address": ipv4_address,
        "netmask": netmask,
        "shutdown": desired_interface.get("admin_state") == "down",
    }

    try:
        run_playbook(variables)
    except Exception as exc:
        return error_from_exception(exc)

    return ok("applied")
