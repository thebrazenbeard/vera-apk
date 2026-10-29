# Vera Android Companion 0.2.4 — explicit V2 owner sessions (source candidate)

Source branch based on Vera APK V2 draft PR #12 at exact commit
`9bbcd3f78508200557146bd7adddb74a072ea3aa`.

## Changes
- **V1 unchanged:** Existing private Tailscale HTTPS `:8443` remains the
  working response-only V1 gateway. Nothing on Lappy's `:18777` or Serve
  configuration has been modified. The original portrait/landscape art,
  app icon, composer and connection-retry behavior remain.
- **V2 is opt-in by endpoint:** `:8444` is the dedicated prospective
  Tailscale Serve address. No connection attempted to :8444 automatically,
  and a :8444 failure must never be retried against :8443 or V1 routes.
- On a user-saved :8444 endpoint with a **separately provisioned device bearer**
  entered through the existing encrypted settings, Android calls
  `/v2/models` and the server-issued owner-scoped `/v2/sessions`,
  `/v2/sessions/{id}/history`, `/v2/chat` routes.
- The approved V2 device credential is stored through existing **Android
  Keystore AES-256-GCM** (not plain SharedPreferences), with no backup of
  secrets. The opaque server-issued session ID is a rejoin hint, **not
  an authenticator**. On reconnect, the app selects the last previously
  accepted owner session (or an authorized session from the server) and
  restores up to twenty encrypted journal exchanges. New Secure Chat asks
  the V2 server to create a fresh owner session.
- V2 sends use the selected server-issued session and new random request
  IDs. Inference occurs only on the server; uncertain delivery restores the
  draft with a check-history warning, to avoid blind duplicate requests.

## Evidence and remaining gates
- Lappy offline Gradle 9.6.0/Android SDK 37 `:app:testDebugUnitTest`
  and `:app:assembleDebug`: successful, build exit 0.
- Four additional Python source-contract checks passed. Existing V2
  backend suite passed 35 tests before the new Android source patch;
  39 tests pass after it. This is **SOURCE + BUILD evidence**.
- Version `0.2.4`, code 6, package `com.vera.companion`. Built APK
  is a **development-signed** candidate, NOT tested on a physical Android
  device. Do not install it as a V2 migration until pairing is ready.

**DO NOT CLAIM PRODUCTION V2:** The V2 gateway has no persistent qualified
production process and `:8444` is not configured in Tailscale Serve.
There is no out-of-band owner-approved V2 device-bearer enrollment yet.
Original 0.2.3 phone conversations are not silently assigned to a new owner.
A legacy V1 shared bearer was exposed in a prior assistant chat and must
be rotated after a continuity-preserving migration, not sent in chat again.
The complete ChatGPT account export is still pending from the user.

Security guidance: Android's EncryptedSharedPreferences is deprecated;
retain the existing AndroidKeystore AES-GCM implementation rather than
reintroducing deprecated APIs. Tailscale Serve headers are identity-bearing
only under the documented loopback-only proxy trust boundary; this patch
does NOT assume those headers prove V2 owner authentication or
automatically authorize a shared-tailnet user.

Next gate: a separate local admin-approved pairing exchange, robust
attestation/owner binding, per-device credential revocation and restart
readback, live VPN-correct `:8444` route only after owner approval, and
physical phone Wi-Fi/cellular/rotation acceptance. Keep all source PRs
draft until qualified.
