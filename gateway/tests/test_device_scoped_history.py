"""Adversarial device-scoped encrypted history tests; synthetic data only."""
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import sys
sys.path.insert(0, os.environ.get('VERA_STM_SOURCE',r'D:\VERA\stm-20261028'))
from stm_phone_journal import EncryptedJournal
from device_scoped_history import DeviceScopedHistory, AccessDenied, InvalidRequest

class ScopedHistoryTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        p = Path(self.temp.name)
        (p / "key.bin").write_bytes(os.urandom(32))
        self.store = DeviceScopedHistory(p / "access.sqlite3", EncryptedJournal(p / "journal.sqlite3", p / "key.bin"))
        self.pc = self.store.provision("owner_one", "windows")
        self.phone = self.store.provision("owner_one", "android")
        self.other = self.store.provision("owner_two", "different-owner")

    def test_provision_does_not_store_raw_tokens(self):
        content = self.store.access_db.read_bytes()
        self.assertNotIn(self.pc["token"].encode(), content)
        self.assertNotIn(self.phone["token"].encode(), content)
        self.assertNotIn(b"synthetic-secret", content)

    def test_device_scoped_same_owner_retrieval(self):
        sid = self.store.create_session(self.phone["token"])
        self.store.append(self.phone["token"], sid, "req_" + "a" * 30, "vera-local:latest",
                          "Secret synthetic prompt", "Secret synthetic answer")
        self.assertEqual(len(self.store.history(self.pc["token"], sid)), 1)
        self.assertEqual(self.store.history(self.pc["token"], sid)[0]["user"], "Secret synthetic prompt")
        self.assertIn(sid, self.store.list_sessions(self.pc["token"]))
        self.assertNotIn(b"Secret synthetic prompt", self.store.journal_db.read_bytes())

    def test_cross_owner_and_unknown_session_rejected(self):
        sid = self.store.create_session(self.pc["token"])
        with self.assertRaises(AccessDenied):
            self.store.history(self.other["token"], sid)
        with self.assertRaises(AccessDenied):
            self.store.append(self.other["token"], sid, "req_" + "b" * 30, "vera-local:latest", "hi", "hello")
        with self.assertRaises(AccessDenied):
            self.store.history(self.pc["token"], "unknown_session_1234567890")
        with self.assertRaises(AccessDenied):
            self.store.history("legacy_phone_token_unknown", sid)

    def test_rotation_invalidates_previous_credential(self):
        session = self.store.create_session(self.pc["token"])
        newer = self.store.rotate(self.pc["device_id"])
        with self.assertRaises(AccessDenied):
            self.store.history(self.pc["token"],session)
        self.assertEqual(self.store.history(newer,session),[])
        with self.assertRaises(InvalidRequest):
            self.store.rotate("not-a-device")

    def test_revocation_denies_both_reads_and_writes(self):
        sid = self.store.create_session(self.pc["token"])
        self.store.revoke(self.pc["device_id"])
        with self.assertRaises(AccessDenied):
            self.store.history(self.pc["token"], sid)
        with self.assertRaises(AccessDenied):
            self.store.append(self.pc["token"], sid, "req_" + "c"*30, "vera-local:latest", "hi", "hello")
        self.assertEqual(self.store.history(self.phone["token"], sid), [])

    def test_duplicate_request_and_replay_conflict(self):
        sid = self.store.create_session(self.pc["token"])
        req = "req_" + "d"*30
        self.store.append(self.pc["token"], sid, req, "vera-local:latest", "hello", "reply")
        self.store.append(self.pc["token"], sid, req, "vera-local:latest", "hello", "reply")
        self.assertEqual(len(self.store.history(self.phone["token"], sid)), 1)
        with self.assertRaises(InvalidRequest):
            self.store.append(self.pc["token"], sid, req, "vera-local:latest", "changed", "reply")

    def test_session_is_not_authentication_or_client_selected_owner(self):
        sid = self.store.create_session(self.pc["token"])
        with self.assertRaises(AccessDenied):
            self.store.history(sid, sid)
        with self.assertRaises(AccessDenied):
            self.store.create_session("owner_one")
        with self.assertRaises(InvalidRequest):
            self.store.provision("owner one", "label")

    def test_history_budget_and_order(self):
        sid = self.store.create_session(self.pc["token"])
        for i in range(13):
            self.store.append(self.pc["token"], sid, "request_" + str(i).zfill(4) + "_1234567890",
                              "vera-local:latest", "question " + str(i), "answer " + str(i))
        recent = self.store.history(self.phone["token"], sid, limit=8)
        self.assertEqual(len(recent), 8)
        self.assertEqual(recent[-1]["user"], "question 12")
        self.assertEqual(len(self.store.list_sessions(self.pc["token"])), 1)

    def test_reopen_and_key_mismatch_fail(self):
        sid = self.store.create_session(self.pc["token"])
        self.store.append(self.pc["token"], sid, "req_" + "e"*30, "vera-local:latest", "hello", "answer")
        reopened = DeviceScopedHistory(self.store.access_db, EncryptedJournal(self.store.journal_db,self.store.key_file))
        self.assertEqual(len(reopened.history(self.pc["token"],sid)),1)
        self.store.key_file.write_bytes(os.urandom(32))
        wrong = DeviceScopedHistory(self.store.access_db, EncryptedJournal(self.store.journal_db,self.store.key_file))
        with self.assertRaises(Exception):
            wrong.history(self.pc["token"],sid)

if __name__ == "__main__":
    unittest.main()
