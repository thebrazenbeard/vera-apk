package com.vera.companion;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;
import org.junit.Test;

public final class VoiceTapLeaseTest {
    @Test public void overlappingOwnersCannotReplaceActiveBinding() {
        VoiceTapLease lease = new VoiceTapLease();
        Object first = new Object();
        Object second = new Object();
        assertTrue(lease.claim(first));
        assertFalse(lease.claim(second));
        assertFalse(lease.release(second));
        assertTrue(lease.release(first));
        assertTrue(lease.claim(second));
        assertFalse(lease.release(first));
        assertTrue(lease.release(second));
    }

    @Test public void nullCannotClaimOrRelease() {
        VoiceTapLease lease = new VoiceTapLease();
        assertFalse(lease.claim(null));
        assertFalse(lease.release(null));
    }
}
