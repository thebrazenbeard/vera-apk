#!/usr/bin/env python3
"""Vera phone-to-local-Ollama response-only gateway.

Bind ONLY to loopback. Publish through authenticated Tailscale Serve HTTPS,
never via a router port-forward or public Tailscale Funnel.
"""
import argparse
import hashlib
import http.client
import hmac
import sys
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import re
import socket
import threading
import time
from urllib.request import Request, build_opener, ProxyHandler

MAX_BODY = 32768
MAX_REPLY = 16000
OLLAMA_ROOT = "http://127.0.0.1:11434"
OPENER = build_opener(ProxyHandler({}))


def journal_session_key(session_id, bearer, scope):
    """Bind a journal lookup to one gateway bearer epoch when explicitly opted in.

    This is NOT an owner identity or a per-session bearer permission check:
    the same authenticated bearer with a known session ID can derive the same
    lookup. Legacy mode deliberately keeps existing archives reachable.
    """
    if scope == "legacy":
        return session_id
    if scope != "bearer-v1":
        raise ValueError("unsupported journal scope")
    # `valid_chat` and CLI authentication already constrain these to ASCII.
    # Do not persist, return to clients, or log the raw pairing bearer.
    return hmac.new(bearer.encode("ascii"),
                    b"vera-apk/stm/bearer-v1\0" + session_id.encode("ascii"),
                    hashlib.sha256).hexdigest()


