"""Private Vera gateway stress probe: no secrets/prompts in output."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
from time import monotonic
from urllib.request import Request, urlopen
from urllib.error import HTTPError

def call(base, token, path, data=None, timeout=95):
    headers = {"Accept":"application/json"}
    if token: headers["Authorization"] = "Bearer " + token
    payload = None if data is None else json.dumps(data).encode()
    if data is not None: headers["Content-Type"] = "application/json"
    req = Request(base + path, data=payload, headers=headers,
                  method="POST" if payload else "GET")
    try:
        with urlopen(req, timeout=timeout) as f:
            return f.status, json.load(f)
    except HTTPError as e:
        return e.code, json.load(e)

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--url", required=True)
    p.add_argument("--token-file", type=Path, required=True)
    p.add_argument("--models", type=int, default=120)
    p.add_argument("--chats", type=int, default=12)
    args = p.parse_args()
    token = args.token_file.read_text(encoding="ascii").strip()
    base = args.url.rstrip("/")
    started = monotonic()
    errors = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        jobs = [pool.submit(call, base, token, "/v1/models", timeout=15)
                for _ in range(args.models)]
        for item in as_completed(jobs):
            try:
                code, reply = item.result()
                if code != 200 or reply.get("mode") != "response_only" or not reply.get("models"):
                    errors.append("inventory")
            except Exception as ex:
                errors.append(type(ex).__name__)
    code, models = call(base, token, "/v1/models")
    assert code == 200
    model = next((m for m in models["models"] if m.startswith("qwen2.5-coder:1.5b")),
                 models["models"][0])
    for i in range(args.chats):
        code, response = call(base, token, "/v1/chat",
            {"model": model, "messages":[{"role":"user","content":"Reply READY only."}]})
        if code != 200 or response.get("mode") != "response_only" or not response.get("reply"):
            errors.append("chat:" + str(i))
    code, _ = call(base, None, "/v1/models")
    if code != 401: errors.append("unauthorized allowed")
    code, _ = call(base, token, "/v1/chat",
                   {"model": model, "messages":[{"role":"system","content":"forbidden"}]})
    if code != 400: errors.append("system role allowed")
    print("STRESS", "url_scope", "tailnet" if base.startswith("https:") else "loopback",
          "inventory",args.models,"chats",args.chats,"seconds",round(monotonic()-started,1),
          "failures",len(errors),"first_failure",errors[:3],flush=True)
    if errors: raise SystemExit(2)

if __name__=="__main__": main()
