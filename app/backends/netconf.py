import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape

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


IF_NS = "urn:ietf:params:xml:ns:yang:ietf-interfaces"
IP_NS = "urn:ietf:params:xml:ns:yang:ietf-ip"
NETCONF_PORT = 830
TIMEOUT = 15


def _connect(router):
    from ncclient import manager

    username, password = router_credentials()

    return manager.connect(
        host=router,
        port=NETCONF_PORT,
        username=username,
        password=password,
        hostkey_verify=False,
        allow_agent=False,
        look_for_keys=False,
        device_params={"name": "iosxe"},
        timeout=TIMEOUT,
    )


def _default_get_config(router, filter_xml):
    with _connect(router) as m:
        return m.get_config(
            source="running",
            filter=("subtree", filter_xml),
        ).data_xml


def _default_edit_config(router, config_xml):
    with _connect(router) as m:
        m.edit_config(target="running", config=config_xml)


def _error_from_exception(exc):
    try:
        from ncclient.operations.errors import TimeoutExpiredError
        from ncclient.transport.errors import (
            AuthenticationError,
            TransportError,
        )
    except ImportError:
        return error_from_exception(exc)

    if isinstance(exc, AuthenticationError):
        return error("authentication_failed")

    if isinstance(exc, (TransportError, TimeoutExpiredError)):
        return error("connection_failed")

    # RPCError and anything else
    return error_from_exception(exc)


def _text(element, path):
    found_element = element.find(path)

    if found_element is None or found_element.text is None:
        return None

    return found_element.text.strip()


def _find_interface(xml_text, interface_name):
    """Return the normalized interface from NETCONF data, or None."""

    root = ET.fromstring(xml_text)

    for interface in root.iter(f"{{{IF_NS}}}interface"):
        if _text(interface, f"{{{IF_NS}}}name") != interface_name:
            continue

        address = interface.find(f"{{{IP_NS}}}ipv4/{{{IP_NS}}}address")

        ipv4 = None
        if address is not None:
            ipv4 = to_cidr(
                _text(address, f"{{{IP_NS}}}ip"),
                _text(address, f"{{{IP_NS}}}netmask"),
            )

        enabled = _text(interface, f"{{{IF_NS}}}enabled")

        return {
            "name": interface_name,
            "ipv4": ipv4,
            "description": _text(interface, f"{{{IF_NS}}}description"),
            "admin_state": "down" if enabled == "false" else "up",
        }

    return None


def get_interface_state(
    router,
    interface_name,
    netconf_get_config=None,
):
    """Return normalized interface status using NETCONF."""

    if netconf_get_config is None:
        netconf_get_config = _default_get_config

    filter_xml = (
        f'<interfaces xmlns="{IF_NS}">'
        f"<interface><name>{escape(interface_name)}</name></interface>"
        f"</interfaces>"
    )

    try:
        xml_text = netconf_get_config(router, filter_xml)
    except Exception as exc:
        return _error_from_exception(exc)

    try:
        interface = _find_interface(xml_text, interface_name)
    except Exception:
        return error("backend_failed")

    if interface is None:
        return not_found()

    return found(interface)


def plan_interface(
    router,
    desired_interface,
    netconf_get_config=None,
):
    """Return create/update/no_change plan using NETCONF status."""

    def get_state(router, interface_name):
        return get_interface_state(router, interface_name, netconf_get_config)

    return planning.plan_interface(router, desired_interface, get_state)


def apply_interface(
    router,
    desired_interface,
    netconf_edit_config=None,
):
    """Apply complete desired interface state using NETCONF."""

    if netconf_edit_config is None:
        netconf_edit_config = _default_edit_config

    try:
        number = loopback_number(desired_interface["name"])
        address, mask = split_cidr(desired_interface["ipv4"])
    except (KeyError, ValueError):
        return error("backend_failed")

    shutdown = ""
    if desired_interface.get("admin_state") == "down":
        shutdown = "<shutdown/>"

    config_xml = f"""<config
    xmlns="urn:ietf:params:xml:ns:netconf:base:1.0"
    xmlns:nc="urn:ietf:params:xml:ns:netconf:base:1.0">
  <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
    <interface>
      <Loopback nc:operation="replace">
        <name>{escape(number)}</name>
        <description>{escape(desired_interface["description"])}</description>
        <ip>
          <address>
            <primary>
              <address>{address}</address>
              <mask>{mask}</mask>
            </primary>
          </address>
        </ip>
        {shutdown}
      </Loopback>
    </interface>
  </native>
</config>"""

    try:
        netconf_edit_config(router, config_xml)
    except Exception as exc:
        return _error_from_exception(exc)

    return ok("applied")
