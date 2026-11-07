# Vera APK: local speech output contract V0 (source-only candidate)

## Ownership and current qualification

- `vera-mono` owns the future speech renderer. An in-memory `SpeechWave` WAV result is a proposed bridge output, **not** an authenticated connection to this Android client.
- `vera-apk` owns device speaker delivery. This patch supplies a bounded WAV decoder and opt-in `AudioTrack` playback primitive only. It does **not** connect the app UI, fetch from the gateway, install an APK, or demonstrate sound from a phone.
- Existing stacked Android Draft PRs (notably #10 and #23) own the direct Tailscale HTTPS/bearer gateway and chat flow. This isolated addition does not edit their source. Integration needs coordination and new review at the then-current head.
- No Matrix SDK, login, room, voice-message sending, or media upload is included. The separate VN2 Tuwunel homeserver is not an APK account or proof of messaging capability.

## Candidate boundary

1. A **visible, explicit user tap** invokes `VoiceWavePlayer.playFromUserTap(context, wavBytes)`; do not call it from a background observer or automatically after a model inference.
2. `VoiceWav16.parse` accepts only uncompressed RIFF/WAVE PCM **16-bit little-endian**, mono or stereo, sample rate 8–48 kHz, at most 6 MB including headers and at most 30 seconds of PCM; it verifies RIFF and chunk sizes, format arithmetic, and frame alignment. All other payloads fail closed.
3. The player requests transient Android audio focus, writes the entire PCM payload before playback, plays through `AudioTrack`, then releases native resources at the playback marker. The Activity must also close the returned player on `onStop()`/`onDestroy()`, and immediately when user stops playback. Focus loss closes it.
4. No recording, local file, history, cache, background agent, upload, message, credential, voice model, or Suno audio/reference is included.

## Compatibility with speech-engine candidate

The renderer's output advertises sample rate, channels, frame count, digest and evidence class. **Do not trust those claims in place of parsing the WAV payload.** Its supported PCM sample widths may include 8/24/32-bit, which this Android V0 intentionally rejects. A later authorized adapter may request/convert a 16-bit format; this patch does not invent a lossless conversion or claim end-to-end interoperability.

## Validation and remaining gates

- Run local JVM decoder unit tests or Gradle `:app:testDebugUnitTest` with an available JDK/Android SDK. Parser unit tests do not verify Android `AudioTrack` or actual audio focus.
- On an explicitly authorized target phone, qualify Android build, foreground tap/focus, speaker output, lifecycle interruption, unsupported format errors, and focus contention; record exact APK hash and device runtime evidence.
- To integrate with the gateway or Matrix later, establish authenticated authorization, provenance, media transport, explicit per-message send approval, E2EE expectations, and no silent capture/send. No such effects are authorized by this source patch.

> Hostile review: A WAV render is not proof of a speaking voice or a Matrix voice message. A callable Android output method is not a user gesture. Test the adapter that binds a genuine UI event, and distinguish static source code from an installed, audible device result.
