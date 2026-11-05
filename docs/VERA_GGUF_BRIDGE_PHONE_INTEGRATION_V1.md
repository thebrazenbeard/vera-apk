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

## 2026-11-05 follow-up: optional persona-governed interface composition

The raw `/v1/chat/completions` GGUF bridge above does **not** inject Vera's
pinned conversational profile, even though the UI calls itself Vera. It also
does not forward `finish_reason=length|content_filter` as an Android status.
Those are real limitations of the earlier bridge path. Neither behavior
should be mistaken for qualified local Vera personality or memory.

Stacked source-only APK changes add an **explicit** third backend,
`--upstream-backend vera-interface`, compatible with the draft `v-e-r-a`
governed browser interface PR #27 (exact inspected head
`13ad06d45b8b9f2b5d89ce143699f4256501edf3`). The old default Ollama
and optional raw bridge remain unchanged. This path is also **not deployed**.

```text
Android APK --existing Tailscale HTTPS/pairing bearer--> phone gateway
phone gateway --bounded loopback, CSRF session--> v-e-r-a /api/chat
v-e-r-a --pinned Vera behavior profile--> locally qualified model backend
```

After separate host/model/interface qualification, an operator may select it
on an isolated gateway listener by passing the same exact port/model flags:

```text
python gateway/vera_inference_gateway.py --token-file <PRIVATE_FILE> \
  --port 18777 --upstream-backend vera-interface \
  --bridge-port <QUALIFIED_LOCAL_INTERFACE_PORT> \
  --bridge-model-id <EXACT_LIVE_MODEL_ID>
```

The port and model values above are placeholders, not deployment findings.

- The gateway obtains `/api/session` locally, then checks `/api/status` and
  `/api/models`; the upstream CSRF token never goes to Android, journal,
  logs or the ordinary phone response. It is **not** durable authentication.
- A response is accepted only with the pinned `VERA_BEHAVIOR_PROFILE_V1`
  profile/presentation Git-blob receipts and explicit
  `SOURCE_ONLY`/`server_owned_system`, `trained_weights_modified=false`,
  `identity_attested=false` claims. These prove a server configuration
  claim, **not** learned model identity or conversational quality.
- All phone traffic remains bearer-authenticated and response-only. The
  interface receives exactly `model` and bounded `messages`, never private
  vault capabilities, `recall_saved`, tool calls, external-action authority,
  or the phone bearer. Failure never falls back to the raw bridge.
- Governed conversations use at most five saved pairs plus the current user
  message, eleven alternating turns total (within the interface's twelve-
  message limit). Each turn is at most 4000 characters, aggregate 16000.
  The existing journal retention and pairing-epoch controls remain in force.
- The gateway forwards validated `response_completion_status` values
  `complete|length_limited|filtered|unknown`, the matching tri-state
  truncation/incompleteness fields, and the response token cap. Android
  displays a visible state warning for incomplete or unknown replies while
  retaining old `GatewayClient.chat(...)` as a compatibility adapter.

The new `gateway/tests/test_vera_interface_backend.py` exercises two local
mock HTTP servers and actual gateway routing. Passing those tests does
**not** establish a live phone build, Qwen inference, profile effectiveness,
session resilience under process restart, or installed runtime identity.

## 2026-11-05 W47: completion provenance and divergent upstream warning

The optional raw `vera-bridge` backend now preserves its upstream validated
OpenAI-compatible `finish_reason` on the response-only phone reply:

| Upstream `finish_reason` | Phone completion status | Incomplete | Truncated |
| --- | --- | --- | --- |
| `stop` | `complete` | false | false |
| `length` | `length_limited` | true | true |
| `content_filter` | `filtered` | true | false |

This is only a **reported decoding outcome**; it does not attest model
identity or install Vera's behavior profile. The Android client accepts a
typed completion receipt **without** `persona_source` in this raw-bridge
case; if a persona source *is* supplied, its SOURCE_ONLY/authority fields
must still validate. Existing `VeraBridgeBackend.chat()` remains a text-only
Python compatibility adapter. Legacy Ollama remains unchanged and continues
to omit completion metadata; no fabricated `complete` status is supplied.
Android labels a typed raw-bridge reply **LOCAL MODEL** with a visible
`Vera persona not configured` status. Legacy Ollama's preexisting display is
unchanged when no completion receipt exists; no identity is inferred from
that older path either.

