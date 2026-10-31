#!/usr/bin/env python3
"""One-shot, non-secret-emitting live gateway probe."""
import argparse
import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

def fetch(url, token=None, payload=None):
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    raw = None if payload is None else json.dumps(payload).encode("utf-8")
    if raw is not None:
        headers["Content-Type"] = "application/json"
    req = Request(url, data=raw, headers=headers,
                  method="POST" if raw is not None else "GET")
    try:
        with urlopen(req, timeout=95) as response:
            return response.status, json.loads(response.read(65536))
    except HTTPError as error:
        return error.code, json.loads(error.read(65536))

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--url", required=True)
    p.add_argument("--token-file", type=Path, required=True)
    args = p.parse_args()
    base = args.url.rstrip("/")
    code, _ = fetch(base + "/v1/models")
    assert code == 401, "anonymous model inventory must fail"
    secret = args.token_file.read_text(encoding="ascii").strip()
    code, info = fetch(base + "/v1/models", secret)
    assert code == 200 and info.get("mode") == "response_only"
    models = info["models"]
    assert models, "no available local models"
    model = next((x for x in models if x == "vera-local:latest"), models[0])
    code, reply = fetch(base + "/v1/chat", secret,
                        {"model": model, "messages": [{"role": "user",
                         "content": "Reply with one word: READY"}]})
    assert code == 200 and reply.get("mode") == "response_only"
    assert isinstance(reply.get("reply"), str) and reply["reply"].strip()
    print("PASS anonymous=401 authorized_models=" + str(len(models))
          + " model=" + model + " reply_chars=" + str(len(reply["reply"]))
          + " mode=" + reply["mode"])

if __name__ == "__main__":
    main()
