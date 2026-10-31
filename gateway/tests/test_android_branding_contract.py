from pathlib import Path
import re
import unittest

MAIN = Path(__file__).resolve().parents[2] / "app/src/main/java/com/vera/companion/MainActivity.java"

class BrandingContractTest(unittest.TestCase):
    def test_wallpaper_not_obscured_by_opaque_overlay(self):
        text = MAIN.read_text(encoding="utf-8")
        match = re.search(r'dimmer\.setBackgroundColor\(Color\.argb\((\d+)', text)
        self.assertIsNotNone(match)
        self.assertLessEqual(int(match.group(1)), 125)
    def test_conversation_has_bubbles_not_plain_append(self):
        text = MAIN.read_text(encoding="utf-8")
        self.assertIn("transcript.addView(", text)
        self.assertIn("messageBubble(", text)
        self.assertNotIn('conversation.append(', text)
    def test_model_selection_prefers_vera(self):
        text = MAIN.read_text(encoding="utf-8")
        self.assertIn("ModelPreference.choose(", text)
    def test_connection_controls_collapsible(self):
        text = MAIN.read_text(encoding="utf-8")
        self.assertIn("connectionPanel.setVisibility(", text)
        self.assertIn("connectionToggle", text)

if __name__=="__main__":
    unittest.main()
