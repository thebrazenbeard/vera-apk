package com.vera.companion;

import org.junit.Test;
import static org.junit.Assert.*;

public final class ConversationHistoryPolicyTest {
    @Test public void onlyCompletedOrLegacyTurnsEnterNextModelContext() {
        assertTrue(ConversationHistoryPolicy.replayable("complete"));
        assertTrue(ConversationHistoryPolicy.replayable("not_reported"));
        for (String status : new String[]{"length_limited", "filtered", "unknown", "", null}) {
            assertFalse(ConversationHistoryPolicy.replayable(status));
        }
    }
}
