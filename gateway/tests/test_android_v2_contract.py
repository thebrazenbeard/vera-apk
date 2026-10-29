"""V2 Android boundary source regression (not a phone runtime test)."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2] / "app" / "src" / "main" / "java" / "com" / "vera" / "companion"

class V2AndroidBoundary(unittest.TestCase):
    def test_v2_endpoint_explicit(self):
        policy = (ROOT/"EndpointPolicy.java").read_text(encoding="utf-8")
        self.assertIn('uri.getPort() != 8444',policy)
        self.assertIn('return normalized.endsWith(":8444")',policy)

    def test_v2_never_reuses_legacy_routes(self):
        code = (ROOT/"V2GatewayClient.java").read_text(encoding="utf-8")
        self.assertIn("if (!enabled(base))",code)
        for path in ('"/v2/models"','"/v2/sessions"','"/v2/chat"'):
            self.assertIn(path, code)
        self.assertNotIn('"/v1/chat"',code)

    def test_encrypted_device_credential_kept_in_existing_keystore(self):
        code = (ROOT/"SecureConfig.java").read_text(encoding="utf-8")
        self.assertIn('KeyStore.getInstance("AndroidKeyStore")',code)
        self.assertIn('Cipher.getInstance("AES/GCM/NoPadding")',code)
        self.assertIn('setV2SessionId',code)
        self.assertIn('.remove("v2_session_id")',code)

    def test_ui_connection_and_send_are_mode_bound(self):
        code = (ROOT/"MainActivity.java").read_text(encoding="utf-8")
        self.assertIn("V2GatewayClient.enabled(url)",code)
        self.assertIn("V2GatewayClient.history(url,token,restoredSession)",code)
        self.assertIn("V2GatewayClient.chat(url,token,selected,v2SessionId,requestId,prompt)",code)
        self.assertIn("V2 response uncertain; reconnect to inspect saved history.",code)
        self.assertIn("v2NewChat.setVisibility(v2 ? View.VISIBLE : View.GONE)",code)

if __name__ == "__main__":
    unittest.main()
