> **License:** Source-visible, not open source. Original material is proprietary. Commercial use, redistribution, hosted-service use, and commercial derivative products require written permission. See [LICENSE](LICENSE) and [COMMERCIAL_LICENSE.md](COMMERCIAL_LICENSE.md). Separately identified third-party components retain their own licenses.

# vera-apk

Android companion surface for Vera.

This repository is intentionally a **client**, not Vera's identity, memory authority, control plane, or permission source. The current V1 foundation provides a native Android shell plus an explicit capability gate. It starts unbound and performs no network or external effect by default.

## V1 boundary

`CLIENT_UI != AUTHORITY`

`LOCAL_CACHE != CANONICAL_MEMORY`

`RENDERED_ACTION != AUTHORIZED_EFFECT`

`CONNECTION_AVAILABLE != CONNECTION_ACTIVE`

The app may eventually observe approved Vera state and submit explicitly authorized requests through a separately qualified transport. It must not manufacture authority locally.

## Current foundation

- Java 17 Android application with no third-party runtime dependencies.
- Android Gradle Plugin 9.4.0 / Gradle 9.6.0 baseline.
- API 37 compile/target baseline; minSdk 29.
- Local status screen that reports the client as unbound.
- `CapabilityGate` reference mechanism requiring an explicit effect authorization token before an effect-capable UI path may proceed.
- Unit tests for the capability gate.
- CI build/test workflow.
- Architecture and security contracts under `docs/`.

## Build

Requirements:
- JDK 17
- Android SDK Platform 37
- Gradle 9.6.0

```bash
gradle :app:testDebugUnitTest
gradle :app:assembleDebug
```

No production endpoint, credential, signing key, or Vera runtime route is stored in this repository.

## STM and cross-device memory status (2026-10-28)

The selected Vera STM lifecycle is **day-30 historical-review eligibility and day-45 local source expiry** for new, explicitly consented archived conversation turns. This Android client does **not** capture or archive user conversations automatically and does not own canonical memory.

The STM library's optional Android/Linux local AF_UNIX adapter can verify a same-device kernel UID only when a trusted Android PackageManager resolver checks the current full package set, signing certificate and Android user profile. That local check is **not** identity proof for a phone talking to a Windows PC over Wi-Fi, Tailscale or other transport. No cross-device pairing, authorized private-memory channel, account binding or live Vera conversation ingestion is established here. The Android app remains `NO_AUTO_BIND`.

Future cross-device memory requires user-visible pairing and revocation, mutual device authentication, TLS-protected transport, an independently verified owner binding, explicit consent and category-scoped authorization. Private-history transfer to DeepMemoryStorage needs a separate reviewed write contract; it must not target the public Git repository.
## Integration rule

The canonical Vera portfolio currently classifies this repository as `NO_AUTO_BIND`. Populating source does not change that. Runtime binding requires a separate reviewed transport contract, current endpoint evidence, authentication design, effect-authorization semantics, and behavioral qualification.

See [docs/ARCHITECTURE_V1.md](docs/ARCHITECTURE_V1.md) and [docs/SECURITY_MODEL_V1.md](docs/SECURITY_MODEL_V1.md).