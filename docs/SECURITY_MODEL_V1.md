# Vera APK Security Model V1

## Threats

- a compromised or stale client trying to self-authorize;
- replay of an old approval;
- UI confusion between requested and completed actions;
- credential leakage into logs or repository state;
- cached data being mistaken for canonical memory;
- endpoint substitution or downgrade;
- background execution exceeding the user's current intent.

## Invariants

- Default state is unbound.
- No effect-capable path proceeds without an explicit authorization token.
- A token's presence is only a client precondition; remote systems must revalidate it.
- The client never treats a successful HTTP submission as a verified outcome.
- Secrets are not logged.
- Local cache is disposable and non-authoritative.
- Background activity must be separately bounded and user-visible.
- Transport activation is explicit and reversible.

## V1 non-goals

V1 does not implement authentication, remote transport, push messaging, background agents, microphone/camera capture, device administration, accessibility-service control, or privileged Android permissions.
