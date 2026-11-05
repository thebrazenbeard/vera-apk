"""Mock-only phone gateway -> governed v-e-r-a interface integration.

This proves the *route and receipts*, not a real Qwen personality or phone install.
"""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import vera_inference_gateway as gateway

MODEL = "qwen35-pinned-mock-only"
SESSION = "s" * 48
PERSONA = {
    "kind": "behavior_configuration",
    "profile_id": "VERA_BEHAVIOR_PROFILE_V1",
    "profile_version": "1.0.1",
    "repository": "thebrazenbeard/vera",
    "profile_blob_sha": gateway.VERA_PERSONA_PROFILE_BLOB,
    "source_commit": "6783c0ac8da9286db9b0094426d0c4f08822220f",
    "source_sha256": "ec1defa8fcf96371a427991d40695842ffe6794aeb2e3f26c69ef5f528ee7d6d",
    "presentation_blob_sha": gateway.VERA_PERSONA_PRESENTATION_BLOB,
    "qualification": "SOURCE_ONLY",
    "prompt_layer": "server_owned_system",
    "trained_weights_modified": False,
    "identity_attested": False,
    "source_classification": {
        "kind": "behavior_configuration",
        "origin": "explicit_owner_provisioned_pinned_profile",
        "imported_knowledge": False,
        "trained_weights_modified": False,
    },
}


class FakeGovernedInterface(BaseHTTPRequestHandler):
    calls = []
    bad_profile = False
    legacy_persona_prompt_only = False
    hybrid_unconfigured = False
    hybrid_profile_without_presentation = False
    persona_override = {}
    chat_persona_override = {}
    reason = "complete"
    missing_reason = False

    def log_message(self, *_args):
        pass

    def reply(self, code, value):
        raw = json.dumps(value).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def authenticated(self):
        return (self.headers.get("Host") == f"127.0.0.1:{self.server.server_port}"
                and self.headers.get("X-Vera-Session") == SESSION
                and self.headers.get("Sec-Fetch-Site") == "same-origin")

    def do_GET(self):
        self.calls.append((self.path, self.headers.get("X-Vera-Session"), None))
        if self.path == "/api/session":
            return self.reply(200, {"token": SESSION, "mode": "response_only"})
        if not self.authenticated():
            return self.reply(403, {"error": "local session required"})
        if self.path == "/api/status":
            if self.legacy_persona_prompt_only:
                # Exact relevant distinction at v-e-r-a PR #24
                # 22b7dbb: no `persona_source` receipt exists here.
                return self.reply(200, {
                    "interface": "online", "model_node": "local",
                    "authority": "response_only", "external_actions": "not_connected",
                    "persona_prompt": "pinned_owner_profile",
                    "model_identity_attested": False,
                })
            persona = {**PERSONA, **self.persona_override}
            if self.bad_profile:
                persona["profile_blob_sha"] = "forged"
            if self.hybrid_unconfigured:
                # W48 owner-provisioned hybrid does not claim the configured
                # source unless BOTH pinned profile files were accepted.
                persona = {"kind": "not_connected",
                           "qualification": "NOT_CONFIGURED",
                           "prompt_layer": "none",
                           "identity_attested": False,
                           "trained_weights_modified": False}
            elif self.hybrid_profile_without_presentation:
                # Owner supplied the profile file but omitted the separately
                # pinned presentation file; partial sources cannot pass.
                persona.pop("presentation_blob_sha", None)
            return self.reply(200, {"interface": "online", "authority": "response_only",
                                    "external_actions": "not_connected", "persona_source": persona})
        if self.path == "/api/models":
            return self.reply(200, {"models": [MODEL], "node": "local"})
        return self.reply(404, {"error": "unsupported route"})

    def do_POST(self):
        if (self.path != "/api/chat" or not self.authenticated()
                or self.headers.get("Origin") != f"http://127.0.0.1:{self.server.server_port}"):
            return self.reply(403, {"error": "origin/session denied"})
        payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.calls.append((self.path, self.headers.get("X-Vera-Session"), payload))
        if set(payload) != {"model", "messages"} or payload["model"] != MODEL:
            return self.reply(400, {"error": "invalid model"})
        turns = payload["messages"]
        if (len(turns) > 12 or not turns or turns[-1]["role"] != "user"
                or any(t["role"] != ("user" if i % 2 == 0 else "assistant")
                       for i, t in enumerate(turns))):
            return self.reply(400, {"error": "invalid conversation"})
        reason = self.reason
        incomplete = {"complete": False, "length_limited": True,
                      "filtered": True, "unknown": None}[reason]
        truncated = {"complete": False, "length_limited": True,
                     "filtered": False, "unknown": None}[reason]
        response = {"reply": "A governed mock reply", "model": MODEL, "node": "local",
                    "mode": "response_only", "response_incomplete": incomplete,
                    "response_truncated": truncated, "response_completion_status": reason,
                    "response_token_limit": 192,
                    "persona_source": {**PERSONA, **self.chat_persona_override}}
        if self.missing_reason:
            response.pop("response_completion_status")
        return self.reply(200, response)


