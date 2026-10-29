"""Vera V2 separately bound device-authenticated inference & history candidate.

No legacy bearer fallback, session-ownership self-assertion, HTTP enrollment,
history export, public bind, or conversion of old unowned sessions.
"""
from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import sys
import threading

from device_scoped_history import AccessDenied, DeviceScopedHistory, InvalidRequest
from vera_inference_gateway import models, ollama, strict_json

MAX_BODY = 8192
_SESSION_PATH = re.compile(r"/v2/sessions/([A-Za-z0-9_-]{16,128})/history\Z")


class DeviceServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, store, handler=None):
        self.store = store
        self.slots = threading.BoundedSemaphore(6)
        super().__init__(address, handler or DeviceHandler)

    def process_request(self, request, client_address):
        if not self.slots.acquire(blocking=False):
            request.close()
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self.slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.slots.release()


class DeviceHandler(BaseHTTPRequestHandler):
    server_version = "VeraDeviceGateway/2"

    def log_message(self, *_):
        pass

    def setup(self):
        super().setup()
        self.connection.settimeout(10)

    def response(self, code, payload):
        encoded = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        try:
            self.wfile.write(encoded)
        except (ConnectionError, BrokenPipeError):
            pass

    def authenticate(self):
        header = self.headers.get("Authorization", "")
        if not header.startswith("Bearer ") or len(header) > 160:
            raise AccessDenied("invalid credentials")
        return header[7:]

    def _body(self):
        if self.headers.get("Content-Type", "").split(";",1)[0] != "application/json":
            raise InvalidRequest("JSON required")
        if self.headers.get("Transfer-Encoding"):
            raise InvalidRequest("ambiguous transfer")
        try:
            size = int(self.headers.get("Content-Length", ""))
        except (ValueError, TypeError) as exc:
            raise InvalidRequest("body length missing") from exc
        if not 0 < size <= MAX_BODY:
            raise InvalidRequest("body exceeds bound")
        data = self.rfile.read(size)
        if len(data) != size:
            raise InvalidRequest("body incomplete")
        return strict_json(data)

    def do_GET(self):
        if self.path not in ("/v2/models", "/v2/sessions") and not _SESSION_PATH.fullmatch(self.path):
            return self.response(404, {"error":"not found"})
        try:
            token = self.authenticate()
            if self.path == "/v2/models":
                self.server.store.authenticate(token)
                return self.response(200, {"models":models(),"mode":"response_only","node":"local"})
            if self.path == "/v2/sessions":
                return self.response(200, {"sessions":self.server.store.list_sessions(token)})
            session = _SESSION_PATH.fullmatch(self.path).group(1)
            history = self.server.store.history(token,session,limit=20,max_bytes=48000)
            return self.response(200,{"session_id":session,"turns":history})
        except AccessDenied:
            return self.response(403, {"error":"forbidden"})
        except (ValueError, OSError):
            return self.response(503, {"error":"unavailable"})

    def do_POST(self):
        if self.path not in ("/v2/sessions","/v2/chat"):
            return self.response(404, {"error":"not found"})
        try:
            token = self.authenticate()
            # Authenticate before reading a body (and before any model work).
            self.server.store.authenticate(token)
            payload = self._body()
            if self.path == "/v2/sessions":
                if payload != {}:
                    raise InvalidRequest("empty session creation body required")
                return self.response(201, {"session_id":self.server.store.create_session(token)})
            if type(payload) is not dict or set(payload) != {"session_id","request_id","model","content"}:
                raise InvalidRequest("invalid chat schema")
            session = payload["session_id"]
            # Check owner *before* costly inference. Session ID is not a credential.
            self.server.store.history(token,session,limit=1,max_bytes=1024)
            model = payload["model"]
            content = payload["content"]
            request_id = payload["request_id"]
            if type(model) is not str or len(model) > 128 or model not in models():
                raise InvalidRequest("model unavailable")
            if type(content) is not str or not 1 <= len(content) <= 4096:
                raise InvalidRequest("invalid prompt")
            if type(request_id) is not str or not re.fullmatch(r"[A-Za-z0-9_-]{16,128}",request_id):
                raise InvalidRequest("invalid request ID")
            previous = self.server.store.history(token,session,limit=8,max_bytes=14000)
            messages = []
            for turn in previous:
                messages.extend(({"role":"user","content":turn["user"]},
                                 {"role":"assistant","content":turn["assistant"]}))
            messages.append({"role":"user","content":content})
            result = ollama("/api/chat",{"model":model,"messages":messages,"stream":False,
                                        "options":{"num_predict":256}},timeout=90)
            reply = result.get("message",{}).get("content")
            if type(reply) is not str or not 1 <= len(reply) <= 16000:
                raise ValueError("invalid response")
            # Recheck the token/session under the storage lock for revocation.
            self.server.store.append(token,session,request_id,model,content,reply)
            return self.response(200, {"reply":reply,"model":model,"node":"local","mode":"response_only"})
        except AccessDenied:
            return self.response(403, {"error":"forbidden"})
        except (InvalidRequest, ValueError, UnicodeError, TypeError, AttributeError):
            return self.response(400, {"error":"invalid request"})
        except Exception:
            return self.response(503, {"error":"unavailable"})

    def do_OPTIONS(self):
        self.response(403, {"error":"not a browser API"})


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--access-db",type=Path,required=True)
    p.add_argument("--journal-db",type=Path,required=True)
    p.add_argument("--journal-key-file",type=Path,required=True)
    p.add_argument("--stm-root",type=Path,required=True)
    p.add_argument("--port",type=int,default=18781)
    p.add_argument("action", choices=("serve","provision","revoke"))
    p.add_argument("--owner-id")
    p.add_argument("--label")
    p.add_argument("--device-id")
    args=p.parse_args()
    sys.path.insert(0,str(args.stm_root.resolve()))
    from stm_phone_journal import EncryptedJournal
    store=DeviceScopedHistory(args.access_db,EncryptedJournal(args.journal_db,args.journal_key_file))
    if args.action == "provision":
        # Authorized local administrator/terminal only. NEVER do this over HTTP.
        if not args.owner_id or not args.label: p.error("owner-id and label required")
        info=store.provision(args.owner_id,args.label)
        print(json.dumps(info))
    elif args.action == "revoke":
        if not args.device_id: p.error("device-id required")
        print("REVOKED",store.revoke(args.device_id))
    else:
        if not 1024 <= args.port <= 65535: p.error("invalid port")
        with DeviceServer(("127.0.0.1",args.port),store) as server:
            print("Vera V2 device gateway listening loopback-only",args.port,flush=True)
            server.serve_forever(poll_interval=0.2)


if __name__=="__main__":
    main()
