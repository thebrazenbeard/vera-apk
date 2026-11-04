# APK host-backed inference candidates

This is a syntax-only, fail-closed discovery seam. The Vera Android companion can label a possible inference host as **Lappy**, **VN1**, or **VN2**, and validate an explicitly entered HTTPS origin. A valid candidate is **not** a connection, pairing, host identity check, API health check, authorization grant, or inference capability.

## Boundary

- Host-backed inference means a phone connects to a separate model-serving computer, potentially over an authenticated Tailscale route. It is **not** on-device Android inference.
- The Android application currently has no Internet permission, API client, credential storage, trusted host identity, or established inference contract; this change does not add any of those. No network call is made and the candidate is not persisted.
- The parser requires an HTTPS origin without URL credentials, path, query, fragment, whitespace, or a loopback hostname. A successfully parsed origin does not authenticate the server or validate its certificate, and does not prove that the host exists.
- Do not embed tailnet names, private addresses, tokens, credentials, or TLS certificate-validation bypasses in this app.
- Future actual connection requires verification of the real Lappy/VN host identity, runtime API and version contract, certificate trust, authentication and authorization scope, consent/revocation, timeout and recovery behavior, plus device-side tests before enabling networking.
- A genuine phone-local GGUF runtime is a separate effort requiring Android hardware, RAM/storage/thermal qualification and an explicit on-device model contract; a host's 4 GB VRAM limit says nothing about phone runtime availability.

## Verification

Run `./gradlew :app:testDebugUnitTest` in a configured Android SDK/Java 17 environment. The focused pure-Java tests exercise accepted host labels and rejected origins. A successful unit test is not evidence of Android UI usability, actual host networking, TLS trust, model response, or end-to-end local inference.

This work does not incur hosted runtime spending or introduce paid dependencies.