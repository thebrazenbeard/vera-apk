from contextlib import closing
import hmac, os, sqlite3, tempfile, threading, unittest
from pathlib import Path
from owner_outbox_v0 import (EncryptedDeviceOutbox, AccessDenied, InvalidEnvelope,
                             Conflict, StorageFailure, canonical_bytes)

NOW=1780000000
class OutboxTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db=Path(self.temp.name)/"outbox.db"
        self.enc=os.urandom(32);self.approval=os.urandom(32);self.revoked=set()
        self.devices={"a":{"owner_id":"owner_12345","device_id":"device_aaaaaaaaaaaaaaaa"},
                      "b":{"owner_id":"owner_12345","device_id":"device_bbbbbbbbbbbbbbbb"},
                      "c":{"owner_id":"other_12345","device_id":"device_cccccccccccccccc"}}
        def authenticate(token):
            if token in self.revoked or token not in self.devices: raise AccessDenied("invalid")
            return dict(self.devices[token])
        self.auth=authenticate
        self.box=EncryptedDeviceOutbox(self.db,self.enc,self.approval,self.auth)
    def env(self, **updates):
        d=dict(owner_id="owner_12345",device_id="device_aaaaaaaaaaaaaaaa",
               request_id="request_1234567890abcd",body="Confidential synthetic hello",
               kind="diagnostic",issued_at=NOW,expires_at=NOW+900)
        d.update(updates)
        return d
    def permit(self,e):
        return hmac.new(self.approval,b"VERA_OUTBOX_V0\x00"+canonical_bytes(e),"sha256").hexdigest()
    def put(self,e=None):
        e=e or self.env()
        return self.box.enqueue_approved(e,self.permit(e),now=NOW)
    def test_default_deny(self):
        for proof in (None,"","00"*32):
            with self.assertRaises(AccessDenied):
                self.box.enqueue_approved(self.env(),proof,now=NOW)
        self.assertEqual(self.box.poll("a",now=NOW),[])
    def test_offer_retry_and_ack_replay(self):
        mid=self.put()["message_id"]
        p1=self.box.poll("a",now=NOW)[0]
        p2=self.box.poll("a",now=NOW)[0]
        self.assertEqual(p1["message_id"],p2["message_id"])
        self.assertEqual((p1["offer_attempt"],p2["offer_attempt"]),(1,2))
        self.assertEqual(p1["state"],"OFFERED_NOT_DELIVERED")
        self.assertFalse(self.box.ack("a",mid,now=NOW+1)["replayed"])
        self.assertTrue(self.box.ack("a",mid,now=NOW+2)["replayed"])
        self.assertEqual(self.box.poll("a",now=NOW+3),[])
    def test_duplicate_and_conflict(self):
        mid=self.put()["message_id"]
        replay=self.put()
        self.assertEqual(mid,replay["message_id"])
        self.assertTrue(replay["replayed"])
        with self.assertRaises(Conflict):self.put(self.env(body="changed"))
    def test_reenqueue_after_acked_preserves_acked_receipt(self):
        first=self.put()
        mid=first["message_id"]
        self.box.poll("a",now=NOW)
        self.box.ack("a",mid,now=NOW+1)
        replay=self.put()
        self.assertEqual(replay["message_id"],mid)
        self.assertEqual(replay["state"],"DEVICE_ACK_CLAIM")
        self.assertTrue(replay["replayed"])
        self.assertEqual(self.box.poll("a",now=NOW+2),[])

    def test_foreign_and_revoked_token(self):
        mid=self.put()["message_id"]
        self.assertEqual(self.box.poll("b",now=NOW),[])
        self.assertEqual(self.box.poll("c",now=NOW),[])
        with self.assertRaises(AccessDenied):self.box.ack("b",mid,now=NOW)
        with self.assertRaises(AccessDenied):self.box.poll("bad",now=NOW)
        self.revoked.add("a")
        with self.assertRaises(AccessDenied):self.box.poll("a",now=NOW)
    def test_expiry(self):
        mid=self.put(self.env(expires_at=NOW+1))["message_id"]
        self.assertEqual(self.box.poll("a",now=NOW+2),[])
        with self.assertRaises(AccessDenied):self.box.ack("a",mid,now=NOW+2)
    def test_restart_same_key_and_wrong_key(self):
        mid=self.put()["message_id"]
        second=EncryptedDeviceOutbox(self.db,self.enc,self.approval,self.auth)
        self.assertEqual(second.poll("a",now=NOW)[0]["message_id"],mid)
        bad=EncryptedDeviceOutbox(self.db,os.urandom(32),self.approval,self.auth)
        with self.assertRaises(StorageFailure):bad.poll("a",now=NOW)
    def test_tamper_ciphertext(self):
        mid=self.put()["message_id"]
        with closing(sqlite3.connect(self.db)) as con, con:
            con.execute("UPDATE outbox SET ciphertext=? WHERE message_id=?",(b"not authentic",mid))
        with self.assertRaises(StorageFailure):self.box.poll("a",now=NOW)
    def test_no_plaintext_in_db(self):
        e=self.env(body="UNIQUE_SYNTHETIC_PLAINTEXT_TO_EXCLUDE")
        self.put(e)
        self.assertNotIn(e["body"].encode(),self.db.read_bytes())
    def test_approval_exact_recipient_scope(self):
        e=self.env()
        proof=self.permit(e)
        for changed in [dict(e,device_id="device_bbbbbbbbbbbbbbbb"),
                        dict(e,body="different"),
                        dict(e,kind="owner_approved_message"),
                        dict(e,expires_at=NOW+3600)]:
            with self.assertRaises(AccessDenied):
                self.box.enqueue_approved(changed,proof,now=NOW)
    def test_concurrent_deduplication(self):
        ids=[];errs=[]
        def go():
            try:ids.append(self.put()["message_id"])
            except Exception as exc:errs.append(exc)
        t1=threading.Thread(target=go);t2=threading.Thread(target=go)
        t1.start();t2.start();t1.join(8);t2.join(8)
        self.assertFalse(errs)
        self.assertEqual(len(ids),2)
        self.assertEqual(ids[0],ids[1])
        with closing(sqlite3.connect(self.db)) as c:
            self.assertEqual(c.execute("SELECT count(*) FROM outbox").fetchone()[0],1)
    def test_bounds(self):
        for change in [dict(body=""),dict(body="x"*4097),dict(issued_at=NOW-500),
                       dict(expires_at=NOW+86402),dict(kind="obsession_direct_send"),
                       dict(extras=1),dict(issued_at=True)]:
            with self.assertRaises(InvalidEnvelope):
                self.put(self.env(**change))
        for n in (0,21,True,"2"):
            with self.assertRaises(InvalidEnvelope):self.box.poll("a",now=NOW,limit=n)