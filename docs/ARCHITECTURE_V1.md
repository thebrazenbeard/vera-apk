# Vera APK Architecture V1

## Role

`vera-apk` is a presentation and request-orchestration client.

It may:
- render approved state;
- collect user intent;
- prepare bounded requests;
- display verified receipts;
- cache non-authoritative presentation state.

It may not:
- become Vera's canonical memory;
- define Vera's identity;
- mint effect authority;
- silently activate a transport;
- treat local UI state as proof of remote state.

## Layers

1. **Presentation** — Android activities/views and local rendering.
2. **Client policy** — capability gating and local fail-closed checks.
3. **Transport adapter** — future authenticated route; absent in V1.
4. **Remote authority** — external to this repository; must independently validate every requested effect.
5. **Receipt/readback** — future remote result returned to the client and clearly distinguished from request submission.

## Currentness

Any future mutable remote fact must include a read/observation time or exact revision. Cached state is stale-tolerant UI material, not canonical truth.

## Effect lifecycle

`INTENT -> LOCAL_GATE -> TRANSPORT_REQUEST -> REMOTE_AUTHORITY_CHECK -> EFFECT_ATTEMPT -> READBACK -> VERIFIED_OUTCOME`

V1 implements only the local gate and presentation shell.

## Secrets

No production secret belongs in Git. Future credentials should use Android platform credential facilities or another separately reviewed protected channel.
