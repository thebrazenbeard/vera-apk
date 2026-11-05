package com.vera.companion;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

public final class PairingSessionPolicyTest {
    private static final String URL = "https://lappy.example.ts.net";
    private static final String TOKEN_A = "a".repeat(48);
    private static final String TOKEN_B = "b".repeat(48);

    @Test public void exactResavePreservesConversationSession() {
        assertFalse(PairingSessionPolicy.requiresNewSession(URL, TOKEN_A, URL, TOKEN_A));
    }

    @Test public void changedBearerOnSameGatewayGetsNewSession() {
        assertTrue(PairingSessionPolicy.requiresNewSession(URL, TOKEN_A, URL, TOKEN_B));
    }

    @Test public void changedGatewayGetsNewSessionEvenWithSameBearer() {
        assertTrue(PairingSessionPolicy.requiresNewSession(URL, TOKEN_A,
                "https://vn1.example.ts.net", TOKEN_A));
    }

    @Test public void missingOrUnreadablePreviousCredentialNeverReusesSession() {
        assertTrue(PairingSessionPolicy.requiresNewSession("", null, URL, TOKEN_A));
        assertTrue(PairingSessionPolicy.requiresNewSession(null, TOKEN_A, URL, TOKEN_A));
    }
}
