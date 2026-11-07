"""Encrypted, owner-scoped offline outbox. SOURCE CANDIDATE, not installed."""
from __future__ import annotations
from contextlib import closing, contextmanager
from hashlib import sha256
import hmac, json, re, secrets, sqlite3, time
from pathlib import Path
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag

ID = re.compile(r"[A-Za-z0-9_-]{16,128}\Z")
OWNER = re.compile(r"[A-Za-z0-9_-]{5,64}\Z")
MAC = re.compile(r"[0-9a-f]{64}\Z")
FIELDS = frozenset(("owner_id","device_id","request_id","body","kind","issued_at","expires_at"))
KINDS = frozenset(("diagnostic","owner_approved_message"))

class AccessDenied(PermissionError): pass
class InvalidEnvelope(ValueError): pass
class Conflict(ValueError): pass
class StorageFailure(RuntimeError): pass

def canonical_bytes(obj):
    return json.dumps(obj, sort_keys=True, separators=(",",":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")

class EncryptedDeviceOutbox:
    """Only the host may enqueue. Device polling and ack require fresh authentication.

    The authenticate callback must resolve ACTIVE credentials to {owner_id,device_id}.
    Approval signing happens in a separate owner-controlled policy gate, not the model.
    """
    def __init__(self, path, enc_key, approval_key, authenticate):
        if type(enc_key) is not bytes or len(enc_key)!=32:
            raise InvalidEnvelope("AES256 key required")
        if type(approval_key) is not bytes or len(approval_key)<32 or hmac.compare_digest(enc_key, approval_key):
            raise InvalidEnvelope("independent approval key required")
        if not callable(authenticate):
            raise InvalidEnvelope("device authenticator required")
        self.path=Path(path)
        if self.path.is_symlink() or not self.path.parent.is_dir():
            raise StorageFailure("invalid DB path")
        self.aead=AESGCM(enc_key)
        self.approval_key=approval_key
        self.authenticate=authenticate
        with closing(self._db()) as db:
            db.executescript("""
              CREATE TABLE IF NOT EXISTS outbox(
                message_id TEXT PRIMARY KEY, owner_id TEXT NOT NULL,
                device_id TEXT NOT NULL, request_id TEXT NOT NULL,
                proposal_hash BLOB NOT NULL, nonce BLOB NOT NULL, ciphertext BLOB NOT NULL,
                issued_at INTEGER NOT NULL, expires_at INTEGER NOT NULL,
                kind TEXT NOT NULL, offers INTEGER NOT NULL DEFAULT 0,
                acked_at INTEGER, UNIQUE(owner_id,device_id,request_id)
              );
              CREATE INDEX IF NOT EXISTS pending_idx
                ON outbox(owner_id,device_id,acked_at,expires_at);
            """)
    def _db(self):
        if self.path.is_symlink(): raise StorageFailure("symlink refused")
        db=sqlite3.connect(str(self.path), timeout=5, isolation_level=None)
        db.execute("PRAGMA busy_timeout=5000")
        db.execute("PRAGMA secure_delete=ON")
        return db
    @contextmanager
    def _tx(self):
        with closing(self._db()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                yield db
                db.commit()
            except BaseException:
                db.rollback()
                raise
    @staticmethod
    def _now(now):
        value=int(time.time()) if now is None else now
        if type(value) is not int or value<0: raise InvalidEnvelope("bad clock")
        return value
    def _principal(self, token):
        if type(token) is not str or not token: raise AccessDenied("credential required")
        p=self.authenticate(token)
        if type(p) is not dict or set(p)!={"owner_id","device_id"}:
            raise AccessDenied("malformed authenticated principal")
        owner,device=p["owner_id"],p["device_id"]
        if type(owner) is not str or not OWNER.fullmatch(owner):
            raise AccessDenied("malformed authenticated owner")
        if type(device) is not str or not ID.fullmatch(device):
            raise AccessDenied("malformed authenticated device")
        return owner,device
    @staticmethod
    def _aad(mid, owner, device, request, issued, expiry, kind):
        return canonical_bytes(dict(message_id=mid,owner_id=owner,device_id=device,
                                    request_id=request,issued_at=issued,
                                    expires_at=expiry,kind=kind))
    def enqueue_approved(self, proposal, permit_mac, *, now=None):
        """Host-only queue operation; no outbound network effect."""
        now=self._now(now)
        if type(proposal) is not dict or set(proposal)!=FIELDS:
            raise InvalidEnvelope("unexpected proposal fields")
        owner,device,request=(proposal[k] for k in ("owner_id","device_id","request_id"))
        if type(owner) is not str or not OWNER.fullmatch(owner):
            raise InvalidEnvelope("bad owner")
        if type(device) is not str or not ID.fullmatch(device):
            raise InvalidEnvelope("bad recipient")
        if type(request) is not str or not ID.fullmatch(request):
            raise InvalidEnvelope("bad idempotency key")
        body=proposal["body"]
        if type(body) is not str or not 1<=len(body.encode("utf-8"))<=4096:
            raise InvalidEnvelope("message exceeds bounds")
        if type(proposal["kind"]) is not str or proposal["kind"] not in KINDS:
            raise InvalidEnvelope("invalid message kind")
        issued,expiry=proposal["issued_at"],proposal["expires_at"]
        if type(issued) is not int or type(expiry) is not int or abs(issued-now)>120 or not 1<=expiry-now<=86400:
            raise InvalidEnvelope("stale or malformed approval")
        if type(permit_mac) is not str or not MAC.fullmatch(permit_mac):
            raise AccessDenied("host approval absent")
        raw=canonical_bytes(proposal)
        expected=hmac.new(self.approval_key,b"VERA_OUTBOX_V0\x00"+raw,"sha256").hexdigest()
        if not hmac.compare_digest(expected,permit_mac):
            raise AccessDenied("host approval invalid")
        digest=sha256(raw).digest()
        with self._tx() as db:
            prior=db.execute("SELECT message_id,proposal_hash,acked_at FROM outbox WHERE owner_id=? AND device_id=? AND request_id=?",
                             (owner,device,request)).fetchone()
            if prior:
                if not hmac.compare_digest(prior[1],digest): raise Conflict("request ID reused with different content")
                return {"message_id":prior[0],"state":"DEVICE_ACK_CLAIM" if prior[2] is not None else "QUEUED_UNSENT","replayed":True}
            n=db.execute("SELECT COUNT(*) FROM outbox WHERE owner_id=? AND device_id=? AND acked_at IS NULL AND expires_at>?",
                         (owner,device,now)).fetchone()[0]
            if n>=32: raise Conflict("recipient queue full")
            mid=secrets.token_hex(16)
            nonce=secrets.token_bytes(12)
            aad=self._aad(mid,owner,device,request,issued,expiry,proposal["kind"])
            cipher=self.aead.encrypt(nonce,body.encode("utf-8"),aad)
            db.execute("INSERT INTO outbox(message_id,owner_id,device_id,request_id,proposal_hash,nonce,ciphertext,issued_at,expires_at,kind) VALUES (?,?,?,?,?,?,?,?,?,?)",
                       (mid,owner,device,request,digest,nonce,cipher,issued,expiry,proposal["kind"]))
            return {"message_id":mid,"state":"QUEUED_UNSENT","replayed":False}
    def poll(self, token, *, now=None, limit=20):
        now=self._now(now)
        if type(limit) is not int or not 1<=limit<=20: raise InvalidEnvelope("poll bound")
        owner,device=self._principal(token)
        with self._tx() as db:
            rows=db.execute("SELECT message_id,request_id,nonce,ciphertext,issued_at,expires_at,kind,offers FROM outbox WHERE owner_id=? AND device_id=? AND acked_at IS NULL AND expires_at>? ORDER BY issued_at,message_id LIMIT ?",
                            (owner,device,now,limit)).fetchall()
            result=[]
            for mid,rid,nonce,cipher,issued,expiry,kind,offers in rows:
                try:
                    text=self.aead.decrypt(nonce,cipher,self._aad(mid,owner,device,rid,issued,expiry,kind)).decode("utf-8")
                except (InvalidTag,UnicodeError) as ex:
                    raise StorageFailure("encrypted content invalid") from ex
                db.execute("UPDATE outbox SET offers=offers+1 WHERE message_id=?",(mid,))
                result.append({"message_id":mid,"body":text,"kind":kind,"expires_at":expiry,
                               "offer_attempt":offers+1,"state":"OFFERED_NOT_DELIVERED"})
            return result
    def ack(self, token, message_id, *, now=None):
        now=self._now(now)
        if type(message_id) is not str or not ID.fullmatch(message_id):
            raise AccessDenied("unknown message")
        owner,device=self._principal(token)
        with self._tx() as db:
            row=db.execute("SELECT expires_at,acked_at FROM outbox WHERE message_id=? AND owner_id=? AND device_id=?",
                           (message_id,owner,device)).fetchone()
            if row is None: raise AccessDenied("unknown message")
            expiry,acked=row
            if acked is not None:
                return {"message_id":message_id,"state":"DEVICE_ACK_CLAIM","replayed":True}
            if now>=expiry: raise AccessDenied("message expired")
            db.execute("UPDATE outbox SET acked_at=? WHERE message_id=?",(now,message_id))
            return {"message_id":message_id,"state":"DEVICE_ACK_CLAIM","replayed":False}