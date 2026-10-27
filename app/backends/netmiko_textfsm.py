from app.backends.common import (
    error,
    error_from_exception,
    found,
    not_found,
    ok,
    router_credentials,
)


TIMEOUT = 15


def _connect(router):
    from netmiko import ConnectHandler

    username, password = router_credentials()

    return ConnectHandler(
        device_type="cisco_ios",
        host=router,
        username=username,
        password=password,
        conn_timeout=TIMEOUT,
    )


def _read(conn, interface_name):
    """Run the two status commands and return parsed (ip_info, descriptions)."""

    ip_info = conn.send_command(
        f"show ip interface {interface_name}",
        use_textfsm=True,
    )
    descriptions = conn.send_command(
        "show interfaces description",
        use_textfsm=True,
    )

    # TextFSM returns raw text when nothing matched the template
    if isinstance(ip_info, str):
        if ip_info.strip() and "Invalid input" not in ip_info:
            raise RuntimeError("cannot parse show ip interface")
        ip_info = []

    if not isinstance(descriptions, list):
        raise RuntimeError("cannot parse show interfaces description")

    return ip_info, descriptions


def _default_netmiko_get(router, interface_name):
    with _connect(router) as conn:
        return _read(conn, interface_name)


def _default_netmiko_delete(router, interface_name):
    with _connect(router) as conn:
        if _normalize(*_read(conn, interface_name), interface_name) is None:
            return "not_found"

        conn.send_config_set([f"no interface {interface_name}"])

        if _normalize(*_read(conn, interface_name), interface_name) is not None:
            raise RuntimeError(f"{interface_name} still present after delete")

        return "deleted"


def _error_from_exception(exc):
    try:
        from netmiko.exceptions import (
            NetmikoAuthenticationException,
            NetmikoTimeoutException,
        )
    except ImportError:
        return error_from_exception(exc)

    if isinstance(exc, NetmikoAuthenticationException):
        return error("authentication_failed")

    if isinstance(exc, NetmikoTimeoutException):
        return error("connection_failed")

    return error_from_exception(exc)


def _full_name(name):
    """Lo123 -> Loopback123"""

    name = name.strip()

    if name.startswith("Lo") and not name.startswith("Loopback"):
        return "Loopback" + name[len("Lo"):]

    return name


def _normalize(ip_info, descriptions, interface_name):
    """Build the normalized interface from parsed records, or None."""

    record = None
    for row in ip_info:
        if _full_name(row.get("interface", "")) == interface_name:
            record = row
            break

    if record is None:
        return None

    addresses = record.get("ip_address") or []
    prefixes = record.get("prefix_length") or []

    ipv4 = None
    if addresses and prefixes:
        ipv4 = f"{addresses[0]}/{prefixes[0]}"

    description = None
    for row in descriptions:
        if _full_name(row.get("port", "")) == interface_name:
            description = row.get("description") or None
            break

    link_status = record.get("link_status", "").strip().lower()

    return {
        "name": interface_name,
        "ipv4": ipv4,
        "description": description,
        "admin_state": (
            "down" if link_status == "administratively down" else "up"
        ),
    }


def get_interface_state(
    router,
    interface_name,
    netmiko_get=None,
):
    """Return normalized interface status using Netmiko + TextFSM."""

    if netmiko_get is None:
        netmiko_get = _default_netmiko_get

    try:
        ip_info, descriptions = netmiko_get(router, interface_name)
    except Exception as exc:
        return _error_from_exception(exc)

    try:
        interface = _normalize(ip_info, descriptions, interface_name)
    except Exception:
        return error("backend_failed")

    if interface is None:
        return not_found()

    return found(interface)


def delete_interface(
    router,
    interface_name,
    netmiko_delete=None,
):
    """Delete an interface using Netmiko."""

    if netmiko_delete is None:
        netmiko_delete = _default_netmiko_delete

    try:
        result = netmiko_delete(router, interface_name)
    except Exception as exc:
        return _error_from_exception(exc)

    if result == "deleted":
        return ok("deleted")

    if result == "not_found":
        return not_found()

    return error("backend_failed")
