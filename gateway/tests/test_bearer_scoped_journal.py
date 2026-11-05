"""Mock gateway tests of opt-in bearer-epoch history partitioning.

No phone, external service, model weights, or real encrypted STM journal used.
"""

import json
from pathlib import Path
import sys
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import vera_inference_gateway as gateway


SESSION = "session_identifier_w44_20261105"
OTHER_SESSION = "second_session_identifier_w44_20261105"
TOKEN_A = "a" * 48
TOKEN_B = "b" * 48


class RecordedJournal:
    def __init__(self):
        self.records = {}

    def recent(self, session_id, *, limit=8, max_bytes=14000):
        return self.records.get(session_id, [])[-limit:]

    def append_turn(self, session_id, request_id, model, user, assistant):
        self.records.setdefault(session_id, []).append({
            "user": user, "assistant": assistant})
        return len(self.records[session_id])


class BearerScopedJournalTests(unittest.TestCase):
    def setUp(self):
        self.journal = RecordedJournal()
        self.calls = 0

    def chat(self, token, prompt, *, scope="bearer-v1", session_id=SESSION,
             supplied_bearer=None):
        server = gateway.BoundedServer(("127.0.0.1", 0), gateway.Handler, token,
                                       journal=self.journal, journal_scope=scope)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            self.calls += 1
            url = "http://127.0.0.1:%d/v1/chat" % server.server_port
            body = {"model": "demo", "messages": [{"role": "user", "content": prompt}],
                    "session_id": session_id,
                    "request_id": "request_identifier_w44_%06d" % self.calls}
            request = Request(url, data=json.dumps(body).encode(),
                              headers={"Authorization": "Bearer " + (
                                  token if supplied_bearer is None else supplied_bearer),
                                       "Content-Type": "application/json"}, method="POST")
            with patch.object(gateway, "models", return_value=["demo"]), \
                 patch.object(gateway, "ollama", return_value={"message": {"content": "ACK"}}) as upstream:
                if supplied_bearer is not None and supplied_bearer != token:
                    with self.assertRaises(HTTPError) as denied:
                        urlopen(request, timeout=4)
                    self.assertEqual(denied.exception.code, 401)
                    upstream.assert_not_called()
                    return None
                with urlopen(request, timeout=4) as response:
                    self.assertEqual(response.status, 200)
                    self.assertEqual(json.load(response)["reply"], "ACK")
                return upstream.call_args.args[1]["messages"]
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=3)

    def test_scoped_history_changes_with_bearer_not_client_session(self):
        first = self.chat(TOKEN_A, "first private note")
        self.assertEqual(first, [{"role": "user", "content": "first private note"}])
        second = self.chat(TOKEN_B, "new bearer should not see first note")
        self.assertEqual(second, [{"role": "user", "content":
                                    "new bearer should not see first note"}])
        third = self.chat(TOKEN_A, "original bearer again")
        self.assertEqual(third[0], {"role": "user", "content": "first private note"})
        self.assertEqual(third[-1], {"role": "user", "content": "original bearer again"})
        self.assertEqual(len(self.journal.records), 2)
        self.assertNotIn(SESSION, self.journal.records)
        self.assertNotIn(TOKEN_A, str(self.journal.records))
        self.assertNotIn(TOKEN_B, str(self.journal.records))

    def test_legacy_records_stay_present_but_are_not_silently_imported(self):
        self.chat(TOKEN_A, "legacy saved text", scope="legacy")
        self.assertIn(SESSION, self.journal.records)
        self.assertEqual(self.chat(TOKEN_A, "scoped fresh text"),
                         [{"role": "user", "content": "scoped fresh text"}])
        self.assertEqual(len(self.journal.records), 2)
        self.assertEqual(self.journal.records[SESSION][0]["user"], "legacy saved text")

    def test_distinct_session_ids_same_bearer_stay_separate(self):
        self.chat(TOKEN_A, "first session")
        other = self.chat(TOKEN_A, "other session", session_id=OTHER_SESSION)
        self.assertEqual(other, [{"role": "user", "content": "other session"}])
        self.assertEqual(len(self.journal.records), 2)

    def test_wrong_bearer_is_rejected_before_scoped_journal_access(self):
        self.chat(TOKEN_A, "saved by A")
        before = dict(self.journal.records)
        self.assertIsNone(self.chat(TOKEN_B, "try old bearer", supplied_bearer=TOKEN_A))
        self.assertEqual(self.journal.records, before)

    def test_scope_is_not_owner_identity_and_invalid_modes_fail(self):
        first_key = gateway.journal_session_key(SESSION, TOKEN_A, "bearer-v1")
        self.assertEqual(first_key, gateway.journal_session_key(SESSION, TOKEN_A, "bearer-v1"))
        self.assertEqual(len(first_key), 64)
        self.assertNotEqual(first_key, SESSION)
        self.assertNotEqual(first_key, gateway.journal_session_key(SESSION, TOKEN_B, "bearer-v1"))
        self.assertEqual(gateway.journal_session_key(SESSION, TOKEN_A, "legacy"), SESSION)
        with self.assertRaisesRegex(ValueError, "unsupported"):
            gateway.journal_session_key(SESSION, TOKEN_A, "other")
        with self.assertRaisesRegex(ValueError, "requires an enabled"):
            gateway.BoundedServer(("127.0.0.1", 0), gateway.Handler, TOKEN_A,
                                  journal_scope="bearer-v1")


if __name__ == "__main__":
    unittest.main()
