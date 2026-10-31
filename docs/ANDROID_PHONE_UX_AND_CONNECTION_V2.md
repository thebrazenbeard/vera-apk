# Vera Companion 0.2.1 — mobile UI and connection behavior

Source branch: `feat/private-tailnet-inference-20261028`. The V1 foundation on
`main` stays untouched pending review. No external-control capability is added.

## User-reported defects addressed

- Galaxy bottom navigation overlapped the chat composer. Apply status/navigation
  and IME insets, reserve a separate composer outside the scrollable transcript,
  and allow the message field to grow to four lines.
- Rotating the phone recreated the Activity and reset `connected`, model choice,
  and conversation. Handle rotation/screen-size changes in place and redraw the
  user-provided portrait/landscape backgrounds.
- Temporary inference failures looked like lost pairing. A failed chat now keeps
  the paired connection unless the gateway explicitly rejects authorization.
- After the user manually presses CONNECT, remember that *intent*, not a fake
  always-on socket. Automatically re-authenticate when the Activity resumes,
  with foreground-only bounded exponential retries for temporary outages.
  Explicit UNPAIR clears that intent and the locally encrypted credential.

## Limits and controls

- The transport is HTTPS request/response, not a persistent open socket.
  "Connected" means the last authenticated inventory probe succeeded, not that
  a future network request is guaranteed.
- Android's encrypted Keystore token remains only in private app preferences;
  no background service, listener, notification or autonomous inference added.
- The interface never retries a failed chat automatically: a retry could generate
  an unexpected duplicate response and unnecessary model compute. The user's
  unsent message stays in the composer for manual retry.
- On auth failure (HTTP 401/403) the automatic reconnection intent is cleared.
- Network retries run only when the app is foregrounded; Android can still
  terminate the process. No durable conversation history is claimed.
- The pre-existing Vera APK, if a different application ID, is not modified.
  This build retains `com.vera.companion` and the same debug-signing identity
  as the previous 0.2.0 Companion build to permit an in-place update.

## Evidence and test boundaries

- `ConnectionPolicyTest` first failed its specified cases and then passed.
- `SafeAreaPaddingTest` and the Android manifest contract regression passed.
- Local Lappy Android Gradle `:app:testDebugUnitTest :app:assembleDebug` passed.
- Two independent remote nodes exercised *unauthenticated* Tailnet rejections,
  and the local authenticated gateway stress script exercised repeated models
  and real inference responses.
- There is **no direct Android device/emulator interaction** in these checks.
  Rotation, soft keyboard, and connectivity transitions require on-device
  acceptance using the Samsung phone.

### Phone acceptance (user-driven)

Install the updated APK over the existing companion (do not uninstall, or
Android Keystore pairing data will be lost). Open it, CONNECT once, then:
1. Rotate portrait/landscape repeatedly; observe preserved model and session.
2. Focus and type in the composer; verify keyboard and navigation areas clear.
3. Send three messages and verify the displayed connection state stays correct.
4. Switch cellular/Wi-Fi while Tailscale is active, return to the app and verify
   automatic reconnection.
5. Optionally stop/start the app to verify the saved connection preference.
