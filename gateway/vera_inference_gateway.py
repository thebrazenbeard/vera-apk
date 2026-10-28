#!/usr/bin/env python3
"""Vera phone-to-local-Ollama response-only gateway.

Bind ONLY to loopback. Publish through authenticated Tailscale Serve HTTPS,
never via a router port-forward or public Tailscale Funnel.
"""
import argparse
import hmac
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import re
import socket
import threading
from urllib.request import Request, build_opener, ProxyHandler

MAX_BODY = 32768
MAX_REPLY = 16000
OLLAMA_ROOT = "http://127.0.0.1:11434"
OPENER = build_opener(ProxyHandler({}))


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


def valid_chat(payload, allowed):
    if type(payload) is not dict or set(payload) != {"model", "messages"}:
        raise ValueError("chat schema invalid")
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
    def __init__(self, address, handler, token):
        self.token = token
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
            self.respond(200, {"models": models(), "node": "local", "mode": "response_only"})
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
            model, messages = valid_chat(strict_json(raw), models())
        except (ValueError, TypeError, UnicodeError, AttributeError):
            return self.respond(400, {"error": "invalid chat request"})
        except Exception:
            return self.respond(503, {"error": "model inventory unavailable"})
        try:
            result = ollama("/api/chat", {"model": model, "messages": messages,
                "stream": False, "options": {"num_predict": 256}}, timeout=90)
            answer = result.get("message", {}).get("content")
            if type(answer) is not str or not 1 <= len(answer) <= MAX_REPLY:
                raise ValueError("invalid model response")
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
    args = parser.parse_args()
    token = args.token_file.read_text(encoding="ascii").strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{32,128}", token):
        parser.error("invalid pairing token file")
    if not 1024 <= args.port <= 65535:
        parser.error("port out of range")
    with BoundedServer(("127.0.0.1", args.port), Handler, token) as server:
        print("Vera inference gateway listening on loopback:", args.port, flush=True)
        server.serve_forever(poll_interval=0.5)


if __name__ == "__main__":
    main()
