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
