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
        # Capture pairing mode and session before dispatch, never use mutable UI state
        # from the worker after an asynchronous pairing replacement.
        self.assertIn("final boolean v2Request = usingV2;", code)
        self.assertIn("final String targetSession = v2SessionId;", code)
        self.assertIn("V2GatewayClient.chat(url,token,selected,targetSession,requestId,prompt,",code)
        self.assertIn("pairingEpoch,epoch)",code)
        self.assertIn("if (!pairingEpoch.isCurrent(epoch)) return;", code)
        self.assertIn("V2 response uncertain; reconnect to inspect saved history.",code)
        self.assertIn("v2NewChat.setVisibility(v2 ? View.VISIBLE : View.GONE)",code)

    def test_pairing_replacement_and_unpair_clear_old_unsent_draft(self):
        code = (ROOT/"MainActivity.java").read_text(encoding="utf-8")
        replaced = code.split("private void save()", 1)[1].split("private void unpair()", 1)[0]
        erased = code.split("private void unpair()", 1)[1].split("private void connect()", 1)[0]
        self.assertIn('input.setText("");', replaced)
        self.assertIn('input.setText("");', erased)

    def test_v2_session_resume_hint_must_be_persisted_before_success(self):
        credentials = (ROOT/"SecureConfig.java").read_text(encoding="utf-8")
        connect_ui = (ROOT/"MainActivity.java").read_text(encoding="utf-8")
        method = credentials.split("public static void setV2SessionId(", 1)[1].split(
            "public static String sessionId(", 1
        )[0]
        self.assertIn('throw new SecurityException("V2 session hint persistence failed")', method)
        self.assertIn("if (!context.getSharedPreferences(", method)
        self.assertIn("catch (SecurityException storageFailure)", connect_ui)

    def test_http_post_write_has_cancelable_short_admission_gate(self):
        transport = (ROOT/"GatewayClient.java").read_text(encoding="utf-8")
        epoch = (ROOT/"PairingEpoch.java").read_text(encoding="utf-8")
        self.assertIn("pairing.sendIfCurrent(generation, connection::disconnect", transport)
        self.assertIn("permit.requireActive();", transport)
        self.assertIn("try (OutputStream out = connection.getOutputStream())", transport)
        self.assertIn("synchronized (this)", epoch)
        self.assertNotIn("synchronized void sendIfCurrent", epoch)
        self.assertNotIn("synchronized void invalidate()", epoch)
        self.assertIn("Pairing revoked before dispatch", epoch)

    def test_session_creation_and_inbox_ack_post_share_revocation_permit(self):
        client = (ROOT/"V2GatewayClient.java").read_text(encoding="utf-8")
        ui = (ROOT/"MainActivity.java").read_text(encoding="utf-8")
        self.assertIn('post(base,token,"/v2/sessions",new JSONObject(),201,pairing,generation)', client)
        self.assertIn('new JSONObject().put("message_id", messageId), 200, pairing, generation)', client)
        self.assertIn('V2GatewayClient.createSession(url, token, pairingEpoch, epoch)', ui)
        self.assertIn('V2GatewayClient.acknowledgeInbox(url, token, item.messageId,', ui)

    def test_unpair_revokes_keystore_and_syncs_reconnection_intent(self):
        credentials = (ROOT/"SecureConfig.java").read_text(encoding="utf-8")
        self.assertIn("store.deleteEntry(ALIAS)", credentials)
        self.assertIn("revokedInProcess = true;", credentials)
        self.assertIn('putBoolean("connection_wanted", wanted).commit()', credentials)
        self.assertIn("Pairing erasure incomplete; reboot safety unverified", credentials)

if __name__ == "__main__":
    unittest.main()
