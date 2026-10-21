import yaml


def validate_request(data):
    """
    Validate one IPA2026 desired-state request.

    Return a response dictionary according to
    specs/response-spec-v1.md.
    """

    allow_router = ["10.0.29.101", "10.0.29.102", "10.0.29.103", "10.0.29.104", "10.0.29.105"]
    allow_method_action = {
        "restconf": ["status", "plan", "apply"],
        "netconf": ["status", "plan", "apply"],
        "ansible": ["apply"],
        "netmiko-textfsm": ["status", "delete"],
    }

    version = data.get("version")
    if type(version) is not int or version != 1:
        return {"status": "error", "result": "invalid_version"}

    router = data.get("router")
    if not router:
        return {"status": "error", "result": "missing_router"}

    if router not in allow_router:
        return {"status": "error", "result": "invalid_router"}

    method = data.get("method")
    if not method:
        return {"status": "error", "result": "missing_method"}

    if method not in allow_method_action:
        return {"status": "error", "result": "invalid_method"}

    action = data.get("action")
    if not action:
        return {"status": "error", "result": "missing_action"}

    if action not in allow_method_action[method]:
        return {"status": "error", "result": "invalid_action"}

    desired = data.get("desired")
    if not isinstance(desired, dict):
        return {"status": "error", "result": "missing_desired"}

    interface = desired.get("interface")
    if not isinstance(interface, dict):
        return {"status": "error", "result": "missing_interface"}

    if not interface.get("name"):
        return {"status": "error", "result": "missing_interface_name"}

    if action in ("plan", "apply"):
        if not interface.get("ipv4"):
            return {"status": "error", "result": "missing_ipv4"}
        if not interface.get("description"):
            return {"status": "error", "result": "missing_description"}

        admin_state = interface.get("admin_state")
        if not admin_state:
            return {"status": "error", "result": "missing_admin_state"}
        if admin_state not in ["up", "down"]:
            return {"status": "error", "result": "invalid_admin_state"}

    return {"status": "ok", "result": "accepted"}


def process_request_file(path):
    """
    Read a YAML request file, validate it,
    and return a response dictionary.
    """
    with open(path) as f:
        try:
            data = yaml.safe_load(f)
        except yaml.YAMLError:
            return {"status": "error", "result": "invalid_yaml"}

    if not isinstance(data, dict):
        return {"status": "error", "result": "invalid_yaml"}

    return validate_request(data)
