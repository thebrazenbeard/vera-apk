"""Negative and positive controls for V2 inbox, synthetic credentials only."""
from contextlib import closing
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import hmac
import json
import os
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, os.environ.get("VERA_STM_SOURCE", r"D:\VERA\stm-20261028"))
from stm_phone_journal import EncryptedJournal
from device_scoped_history import DeviceScopedHistory
from device_inbox_v2 import InboxDeviceServer
from owner_outbox_v0 import EncryptedDeviceOutbox, canonical_bytes


class InboxHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        p = Path(self.temp.name)
        (p / "key.bin").write_bytes(os.urandom(32))
        self.store = DeviceScopedHistory(
            p / "access.sqlite3", EncryptedJournal(
                p / "journal.sqlite3", p / "key.bin"))
        self.owner = self.store.provision("owner_alpha", "phone")
        self.other = self.store.provision("owner_other", "stranger")
        self.second = self.store.provision("owner_alpha", "otherphone")
        self.enc = os.urandom(32)
        self.signer = os.urandom(32)
        self.db = p / "inbox.sqlite3"
        self.outbox = EncryptedDeviceOutbox(
            self.db, self.enc, self.signer, self.store.authenticate)
        self.server = InboxDeviceServer(("127.0.0.1", 0), self.store, self.outbox)
        self.thread = threading.Thread(
            target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop)

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)

    def request(self, method, path, token=None, payload=None):
        headers = {"Accept": "application/json"}
        if token:
            headers["Authorization"] = "Bearer " + token
        data = None if payload is None else json.dumps(payload).encode()
        if data is not None:
            headers["Content-Type"] = "application/json"
        req = Request(
            "http://127.0.0.1:%d%s" % (self.server.server_port, path),
            data=data, headers=headers, method=method)
        try:
            with urlopen(req, timeout=4) as r:
                return r.status, json.load(r)
        except HTTPError as e:
            return e.code, json.load(e)

    def enqueue(self, *, token_owner=None, request_id="request_1234567890abcd",
                content="VERA diagnostic synthetic"):
        from time import time
        principal = token_owner or self.owner
        now = int(time())
        proposal = {
            "owner_id": "owner_alpha",
            "device_id": principal["device_id"],
            "request_id": request_id,
            "body": content,
            "kind": "diagnostic",
            "issued_at": now,
            "expires_at": now + 600,
        }
        mac = hmac.new(
            self.signer, b"VERA_OUTBOX_V0\x00" + canonical_bytes(proposal),
            "sha256").hexdigest()
        return self.outbox.enqueue_approved(proposal, mac)

    def test_requires_active_v2_device_token(self):
        mid = self.enqueue()["message_id"]
        for token in (None, "x" * 48, self.other["token"]):
            status, body = self.request("GET", "/v2/inbox", token)
            if token == self.other["token"]:
                self.assertEqual((status, body["messages"]), (200, []))
            else:
                self.assertEqual(status, 403)
            self.assertEqual(self.request("POST", "/v2/inbox/ack", token,
                                          {"message_id": mid})[0], 403)
        self.assertEqual(
            self.request("GET", "/v2/inbox", self.second["token"])[1]["messages"], [])

    def test_host_approved_only_and_ack_idempotency(self):
        mid = self.enqueue()["message_id"]
        first_status, first = self.request("GET", "/v2/inbox", self.owner["token"])
        self.assertEqual(first_status, 200)
        self.assertEqual(first["schema"], "vera.inbox.v1")
        self.assertEqual(first["origin"], "vera_host_approved")
        self.assertEqual(first["messages"][0]["message_id"], mid)
        self.assertEqual(first["messages"][0]["state"], "OFFERED_NOT_DELIVERED")
        second = self.request("GET", "/v2/inbox", self.owner["token"])[1]
        self.assertEqual(second["messages"][0]["message_id"], mid)
        self.assertEqual(second["messages"][0]["offer_attempt"], 2)
        a = self.request("POST", "/v2/inbox/ack", self.owner["token"],
                         {"message_id": mid})
        self.assertEqual(a[0], 200)
        self.assertEqual(a[1]["state"], "DEVICE_ACK_CLAIM")
        self.assertFalse(a[1]["replayed"])
        again = self.request("POST", "/v2/inbox/ack", self.owner["token"],
                             {"message_id": mid})
        self.assertTrue(again[1]["replayed"])
        self.assertEqual(
            self.request("GET", "/v2/inbox", self.owner["token"])[1]["messages"], [])

    def test_no_model_or_public_send_endpoint(self):
        for route in ("/v2/inbox/send", "/v2/inbox/enqueue",
                      "/v2/inbox/owner", "/v1/inbox"):
            self.assertEqual(self.request("POST", route, self.owner["token"],
                                          {"body": "attack"})[0], 404)
        self.assertEqual(
            self.request("GET", "/v2/inbox/send", self.owner["token"])[0], 404)
        self.assertEqual(
            self.request("OPTIONS", "/v2/inbox")[0], 403)

    def test_rejects_wrong_device_and_ack_schema(self):
        mid = self.enqueue()["message_id"]
        self.assertEqual(self.request("POST", "/v2/inbox/ack",
                         self.second["token"], {"message_id": mid})[0], 403)
        for payload in ({"message_id": mid, "owner_id": "owner_alpha"},
                        {"message_id": "invalid"}, {"message_id": 42}, {}):
            code, _ = self.request("POST", "/v2/inbox/ack",
                                   self.owner["token"], payload)
            self.assertIn(code, (400, 403))
        self.assertEqual(
            self.request("GET", "/v2/inbox", self.owner["token"])[1]["messages"][0]["message_id"], mid)

    def test_revocation_blocks_poll_and_ack(self):
        mid = self.enqueue()["message_id"]
        self.store.revoke(self.owner["device_id"])
        self.assertEqual(self.request("GET", "/v2/inbox",
                                     self.owner["token"])[0], 403)
        self.assertEqual(self.request("POST", "/v2/inbox/ack",
                                     self.owner["token"],
                                     {"message_id": mid})[0], 403)

    def test_restart_outbox_remains_pending(self):
        mid = self.enqueue()["message_id"]
        first = self.request("GET", "/v2/inbox", self.owner["token"])[1]
        self.assertEqual(first["messages"][0]["message_id"], mid)
        newer = EncryptedDeviceOutbox(
            self.db, self.enc, self.signer, self.store.authenticate)
        self.server.inbox = newer
        resumed = self.request("GET", "/v2/inbox", self.owner["token"])[1]
        self.assertEqual(resumed["messages"][0]["message_id"], mid)
        self.assertEqual(resumed["messages"][0]["offer_attempt"], 2)


if __name__ == "__main__":
    unittest.main()
