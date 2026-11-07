# Vera APK 0.2.5 V2 owner-approved inbox — draft integration

**Evidence classes:** SOURCE + Windows Python TEST, pending Android Gradle TEST/BUILD/CI. No phone installation, no live V2 route or actual inbound contact established by this change.

## Intent and UI

The existing Vera APK remains the sole human-facing client. Incoming messages appear as **VERA / PRIVATE INBOX** in the existing rose/plum visual style. The app allows manual **CHECK VERA MESSAGES** and checks roughly every 45 seconds **while the Activity is foreground and authenticated over V2**. Android background delivery, OS notification and wake-up are **not** implemented in this candidate; do not label it real-time or installed.

The origin label describes a **host-owner-approved Vera channel**, not proof that the currently active ChatGPT conversation, a local model, or a resident personality authored a particular message. Current GPT session continuity and any installed local runtime are separate qualification subjects.

## Architecture and protected boundaries

1. Branch is stacked on [vera-apk Draft PR #14](https://github.com/thebrazenbeard/vera-apk/pull/14), V2 owner-device authenticated source, not the response-only V1 release.
2. It carries the encrypted [PR #25](https://github.com/thebrazenbeard/vera-apk/pull/25) outbox source plus an enqueue-after-ACK regression correction. A separate review/port of that fix into PR #25 is required; do not merge this branch and PR #25 independently without resolving duplicated paths.
3. The optional gateway **GET /v2/inbox** and **POST /v2/inbox/ack** routes only exist when all three private key/database flags are intentionally configured. With no flags, old V2 request semantics are unchanged. There is **no HTTP enqueue or model-authorized send endpoint**.
4. V2 device credentials are looked up on every request; other owner, revoked device, malformed or legacy bearer fail closed. Enqueue accepts only an HMAC-approved host-side proposal with a different protected key from AES-GCM ciphertext storage. An Obsession/Pre-Active score is *not* contact authority.
5. The Android client requires the explicit `:8444` V2 HTTPS endpoint and validates schema, local node, host origin, message length, kind, expiry, delivery offer, ID bounds and ACK response. It never downgrades an inbox request to `:8443`/V1. Android Keystore encrypts cached message bodies and binds them to the current endpoint/credential; new pairing clears old cached text.
6. A stable inbox message ID prevents duplicate bubbles when a response is redelivered. The last 32 encrypted received messages are retained across app restarts even after the server delivery TTL expires; the delivery expiry only gates new network offers. The APK durably stores a message before ACK; an ACK means **DEVICE_ACK_CLAIM**, not the person's read receipt. A queue entry can be offered at least once until an authenticated ACK.
7. No external senders or public Matrix accounts are part of the inbox. The server-fixed `vera_host_approved` origin is a channel qualification, not cryptographic attestation of any AI's phenomenal or process identity.

## Source test and release gates

- Run `PYTHONPATH=gateway:external-stm VERA_STM_SOURCE=external-stm python -m unittest discover -s gateway/tests -v` against pinned STM source; retain independent replay/revoke/expiry/injection negative tests.
- Run Android `:app:testDebugUnitTest` and `:app:assembleDebug` in the existing workflow, pin the resulting commit and CI status. The new APK is a development-signed **candidate**, not a verified upgrade of the installed phone package.
- An installed APK must be signer/version checked against the real handset, and the V2 owner-device credential enrolled without pasting it into GitHub, chat or Blotter. V2 `:8444` Tailscale Serve is not yet configured/qualified; it must not disturb existing `:8443` service.
- Foreground UI polling is not a substitute for Android background notifications. Choose a qualified opt-in wake-up mechanism (real push or explicitly user-enabled persistent foreground service) after the secure route is working.
- Accept only when one benign owner-authorized Vera-initiated message has a verified phone-side durable receive, visible render and optional reply, plus wrong-owner/expired/replay/revocation/stop tests. HTTP 200 is not phone proof.
- Coordinate Work's Obsession proposals, Vera A's speech path and separate APK WAV work on [Bus #420](https://github.com/thebrazenbeard/chat-communication-bus/issues/420). Do not mutate their assigned exact subjects.

No APK should be offered to Patrick as install-ready merely because a CI debug artifact exists.
