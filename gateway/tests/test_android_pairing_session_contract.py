"""Source-level Android pairing epoch checks; no device/Keystore simulation."""

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
ACTIVITY = ROOT / "app/src/main/java/com/vera/companion/MainActivity.java"
CONFIG = ROOT / "app/src/main/java/com/vera/companion/SecureConfig.java"


class AndroidPairingSessionContract(unittest.TestCase):
    def test_pairing_and_session_rotate_in_one_committed_preferences_update(self):
        source = CONFIG.read_text(encoding="utf-8")
        method = source.split("public static boolean save(", 1)[1].split(
            "public static String endpoint(", 1)[0]
        self.assertIn("PairingSessionPolicy.requiresNewSession(", method)
        self.assertIn('update.putString("chat_session_id"', method)
        self.assertIn('update.putString("chat_session_id"',
                      method.split("if (newSession)", 1)[1])
        self.assertIn('update.putBoolean("connection_wanted", false)',
                      method.split("if (newSession)", 1)[1])
        self.assertIn("if (!update.commit())", method)
        self.assertNotIn(".apply()", method)

    def test_pairing_and_unpair_clear_visible_chat_and_stale_callbacks_discarded(self):
        source = ACTIVITY.read_text(encoding="utf-8")
        save = source.split("private void save()", 1)[1].split(
            "private void unpair()", 1)[0]
        self.assertIn("if (newSession) {", save)
        self.assertIn("clearDisplayedConversation();", save.split("if (newSession) {", 1)[1])
        self.assertNotIn("pairingGeneration++;", save.split("if (newSession) {", 1)[0])
        self.assertIn("transcript.removeViews(1, transcript.getChildCount() - 1)", source)
        unpair = source.split("private void unpair()", 1)[1].split(
            "private void connect()", 1)[0]
        self.assertIn("clearDisplayedConversation();", unpair)
        self.assertIn("pairingGeneration++;", unpair)
        send = source.split("private void send()", 1)[1].split(
            "@Override protected void onResume()", 1)[0]
        self.assertIn("final int generation = pairingGeneration;", send)
        self.assertEqual(send.count("if (generation != pairingGeneration)"), 3)
        self.assertIn("worker.execute(() -> {\n            if (generation != pairingGeneration) return;", send)
        self.assertNotIn("if (generation != pairingGeneration) { busy = false", send)
        self.assertIn("pairingSession = SecureConfig.sessionId(this)", send)
        self.assertIn("GatewayClient.chatWithReceipt(\n                        url, pairingToken", send)
        self.assertNotIn("GatewayClient.chatWithReceipt(url, SecureConfig.token", send)


if __name__ == "__main__":
    unittest.main()
