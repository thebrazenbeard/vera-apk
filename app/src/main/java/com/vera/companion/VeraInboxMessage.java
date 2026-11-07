package com.vera.companion;

import java.nio.charset.StandardCharsets;

/** Immutable, strictly bounded host-approved Vera inbox message wire value. */
public final class VeraInboxMessage {
    public final String messageId;
    public final String body;
    public final String kind;
    public final long expiresAt;
    public final int offerAttempt;

    public VeraInboxMessage(String messageId, String body, String kind,
                            long expiresAt, int offerAttempt, long nowSeconds) {
        this(messageId, body, kind, expiresAt, offerAttempt, nowSeconds, true);
    }

    /** Delivery expiration limits server offers, not encrypted local history. */
    public static VeraInboxMessage fromEncryptedStore(
            String messageId, String body, String kind,
            long expiresAt, int offerAttempt, long nowSeconds) {
        return new VeraInboxMessage(messageId, body, kind, expiresAt,
                offerAttempt, nowSeconds, false);
    }

    private VeraInboxMessage(String messageId, String body, String kind,
                             long expiresAt, int offerAttempt, long nowSeconds,
                             boolean freshDelivery) {
        if (messageId == null || !messageId.matches("[a-f0-9]{32}"))
            throw new IllegalArgumentException("Invalid message id");
        if (body == null || body.isEmpty()
                || body.getBytes(StandardCharsets.UTF_8).length > 4096)
            throw new IllegalArgumentException("Invalid inbound text");
        // Prevent display-control text from masquerading as an app-authorized
        // speaker or reversing the direction of message labels.
        for (int i=0; i<body.length(); i++) {
            char ch=body.charAt(i);
            if ((Character.isISOControl(ch) && ch!='\n' && ch!='\t')
                    || (ch>=0x202A && ch<=0x202E)
                    || (ch>=0x2066 && ch<=0x2069)
                    || ch==0x200B || ch==0xFEFF)
                throw new IllegalArgumentException("Unsafe invisible or directional text");
        }
        if (!"diagnostic".equals(kind) && !"owner_approved_message".equals(kind))
            throw new IllegalArgumentException("Unapproved incoming kind");
        if (expiresAt < 1 || (freshDelivery
                && (expiresAt < nowSeconds - 120 || expiresAt > nowSeconds + 86400 + 120)))
            throw new IllegalArgumentException("Incoming message outside expiry window");
        if (offerAttempt < 1)
            throw new IllegalArgumentException("Invalid delivery attempt");
        this.messageId = messageId;
        this.body = body;
        this.kind = kind;
        this.expiresAt = expiresAt;
        this.offerAttempt = offerAttempt;
    }

    public static boolean authorizedEnvelope(String schema, String origin, String node) {
        return "vera.inbox.v1".equals(schema)
                && "vera_host_approved".equals(origin)
                && "local".equals(node);
    }

    /** A device acknowledgment is a storage receipt, never proof the user read it. */
    public static boolean validAck(String schema, String origin,
                                   String messageId, String expectedId,
                                   String state) {
        return "vera.inbox.ack.v1".equals(schema)
                && "vera_host_approved".equals(origin)
                && expectedId != null && expectedId.equals(messageId)
                && "DEVICE_ACK_CLAIM".equals(state);
    }
}
