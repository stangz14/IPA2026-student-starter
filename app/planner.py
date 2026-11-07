MANAGED_FIELDS = ("ipv4", "description", "admin_state")


def _same(desired_value, current_value):
    """Compare as text so YAML numbers (description: 2026) match router strings."""

    if desired_value is None or current_value is None:
        return desired_value is current_value

    return str(desired_value) == str(current_value)


def build_plan(desired_interface, current_interface):
    """
    Compare desired interface state with normalized current state
    and return a plan according to specs/plan-spec-v1.md.
    """

    if not current_interface:
        return {
            "status": "ok",
            "result": "planned",
            "operation": "create",
            "changes": {
                field: {"to": desired_interface.get(field)}
                for field in MANAGED_FIELDS
            },
        }

    changes = {}

    for field in MANAGED_FIELDS:
        desired_value = desired_interface.get(field)
        current_value = current_interface.get(field)

        if not _same(desired_value, current_value):
            # Keep real values: a missing description stays null, not "None".
            changes[field] = {"from": current_value, "to": desired_value}

    if changes:
        return {
            "status": "ok",
            "result": "planned",
            "operation": "update",
            "changes": changes,
        }

    return {
        "status": "ok",
        "result": "planned",
        "operation": "no_change",
        "changes": {},
    }
