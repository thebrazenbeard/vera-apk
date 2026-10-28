"""Gateway contract checks: encrypted journal is a separate explicit dependency."""
import json
from pathlib import Path
import sys
import threading
import unittest
from unittest.mock import patch
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import vera_inference_gateway as gateway


class FakeJournal:
    def __init__(self):
        self.saved = []
        self.old = [{"user": "remembered question", "assistant": "remembered answer"}]

    def recent(self, session_id, limit=8, max_bytes=14000):
        return self.old

    def append_turn(self, session_id, request_id, model, user, assistant):
        self.saved.append((session_id, request_id, model, user, assistant))
        return len(self.saved)


class PersistenceContract(unittest.TestCase):
    def test_accepts_explicit_turn_ids_only_as_pair(self):
        base = {"model": "demo", "messages": [{"role": "user", "content": "test"}]}
        both = dict(base, session_id="session_identifier_20261028",
                    request_id="request_identifier_20261028")
        self.assertEqual(gateway.valid_chat(both, ["demo"])[0], "demo")
        with self.assertRaises(ValueError):
            gateway.valid_chat(dict(base, session_id="session_identifier_20261028"), ["demo"])

    def test_authenticated_inference_persists_before_success(self):
        journal = FakeJournal()
        server = gateway.BoundedServer(("127.0.0.1", 0), gateway.Handler, "x"*48, journal=journal)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            payload = {"model": "demo",
                "messages": [{"role": "user", "content": "new question"}],
                "session_id": "session_identifier_20261028",
                "request_id": "request_identifier_20261028"}
            req = Request("http://127.0.0.1:%s/v1/chat" % server.server_port,
                          data=json.dumps(payload).encode(),
                          headers={"Authorization": "Bearer " + "x"*48,
                                   "Content-Type": "application/json"}, method="POST")
            with patch.object(gateway, "models", return_value=["demo"]), \
                 patch.object(gateway, "ollama", return_value={"message": {"content": "READY"}}) as upstream:
                with urlopen(req, timeout=5) as res:
                    self.assertEqual(res.status, 200)
                    self.assertEqual(json.load(res)["reply"], "READY")
            self.assertEqual(len(journal.saved), 1)
            self.assertEqual(journal.saved[0][3:], ("new question", "READY"))
            self.assertEqual(upstream.call_args.args[1]["messages"][-1],
                             {"role": "user", "content": "new question"})
            self.assertEqual(upstream.call_args.args[1]["messages"][0],
                             {"role": "user", "content": "remembered question"})
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)

if __name__ == "__main__": unittest.main()
