"""Part 4 student implementation."""

from app.backends import ansible, netconf, netmiko_textfsm, restconf

BACKENDS = {
    "restconf": restconf,
    "netconf": netconf,
    "ansible": ansible,
    "netmiko-textfsm": netmiko_textfsm,
}

ACTION_FUNCTIONS = {
    "status": "get_interface_state",
    "plan": "plan_interface",
    "apply": "apply_interface",
    "delete": "delete_interface",
}

CAPABILITIES = {
    "restconf": ("status", "plan", "apply"),
    "netconf": ("status", "plan", "apply"),
    "ansible": ("apply",),
    "netmiko-textfsm": ("status", "delete"),
}


def dispatch_request(data):
    """Send an already validated request to the matching backend."""
    method = data.get("method")
    action = data.get("action")

    if method not in BACKENDS:
        return {"status": "error", "result": "invalid_method"}
    if action not in CAPABILITIES[method]:
        return {"status": "error", "result": "invalid_action"}

    # Look the function up at call time so it always uses the current backend.
    backend = getattr(BACKENDS[method], ACTION_FUNCTIONS[action])

    router = data["router"]
    interface = data["desired"]["interface"]

    if action in ("status", "delete"):
        return backend(router, interface["name"])
    return backend(router, interface)
