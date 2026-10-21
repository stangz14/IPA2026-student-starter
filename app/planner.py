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
                "ipv4": {
                    "to": f"{desired_interface.get("ipv4")}"
                },
                "description": {
                    "to": f"{desired_interface.get("description")}"
                },
                "admin_state": {
                    "to": f"{desired_interface.get("admin_state")}"
                }
            }
        }
        
    changes = {}
    
    if desired_interface.get("ipv4") != current_interface.get("ipv4"):
        changes["ipv4"] = {
                "from": f"{current_interface.get("ipv4")}",
                "to": f"{desired_interface.get("ipv4")}"
        }
    
    if desired_interface.get("description") != current_interface.get("description"):
        changes["description"] = {
                "from": f"{current_interface.get("description")}",
                "to": f"{desired_interface.get("description")}"
        }
    
    if desired_interface.get("admin_state") != current_interface.get("admin_state"):
        changes["admin_state"] = {
                "from": f"{current_interface.get("admin_state")}",
                "to": f"{desired_interface.get("admin_state")}"
        }
    
    if changes:
        return {
            "status": "ok",
            "result": "planned",
            "operation": "update",
            "changes": changes
        }
    
    return {
        "status": "ok",
        "result": "planned",
        "operation": "no_change",
        "changes": {}
    }