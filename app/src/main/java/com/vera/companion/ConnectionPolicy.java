package com.vera.companion;

/** Local retry policy: only a gateway auth rejection invalidates pairing. */
public final class ConnectionPolicy {
    private ConnectionPolicy() {}

    public static boolean requiresPairing(String error) {
        return "Gateway returned HTTP 401".equals(error)
                || "Gateway returned HTTP 403".equals(error);
    }

    public static long reconnectDelayMs(int attempt) {
        int capped = Math.min(4, Math.max(0, attempt));
        return Math.min(30000L, 2000L << capped);
    }
}
