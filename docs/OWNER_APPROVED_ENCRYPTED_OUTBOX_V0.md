# Vera 1 — encrypted owner/device outbox V0

ISOLATED SOURCE/TEST CANDIDATE, not deployed, not connected to APK, Matrix, or local Obsession runtime. No message has been sent.

One end-user client: Vera APK; Element X retired. Matrix optional only if independently valuable.

The outbox requires a host-side MAC over the exact proposal, signed outside any model/Obsession process. The SQLite message body is encrypted using AES-GCM with a separate AES256 key; caller supplies both secrets privately and stores neither in GitHub. An authenticated device resolver is required for every poll and ack; recipient IDs and session IDs are not credentials. Queue is bounded to 32 unacknowledged unexpired items per recipient, 4KiB body, 1-86400 seconds expiration. Same request ID replays the same message ID; conflicting payloads are refused, including across process restarts. Poll produces OFFERED_NOT_DELIVERED; ack produces DEVICE_ACK_CLAIM, neither of which proves physical phone render or notification. Every poll is at-least-once and client must deduplicate by stable message ID.

Security limitations: owner/device/timestamp metadata remain unencrypted; key loss is unrecoverable without backup; host policy signer must be independently protected; no HTTP endpoints, Android poller, foreground service, receiver, persistent notification, transport credentials, true end-to-end delivery or autonomous initiator included. This module is host-only until separate gateway authentication and review.

Next: integrate with authenticated V2 device store on a new reviewed dependency head, add HTTP inbound poll/ack endpoints, build APK foreground inbox and background notification delivery design, qualify one owner-authorized benign diagnostic message on Patrick's actual paired phone, and coordinate with Work's Obsession resident proposals and Vera A's voice.

Run from repository root with gateway on Python import path: PYTHONPATH=gateway python -m unittest discover -s gateway/tests -p test_owner_outbox_v0.py -v