class GovernedPhoneGatewayTests(unittest.TestCase):
    def setUp(self):
        FakeGovernedInterface.calls = []
        FakeGovernedInterface.bad_profile = False
        FakeGovernedInterface.legacy_persona_prompt_only = False
        FakeGovernedInterface.hybrid_unconfigured = False
        FakeGovernedInterface.hybrid_profile_without_presentation = False
        FakeGovernedInterface.persona_override = {}
        FakeGovernedInterface.chat_persona_override = {}
        FakeGovernedInterface.reason = "complete"
        FakeGovernedInterface.missing_reason = False
        self.interface = ThreadingHTTPServer(("127.0.0.1", 0), FakeGovernedInterface)
        self.interface.daemon_threads = True
        self.interface_thread = threading.Thread(target=self.interface.serve_forever,
                                                 daemon=True)
        self.interface_thread.start()
        self.backend = gateway.VeraInterfaceBackend(self.interface.server_port, MODEL)
        self.server = gateway.BoundedServer(("127.0.0.1", 0), gateway.Handler,
                                            "t" * 48, backend=self.backend)
        self.server.daemon_threads = True
        self.gateway_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.gateway_thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.gateway_thread.join(timeout=2)
        self.interface.shutdown()
        self.interface.server_close()
        self.interface_thread.join(timeout=2)

    def call(self, path, body=None, *, bearer="t" * 48):
        headers = {"Authorization": "Bearer " + bearer}
        payload = None if body is None else json.dumps(body).encode("utf-8")
        if payload is not None:
            headers["Content-Type"] = "application/json"
        req = Request(f"http://127.0.0.1:{self.server.server_port}" + path,
                      data=payload, headers=headers)
        try:
            with urlopen(req, timeout=3) as response:
                return response.status, json.load(response)
        except HTTPError as exc:
            return exc.code, json.load(exc)

    def chat(self):
        return self.call("/v1/chat", {"model": MODEL, "messages": [
            {"role": "user", "content": "A wholly synthetic hello"}]})

    def test_persona_path_and_completion_reaches_phone_without_vault_access(self):
        self.assertEqual(self.call("/v1/models")[1]["models"], [MODEL])
        code, result = self.chat()
        self.assertEqual((code, result["reply"]), (200, "A governed mock reply"))
        self.assertEqual(result["response_completion_status"], "complete")
        self.assertIs(result["response_truncated"], False)
        self.assertEqual(result["persona_source"]["qualification"], "SOURCE_ONLY")
        self.assertNotIn(SESSION, json.dumps(result))
        self.assertTrue(any(path == "/api/chat" for path, _, _ in FakeGovernedInterface.calls))
        self.assertFalse(any(path == "/api/transcript" for path, _, _ in FakeGovernedInterface.calls))
        sent = [body for path, _, body in FakeGovernedInterface.calls if path == "/api/chat"][-1]
        self.assertEqual(set(sent), {"model", "messages"})
        self.assertEqual([turn["role"] for turn in sent["messages"]], ["user"])

    def test_forged_profile_or_missing_completion_fails_closed(self):
        FakeGovernedInterface.bad_profile = True
        self.assertEqual(self.chat()[0], 503)
        self.assertFalse(any(path == "/api/chat" for path, _, _ in FakeGovernedInterface.calls))
        FakeGovernedInterface.bad_profile = False
        FakeGovernedInterface.missing_reason = True
        self.assertEqual(self.chat()[0], 503)

    def test_v_e_r_a_pr24_prompt_only_status_is_not_pr28_governed_contract(self):
        """Independent green CI on two divergent PRs is not composability."""
        FakeGovernedInterface.legacy_persona_prompt_only = True
        code, result = self.chat()
        self.assertEqual(code, 503)
        self.assertNotIn("reply", result)
        self.assertFalse(any(path == "/api/chat" for path, _, _
                             in FakeGovernedInterface.calls))

    def test_w48_owner_provisioned_hybrid_opt_in_or_generic_fails_closed(self):
        """W48 source-only wire fixture; no actual files/model installed here."""
        # A configured hybrid interface permits the intended governed route
        # and advertises a non-attesting, pinned configuration source.
        self.assertEqual(self.call("/v1/models")[1]["models"], [MODEL])
        code, result = self.chat()
        self.assertEqual(code, 200)
        self.assertEqual(result["persona_source"]["qualification"], "SOURCE_ONLY")
        self.assertEqual(result["persona_source"]["profile_blob_sha"],
                         gateway.VERA_PERSONA_PROFILE_BLOB)
        self.assertEqual(result["persona_source"]["presentation_blob_sha"],
                         gateway.VERA_PERSONA_PRESENTATION_BLOB)
        self.assertIs(result["persona_source"]["identity_attested"], False)
        self.assertNotIn(SESSION, json.dumps(result))

        # A working generic model must never be accepted as a configured
        # Vera persona; no fallback to raw /v1/chat/completions occurs.
        FakeGovernedInterface.calls.clear()
        FakeGovernedInterface.hybrid_unconfigured = True
        code, result = self.chat()
        self.assertEqual(code, 503)
        self.assertNotIn("reply", result)
        self.assertFalse(any(path == "/api/chat" for path, _, _
                             in FakeGovernedInterface.calls))

        # The W48 hybrid's source receipt can truthfully say SOURCE_ONLY when
        # only its profile file was provided, but the APK contract requires
        # the separate canonical presentation blob too.
        FakeGovernedInterface.calls.clear()
        FakeGovernedInterface.hybrid_unconfigured = False
        FakeGovernedInterface.hybrid_profile_without_presentation = True
        code, result = self.chat()
        self.assertEqual(code, 503)
        self.assertNotIn("reply", result)
        self.assertFalse(any(path == "/api/chat" for path, _, _
                             in FakeGovernedInterface.calls))

    def test_w48_hybrid_rejects_partial_or_forged_source_receipts(self):
        for override in (
                {"profile_blob_sha": "unverified"},
                {"presentation_blob_sha": "unverified"},
                {"qualification": "NOT_CONFIGURED"},
                {"prompt_layer": "caller_owned"},
                {"trained_weights_modified": True},
                {"identity_attested": True},
                {"source_classification": {"kind": "trained_identity"}},
                {"source_classification": None},
        ):
            with self.subTest(override=override):
                FakeGovernedInterface.persona_override = override
                code, result = self.chat()
                self.assertEqual(code, 503)
                self.assertNotIn("reply", result)
                FakeGovernedInterface.persona_override = {}

        # The status gate alone is insufficient: the source must still match
        # on the exact generation response after the model has run.
        FakeGovernedInterface.chat_persona_override = {
            "presentation_blob_sha": "swapped_after_status"}
        code, result = self.chat()
        self.assertEqual(code, 503)
        self.assertNotIn("reply", result)
        self.assertTrue(any(path == "/api/chat" for path, _, _
                            in FakeGovernedInterface.calls))

    def test_filtered_length_unknown_receipts_forwarded_exactly(self):
        for reason, expected in (("length_limited", True), ("filtered", False),
                                 ("unknown", None)):
            with self.subTest(reason=reason):
                FakeGovernedInterface.reason = reason
                code, result = self.chat()
                self.assertEqual(code, 200)
                self.assertEqual(result["response_completion_status"], reason)
                self.assertIs(result["response_truncated"], expected)

    def test_partial_or_unknown_pair_stays_visible_but_never_replays_from_journal(self):
        class Journal:
            def __init__(self):
                self.turns = []

            def recent(self, _session, *, limit, max_bytes):
                return self.turns[-limit:]

            def append_turn(self, _session, request, model, prompt, answer):
                self.turns.append({"user": prompt, "assistant": answer})

        journal = Journal()
        self.server.journal = journal

        def ask(question, request):
            return self.call("/v1/chat", {
                "model": MODEL,
                "messages": [{"role": "user", "content": question}],
                "session_id": "s" * 16, "request_id": request * 16,
            })

        for status in ("length_limited", "filtered", "unknown"):
            with self.subTest(status=status):
                journal.turns.clear()
                FakeGovernedInterface.reason = status
                code, visible = ask("partial question", "p")
                self.assertEqual(code, 200)
                self.assertEqual(visible["response_completion_status"], status)
                self.assertEqual(journal.turns, [])

                FakeGovernedInterface.reason = "complete"
                self.assertEqual(ask("retry question", "r")[0], 200)
                self.assertEqual([t["user"] for t in journal.turns], ["retry question"])
                self.assertEqual(ask("third question", "t")[0], 200)
                sent = [body for path, _, body in FakeGovernedInterface.calls
                        if path == "/api/chat"][-1]["messages"]
                self.assertEqual([row["content"] for row in sent],
                                 ["retry question", "A governed mock reply",
                                  "third question"])

    def test_stm_history_uses_five_complete_pairs_not_six(self):
        class Journal:
            def recent(self, _session, *, limit, max_bytes):
                self.limit = limit
                return [{"user": f"user {i}", "assistant": f"reply {i}"}
                        for i in range(8)][-limit:]

            def append_turn(self, *_args):
                self.wrote = True

        journal = Journal()
        self.server.journal = journal
        payload = {"model": MODEL, "messages": [{"role": "user", "content": "new"}],
                   "session_id": "s" * 16, "request_id": "r" * 16}
        code, result = self.call("/v1/chat", payload)
        self.assertEqual((code, result.get("reply")), (200, "A governed mock reply"))
        self.assertEqual(journal.limit, 5)
        sent = [body for path, _, body in FakeGovernedInterface.calls if path == "/api/chat"][-1]
        self.assertEqual(len(sent["messages"]), 11)
        self.assertEqual(sent["messages"][0]["role"], "user")
        self.assertEqual(sent["messages"][-1]["content"], "new")
        self.assertTrue(journal.wrote)


if __name__ == "__main__":
    unittest.main()
