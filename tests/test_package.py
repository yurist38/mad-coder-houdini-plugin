import json
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).parents[1]


class PackageTests(unittest.TestCase):
    def test_houdini_package_is_valid_json(self) -> None:
        package = json.loads((ROOT / "packages" / "mad-coder.json").read_text())
        self.assertEqual(package["hpath"], "$HOUDINI_PACKAGE_PATH/../mad-coder")
        self.assertIn("21.0", package["enable"])

    def test_python_panel_is_valid_xml(self) -> None:
        panel = ROOT / "mad-coder" / "python_panels" / "mad_coder.pypanel"
        document = ET.parse(panel)
        interface = document.getroot().find("interface")
        self.assertIsNotNone(interface)
        self.assertEqual(interface.attrib["name"], "mad_coder")


if __name__ == "__main__":
    unittest.main()
