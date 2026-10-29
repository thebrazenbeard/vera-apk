package com.vera.companion;

import java.net.URI;
import java.net.URISyntaxException;
import java.util.Locale;

/** Explicit HTTPS Tailnet-only inference endpoint. No localhost or public fallback. */
public final class EndpointPolicy {
    private EndpointPolicy() {}

    /** V2 is explicitly selected by its dedicated Tailscale Serve port. */
    public static boolean isV2(String endpoint) {
        String normalized = normalize(endpoint);
        return normalized.endsWith(":8444");
    }

    public static String normalize(String entered) {
        if (entered == null) throw new IllegalArgumentException("Enter a Tailscale HTTPS address");
        String input = entered.trim();
        try {
            URI uri = new URI(input);
            String host = uri.getHost();
            if (!"https".equalsIgnoreCase(uri.getScheme()) || host == null
                    || !host.toLowerCase(Locale.ROOT).endsWith(".ts.net")
                    || host.length() <= ".ts.net".length() || uri.getUserInfo() != null
                    || uri.getRawQuery() != null || uri.getRawFragment() != null
                    || (uri.getRawPath() != null && !uri.getRawPath().isEmpty()
                        && !"/".equals(uri.getRawPath()))
                    || (uri.getPort() != -1 && uri.getPort() != 8443 && uri.getPort() != 8444 && uri.getPort() != 443)) {
                throw new IllegalArgumentException("Use HTTPS Tailscale :8443 for legacy or :8444 for V2");
            }
            return "https://" + host.toLowerCase(Locale.ROOT)
                    + (uri.getPort() == -1 ? "" : ":" + uri.getPort());
        } catch (URISyntaxException e) {
            throw new IllegalArgumentException("Invalid Tailscale HTTPS address");
        }
    }
}
