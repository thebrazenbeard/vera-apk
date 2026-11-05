"""Static Android receipt-path contract, not an APK or device test."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
CLIENT = ROOT / "app/src/main/java/com/vera/companion/GatewayClient.java"
ACTIVITY = ROOT / "app/src/main/java/com/vera/companion/MainActivity.java"


class AndroidCompletionReceiptContract(unittest.TestCase):
    def test_android_parses_typed_completion_without_loosening_pairing(self):
        source = CLIENT.read_text(encoding="utf-8")
        self.assertIn('chatWithReceipt(base, token, model, history, sessionId, requestId).text',
                      source)
        self.assertIn('"response_completion_status"', source)
        self.assertIn('"response_incomplete"', source)
        self.assertIn('"response_truncated"', source)
        self.assertIn('"persona_source"', source)
        self.assertIn('"SOURCE_ONLY"', source)
        self.assertIn('"server_owned_system"', source)
        self.assertIn('"identity_attested"', source)
        self.assertIn('"response_only"', source)
        self.assertIn('"Authorization", "Bearer " + token', source)

        activity = ACTIVITY.read_text(encoding="utf-8")
        self.assertIn('GatewayClient.chatWithReceipt(', activity)
        self.assertIn('if (generation != pairingGeneration) return;', activity)
        self.assertIn('completion.equals("length_limited")', activity)
        self.assertIn('completion.equals("filtered")', activity)
        self.assertIn('completion.equals("unknown")', activity)
        self.assertNotIn('X-Vera-Session', activity)


if __name__ == "__main__":
    unittest.main()
