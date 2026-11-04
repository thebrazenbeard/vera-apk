"""Offline contract tests for explicit Vera GGUF bridge upstream selection."""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
import threading
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
        self.wfile.write(raw)

    def do_GET(self):
        if self.path == "/health":
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
        message = {"role": "assistant", "content": "A bounded reply"}
        if self.tool_response:
            message["tool_calls"] = [{"id": "t", "type": "function"}]
        if self.invalid_utf8_text:
            message["content"] = "\ud800"
        reply = {
            "model": "unexpected-model" if self.changed_model else self.model_id,
            "choices": [{"index": 0, "message": message, "finish_reason": "stop"}],
        }
        if self.extra_response:
            reply["effect_authority"] = True
        return self.reply(200, reply)


class BridgeContractTests(unittest.TestCase):
    def setUp(self):
        for flag, value in (("ready", True), ("tool_response", False),
                            ("changed_model", False), ("redirect", False),
                            ("extra_response", False), ("invalid_utf8_text", False)):
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

    def test_bridge_scope_rejects_invalid_ports_and_model_ids(self):
        for bad in (0, -1, 65536, 1.25, True, "1234"):
            with self.subTest(port=bad), self.assertRaises(ValueError):
                gateway.VeraBridgeBackend(bad, "model")
        for bad in ("", " model", "model ", "X" * 129, 123):
            with self.subTest(model=bad), self.assertRaises(ValueError):
                gateway.VeraBridgeBackend(11439, bad)


if __name__ == "__main__":
    unittest.main()
