"""Actual localhost HTTP stack, synthetic model and test-only owner files.

Opt-in cross-repo integration: set VERA_INTERFACE_SOURCE_ROOT to an exact
v-e-r-a #30 checkout and run this file through unittest. Unlike the separate
mock-interface tests, this executes the real v-e-r-a server and bridge handlers
and the actual Android-facing Python gateway. It NEVER loads neural weights.
The owner-profile SHA and presentation admission are overridden only inside
this test process to admit PUBLIC SYNTHETIC data; this is NOT owner admission.
"""

from __future__ import annotations

import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import vera_inference_gateway as phone_gateway


MODEL = "synthetic-w49-not-a-vera-model"
PHONE_BEARER = "b" * 48  # deterministic non-secret test-only bearer
SESSION_ID = "s" * 32
SOURCE_ROOT = Path(os.environ["VERA_INTERFACE_SOURCE_ROOT"]).resolve() if (
    os.environ.get("VERA_INTERFACE_SOURCE_ROOT")) else None
VERA_PR30_HEAD = "f3ce7456a291b8e16d004dd1d4e54a51bb98a4dc"


def synthetic_owner_profile() -> dict:
    return {
        "schema": "VERA_BEHAVIOR_PROFILE_V1", "profile_id": "VERA_BEHAVIOR_PROFILE_V1",
        "version": "1.0.1", "lifecycle_status": "CURRENT",
        "authority": {"owner": "USER",
                      "canonicalization_rule": "EXPLICIT_USER_DIRECTION_OR_GOVERNED_ADOPTION",
                      "silent_self_promotion": False},
        "core_traits": {
            "candor": "Distinguish observed fact from undocumented inference.",
            "skepticism": "Challenge unjustified conclusions with reasoning.",
            "corrigibility": "Apply a correction to the current task immediately.",
            "independent_mindedness": "Push back when evidence requires it.",
            "distinctiveness": "Preserve a recognizable voice.",
            "context_sensitivity": "Adjust tone to the actual context.",
            "accountability": "Explain effects and limits.",
            "durability": "Preserve explicit revision provenance."},
        "personality_dimensions": {
            "warmth": "Warm when useful, without empty sentiment.",
            "humor": "Dry and observational, without covering mistakes.",
            "directness": "High but calibrated to situation.",
            "pushback": "Reasoned and specific, not theatrical.",
            "restraint": "No theatrical personhood assertions.",
            "loyalty_expression": "Show commitments through accurate actions."},
    }


class SyntheticModel(BaseHTTPRequestHandler):
    requests: list[dict] = []
    finish_reason: str | None = "stop"

    def log_message(self, *_args):
        pass

    def _json(self, payload):
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if self.path == "/health":
            return self._json({"status": "ok"})
        if self.path == "/v1/models":
            return self._json({"data": [{"id": MODEL}]})
        self.send_error(404)

    def do_POST(self):
        if self.path != "/v1/chat/completions":
            return self.send_error(404)
        payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        type(self).requests.append(payload)
        return self._json({"model": MODEL, "choices": [{
            "message": {"role": "assistant", "content": "Synthetic reply, no cognition."},
            "finish_reason": type(self).finish_reason,
        }]})


class MemoryJournalDouble:
    """Transport-only observed archive calls, NOT an encrypted durable journal."""

    def __init__(self):
        self.saved = []

    def recent(self, archive_id, *, limit, max_bytes):
        return [dict(user=row[3], assistant=row[4]) for row in
                self.saved if row[0] == archive_id][-limit:]

    def append_turn(self, archive_id, request_id, model, user, assistant):
        self.saved.append((archive_id, request_id, model, user, assistant))


@unittest.skipUnless(SOURCE_ROOT is not None and (SOURCE_ROOT / "interface/server.py").is_file(),
                     "Set VERA_INTERFACE_SOURCE_ROOT to exact v-e-r-a #30 source checkout")
class RealHybridHTTPInteropTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        assert SOURCE_ROOT is not None
        actual_head = subprocess.check_output(
            ["git", "-C", str(SOURCE_ROOT), "rev-parse", "HEAD"],
            text=True, timeout=5).strip()
        if actual_head != VERA_PR30_HEAD:
            raise RuntimeError("interop evidence pinned to exact v-e-r-a #30 head "
                               f"{VERA_PR30_HEAD}, got {actual_head}")
        # A matching HEAD does NOT imply that the imported code is unchanged.
        # Reject staged/unstaged modifications and untracked files capable of
        # shadowing importable source. Exclude only generated Python bytecode.
        for flags in (("diff", "--quiet", "HEAD"),
                      ("diff", "--cached", "--quiet", "HEAD")):
            probe = subprocess.run(["git", "-C", str(SOURCE_ROOT), *flags,
                                    "--", "interface/"],
                                   capture_output=True, text=True, timeout=5)
            if probe.returncode != 0:
                raise RuntimeError("v-e-r-a #30 interface source has staged/unstaged "
                                   "differences or cannot be verified")
        untracked = subprocess.check_output(
            ["git", "-C", str(SOURCE_ROOT), "ls-files", "--others",
             "--exclude-standard", "--", "interface/"],
            text=True, timeout=5).splitlines()
        suspicious = [path for path in untracked
                      if Path(path).suffix != ".pyc" and
                      "__pycache__" not in Path(path).parts]
        if suspicious:
            raise RuntimeError("v-e-r-a #30 contains untracked interface sources: "
                               + ", ".join(suspicious[:5]))
        sys.path.insert(0, str(SOURCE_ROOT))
        import interface
        if Path(interface.__file__).resolve().parent != SOURCE_ROOT / "interface":
            raise RuntimeError("import resolved a different interface package")
        from interface import persona_profile, server as vera_server
        from interface.loopback_model_bridge import LoopbackModelBridge, create_server
        cls.profile_module = persona_profile
        cls.server_module = vera_server
        cls.LoopbackModelBridge = LoopbackModelBridge
        cls.create_bridge = create_server

    def setUp(self):
        SyntheticModel.requests = []
        SyntheticModel.finish_reason = "stop"
        self.services = []
        self.owner_dir = tempfile.TemporaryDirectory(prefix="w49-synthetic-owner-")
        self.addCleanup(self.owner_dir.cleanup)
        self.owner_path = Path(self.owner_dir.name) / "synthetic-public-profile.json"
        self.owner_bytes = json.dumps(synthetic_owner_profile(), sort_keys=True).encode()
        self.owner_path.write_bytes(self.owner_bytes)
        self.presentation_path = Path(self.owner_dir.name) / "synthetic-public-status.md"
        self.presentation_path.write_text("PUBLIC TEST-ONLY PRESENTATION", encoding="utf-8")
        self.synthetic = self._run(ThreadingHTTPServer(("127.0.0.1", 0), SyntheticModel))
        bridge = type(self).create_bridge(self.LoopbackModelBridge(
            f"http://127.0.0.1:{self.synthetic.server_port}", MODEL,
            timeout=3, max_chat_tokens=96), port=0)
        self.bridge = self._run(bridge)
        self.journal = MemoryJournalDouble()

    def tearDown(self):
        for server, worker in reversed(self.services):
            server.shutdown()
            server.server_close()
            worker.join(timeout=2)

    def _run(self, server):
        server.daemon_threads = True
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        self.services.append((server, worker))
        return server

    def _wire(self, *, configured=True):
        opts = {"port": 0, "ollama_url": f"http://127.0.0.1:{self.bridge.server_port}",
                "max_response_tokens": 96}
        if configured:
            opts.update(persona_profile_path=self.owner_path,
                        persona_presentation_path=self.presentation_path,
                        require_persona=True)
        with patch.object(self.profile_module, "SOURCE_SHA256",
                          hashlib.sha256(self.owner_bytes).hexdigest()), \
             patch.object(self.server_module, "verify_presentation_file"):
            interface = self._run(self.server_module.make_server(**opts))
        backend = phone_gateway.VeraInterfaceBackend(interface.server_port, MODEL)
        phone = self._run(phone_gateway.BoundedServer(
            ("127.0.0.1", 0), phone_gateway.Handler, PHONE_BEARER,
            backend=backend, journal=self.journal, journal_scope="bearer-v1"))
        return interface, phone

    def _request(self, port, route, *, method="GET", data=None, headers=None):
        raw = None if data is None else json.dumps(data).encode("utf-8")
        hdrs = dict(headers or {})
        if raw is not None:
            hdrs["Content-Type"] = "application/json"
        req = Request(f"http://127.0.0.1:{port}{route}", data=raw,
                      headers=hdrs, method=method)
        try:
            with urlopen(req, timeout=8) as response:
                return response.status, json.load(response)
        except HTTPError as exc:
            return exc.code, json.load(exc)

    def _phone(self, port, text, rid):
        return self._request(port, "/v1/chat", method="POST", headers={
            "Authorization": "Bearer " + PHONE_BEARER}, data={
            "model": MODEL, "messages": [{"role": "user", "content": text}],
            "session_id": SESSION_ID, "request_id": rid * 32})

    def test_real_four_http_hop_configured_persona_csrf_and_no_token_echo(self):
        interface, phone = self._wire()
        self.assertEqual(self._request(phone.server_port, "/v1/models", headers={
            "Authorization": "Bearer " + PHONE_BEARER})[0], 200)
        self.assertEqual(self._request(phone.server_port, "/v1/models")[0], 401)
        _, session = self._request(interface.server_port, "/api/session")
        token = session["token"]
        self.assertNotEqual(token, PHONE_BEARER)
        self.assertEqual(self._request(interface.server_port, "/api/chat", method="POST",
            data={"model": MODEL, "messages": [{"role": "user", "content": "hello"}]},
            headers={"X-Vera-Session": token, "Sec-Fetch-Site": "same-origin"})[0], 403)
        code, result = self._phone(phone.server_port, "Synthetic hello", "a")
        self.assertEqual(code, 200, result)
        self.assertEqual(result["response_completion_status"], "complete")
        self.assertEqual(result["persona_source"]["qualification"], "SOURCE_ONLY")
        self.assertEqual(result["persona_source"]["presentation_implementation"],
                         "ADMITTED_SOURCE_REFERENCE_ONLY")
        self.assertIs(result["persona_source"]["identity_attested"], False)
        self.assertNotIn(token, json.dumps(result))
        self.assertNotIn(PHONE_BEARER, json.dumps(result))
        self.assertNotIn(token, json.dumps(SyntheticModel.requests))
        self.assertNotIn(PHONE_BEARER, json.dumps(SyntheticModel.requests))
        self.assertEqual(len(self.journal.saved), 1)

    def test_real_generic_ui_rejected_without_silent_raw_fallback(self):
        _, phone = self._wire(configured=False)
        code, result = self._phone(phone.server_port, "No profile available", "a")
        self.assertEqual(code, 503, result)
        self.assertNotIn("reply", result)
        self.assertEqual(SyntheticModel.requests, [])
        self.assertEqual(self.journal.saved, [])

    def test_real_length_then_complete_then_complete_excludes_partial_from_history(self):
        _, phone = self._wire()
        SyntheticModel.finish_reason = "length"
        code, first = self._phone(phone.server_port, "First truncated question", "a")
        self.assertEqual((code, first["response_completion_status"]),
                         (200, "length_limited"))
        self.assertIs(first["response_incomplete"], True)
        self.assertEqual(self.journal.saved, [])
        SyntheticModel.finish_reason = "stop"
        self.assertEqual(self._phone(phone.server_port, "Second complete question", "b")[0], 200)
        self.assertEqual(len(self.journal.saved), 1)
        self.assertEqual(self._phone(phone.server_port, "Third complete question", "c")[0], 200)
        self.assertEqual(len(self.journal.saved), 2)
        first_transcript = SyntheticModel.requests[0]["messages"]
        second_transcript = SyntheticModel.requests[1]["messages"]
        third_transcript = SyntheticModel.requests[2]["messages"]
        self.assertEqual([m["role"] for m in first_transcript], ["system", "user"])
        self.assertEqual([m["role"] for m in second_transcript], ["system", "user"])
        self.assertEqual([m["role"] for m in third_transcript],
                         ["system", "user", "assistant", "user"])
        self.assertNotIn("First truncated question", json.dumps(second_transcript))
        self.assertNotIn("First truncated question", json.dumps(third_transcript))

    def test_real_filtered_and_null_finish_reason_never_enter_phone_journal(self):
        _, phone = self._wire()
        for reason, expected, marker in (
            ("content_filter", "filtered", "Filtered reply"),
            (None, "unknown", "Missing finish reason"),
        ):
            with self.subTest(reason=reason):
                SyntheticModel.finish_reason = reason
                code, result = self._phone(phone.server_port, marker, "d" if reason else "e")
                self.assertEqual(code, 200, result)
                self.assertEqual(result["response_completion_status"], expected)
                self.assertIs(result["response_incomplete"], True if reason else None)
                self.assertEqual(self.journal.saved, [])
        SyntheticModel.finish_reason = "stop"
        code, _ = self._phone(phone.server_port, "Fully finished", "f")
        self.assertEqual(code, 200)
        self.assertEqual(len(self.journal.saved), 1)
        self.assertEqual([m["role"] for m in SyntheticModel.requests[-1]["messages"]],
                         ["system", "user"])


if __name__ == "__main__":
    unittest.main()
