package com.vera.companion;

/** Pairing identity, not a permission to read or delete a gateway journal. */
public final class PairingSessionPolicy {
    private PairingSessionPolicy() {}

    public static boolean requiresNewSession(String previousEndpoint, String previousToken,
                                             String nextEndpoint, String nextToken) {
        return previousEndpoint == null || previousToken == null
                || !previousEndpoint.equals(nextEndpoint)
                || !previousToken.equals(nextToken);
    }
}
