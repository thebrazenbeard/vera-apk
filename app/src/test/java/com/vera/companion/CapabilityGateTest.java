package com.vera.companion;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

public final class CapabilityGateTest {
    @Test
    public void rejectsMissingAuthorization() {
        var request = new CapabilityGate.EffectRequest("example.effect", "");
        assertFalse(CapabilityGate.maySubmit(request));
    }

    @Test
    public void acceptsExplicitAuthorizationForSubmissionStageOnly() {
        var request = new CapabilityGate.EffectRequest("example.effect", "authz:example");
        assertTrue(CapabilityGate.maySubmit(request));
    }
}
