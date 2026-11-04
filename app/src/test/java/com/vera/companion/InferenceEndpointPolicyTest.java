package com.vera.companion;

import org.junit.Test;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.fail;

public final class InferenceEndpointPolicyTest {
    @Test public void acceptsExplicitHostCandidatesWithoutConnecting() {
        for (String name : new String[]{"Lappy", "VN1", "VN2"}) {
            InferenceEndpointPolicy.Candidate candidate = InferenceEndpointPolicy.validate(
                    name, "https://host.tailnet.ts.net:8443");
            assertEquals(name, candidate.hostLabel);
            assertEquals("https://host.tailnet.ts.net:8443", candidate.origin);
        }
    }

    @Test public void rejectsUnknownHostLabels() {
        assertInvalid("Other", "https://host.tailnet.ts.net");
        assertInvalid(null, "https://host.tailnet.ts.net");
    }

    @Test public void rejectsMalformedOrUnsafeOrigins() {
        String[] invalid = {
                null, "", " https://host.ts.net", "https://host.ts.net ",
                "http://host.ts.net", "https://user:token@host.ts.net",
                "https://host.ts.net/path", "https://host.ts.net/?token=abc",
                "https://host.ts.net#frag", "https://localhost:8765",
                "https://127.0.0.1:8765", "https://host.ts.net:0",
                "https://host.ts.net:", "https://host.ts.net /stuff",
                "//host.ts.net", "not a URL"
        };
        for (String origin : invalid) assertInvalid("Lappy", origin);
    }

    private static void assertInvalid(String hostLabel, String origin) {
        try {
            InferenceEndpointPolicy.validate(hostLabel, origin);
            fail("Accepted " + hostLabel + " / " + origin);
        } catch (IllegalArgumentException expected) {
            // Rejected before any connection attempt.
        }
    }
}