def strict_json(raw):
    def unique(pairs):
        result = {}
        for k, v in pairs:
            if k in result:
                raise ValueError("duplicate JSON key")
            result[k] = v
        return result
    return json.loads(raw.decode("utf-8"), object_pairs_hook=unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON")))


def ollama(path, data=None, timeout=12):
    if path not in ("/api/tags", "/api/chat"):
        raise ValueError("invalid upstream operation")
    headers = {"Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    raw = None if data is None else json.dumps(data, ensure_ascii=False).encode("utf-8")
    request = Request(OLLAMA_ROOT + path, data=raw, headers=headers,
                      method="POST" if raw is not None else "GET")
    with OPENER.open(request, timeout=timeout) as reply:
        if reply.status != 200:
            raise ValueError("upstream error")
        content = reply.read(131073)
        if len(content) > 131072:
            raise ValueError("upstream response too large")
    return strict_json(content)


def models():
    reply = ollama("/api/tags")
    entries = reply.get("models")
    if type(entries) is not list:
        raise ValueError("invalid model inventory")
    return [e["name"] for e in entries[:32]
            if type(e) is dict and type(e.get("name")) is str
            and 1 <= len(e["name"]) <= 128]


class VeraBridgeBackend:
    """Explicit opt-in to the *local* v-e-r-a #24 guarded GGUF bridge.

    This only changes the existing authenticated phone gateway's local model
    upstream. It does not expose the bridge to the tailnet, admit weights,
    change pairing, or add tools/effect authority.
    """

    def __init__(self, port, model_id):
        if type(port) is not int or not 1024 <= port <= 65535:
            raise ValueError("bridge port must be an unprivileged local TCP port")
        if (type(model_id) is not str or not 0 < len(model_id) <= 128
                or model_id != model_id.strip() or any(ord(c) < 32 for c in model_id)):
            raise ValueError("exact bridge model ID required")
        model_id.encode("utf-8")
        self.port = port
        self.root = f"http://127.0.0.1:{port}"
        self.model_id = model_id

    def _json(self, path, data=None, *, timeout, max_bytes):
        if path not in ("/health", "/api/tags", "/v1/chat/completions"):
            raise ValueError("unsupported bridge operation")
        raw = None if data is None else json.dumps(data, ensure_ascii=False).encode("utf-8")
        deadline = time.monotonic() + timeout
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=timeout)
        expired = threading.Event()
        guard_socket = None

        def abort():
            expired.set()
            # With Connection: close, getresponse() may detach connection.sock
            # while HTTPResponse still owns the readable socket. Retain a dup.
            active = guard_socket or connection.sock
            if active is not None:
                try:
                    active.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass

        timer = threading.Timer(timeout, abort)
        timer.daemon = True
        timer.start()
        try:
            connection.request("POST" if raw is not None else "GET", path,
                               body=raw, headers={"Accept": "application/json",
                                                  "Content-Type": "application/json",
                                                  "Connection": "close"})
            if connection.sock is not None:
                guard_socket = connection.sock.dup()
            response = connection.getresponse()
            if (response.status != 200
                    or response.getheader("Content-Type", "").split(";", 1)[0].strip()
                    != "application/json"):
                raise ValueError("invalid bridge response status/type")
            content = response.read(max_bytes + 1)
            if expired.is_set() or time.monotonic() >= deadline:
                raise TimeoutError("bridge aggregate request deadline exceeded")
        except (OSError, http.client.HTTPException) as exc:
            if expired.is_set() or time.monotonic() >= deadline:
                raise TimeoutError("bridge aggregate request deadline exceeded") from exc
            raise
        finally:
            timer.cancel()
            connection.close()
            if guard_socket is not None:
                guard_socket.close()
        if len(content) > max_bytes:
            raise ValueError("bridge response too large")
        return strict_json(content)

    def models(self):
        health = self._json("/health", timeout=3, max_bytes=4096)
        if (type(health) is not dict or health.get("status") != "ok"
                or health.get("effect_authority") is not False):
            raise ValueError("bridge health/authority contract unavailable")
        inventory = self._json("/api/tags", timeout=3, max_bytes=4096)
        entries = inventory.get("models") if type(inventory) is dict else None
        if (type(entries) is not list or len(entries) != 1
                or type(entries[0]) is not dict or set(entries[0]) != {"name"}
                or entries[0]["name"] != self.model_id):
            raise ValueError("exact bridge model absent or changed")
        return [self.model_id]

    def chat(self, model, messages):
        # Check again immediately before generation. The v-e-r-a bridge checks
        # its own pinned upstream ID again, but neither check is host admission.
        if model != self.model_id or self.models() != [model]:
            raise ValueError("bridge model changed")
        result = self._json("/v1/chat/completions", {
            "model": model, "messages": messages, "stream": False, "max_tokens": 256,
        }, timeout=70, max_bytes=65536)
        if (type(result) is not dict or set(result) != {"model", "choices"}
                or result["model"] != model or type(result["choices"]) is not list
                or len(result["choices"]) != 1):
            raise ValueError("bridge response/model identity mismatch")
        choice = result["choices"][0]
        if (type(choice) is not dict
                or set(choice) != {"index", "message", "finish_reason"}
                or choice["index"] != 0
                or choice["finish_reason"] not in ("stop", "length", "content_filter")):
            raise ValueError("unsupported bridge response")
        message = choice["message"]
        if (type(message) is not dict or set(message) != {"role", "content"}
                or message["role"] != "assistant" or type(message["content"]) is not str
                or not 1 <= len(message["content"]) <= MAX_REPLY):
            raise ValueError("non-text or effect-capable bridge response")
        message["content"].encode("utf-8")  # A malformed surrogate must not crash the handler.
        return message["content"]


def valid_chat(payload, allowed):
    if type(payload) is not dict:
        raise ValueError("chat schema invalid")
    fields = set(payload)
    if fields not in ({"model", "messages"},
                      {"model", "messages", "session_id", "request_id"}):
        raise ValueError("chat schema invalid")
    if "session_id" in payload:
        for key in ("session_id", "request_id"):
            value = payload[key]
            if type(value) is not str or not re.fullmatch(r"[A-Za-z0-9_-]{16,128}", value):
                raise ValueError("invalid session/request identifier")
    model, items = payload["model"], payload["messages"]
    if type(model) is not str or model not in allowed:
        raise ValueError("model unavailable")
    if type(items) is not list or not 1 <= len(items) <= 12:
        raise ValueError("history outside bounds")
    if items[-1].get("role") != "user":
        raise ValueError("last message must be user")
    for entry in items:
        if type(entry) is not dict or set(entry) != {"role", "content"}:
            raise ValueError("message schema invalid")
        if entry["role"] not in ("user", "assistant"):
            raise ValueError("role forbidden")
        if type(entry["content"]) is not str or not 1 <= len(entry["content"]) <= 4096:
            raise ValueError("content outside bounds")
    return model, items


class BoundedServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True
    def __init__(self, address, handler, token, journal=None, *, backend=None,
                 journal_scope="legacy"):
        if journal_scope not in ("legacy", "bearer-v1"):
            raise ValueError("unsupported journal scope")
        if journal is None and journal_scope != "legacy":
            raise ValueError("bearer-scoped journal requires an enabled journal")
        self.token = token
        self.journal = journal
        self.journal_scope = journal_scope
        self.backend = backend
        self.slots = threading.BoundedSemaphore(6)
        super().__init__(address, handler)
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


class Handler(BaseHTTPRequestHandler):
    server_version = "VeraInference/1"
    def log_message(self, *_args):
        pass  # never record prompts or Authorization
    def setup(self):
        super().setup()
        self.connection.settimeout(12)
    def respond(self, code, payload):
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        try:
            self.wfile.write(raw)
        except (BrokenPipeError, ConnectionError):
            pass
    def authorized(self):
        candidate = self.headers.get("Authorization", "")
        expected = "Bearer " + self.server.token
        return hmac.compare_digest(candidate, expected)
    def do_GET(self):
        if not self.authorized():
            return self.respond(401, {"error": "unauthorized"})
        if self.path != "/v1/models":
            return self.respond(404, {"error": "not found"})
        try:
            inventory = self.server.backend.models() if self.server.backend else models()
            self.respond(200, {"models": inventory, "node": "local", "mode": "response_only"})
        except Exception:
            self.respond(503, {"error": "model inventory unavailable"})
    def do_POST(self):
        if not self.authorized():
            return self.respond(401, {"error": "unauthorized"})
        if self.path != "/v1/chat":
            return self.respond(404, {"error": "not found"})
        if self.headers.get("Content-Type", "").split(";", 1)[0].strip() != "application/json":
            return self.respond(415, {"error": "JSON required"})
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            return self.respond(411, {"error": "length required"})
        if (length < 1 or length > MAX_BODY or
                self.headers.get("Transfer-Encoding")):
            return self.respond(413, {"error": "request too large"})
        try:
            raw = self.rfile.read(length)
            if len(raw) != length:
                raise ValueError("incomplete request")
            payload = strict_json(raw)
            inventory = self.server.backend.models() if self.server.backend else models()
            model, messages = valid_chat(payload, inventory)
        except (ValueError, TypeError, UnicodeError, AttributeError):
            return self.respond(400, {"error": "invalid chat request"})
        except Exception:
            return self.respond(503, {"error": "model inventory unavailable"})
        try:
            session_id = payload.get("session_id")
            request_id = payload.get("request_id")
            if self.server.journal is not None and session_id is not None:
                archive_id = journal_session_key(
                    session_id, self.server.token, self.server.journal_scope)
                # v-e-r-a's guarded bridge accepts at most 13 messages:
                # six history pairs plus the current user turn. Preserve the
                # eight-turn legacy Ollama behavior when that backend is used.
                history_limit = 6 if self.server.backend is not None else 8
                prior = self.server.journal.recent(
                    archive_id, limit=history_limit, max_bytes=14000)
                messages = []
                for turn in prior:
                    messages.extend(({"role": "user", "content": turn["user"]},
                                     {"role": "assistant", "content": turn["assistant"]}))
                messages.append({"role": "user", "content": payload["messages"][-1]["content"]})
            if self.server.backend is not None and (
                    len(messages) > 13 or sum(len(row["content"]) for row in messages) > 20000):
                raise ValueError("bridge conversation exceeds text-only bounds")
            if self.server.backend:
                answer = self.server.backend.chat(model, messages)
            else:
                result = ollama("/api/chat", {"model": model, "messages": messages,
                    "stream": False, "options": {"num_predict": 256}}, timeout=90)
                answer = result.get("message", {}).get("content")
            if type(answer) is not str or not 1 <= len(answer) <= MAX_REPLY:
                raise ValueError("invalid model response")
            if self.server.journal is not None and session_id is not None:
                self.server.journal.append_turn(archive_id, request_id, model,
                    payload["messages"][-1]["content"], answer)
            return self.respond(200, {"reply": answer, "model": model,
                                      "node": "local", "mode": "response_only"})
        except Exception:
            self.respond(503, {"error": "local inference unavailable"})
    def do_OPTIONS(self):
        self.respond(403, {"error": "not a browser API"})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--token-file", type=Path, required=True)
    parser.add_argument("--port", type=int, default=18777)
    parser.add_argument("--journal-db", type=Path)
    parser.add_argument("--journal-key-file", type=Path)
    parser.add_argument("--stm-root", type=Path)
    parser.add_argument("--journal-scope", choices=("legacy", "bearer-v1"),
                        default="legacy")
    parser.add_argument("--upstream-backend", choices=("ollama", "vera-bridge"),
                        default="ollama")
    parser.add_argument("--bridge-port", type=int)
    parser.add_argument("--bridge-model-id")
    args = parser.parse_args()
    token = args.token_file.read_text(encoding="ascii").strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{32,128}", token):
        parser.error("invalid pairing token file")
    if not 1024 <= args.port <= 65535:
        parser.error("port out of range")
    journal = None
    config = (args.journal_db, args.journal_key_file, args.stm_root)
    if any(x is not None for x in config):
        if not all(x is not None for x in config):
            parser.error("journal requires db, key file and stm root")
        sys.path.insert(0, str(args.stm_root.resolve()))
        from stm_phone_journal import EncryptedJournal
        journal = EncryptedJournal(args.journal_db, args.journal_key_file)
    elif args.journal_scope != "legacy":
        parser.error("bearer-scoped journal requires --journal-db, --journal-key-file and --stm-root")
    backend = None
    if args.upstream_backend == "vera-bridge":
        if args.bridge_port is None or args.bridge_model_id is None:
            parser.error("vera-bridge requires exact --bridge-port and --bridge-model-id")
        try:
            backend = VeraBridgeBackend(args.bridge_port, args.bridge_model_id)
        except ValueError as exc:
            parser.error(str(exc))
        if args.bridge_port == args.port:
            parser.error("gateway and bridge must use different loopback ports")
    elif args.bridge_port is not None or args.bridge_model_id is not None:
        parser.error("bridge options require --upstream-backend vera-bridge")
    with BoundedServer(("127.0.0.1", args.port), Handler, token,
                       journal=journal, backend=backend,
                       journal_scope=args.journal_scope) as server:
        print("Vera inference gateway listening on loopback:", args.port, flush=True)
        server.serve_forever(poll_interval=0.5)


if __name__ == "__main__":
    main()
