# Vera 0.2.3 — immediate send acknowledgement and Lappy STM archive

This candidate fixes the user's 2026-10-28 Galaxy report: pressing SEND previously
left the draft in the composer until the full model reply returned.

## Phone behavior

- On tap, validate the message, immediately render its YOU bubble, clear the
  input, and display `Message queued - Vera is generating...`.
- Disable SEND while the request is in flight. On success, append Vera's answer
  and display the actual serving model.
- On transport/auth/model failure, do **not** report delivery; restore the
  outgoing draft if the composer is empty and add an explicit delivery-error
  bubble. Never silently retry an LLM request (could cause duplicate compute).
- The existing Vera wallpapers, local `vera-local:latest` model preference,
  connection settings, rotation and reconnection fixes are retained.

## Local encrypted history

With explicit `--journal-db`, `--journal-key-file`, `--stm-root` flags, the
gateway uses `thebrazenbeard/stm` source branch
`feat/vera-phone-journal-20261028` to archive accepted successful exchanges.
User and assistant text are encrypted with AES-256-GCM at rest in Lappy-only
SQLite. A per-install pseudonymous session ID survives app reopen, and each
send receives a random request ID. The gateway reconstructs up to eight
archived turns (max 14KB) before adding the current user request, rather than
trusting a client-supplied full history. This bounds working context without
deleting the permanent encrypted transcript evidence.

When optional journal configuration is absent, the legacy response-only chat
API is preserved without archiving; older companion APKs lacking session IDs
are accepted but their exchanges cannot be archived by this mechanism.
The encrypted journal and its random 32-byte key live **outside both source
repositories** with operator-specific Windows ACLs. The HTTP API exposes
neither history export nor a deletion endpoint, and no authentication tokens
are stored in chat memory. A local authenticated owner tool can read/delete
sessions. The archive is raw **untrusted** conversational evidence, not an
automatic source of verified facts, long-term semantic memory, training data,
or effect authority.

### Pairing-to-session boundary

On the Android companion, saving a *changed* normalized gateway endpoint **or**
bearer starts a new pseudonymous chat session. Re-saving the identical endpoint
and bearer retains the current session. The preference update writes the new
credential and session ID together, and the visible chat bubbles are cleared
when the pairing changes. An exact same-pair re-save does not invalidate an
in-flight reply or reset the prior connection intent. A changed-pairing
in-flight reply from the previous pairing is not
shown in the new conversation; a request already sent (or racing the epoch
check) may still finish and be archived under its *previous* session. Stale
queued requests are skipped when detected, but an old slow request can delay
a newly queued connection while the single worker drains.
Existing encrypted journal records are **not
deleted** or migrated automatically; session migration requires an explicit,
separately authorized owner workflow.

This is a *client-side continuity boundary*, not server-side tenant isolation:
the V1 gateway still indexes archived turns by caller-supplied `session_id` and
does not bind that identifier cryptographically to a specific bearer/owner.
Anyone already authorized with the bearer and a known old session ID may still
reach that old context. The independently developed V2 owner-scoped session and
revocation mechanisms need separate qualification before making stronger
cross-owner confidentiality claims. Switching models within an unchanged V1
session can likewise reuse its history; it is not proof of model-specific memory.

### Optional bearer-epoch STM namespace (source-only)

An operator may explicitly start a *separately qualified* V1 gateway with
`--journal-scope bearer-v1` alongside the existing three journal flags. This
uses a domain-separated HMAC-SHA256 of the validated bearer and client-provided
session ID as the lookup key. Only the 64-character pseudonymous derived ID
reaches the encrypted journal; the bearer itself is never stored in journal
records or returned to the model. A changed bearer no longer automatically
retrieves records saved under the previous bearer, even when the client sends
the same session ID. It does not add an API operation, a new listener, or a
permission to retrieve a history from another source.

**This mode is opt-in and OFF by default.** The default `legacy` keeps the
existing journal lookup unchanged. Switching to `bearer-v1` does **not**
silently read or migrate old `legacy` session IDs: their encrypted records stay
on disk but become invisible to ordinary scoped lookup. Reverting to legacy
can expose that prior context again. Credential rotation also strands the
prior bearer-epoch archive until an owner explicitly authorizes a separate
recovery/migration workflow. Don't activate this mode on a live archive without
planning that readback change; no automatic migration or deletion exists.

This HMAC namespace is **not** journal encryption or true owner isolation.
Two devices sharing the same bearer and knowing the same client session ID
still address the same namespace; a valid bearer holder can request any known
session ID within that bearer epoch. V2 owner-scoped authentication/revocation
remains the needed authority boundary. No live switch, journal migration, or
host service restart has been attempted by this source change.

**Scope**: future Vera Companion messages after both client 0.2.3+ and
journal-enabled gateway are active; no retroactive ChatGPT history import and
no automatic access to other ChatGPT chats or files.

## Qualification boundaries

The source must pass gateway/Android regression tests, real inference, test
journal encrypted readback, exact APK build/signature, and release digest.
Android device-level UI transitions require user acceptance; Lappy service
reboot persistence is not established solely by a foreground run. Windows
filesystem ACLs are an additional requirement; storing key + DB on one
compromised machine is not equivalent to independent secret escrow.
