package com.vera.companion;

import org.junit.Test;
import static org.junit.Assert.*;

public final class ConnectionPolicyTest {
    @Test public void expiresPairingOnlyOnAuthenticationRejection() {
        assertTrue(ConnectionPolicy.requiresPairing("Gateway returned HTTP 401"));
        assertTrue(ConnectionPolicy.requiresPairing("Gateway returned HTTP 403"));
        assertFalse(ConnectionPolicy.requiresPairing("Gateway returned HTTP 503"));
        assertFalse(ConnectionPolicy.requiresPairing("timeout"));
    }

    @Test public void reconnectHasBoundedExponentialDelay() {
        assertEquals(2000L, ConnectionPolicy.reconnectDelayMs(0));
        assertEquals(4000L, ConnectionPolicy.reconnectDelayMs(1));
        assertEquals(8000L, ConnectionPolicy.reconnectDelayMs(2));
        assertEquals(30000L, ConnectionPolicy.reconnectDelayMs(12));
        assertEquals(2000L, ConnectionPolicy.reconnectDelayMs(-9));
    }
}
