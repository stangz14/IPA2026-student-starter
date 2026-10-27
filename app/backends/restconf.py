import requests
import urllib3

from app.backends import planning
from app.backends.common import (
    error,
    error_from_exception,
    found,
    loopback_number,
    not_found,
    ok,
    router_credentials,
    split_cidr,
    to_cidr,
)


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

HEADERS = {
    "Accept": "application/yang-data+json",
    "Content-Type": "application/yang-data+json",
}
TIMEOUT = 15
SUCCESS_CODES = (200, 201, 204)
AUTH_FAILED_CODES = (401, 403)


def _default_http_get(url):
    return requests.get(
        url,
        auth=router_credentials(),
        headers=HEADERS,
        verify=False,
        timeout=TIMEOUT,
    )


def _default_http_put(url, json):
    return requests.put(
        url,
        json=json,
        auth=router_credentials(),
        headers=HEADERS,
        verify=False,
        timeout=TIMEOUT,
    )


def _error_from_exception(exc):
    # requests.exceptions.ConnectionError is not a built-in ConnectionError
    if isinstance(
        exc,
        (requests.exceptions.ConnectionError, requests.exceptions.Timeout),
    ):
        return error("connection_failed")

    return error_from_exception(exc)


def _normalize(data):
    """Convert ietf-interfaces JSON into the normalized interface."""

    if isinstance(data, list):
        data = data[0]

    addresses = data.get("ietf-ip:ipv4", {}).get("address", [])

    ipv4 = None
    if addresses:
        ipv4 = to_cidr(addresses[0]["ip"], addresses[0]["netmask"])

    return {
        "name": data["name"],
        "ipv4": ipv4,
        "description": data.get("description"),
        "admin_state": "up" if data.get("enabled", True) else "down",
    }


def get_interface_state(
    router,
    interface_name,
    http_get=None,
):
    """Return normalized interface status using RESTCONF."""

    if http_get is None:
        http_get = _default_http_get

    url = (
        f"https://{router}/restconf/data/"
        f"ietf-interfaces:interfaces/interface={interface_name}"
    )

    try:
        response = http_get(url)
    except Exception as exc:
        return _error_from_exception(exc)

    if response.status_code == 404:
        return not_found()

    if response.status_code in AUTH_FAILED_CODES:
        return error("authentication_failed")

    if response.status_code != 200:
        return error("backend_failed")

    try:
        interface = _normalize(response.json()["ietf-interfaces:interface"])
    except Exception:
        return error("backend_failed")

    return found(interface)


def plan_interface(
    router,
    desired_interface,
    http_get=None,
):
    """Return create/update/no_change plan using RESTCONF status."""

    def get_state(router, interface_name):
        return get_interface_state(router, interface_name, http_get)

    return planning.plan_interface(router, desired_interface, get_state)


def apply_interface(
    router,
    desired_interface,
    http_put=None,
):
    """Apply complete desired interface state using RESTCONF."""

    if http_put is None:
        http_put = _default_http_put

    try:
        number = int(loopback_number(desired_interface["name"]))
        address, mask = split_cidr(desired_interface["ipv4"])
    except (KeyError, ValueError):
        return error("backend_failed")

    loopback = {
        "name": number,
        "description": desired_interface["description"],
        "ip": {
            "address": {
                "primary": {
                    "address": address,
                    "mask": mask,
                }
            }
        },
    }

    if desired_interface.get("admin_state") == "down":
        loopback["shutdown"] = [None]

    url = (
        f"https://{router}/restconf/data/"
        f"Cisco-IOS-XE-native:native/interface/Loopback={number}"
    )

    try:
        response = http_put(
            url,
            json={"Cisco-IOS-XE-native:Loopback": loopback},
        )
    except Exception as exc:
        return _error_from_exception(exc)

    if response.status_code in SUCCESS_CODES:
        return ok("applied")

    if response.status_code in AUTH_FAILED_CODES:
        return error("authentication_failed")

    return error("backend_failed")
