"""V2 HTTP negative controls with test-only keys and encrypted STM."""
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0, os.environ.get("VERA_STM_SOURCE",r"D:\VERA\stm-20261028"))
from stm_phone_journal import EncryptedJournal
from device_scoped_history import DeviceScopedHistory
from device_gateway_v2 import DeviceServer

class DeviceGatewayTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        p = Path(self.tmp.name)
        (p/"key.bin").write_bytes(os.urandom(32))
        self.store = DeviceScopedHistory(p/"access.sqlite3",EncryptedJournal(p/"journal.sqlite3",p/"key.bin"))
        self.pc = self.store.provision("one_owner","windows")
        self.phone = self.store.provision("one_owner","android")
        self.stranger = self.store.provision("other_owner","unauthorized")
        self.server = DeviceServer(("127.0.0.1",0),self.store)
        self.thread = threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.addCleanup(self._stop)

    def _stop(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)

    def call(self, method, path, token=None, obj=None):
        headers = {"Accept":"application/json"}
        if token: headers["Authorization"] = "Bearer " + token
        data = None if obj is None else json.dumps(obj).encode()
        if data is not None: headers["Content-Type"] = "application/json"
        req=Request("http://127.0.0.1:%d"%self.server.server_port + path,
                    headers=headers,data=data,method=method)
        try:
            with urlopen(req,timeout=5) as r:
                return r.status,json.load(r)
        except HTTPError as e:
            return e.code,json.load(e)

    def test_unauthorized_and_legacy_tokens_denied(self):
        self.assertEqual(self.call("GET","/v2/sessions")[0],403)
        self.assertEqual(self.call("GET","/v2/sessions","x"*48)[0],403)
        self.assertEqual(self.call("POST","/v2/sessions","x"*48,{})[0],403)

    def test_full_same_owner_history_without_cross_owner(self):
        status,created=self.call("POST","/v2/sessions",self.pc["token"],{})
        self.assertEqual(status,201)
        sid=created["session_id"]
        with patch("device_gateway_v2.models",return_value=["vera-local:latest"]), \
             patch("device_gateway_v2.ollama",return_value={"message":{"content":"READY"}}):
            status,answer=self.call("POST","/v2/chat",self.pc["token"],
                {"session_id":sid,"request_id":"request_abcde1234567890","model":"vera-local:latest",
                 "content":"hello private"})
            self.assertEqual(status,200)
            self.assertEqual(answer["mode"],"response_only")
        status,history=self.call("GET","/v2/sessions/"+sid+"/history",self.phone["token"])
        self.assertEqual(status,200)
        self.assertEqual(history["turns"][0]["user"],"hello private")
        self.assertEqual(self.call("GET","/v2/sessions/"+sid+"/history",self.stranger["token"])[0],403)
        self.assertEqual(self.call("POST","/v2/chat",self.stranger["token"],
             {"session_id":sid,"request_id":"req_another1234567890","model":"vera-local:latest",
              "content":"steal"})[0],403)
        self.assertNotIn(sid,self.call("GET","/v2/sessions",self.stranger["token"])[1]["sessions"])

    def test_revocation_after_issue_and_unknown_session(self):
        sid=self.store.create_session(self.pc["token"])
        self.store.revoke(self.pc["device_id"])
        self.assertEqual(self.call("GET","/v2/sessions/"+sid+"/history",self.pc["token"])[0],403)
        self.assertEqual(self.call("GET","/v2/sessions/"+sid+"/history",self.phone["token"])[0],200)
        self.assertEqual(self.call("GET","/v2/sessions/not_a_real_session_12345/history",self.phone["token"])[0],403)

    def test_illegal_schema_denied_without_model_request(self):
        sid=self.store.create_session(self.pc["token"])
        with patch("device_gateway_v2.ollama") as model:
            status,_=self.call("POST","/v2/chat",self.pc["token"],
                {"session_id":sid,"request_id":"request_abcde1234567890","model":"x",
                 "content":"hello","role":"system"})
            self.assertEqual(status,400)
            model.assert_not_called()

    def test_browser_preflight_and_nonexistent_route(self):
        self.assertEqual(self.call("OPTIONS","/v2/chat")[0],403)
        self.assertEqual(self.call("GET","/v2/private/keys",self.pc["token"])[0],404)

if __name__=="__main__":
    unittest.main()
