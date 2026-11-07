package com.vera.companion;

import org.junit.Test;
import static org.junit.Assert.*;

/** Pure-Java inbound contract controls; no actual phone or remote gateway. */
public final class VeraInboxMessageTest {
    private static final String ID = "0123456789abcdef0123456789abcdef";
    private static final long NOW = 1800000000L;

    private VeraInboxMessage msg(String id, String body, String kind,
                                 long expiresAt, int attempt) {
        return new VeraInboxMessage(id, body, kind, expiresAt, attempt, NOW);
    }

    @Test public void acceptsHostApprovedBoundedDiagnostic() {
        VeraInboxMessage m = msg(ID, "Hello from Vera", "diagnostic", NOW + 60, 1);
        assertEquals(ID, m.messageId);
        assertEquals("Hello from Vera", m.body);
        assertEquals("diagnostic", m.kind);
    }

    @Test public void acceptsApprovedOwnerMessage() {
        assertEquals("owner_approved_message",
                msg(ID, "A valid note", "owner_approved_message",
                        NOW + 86400, 2).kind);
    }

    @Test public void rejectsSpoofedOriginAndWrongSchema() {
        assertTrue(VeraInboxMessage.authorizedEnvelope(
                "vera.inbox.v1", "vera_host_approved", "local"));
        assertFalse(VeraInboxMessage.authorizedEnvelope(
                "vera.inbox.v1", "another_agent", "local"));
        assertFalse(VeraInboxMessage.authorizedEnvelope(
                "vera.inbox.v2", "vera_host_approved", "local"));
        assertFalse(VeraInboxMessage.authorizedEnvelope(
                "vera.inbox.v1", "vera_host_approved", "cloud"));
    }

    @Test public void rejectsMalformedIdentifiersAndIntruderKind() {
        for (String id : new String[]{"bad", "A".repeat(32), "a".repeat(33), ""}) {
            try { msg(id, "x", "diagnostic", NOW + 60, 1);
                fail("accepted invalid ID"); }
            catch (IllegalArgumentException expected) { }
        }
        try { msg(ID, "x", "obsession_direct_send", NOW + 60, 1);
            fail("accepted non-owner-approved kind"); }
        catch (IllegalArgumentException expected) { }
    }

    @Test public void rejectsExpiredFutureAndOversizedMessages() {
        for (long expiry : new long[]{NOW - 121, NOW + 86521}) {
            try { msg(ID, "x", "diagnostic", expiry, 1);
                fail("accepted invalid expiry"); }
            catch (IllegalArgumentException expected) { }
        }
        for (String content : new String[]{"", "x".repeat(4097), "\u20ac".repeat(1400)}) {
            try { msg(ID, content, "diagnostic", NOW + 60, 1);
                fail("accepted invalid UTF-8 body"); }
            catch (IllegalArgumentException expected) { }
        }
    }

    @Test public void rejectsHiddenSpeakerSpoofingControls() {
        for (String content : new String[]{"hello" + (char)0x202e + "imposter",
                                            "hello" + (char)0x200b + "system",
                                            "bad" + (char)0 + "value"}) {
            try { msg(ID, content, "diagnostic", NOW+60, 1);
                fail("accepted hidden text control"); }
            catch (IllegalArgumentException expected) { }
        }
    }

    @Test public void rejectsBadOfferAttempt() {
        try { msg(ID, "x", "diagnostic", NOW + 60, 0);
            fail("accepted impossible attempt"); }
        catch (IllegalArgumentException expected) { }
    }

    @Test public void locallyStoredMessageSurvivesDeliveryExpiry() {
        VeraInboxMessage saved = VeraInboxMessage.fromEncryptedStore(
                ID, "Retained private conversation", "diagnostic",
                NOW - 86400 * 10L, 1, NOW);
        assertEquals("Retained private conversation", saved.body);
        try {
            msg(ID, "Not a new network delivery", "diagnostic",
                    NOW - 86400 * 10L, 1);
            fail("Accepted a ten-day-old network offer");
        } catch (IllegalArgumentException expected) { }
    }

    @Test public void validatesAckAgainstOriginalMessage() {
        assertTrue(VeraInboxMessage.validAck(
                "vera.inbox.ack.v1", "vera_host_approved", ID, ID, "DEVICE_ACK_CLAIM"));
        assertFalse(VeraInboxMessage.validAck(
                "vera.inbox.ack.v1", "vera_host_approved", "different", ID,
                "DEVICE_ACK_CLAIM"));
        assertFalse(VeraInboxMessage.validAck(
                "vera.inbox.ack.v1", "vera_host_approved", ID, ID, "SENT"));
        assertFalse(VeraInboxMessage.validAck(
                "vera.inbox.ack.v1", "third_party", ID, ID, "DEVICE_ACK_CLAIM"));
    }
}
