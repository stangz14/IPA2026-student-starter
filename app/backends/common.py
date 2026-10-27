import os
from ipaddress import IPv4Interface


def found(interface):
    return {
        "status": "ok",
        "result": "found",
        "interface": interface,
    }


def not_found():
    return {
        "status": "ok",
        "result": "not_found",
        "interface": None,
    }


def ok(result):
    return {"status": "ok", "result": result}


def error(code):
    return {"status": "error", "result": code}


def error_from_exception(exc):
    """
    Map a Python built-in exception to a backend error response.

    Library-specific exceptions (requests, ncclient, netmiko, ...)
    are mapped inside each backend before falling back to this.
    """

    if isinstance(exc, PermissionError):
        return error("authentication_failed")

    if isinstance(exc, (ConnectionError, TimeoutError)):
        return error("connection_failed")

    return error("backend_failed")


def to_cidr(ip, netmask):
    """172.23.123.1 + 255.255.255.255 -> 172.23.123.1/32"""
    return IPv4Interface(f"{ip}/{netmask}").with_prefixlen


def split_cidr(ipv4):
    """172.23.123.1/32 -> ("172.23.123.1", "255.255.255.255")"""
    interface = IPv4Interface(ipv4)
    return str(interface.ip), str(interface.netmask)


def loopback_number(interface_name):
    """Loopback123 -> "123" """
    return interface_name[len("Loopback"):]


def router_credentials():
    return (
        os.environ.get("ROUTER_USER", ""),
        os.environ.get("ROUTER_PASS", ""),
    )
