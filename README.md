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

## Integration rule

The canonical Vera portfolio currently classifies this repository as `NO_AUTO_BIND`. Populating source does not change that. Runtime binding requires a separate reviewed transport contract, current endpoint evidence, authentication design, effect-authorization semantics, and behavioral qualification.

See [docs/ARCHITECTURE_V1.md](docs/ARCHITECTURE_V1.md) and [docs/SECURITY_MODEL_V1.md](docs/SECURITY_MODEL_V1.md).
