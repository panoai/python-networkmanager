"""Unit tests for code generation changes (no D-Bus required).

Verifies that make_method and make_property produce correct code
with explicit D-Bus signatures, independent of a running system.
"""
import os
import unittest
import xml.etree.ElementTree as etree


# Path to NetworkManager.py relative to this test file
_NM_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'NetworkManager.py'
)


def _make_method_call_line(method_xml):
    """Reproduce make_method's call-line generation from XML.

    Extracts the D-Bus interface call line that make_method would
    generate, without exec() or any dbus dependency.

    Note: This intentionally re-implements make_method's logic rather
    than calling it directly.  Importing NetworkManager.py triggers
    D-Bus introspection at import time, so it cannot be imported in
    environments without a running NetworkManager (including macOS
    and most CI).  The trade-off is that a divergence between this
    helper and the real make_method would go undetected; the
    SourceInspectionTest class partially mitigates this by asserting
    on the actual generated source text.
    """
    root = etree.fromstring(method_xml)
    name = root.attrib['name']
    all_args = list(root)
    outargs = [x for x in all_args if x.tag == 'arg'
               and x.attrib.get('direction') == 'out']
    outargstr = ', '.join(
        [x.attrib['name'] for x in outargs]) or 'ret'
    args = [x for x in all_args if x.tag == 'arg'
            and x.attrib.get('direction') == 'in']
    argstr = ', '.join([x.attrib['name'] for x in args])

    in_sig = ''.join([x.attrib['type'] for x in args])
    call_args = argstr + ", " if argstr else ""

    return (
        "        %s = dbus.Interface(self.proxy, '%s').%s("
        "%ssignature='%s')\n"
        % (outargstr, 'org.test.Iface', name, call_args, in_sig)
    )


class MakeMethodSignatureTest(unittest.TestCase):
    """Verify make_method passes explicit signature= in generated code."""

    def test_no_args_method(self):
        """GetSettings() -> signature='' (empty, no input args)."""
        xml = '<method name="GetSettings"></method>'
        code = _make_method_call_line(xml)
        self.assertIn("signature=''", code)
        self.assertIn(".GetSettings(signature='')", code)

    def test_single_string_arg(self):
        """GetConnectionByUuid(uuid: s) -> signature='s'."""
        xml = ('<method name="GetConnectionByUuid">'
               '<arg name="uuid" type="s" direction="in"/>'
               '<arg name="connection" type="o" direction="out"/>'
               '</method>')
        code = _make_method_call_line(xml)
        self.assertIn("signature='s'", code)

    def test_triple_object_path_args(self):
        """ActivateConnection(conn:o, dev:o, specific:o) -> 'ooo'."""
        xml = ('<method name="ActivateConnection">'
               '<arg name="connection" type="o" direction="in"/>'
               '<arg name="device" type="o" direction="in"/>'
               '<arg name="specific_object" type="o" direction="in"/>'
               '<arg name="active_connection" type="o" direction="out"/>'
               '</method>')
        code = _make_method_call_line(xml)
        self.assertIn("signature='ooo'", code)

    def test_complex_signature(self):
        """AddConnection(connection: a{sa{sv}}) -> 'a{sa{sv}}'."""
        xml = ('<method name="AddConnection">'
               '<arg name="connection" type="a{sa{sv}}" direction="in"/>'
               '<arg name="path" type="o" direction="out"/>'
               '</method>')
        code = _make_method_call_line(xml)
        self.assertIn("signature='a{sa{sv}}'", code)

    def test_comma_separates_args_from_signature(self):
        """When args exist, a comma separates them from signature=."""
        xml = ('<method name="Foo">'
               '<arg name="bar" type="s" direction="in"/>'
               '</method>')
        code = _make_method_call_line(xml)
        self.assertIn("bar, signature='s'", code)

    def test_no_comma_when_no_args(self):
        """When no args, signature= is the only parameter."""
        xml = '<method name="Foo"></method>'
        code = _make_method_call_line(xml)
        self.assertIn(".Foo(signature='')", code)


class SourceInspectionTest(unittest.TestCase):
    """Verify source-level properties by reading NetworkManager.py."""

    @classmethod
    def setUpClass(cls):
        with open(_NM_PATH) as f:
            cls.source = f.read()
        cls.lines = cls.source.split('\n')

    def test_property_get_has_ss_signature(self):
        """All Properties.Get calls must include signature='ss'."""
        for i, line in enumerate(self.lines, 1):
            if '.Get(' in line and "dbus_interface='org.freedesktop.DBus.Properties'" in line:
                self.assertIn(
                    "signature='ss'", line,
                    f"Line {i} calls Properties.Get without "
                    f"signature='ss': {line.strip()}"
                )

    def test_property_set_has_ssv_signature(self):
        """The Set call in make_property must include signature='ssv'."""
        set_idx = self.source.index("return self.proxy.Set(")
        set_end = self.source.index("\n", set_idx)
        set_line = self.source[set_idx:set_end]
        self.assertIn("signature='ssv'", set_line)

    def test_all_runtime_get_object_use_introspect_false(self):
        """Every dbus.SystemBus().get_object() must use introspect=False."""
        for i, line in enumerate(self.lines, 1):
            if 'dbus.SystemBus().get_object(' in line:
                self.assertIn(
                    'introspect=False', line,
                    f"Line {i} calls dbus.SystemBus().get_object() "
                    f"without introspect=False: {line.strip()}"
                )

    def test_no_follow_name_owner_changes(self):
        """follow_name_owner_changes should not appear anywhere."""
        self.assertNotIn(
            'follow_name_owner_changes', self.source,
            "follow_name_owner_changes should be removed — "
            "python-networkmanager handles restarts independently"
        )

    def test_init_bus_get_object_preserved(self):
        """Import-time init_bus.get_object must NOT have introspect=False."""
        for i, line in enumerate(self.lines, 1):
            if 'init_bus.get_object(' in line:
                self.assertNotIn(
                    'introspect=False', line,
                    f"Line {i}: init_bus.get_object() should keep "
                    f"introspection enabled (class-level introspection)"
                )


if __name__ == '__main__':
    unittest.main()