**Partial conversation replay:** A `length_limited`, `filtered`, or `unknown`
reply remains visible in the current Android transcript with its status,
but neither its user question nor its incomplete assistant answer enters
subsequent in-memory model history. The gateway also omits that pair from
encrypted STM journaling: the existing journal API has no typed completion
column, so writing the partial text would silently replay it as complete
on the next request. A later complete answer *does* enter history normally.
This intentionally sacrifices cross-turn recovery of partial answers until
a separately reviewed, completion-aware journal schema exists. Historical
rows written before this patch cannot be retroactively classified.

**Live draft incompatibility found:** At exact `v-e-r-a` PR #24 head
`22b7dbbff1b1407a7d8fdc604a5182da8f7c10dc`, `/api/status` offers only
`persona_prompt=pinned_owner_profile` and `model_identity_attested=false`,
not the pinned `persona_source` receipt. Its `/api/chat` also lacks the typed
completion contract of PR #28 (head
`a8384bcb44f6160146c2e7ada4f3394b2128ee37`, stacked on PR #27).
The governed `vera-interface` APK backend therefore **must reject PR #24
with 503**; a mock regression test enforces this. Independent green CIs
for both incompatible drafts do **not** establish composed runtime success.
The two upstream histories require explicit source reconciliation and
fresh integration qualification before any phone/host deployment.

## 2026-11-05 W48: exact hybrid upstream contract (draft-only)

`v-e-r-a` [Draft PR #30](https://github.com/thebrazenbeard/v-e-r-a/pull/30)
at exact reviewed head `9aa153aaf361c7a562d967f53c395d03afcf91d7`
and later exact updated head `5c14304b00679dd17add6c25d709cb042e414ba2`
reconciles the owner-provisioned #24 persona rights model with #28's typed
response status. Its `interface/persona_contract.py`, `persona_profile.py`
and `server.py` were inspected for this phone adapter. No proprietary owner
profile or presentation bytes are copied into this repository.

The phone gateway's opt-in `vera-interface` composition has these source
conditions, enforced by `_profile_ok` on **both** `/api/status` and
`/api/chat`:

| Owner-provisioned upstream state | Receipt | APK treatment |
| --- | --- | --- |
| Exact approved profile JSON **and** presentation MD, both locally verified | Pinned Git blobs `0c79625b...` and `887bfe1d...`; `SOURCE_ONLY`, server-owned system prompt, no attested identity | Accept configured source and typed completion if exact model and response schema also match |
| Neither file configured | `qualification=NOT_CONFIGURED`, `prompt_layer=none` | 503; no generic fallback |
| Profile file verified but presentation missing | `SOURCE_ONLY` with no presentation blob | 503; no partial persona promotion |
| Changed hash, promoted identity claim or changed source between status and chat | Mismatched receipt | 503 |

The updated hybrid receipt also states
`presentation_implementation=ADMITTED_SOURCE_REFERENCE_ONLY` when the
presentation MD bytes pass admission. The APK test asserts that field survives
through `/api/chat`; this **only means the file reference was checked**. It
does not mean bracketed gestures, the nonverbal status-bar contract or other
presentation behavior has been rendered into the active model prompt or
validated in a live conversation.

`gateway/tests/test_vera_interface_backend.py` now contains a deterministic
mock of the published #30 wire shapes, configured success, generic mode,
profile-only mode and adversarial forged/stale receipts. It neither provisions
private source files nor validates that the hosted model actually follows the
configured conversational behavior. Source composition remains **candidate**
until the exact APK+web draft stack is integrated, installed and checked on
an owner-authorized local host. The gateway's model inventory gate currently
requires the configured exact model as the sole exposed entry; additional
installed models will fail closed rather than silently changing the choice.
