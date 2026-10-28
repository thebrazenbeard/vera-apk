"""Native Android lifecycle contract regression without an emulator."""
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
ANDROID = "{http://schemas.android.com/apk/res/android}"

class AndroidLifecycleContractTest(unittest.TestCase):
    def test_rotation_keeps_activity_and_live_inference_session(self):
        app = ET.parse(ROOT / "app/src/main/AndroidManifest.xml").getroot()
        activity = app.find("./application/activity")
        changes = set(activity.attrib.get(ANDROID + "configChanges", "").split("|"))
        self.assertTrue({"orientation", "screenSize", "keyboardHidden"} <= changes)
        self.assertEqual(activity.attrib.get(ANDROID + "windowSoftInputMode"), "adjustResize")

    def test_composer_stays_outside_scrolling_feed_and_handles_insets(self):
        code = (ROOT / "app/src/main/java/com/vera/companion/MainActivity.java").read_text(encoding="utf-8")
        self.assertIn("root.addView(composer", code)
        self.assertIn("root.addView(feed", code)
        self.assertIn("WindowInsets.Type.ime()", code)
        self.assertIn("onConfigurationChanged(Configuration", code)

if __name__ == "__main__":
    unittest.main()
