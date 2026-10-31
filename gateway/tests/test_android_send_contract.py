"""Deterministic source-level regression for immediate send acknowledgement."""
from pathlib import Path
import unittest

MAIN = (Path(__file__).resolve().parents[2] /
        "app/src/main/java/com/vera/companion/MainActivity.java")

class SendContractTest(unittest.TestCase):
    def test_clear_and_show_user_message_before_inference(self):
        src = MAIN.read_text(encoding="utf-8")
        begin = src.index("    private void send()")
        method = src[begin:src.index("    @Override protected void onResume()", begin)]
        worker = method.index("worker.execute(")
        self.assertLess(method.index('append("YOU", prompt);'), worker)
        self.assertLess(method.index('input.setText("");'), worker)
        self.assertEqual(method.count('append("YOU", prompt);'), 1)

    def test_draft_is_restored_after_failed_request(self):
        src = MAIN.read_text(encoding="utf-8")
        begin = src.index("    private void send()")
        method = src[begin:src.index("    @Override protected void onResume()", begin)]
        self.assertIn("input.getText().toString().isEmpty()", method)
        self.assertIn("input.setText(prompt);", method)
        self.assertIn("Message not delivered", method)

if __name__ == "__main__": unittest.main()
