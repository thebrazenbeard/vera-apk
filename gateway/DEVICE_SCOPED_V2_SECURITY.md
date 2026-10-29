# Vera V2 device identity and scoped encrypted retrieval — source candidate

This branch is layered on the existing Vera Companion 0.2.3 source
(`74156f53e2ca92801c0264e4866eea7d8e8226f9`). It **does not**
replace the live Android Tailscale endpoint or the operator's current journal.
Current gateway is on 127.0.0.1:18777 behind tailnet HTTPS :8443.
The new server is on **127.0.0.1:18781 by default** and has no tailnet
Serve route, Funnel, port-forward or external listener.

## Identity & memory boundaries

- A **trusted Lappy administrator** provisions device credentials using
  `device_gateway_v2.py provision` in a private local terminal. The server
  stores a SHA-256 digest of the randomly generated high-entropy per-device
  bearer; it never logs or distributes the plaintext bearer. There is no
  HTTP enrollment or shared legacy bearer fallback. Tokens can be individually
  rotated or revoked by local administrator action; a revoked credential is
  refused for reads and writes.
- Device records reference a private server-controlled **owner principal**.
  `POST /v2/sessions` makes an unpredictable server-issued session ID bound
  to the authenticated owner; a client-supplied session ID never serves as
  authentication. All historical retrieval is authorized using the *server's*
  principal-to-session association. Different owner denied HTTP 403.
- `GET /v2/sessions` returns bounded opaque IDs for the owner only.
  `GET /v2/sessions/{id}/history` retrieves bounded (20 turns/48 KiB)
  **decrypted**, previously AES-GCM-sealed history for the same owner; the
  untrusted data is not upgraded into memory facts, tools or identity.
  `POST /v2/chat` is response-only; it reads prior same-owner turns,
  validates model existence, appends successful user+assistant turns to the
  existing encrypted STM `EncryptedJournal` implementation. There is
  no arbitrary file access, agent tool execution or history dump endpoint.
- Source integration uses exact STM journal commit
  `64e95a2478447b07c42b85e3300bef6cd7b6296e` in CI.
  Old 0.2.3 phone sessions are **not** retrospectively added as
  V2-owned sessions, because there is no attested proof they belong to
  a particular owner.

## Qualification evidence

- 9 registry adversarial tests and 5 HTTP adversarial tests,
  including two device tokens for same owner, different owner forbidden,
  revocation, rotation, wrong/legacy token, malformed request and safe
  encrypted journal readback; 33 total gateway suite tests on Lappy.
- A separate *real local inference* V2 smoke test created two synthetic
  device credentials for one owner and a third for another; invoked
  `vera-local:latest` through the V2 HTTP gateway; retrieved the turn using
  the second device; saw HTTP 403 for the other owner and revoked device;
  checked ciphertext not plaintext; destroyed all synthetic test files
  and closed the test listener. This does **not** qualify real phone onboarding.
- The original production listener at :18777 and Tailscale HTTPS :8443
  were left untouched. No V2 credential was issued for the user's real phone.

## Unresolved gates

1. A separately reviewed on-device **owner-confirmed pairing flow**, with
   protected device credential storage, delivery, revocation and rotation.
   The initial local administrative provisioning command is not adequate
   remote phone onboarding.
2. Prove session lifecycle, concurrent request/duplicate response handling,
   process-restart persistence, key rotation, retention/deletion and denial
   under multi-process operation. The current storage lock is **in-process**,
   not a global distributed transaction. Existing STM v0.5/v0.6 30-day
   review proposals are unmerged and not qualified runtime policies.
3. Authenticate principal/session access *independently* on Android, desktop
   and Linux. Keep export/history unavailable to legacy shared-token clients.
4. Audit sensitive plaintext handling in memory/HTTP, machine ACLs for
   access registry + journal key, backups, tampering and error/log redaction.

No external service was restarted and no data was migrated or deleted.
