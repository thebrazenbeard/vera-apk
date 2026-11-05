"""Offline contract tests for explicit Vera GGUF bridge upstream selection."""

import json
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
import threading
import time
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import vera_inference_gateway as gateway


class FakeVeraBridge(BaseHTTPRequestHandler):
    model_id = "qwen35-test-pinned"
    ready = True
    tool_response = False
    changed_model = False
    redirect = False
    extra_response = False
    invalid_utf8_text = False
    slow_body = False
    slow_headers = False
    finish_reason = "stop"
    received = []

    def log_message(self, *_args):
        return

    def reply(self, status, data, *, location=None):
        raw = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        if location:
            self.send_header("Location", location)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        if self.slow_body:
            for byte in raw:
                try:
                    self.wfile.write(bytes((byte,)))
                    self.wfile.flush()
                except OSError:
                    break
                time.sleep(.04)
        else:
            self.wfile.write(raw)

    def do_GET(self):
        if self.path == "/health":
            if self.slow_headers:
                raw = (b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
                       b"Content-Length: 39\r\n\r\n")
                for byte in raw:
                    try:
                        self.connection.sendall(bytes((byte,)))
                    except OSError:
                        break
                    time.sleep(.04)
                return
            return self.reply(200, {"status": "ok" if self.ready else "unavailable",
                                    "effect_authority": False})
        if self.path == "/api/tags":
            return self.reply(200, {"models": [{"name": self.model_id}]})
        self.reply(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/v1/chat/completions":
            return self.reply(404, {"error": "not found"})
        if self.redirect:
            return self.reply(307, {}, location="http://127.0.0.1:1/invalid")
        payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.received.append(payload)
        if len(payload.get("messages", [])) > 13:
            return self.reply(400, {"error": "invalid message count"})
        message = {"role": "assistant", "content": "A bounded reply"}
        if self.tool_response:
            message["tool_calls"] = [{"id": "t", "type": "function"}]
        if self.invalid_utf8_text:
            message["content"] = "\ud800"
        reply = {
            "model": "unexpected-model" if self.changed_model else self.model_id,
            "choices": [{"index": 0, "message": message,
                         "finish_reason": self.finish_reason}],
        }
        if self.extra_response:
            reply["effect_authority"] = True
        return self.reply(200, reply)


class BridgeContractTests(unittest.TestCase):
    def setUp(self):
        for flag, value in (("ready", True), ("tool_response", False),
                            ("changed_model", False), ("redirect", False),
                            ("extra_response", False), ("invalid_utf8_text", False),
                            ("slow_body", False), ("slow_headers", False),
                            ("finish_reason", "stop")):
            setattr(FakeVeraBridge, flag, value)
        FakeVeraBridge.received = []
        self.upstream = ThreadingHTTPServer(("127.0.0.1", 0), FakeVeraBridge)
        self.upstream.daemon_threads = True
        self.thread = threading.Thread(target=self.upstream.serve_forever, daemon=True)
        self.thread.start()
        self.backend = gateway.VeraBridgeBackend(self.upstream.server_port,
                                                 FakeVeraBridge.model_id)
        self.server = gateway.BoundedServer(("127.0.0.1", 0), gateway.Handler,
                                           "t" * 48, backend=self.backend)
        self.gw_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.gw_thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.gw_thread.join(timeout=3)
        self.upstream.shutdown()
        self.upstream.server_close()
        self.thread.join(timeout=3)

    def call(self, path, token=None, payload=None):
        headers = {}
        if token:
            headers["Authorization"] = "Bearer " + token
        data = None if payload is None else json.dumps(payload).encode()
        if data is not None:
            headers["Content-Type"] = "application/json"
        request = Request("http://127.0.0.1:%d%s" % (self.server.server_port, path),
                          data=data, headers=headers)
        try:
            with urlopen(request, timeout=3) as response:
                return response.status, json.load(response)
        except HTTPError as error:
            return error.code, json.load(error)

    def test_explicit_model_inventory_and_authenticated_text_only_chat(self):
        self.assertEqual(self.call("/v1/models")[0], 401)
        self.assertEqual(FakeVeraBridge.received, [])
        status, inventory = self.call("/v1/models", "t" * 48)
        self.assertEqual((status, inventory["models"]), (200, [FakeVeraBridge.model_id]))
        chat = {"model": FakeVeraBridge.model_id,
                "messages": [{"role": "user", "content": "hello"}]}
        status, result = self.call("/v1/chat", "t" * 48, chat)
        self.assertEqual((status, result["reply"]), (200, "A bounded reply"))
        self.assertEqual(result["mode"], "response_only")
        self.assertEqual(FakeVeraBridge.received, [{
            "model": FakeVeraBridge.model_id, "messages": chat["messages"],
            "stream": False, "max_tokens": 256,
        }])

    def test_raw_bridge_completion_reason_has_typed_receipt_but_no_persona_claim(self):
        chat = {"model": FakeVeraBridge.model_id,
                "messages": [{"role": "user", "content": "synthetic text"}]}
        for reason, status_name, incomplete, truncated in (
                ("stop", "complete", False, False),
                ("length", "length_limited", True, True),
                ("content_filter", "filtered", True, False)):
            with self.subTest(reason=reason):
                FakeVeraBridge.finish_reason = reason
                code, result = self.call("/v1/chat", "t" * 48, chat)
                self.assertEqual((code, result["reply"]), (200, "A bounded reply"))
                self.assertEqual(result["response_completion_status"], status_name)
                self.assertIs(result["response_incomplete"], incomplete)
                self.assertIs(result["response_truncated"], truncated)
                self.assertEqual(result["response_token_limit"], 256)
                self.assertNotIn("persona_source", result)
        # Existing Python backend callers expecting raw text still work.
        self.assertEqual(self.backend.chat(FakeVeraBridge.model_id,
                              chat["messages"]), "A bounded reply")

    def test_raw_length_limited_pair_is_not_archived_as_complete(self):
        class Journal:
            turns = []

            def recent(self, _session, *, limit, max_bytes):
                return self.turns[-limit:]

            def append_turn(self, _session, request, model, prompt, reply):
                self.turns.append({"user": prompt, "assistant": reply})

        journal = Journal()
        self.server.journal = journal
        payload = {"model": FakeVeraBridge.model_id,
                   "messages": [{"role": "user", "content": "partial"}],
                   "session_id": "s" * 16, "request_id": "p" * 16}
        FakeVeraBridge.finish_reason = "length"
        status, result = self.call("/v1/chat", "t" * 48, payload)
        self.assertEqual((status, result["response_completion_status"]),
                         (200, "length_limited"))
        self.assertEqual(journal.turns, [])
        FakeVeraBridge.finish_reason = "stop"
        payload["messages"][0]["content"] = "fresh"
        payload["request_id"] = "r" * 16
        self.assertEqual(self.call("/v1/chat", "t" * 48, payload)[0], 200)
        self.assertEqual([row["user"] for row in journal.turns], ["fresh"])

    def test_undisclosed_effects_model_swap_and_redirect_fail_closed(self):
        chat = {"model": FakeVeraBridge.model_id,
                "messages": [{"role": "user", "content": "hello"}]}
        for flag in ("tool_response", "changed_model", "redirect",
                     "extra_response", "invalid_utf8_text"):
            with self.subTest(flag=flag):
                setattr(FakeVeraBridge, flag, True)
                status, reply = self.call("/v1/chat", "t" * 48, chat)
                self.assertEqual(status, 503)
                self.assertNotIn("reply", reply)
                setattr(FakeVeraBridge, flag, False)

    def test_upstream_health_and_model_inventory_are_not_self_grants(self):
        FakeVeraBridge.ready = False
        self.assertEqual(self.call("/v1/models", "t" * 48)[0], 503)
        FakeVeraBridge.ready = True
        FakeVeraBridge.model_id = "wrong-model"
        self.assertEqual(self.call("/v1/models", "t" * 48)[0], 503)

    def test_dripping_bridge_cannot_exceed_aggregate_deadline(self):
        for mode in ("slow_body", "slow_headers"):
            with self.subTest(mode=mode):
                setattr(FakeVeraBridge, mode, True)
                start = time.monotonic()
                with self.assertRaises((TimeoutError, OSError, ValueError)):
                    self.backend._json("/health", timeout=.2, max_bytes=4096)
                self.assertLess(time.monotonic() - start, 1.0)
                setattr(FakeVeraBridge, mode, False)

    def test_six_concurrent_drips_release_gateway_slots(self):
        FakeVeraBridge.slow_body = True
        original = self.backend._json

        def short_deadline(path, data=None, *, timeout, max_bytes):
            return original(path, data, timeout=.25, max_bytes=max_bytes)

        start = time.monotonic()
        with patch.object(self.backend, "_json", side_effect=short_deadline):
            with ThreadPoolExecutor(max_workers=6) as executor:
                responses = list(executor.map(
                    lambda _: self.call("/v1/models", "t" * 48), range(6)))
        self.assertTrue(all(status == 503 for status, _ in responses))
        self.assertLess(time.monotonic() - start, 2.0)
        FakeVeraBridge.slow_body = False
        self.assertEqual(self.call("/v1/models", "t" * 48)[0], 200)

    def test_bridge_scope_rejects_invalid_ports_and_model_ids(self):
        for bad in (0, -1, 65536, 1.25, True, "1234"):
            with self.subTest(port=bad), self.assertRaises(ValueError):
                gateway.VeraBridgeBackend(bad, "model")
        for bad in ("", " model", "model ", "X" * 129, 123):
            with self.subTest(model=bad), self.assertRaises(ValueError):
                gateway.VeraBridgeBackend(11439, bad)

    def test_eight_saved_stm_turns_trim_to_bridge_thirteen_message_limit(self):
        """The phone journal's 8-turn default would send 17 messages to a 13-cap bridge."""
        class Journal:
            selected_limit = None
            writes = []

            def recent(self, session_id, *, limit, max_bytes):
                self.selected_limit = limit
                self.max_bytes = max_bytes
                return [{"user": f"history user {n}",
                         "assistant": f"history reply {n}"} for n in range(8)][-limit:]

            def append_turn(self, session_id, request_id, model, prompt, reply):
                self.writes.append((session_id, request_id, model, prompt, reply))

        journal = Journal()
        self.server.journal = journal
        chat = {"model": FakeVeraBridge.model_id,
                "messages": [{"role": "user", "content": "newest question"}],
                "session_id": "s" * 16, "request_id": "r" * 16}
        status, response = self.call("/v1/chat", "t" * 48, chat)
        self.assertEqual((status, response.get("reply")), (200, "A bounded reply"))
        self.assertEqual(journal.selected_limit, 6)
        self.assertEqual(len(FakeVeraBridge.received[-1]["messages"]), 13)
        self.assertEqual(FakeVeraBridge.received[-1]["messages"][-1],
                         {"role": "user", "content": "newest question"})
        self.assertEqual(len(journal.writes), 1)


if __name__ == "__main__":
    unittest.main()
