"""Vera V2 device-bound, owner-scoped conversation access candidate.

No HTTP transport or legacy token upgrade in this module. Tokens are issued only
through trusted local administration and never logged by the gateway.
Conversation IDs select records; they never authenticate a caller.
"""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
import hashlib
import hmac
from pathlib import Path
import re
import secrets
import sqlite3
import threading

_OWNER = re.compile(r"[A-Za-z0-9_-]{5,64}\Z")
_LABEL = re.compile(r"[A-Za-z0-9 _-]{1,64}\Z")
_ID = re.compile(r"[A-Za-z0-9_-]{16,128}\Z")
_DEVICE_TOKEN = re.compile(r"[A-Za-z0-9_-]{32,128}\Z")


class AccessDenied(PermissionError):
    pass


class InvalidRequest(ValueError):
    pass


class DeviceScopedHistory:
    def __init__(self, access_db, journal, *, max_history=50):
        self.access_db = Path(access_db)
        self.journal = journal
        self.journal_db = Path(journal.database_path)
        self.key_file = Path(journal.key_file)
        self.max_history = min(100, max(1, int(max_history)))
        self._lock = threading.RLock()
        if self.access_db.is_symlink() or not self.access_db.parent.is_dir():
            raise InvalidRequest("untrusted access registry path")
        with closing(self._db()) as db, db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS devices (
                    device_id TEXT PRIMARY KEY,
                    owner_id TEXT NOT NULL,
                    label TEXT NOT NULL,
                    token_digest BLOB UNIQUE NOT NULL,
                    revoked INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    owner_id TEXT NOT NULL,
                    created_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(created_by) REFERENCES devices(device_id)
                );
                CREATE INDEX IF NOT EXISTS sessions_by_owner
                    ON sessions(owner_id,created_at);
            """)

    def _db(self):
        if self.access_db.is_symlink():
            raise InvalidRequest("registry symlink refused")
        db = sqlite3.connect(str(self.access_db), timeout=10)
        db.execute("PRAGMA busy_timeout=10000")
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA secure_delete=ON")
        return db

    @staticmethod
    def _digest(token):
        return hashlib.sha256(b"vera.device.v2\x00" + token.encode("ascii")).digest()

    def provision(self, owner_id, label):
        """Trusted local administrator only. Raw token displayed once."""
        if (type(owner_id) is not str or not _OWNER.fullmatch(owner_id)
                or type(label) is not str or not _LABEL.fullmatch(label)):
            raise InvalidRequest("invalid owner or device label")
        device = secrets.token_hex(16)
        token = secrets.token_urlsafe(48)
        with self._lock, closing(self._db()) as db, db:
            db.execute("INSERT INTO devices "
                       "(device_id,owner_id,label,token_digest,created_at) VALUES (?,?,?,?,?)",
                       (device,owner_id,label,self._digest(token),
                        datetime.now(timezone.utc).isoformat()))
        return {"device_id":device, "token":token, "label":label}

    def _principal(self, db, token):
        if type(token) is not str or not _DEVICE_TOKEN.fullmatch(token):
            raise AccessDenied("device credential invalid")
        row = db.execute("SELECT device_id,owner_id,revoked FROM devices "
                         "WHERE token_digest=?", (self._digest(token),)).fetchone()
        if row is None or row[2] != 0:
            raise AccessDenied("device credential invalid")
        return row[0], row[1]

    def authenticate(self, token):
        with self._lock, closing(self._db()) as db:
            device, owner = self._principal(db, token)
        return {"device_id":device, "owner_id":owner}

    def create_session(self, token):
        with self._lock, closing(self._db()) as db, db:
            device, owner = self._principal(db, token)
            session_id = secrets.token_hex(20)
            db.execute("INSERT INTO sessions "
                       "(session_id,owner_id,created_by,created_at) VALUES (?,?,?,?)",
                       (session_id,owner,device,datetime.now(timezone.utc).isoformat()))
            return session_id

    def _authorized(self, db, token, session_id):
        device, owner = self._principal(db, token)
        if type(session_id) is not str or not _ID.fullmatch(session_id):
            raise AccessDenied("unavailable session")
        row = db.execute("SELECT owner_id FROM sessions WHERE session_id=?",
                         (session_id,)).fetchone()
        if row is None or not hmac.compare_digest(row[0],owner):
            raise AccessDenied("unavailable session")
        return device, owner

    def list_sessions(self, token, limit=50):
        if type(limit) is not int or limit < 1 or limit > 100:
            raise InvalidRequest("invalid list limit")
        with self._lock, closing(self._db()) as db:
            _,owner = self._principal(db,token)
            rows = db.execute("SELECT session_id FROM sessions WHERE owner_id=? "
                              "ORDER BY created_at DESC,session_id DESC LIMIT ?",
                              (owner,limit)).fetchall()
            return [r[0] for r in rows]

    def history(self, token, session_id, limit=20, max_bytes=48000):
        if type(limit) is not int or not 1 <= limit <= self.max_history:
            raise InvalidRequest("invalid retrieval limit")
        if type(max_bytes) is not int or not 1024 <= max_bytes <= 65536:
            raise InvalidRequest("invalid retrieval budget")
        with self._lock, closing(self._db()) as db:
            self._authorized(db,token,session_id)
            # Keep authorization and the read under one lock so revocation
            # cannot interleave with this read in the same process.
            return self.journal.recent(session_id,limit=limit,max_bytes=max_bytes)

    def lookup(self, token, session_id, request_id):
        """Return a previously completed authorized request without re-inference."""
        if type(request_id) is not str or not _ID.fullmatch(request_id):
            raise InvalidRequest("invalid request identifier")
        with self._lock, closing(self._db()) as db:
            self._authorized(db, token, session_id)
            try:
                return self.journal.get_request(session_id, request_id)
            except ValueError as exc:
                raise InvalidRequest("request replay conflicts with archived data") from exc

    def append(self, token, session_id, request_id, model, user, assistant):
        if type(request_id) is not str or not _ID.fullmatch(request_id):
            raise InvalidRequest("invalid idempotency identifier")
        with self._lock, closing(self._db()) as db:
            self._authorized(db,token,session_id)
            try:
                return self.journal.append_turn(session_id,request_id,model,user,assistant)
            except ValueError as exc:
                raise InvalidRequest("invalid or conflicting journal turn") from exc

    def rotate(self, device_id):
        """Trusted local administrator; previous device credential is invalidated."""
        if type(device_id) is not str or not _ID.fullmatch(device_id):
            raise InvalidRequest("invalid device ID")
        token = secrets.token_urlsafe(48)
        with self._lock, closing(self._db()) as db, db:
            changed = db.execute("UPDATE devices SET token_digest=? "
                                 "WHERE device_id=? AND revoked=0",
                                 (self._digest(token),device_id)).rowcount
            if not changed:
                raise InvalidRequest("device revoked or missing")
        return token

    def revoke(self, device_id):
        """Trusted local administrator only; not exposed over HTTP."""
        if type(device_id) is not str or not _ID.fullmatch(device_id):
            raise InvalidRequest("invalid device ID")
        with self._lock, closing(self._db()) as db, db:
            changed = db.execute("UPDATE devices SET revoked=1 WHERE device_id=?",
                                 (device_id,)).rowcount
            if not changed:
                raise InvalidRequest("unknown device")
            return changed
