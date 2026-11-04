# Vera Companion → guarded GGUF bridge (source-only candidate)

**Status: DRAFT / NO_NEW_DEPLOYMENT / NO_OFFICIAL_QWEN_ADMISSION.** This
optional backend is based on APK PR #10's authenticated phone gateway and
`thebrazenbeard/v-e-r-a` PR #24's loopback OpenAI-compatible GGUF bridge.
Neither draft is merged into its repository's `main` here.
This is a **V1 gateway** adapter only; independent V2 owner-scoped session,
revocation and STM work in stacked APK PRs #12/#14/#15 is not included,
qualified or superseded by this branch. No V2 credential downgrade or
automatic migration is offered.

The existing Android app still talks ONLY to its authenticated, owner-paired
Tailscale Serve HTTPS gateway, with `/v1/models` and `/v1/chat` responses and
encrypted opt-in STM unchanged. The new option changes only that *gateway's*
model provider on the same machine:

```text
Android APK  --HTTPS/Tailscale Serve+Bearer--> 127.0.0.1:18777 phone gateway
phone gateway --no-proxy HTTP 127.0.0.1:11439--> v-e-r-a GGUF bridge
v-e-r-a bridge --guarded loopback HTTP--> separately qualified llama.cpp/KoboldCPP
```

Default remains `--upstream-backend ollama`, using the historical fixed local
Ollama API. To select the source-only bridge path, an owner would need to
qualify the exact local bridge process and model ID, then *explicitly* start
an isolated gateway with, for example:

```text
python gateway/vera_inference_gateway.py --token-file <PRIVATE_FILE> \
  --port 18777 --upstream-backend vera-bridge \
  --bridge-port 11439 --bridge-model-id <EXACT_LIVE_MODEL_ID>
```

That command is illustrative and **has not been executed**. Do not restart
the existing live Lappy phone gateway or reuse its listener without a
separate owner-controlled change window. Do not publish either loopback port
through a public Funnel or direct router forwarding. Real phone acceptance,
TLS device identity, live model identity, resource fit, trained adapter origin
and recovery require independent host evidence.

## Guarded composition contract

- Only an explicit local TCP **port number** is configurable. The model
  backend always resolves to `127.0.0.1`; no hostname, scheme, path, remote
  proxy, redirect, or certificate exception is accepted.
- The operator must supply an exact expected model ID. Before every chat,
  `/health` must advertise `effect_authority=false`, and `/api/tags` must
  identify precisely that one model. These are source-facing consistency
  checks, **not authentication or release grants**.
- Phone bearer authorization happens before contacting the model. Incoming
  messages still allow only bounded `user` and `assistant` text; no tools,
  system messages, model-switch directives or side-effect fields pass.
- **Inherited V1 caveat:** The outer HTTPS phone gateway checks its bearer,
  but does not independently enforce literal HTTP `Host` or `Origin` headers.
  An authorized synthetic request with forged headers still receives a reply.
  This is not a demonstrated browser CSRF (ordinary browsers cannot attach
  the private bearer without preflight, and OPTIONS is rejected), but it is
  not host-origin authentication. The *inner* v-e-r-a bridge independently
  enforces its fixed 127.0.0.1 Host/Origin. A future V1/V2 security change
  should bind the accepted public Host to the qualified owner HTTPS route
  without breaking existing Tailscale Serve forwarding.
- The downstream bridge request uses exact fields `model`, `messages`,
  `stream:false`, `max_tokens:256`. Responses must contain one matching model,
  one assistant text choice and no extensions, function calls or tool calls.
- When encrypted STM is opted in, only six prior user/assistant pairs are
  recalled for this backend, plus the current user question: at most **13**
  messages. The legacy Ollama path retains its eight-pair replay. Aggregate
  bridge text is also bounded to 20,000 characters; this prevents a session
  from failing indefinitely after its seventh saved exchange.
- Any protocol, identity, health, content, size, redirect or deadline failure
  returns 503 and never fabricates a successful model reply. The gateway
  remains `response_only`, not canonical Vera identity or memory authority.
- Every bridge HTTP call uses a monotonic **aggregate** deadline, including
  response-header and response-byte trickles. A timer forcibly shuts down its
  retained socket handle to release workers; six concurrent slow-upstream
  negative probes recover all gateway slots. The bounded policy is not a
  guarantee of upstream model cancellation after the request disconnects.
- The existing optional encrypted STM journal's owner/session/consent rules
  are unchanged; no new automatic knowledge or training input ingestion.

## Evidence and nonclaims

`gateway/tests/test_vera_bridge_backend.py` exercises two real loopback HTTP
servers with a deterministic mock bridge, including authenticated roundtrip,
no-auth rejection, swapped model, tool-effect forgery, unexpected extensions,
redirect refusal, bad UTF-8, an eight-turn STM replay case, and unavailable
upstream. Slow response headers/body and six concurrent drips are also tested
against total deadlines and worker recovery. This is a **source-only
mock contract**, not live Qwen inference, an Android APK build, physical
phone deployment, Tailscale pairing validation, or training evidence.

Real official `Qwen/Qwen3.5-4B` safetensors and October R16 adapter files
currently have separate custody evidence in TRAININGDAY; neither is an
admitted or served GGUF in this bridge. The quarantined third-party Unsloth
Q3 GGUF is not the R16-trained Vera adapter and must not be relabeled as one.
