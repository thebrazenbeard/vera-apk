# W49 physical HTTP transport, wholly synthetic model

This optional integration test exercises the **actual Python HTTP handlers**
across two public source repositories. It does not load any GGUF, model weights,
trained adapter, APK, user credential, or private persona file. Its source pin is:

- `thebrazenbeard/v-e-r-a` Draft PR #30 commit `f3ce7456a291b8e16d004dd1d4e54a51bb98a4dc`.
- `thebrazenbeard/vera-apk` Draft PR #22 commit `f66691246511bdb979ebe0c04e28f45a9ccddcb8` as this test's parent.

The test intentionally resides only in `vera-apk` and uses an **external checkout**
of the exact `v-e-r-a` source through a caller-supplied path. The former is
never copied or vendored. Run from the exact `vera-apk` test checkout:

```sh
VERA_INTERFACE_SOURCE_ROOT=/absolute/path/to/verified/v-e-r-a-pr30-checkout \
  python -m unittest -v gateway.tests.test_real_hybrid_http_interop
```

Without that environment variable, all four cross-repository tests report
SKIP, not PASS. If the supplied repository HEAD is not the pinned SHA, the
run fails until reviewers deliberately qualify the changed source again.

The temporary test topology uses kernel-allocated `127.0.0.1:0` ports:

```text
Synthetic /v1/chat model HTTP server
   <- actual v-e-r-a LoopbackModelBridge HTTP server
   <- actual v-e-r-a /api/chat interface HTTP server
   <- actual vera-apk VeraInterfaceBackend + /v1/chat gateway HTTP server
```

All servers are bound to localhost and shut down after each test. An artificial
owner-profile JSON and a dummy presentation Markdown are written to one
temporary directory. **Only inside the test process**, source admission digests
are mocked to allow these synthetic fixtures. The emitted receipt references
the canonical profile and presentation pins, but those bytes were not admitted:
this validates **cross-process protocol compatibility**, not owner-source
authenticity, behavioral quality, or installed persona. No owner files are
distributed in this test. The test bearer/session tokens are fixed, obviously
non-secret strings used only on these temporary local ports.

What is actually checked over HTTP:

1. The configured source-only persona path successfully traverses all four
   servers, while the raw phone bearer and interface's local session token do
   not reach the model request or return to the phone.
2. Direct interface POST lacking its required `Origin` is rejected with 403,
   and the phone `/v1/models` endpoint rejects requests without bearer (401).
3. The generic/default unconfigured interface is rejected by the governed
   phone backend (503) without silently falling back to an unauthenticated raw
   model persona.
4. `length_limited`, `filtered` and `unknown` generations remain visibly
   typed; an in-memory **test journal double** does not record these as complete
   turns. Later complete questions use coherent history and do not replay the
   incomplete user or assistant fragments. This is gateway transport behavior,
   not actual SQLite/journal encryption qualification.

> **Hostile limitation:** Tests that monkey-patch profile verification must
> never be cited as proving genuine owner-profile admission. The synthetic
> upstream emits fixed sentences rather than reasoning; a successful HTTP
> roundtrip is not evidence of Vera's self-identification, sarcasm comprehension,
> memory, consciousness, personality, trained model, or hardware readiness.
