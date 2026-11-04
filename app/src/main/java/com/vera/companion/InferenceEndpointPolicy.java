package com.vera.companion;

import java.net.URI;
import java.net.URISyntaxException;
import java.util.Locale;

/** Syntax-only validation for a possible host-backed inference origin; never opens a connection. */
public final class InferenceEndpointPolicy {
    private InferenceEndpointPolicy() {}

    public static Candidate validate(String hostLabel, String origin) {
        if (!"Lappy".equals(hostLabel) && !"VN1".equals(hostLabel) && !"VN2".equals(hostLabel)) {
            throw new IllegalArgumentException("Select Lappy, VN1, or VN2.");
        }
        if (origin == null || origin.isEmpty() || !origin.equals(origin.trim())) {
            throw new IllegalArgumentException("Enter an HTTPS origin without whitespace.");
        }
        for (int i = 0; i < origin.length(); i++) {
            if (Character.isWhitespace(origin.charAt(i))) {
                throw new IllegalArgumentException("Whitespace is not allowed in an origin.");
            }
        }
        final URI uri;
        try {
            uri = new URI(origin);
        } catch (URISyntaxException e) {
            throw new IllegalArgumentException("Malformed origin.");
        }
        if (!"https".equalsIgnoreCase(uri.getScheme()) || uri.getHost() == null
                || uri.getRawUserInfo() != null || uri.getRawQuery() != null
                || uri.getRawFragment() != null
                || (uri.getRawPath() != null && !uri.getRawPath().isEmpty())
                || uri.getPort() == 0 || uri.getPort() > 65535
                || (uri.getRawAuthority() != null && uri.getRawAuthority().endsWith(":"))) {
            throw new IllegalArgumentException("Use an HTTPS origin with no path, credentials, query, or fragment.");
        }
        String host = uri.getHost().toLowerCase(Locale.ROOT);
        if (host.equals("localhost") || host.endsWith(".localhost")
                || host.equals("::1") || host.startsWith("127.")) {
            throw new IllegalArgumentException("Use the host's routable HTTPS name, not a loopback address.");
        }
        return new Candidate(hostLabel, uri.toString());
    }

    public static final class Candidate {
        public final String hostLabel;
        public final String origin;

        private Candidate(String hostLabel, String origin) {
            this.hostLabel = hostLabel;
            this.origin = origin;
        }
    }
}
